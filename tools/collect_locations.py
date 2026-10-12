#!/usr/bin/env python3
"""Collect 2021/2022 location details locally and import them via /api/ingest."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from .historical import (YEAR_MAX, YEAR_MIN, detect_event_year, discover_location_urls,
                             extract_visible_text, parse_historical_detail, parse_listing_card)
except ImportError:
    from historical import (YEAR_MAX, YEAR_MIN, detect_event_year, discover_location_urls,
                            extract_visible_text, parse_historical_detail, parse_listing_card)

DEFAULT_ENDPOINT = "http://localhost:8080/api/ingest"
USER_AGENT = "SpaceAppsLocalArchive/1.0"


def allowed_source(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "spaceappschallenge.org" or host.endswith(".spaceappschallenge.org"))


def fetch_page(url, timeout=20, retries=2):
    """Fetch an official page with bounded retries; never bypass access controls."""
    if not allowed_source(url):
        raise ValueError("URL is not an HTTPS Space Apps page")
    error = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                final_url = response.geturl()
                if not allowed_source(final_url):
                    raise ValueError("Redirect left the Space Apps domain")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as caught:
            error = caught
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    raise error


def create_manifest(listing_url, fetcher=fetch_page, captured_at=None):
    """Fetch a listing and create the same manifest consumed by the collector."""
    if not allowed_source(listing_url):
        raise ValueError("Listing URL is not an HTTPS Space Apps URL")
    event_year = detect_event_year(listing_url)
    if not isinstance(event_year, int) or not YEAR_MIN <= event_year <= YEAR_MAX:
        raise ValueError("Could not determine an event year from listing URL")
    html = fetcher(listing_url)
    urls = discover_location_urls(html, listing_url, event_year)
    return {
        "eventYear": event_year,
        "sourceUrl": listing_url,
        "capturedAt": captured_at or datetime.now(timezone.utc).isoformat(),
        "locationUrls": urls,
        "discoveryStatus": "links-found" if urls else "no-detail-links-found",
        "discoveredFrom": "listing-html"
    }


def post_record(payload, endpoint=DEFAULT_ENDPOINT, timeout=20):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "X-Import": "1"
    })
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise ValueError(result.get("error", "Import endpoint rejected the record"))
        return result


def collect_manifest(manifest, fetcher=fetch_page, importer=post_record, delay=0.5):
    event_year = manifest.get("eventYear") or detect_event_year(manifest.get("sourceUrl", ""))
    if not isinstance(event_year, int) or not YEAR_MIN <= event_year <= YEAR_MAX:
        raise ValueError(f"Manifest must contain a valid eventYear from {YEAR_MIN} through {YEAR_MAX}")
    source_url = manifest.get("sourceUrl", "")
    if not allowed_source(source_url):
        raise ValueError("Manifest sourceUrl must be an HTTPS Space Apps URL")
    urls = list(dict.fromkeys(manifest.get("locationUrls") or []))
    cards = {
        item.get("sourceUrl"): item.get("text", "")
        for item in manifest.get("locationCards", [])
        if isinstance(item, dict) and item.get("sourceUrl")
    }
    if not urls:
        return {
            "eventYear": event_year,
            "sourceUrl": source_url,
            "capturedAt": manifest.get("capturedAt"),
            "locationUrls": [],
            "locationCards": [],
            "imported": [],
            "failures": [{"sourceUrl": source_url, "error": "No location detail links were discoverable; listing text was not imported as location records"}],
            "warnings": [],
            "status": "incomplete",
            "discoveredCount": 0
        }

    imported = []
    failures = []
    warnings = []
    for index, location_url in enumerate(urls):
        try:
            if index and delay > 0:
                time.sleep(delay)
            if not allowed_source(location_url):
                raise ValueError("Location URL is not an HTTPS Space Apps page")
            html = fetcher(location_url)
            record, error = parse_historical_detail(html, location_url, event_year)
            if error:
                raise ValueError(error)
            summary = parse_listing_card(cards.get(location_url, ""))
            if record["participants"] is None and summary["participants"] is not None:
                record["participants"] = summary["participants"]
                record["participantsSource"] = "listing-card"
            if record["teams"] is None and summary["teams"] is not None:
                record["teams"] = summary["teams"]
                record["teamsSource"] = "listing-card"
            captured_at = datetime.now(timezone.utc).isoformat()
            # Keep record-level provenance as well as the import-level fields so
            # an exported record remains self-describing.
            record["listingSourceUrl"] = source_url
            record["capturedAt"] = captured_at
            is_global = "universal event" in record["locationName"].lower() or "universal-event" in location_url.lower()
            payload = {
                "eventYear": event_year,
                "sourceUrl": location_url,
                "listingSourceUrl": source_url,
                "listingCapturedAt": manifest.get("capturedAt"),
                "capturedAt": captured_at,
                "text": extract_visible_text(html),
                "records": [] if is_global else [record],
                "globalEvents": [dict(record, name="Universal Event", scope="global", eventType="global")] if is_global else [],
                "unverified": []
            }
            result = importer(payload)
            missing = [field for field in ("participants", "teams") if record[field] is None]
            imported.append({"sourceUrl": location_url, "duplicate": bool(result.get("duplicate")), "complete": not missing})
            if missing:
                warnings.append({"sourceUrl": location_url, "missing": missing})
        except Exception as error:
            failures.append({
                "sourceUrl": location_url,
                "error": str(error),
                "kind": "inaccessible" if isinstance(error, (HTTPError, URLError, TimeoutError, OSError)) else "parse-or-validation"
            })
    return {
        "eventYear": event_year,
        "sourceUrl": source_url,
        "capturedAt": manifest.get("capturedAt"),
        "locationUrls": [failure["sourceUrl"] for failure in failures],
        "locationCards": [item for item in manifest.get("locationCards", [])
                   if isinstance(item, dict) and item.get("sourceUrl") in {failure["sourceUrl"] for failure in failures}],
        "imported": imported,
        "failures": failures,
        "warnings": warnings,
        "discoveredCount": len(urls),
        "status": "complete" if urls and not failures and not warnings else "incomplete"
    }


def _write_retry(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description="Fetch historical location pages and import them to the local archive")
    parser.add_argument("manifest", nargs="?", type=Path, help="Existing JSON manifest")
    parser.add_argument("--listing", help="Official listing URL; fetch and save a manifest locally before collecting")
    parser.add_argument("--manifest-output", type=Path, help="Where --listing saves the generated manifest")
    parser.add_argument("--retry", type=Path, help="Retry manifest created after failed page fetches")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Existing local /api/ingest endpoint")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds to wait between detail-page requests")
    args = parser.parse_args()
    if bool(args.listing) == bool(args.retry or args.manifest):
        parser.error("provide one manifest/retry file or --listing")
    manifest_path = args.retry or args.manifest
    try:
        if args.listing:
            manifest = create_manifest(args.listing)
            manifest_path = args.manifest_output or Path(f"space-apps-{manifest['eventYear']}-locations.manifest.json")
            _write_retry(manifest_path, manifest)
            print(f"Saved listing manifest with {len(manifest['locationUrls'])} detail URLs: {manifest_path}")
        else:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = collect_manifest(manifest, importer=lambda payload: post_record(payload, args.endpoint), delay=max(0, args.delay))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Collection failed: {error}", file=sys.stderr)
        return 1
    retry_path = manifest_path.with_name(manifest_path.stem + ".retry.json")
    if result["failures"]:
        _write_retry(retry_path, result)
        print(f"Edition {result['eventYear']} INCOMPLETE: imported {len(result['imported'])}; failed {len(result['failures'])}. Retry manifest: {retry_path}")
        for failure in result["failures"]:
            print(f"FAILED {failure['sourceUrl']}: {failure['error']}", file=sys.stderr)
    elif result["warnings"]:
        print(f"Edition {result['eventYear']} INCOMPLETE: imported {len(result['imported'])}/{result['discoveredCount']} locations; some fields are unavailable.")
    else:
        print(f"Edition {result['eventYear']} collection complete: imported {len(result['imported'])}/{result['discoveredCount']} locations.")
    for warning in result["warnings"]:
        print(f"INCOMPLETE {warning['sourceUrl']}: missing {', '.join(warning['missing'])}")
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
