#!/usr/bin/env python3
"""Collect 2021/2022 location details locally and import them via /api/ingest."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from .historical import YEAR_MAX, YEAR_MIN, detect_event_year, extract_visible_text, parse_historical_detail
except ImportError:
    from historical import YEAR_MAX, YEAR_MIN, detect_event_year, extract_visible_text, parse_historical_detail

DEFAULT_ENDPOINT = "http://localhost:8080/api/ingest"
USER_AGENT = "SpaceAppsLocalArchive/1.0"


def allowed_source(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "spaceappschallenge.org" or host.endswith(".spaceappschallenge.org"))


def fetch_page(url, timeout=20):
    if not allowed_source(url):
        raise ValueError("URL is not an HTTPS Space Apps page")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        if not allowed_source(final_url):
            raise ValueError("Redirect left the Space Apps domain")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


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
        raise ValueError("Manifest must contain a valid eventYear from 2021 through 2025")
    source_url = manifest.get("sourceUrl", "")
    if not allowed_source(source_url):
        raise ValueError("Manifest sourceUrl must be an HTTPS Space Apps URL")
    urls = list(dict.fromkeys(manifest.get("locationUrls") or []))
    if not urls:
        raise ValueError("Manifest has no locationUrls; re-capture the locations listing")

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
            captured_at = datetime.now(timezone.utc).isoformat()
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
            imported.append({"sourceUrl": location_url, "duplicate": bool(result.get("duplicate"))})
            missing = [field for field in ("participants", "teams") if record[field] is None]
            if missing:
                warnings.append({"sourceUrl": location_url, "missing": missing})
        except Exception as error:
            failures.append({"sourceUrl": location_url, "error": str(error)})
    return {
        "eventYear": event_year,
        "sourceUrl": source_url,
        "capturedAt": manifest.get("capturedAt"),
        "locationUrls": [failure["sourceUrl"] for failure in failures],
        "imported": imported,
        "failures": failures,
        "warnings": warnings
    }


def _write_retry(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description="Fetch historical location pages and import them to the local archive")
    parser.add_argument("manifest", type=Path, help="JSON manifest saved by the capture bookmarklet")
    parser.add_argument("--retry", type=Path, help="Retry manifest created after failed page fetches")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Existing local /api/ingest endpoint")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds to wait between detail-page requests")
    args = parser.parse_args()
    manifest_path = args.retry or args.manifest
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = collect_manifest(manifest, importer=lambda payload: post_record(payload, args.endpoint), delay=max(0, args.delay))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Collection failed: {error}", file=sys.stderr)
        return 1
    retry_path = manifest_path.with_name(manifest_path.stem + ".retry.json")
    if result["failures"]:
        _write_retry(retry_path, result)
        print(f"Imported {len(result['imported'])}; failed {len(result['failures'])}. Retry manifest: {retry_path}")
        for failure in result["failures"]:
            print(f"FAILED {failure['sourceUrl']}: {failure['error']}", file=sys.stderr)
    else:
        print(f"Imported {len(result['imported'])} locations for edition {result['eventYear']}; no failures.")
    for warning in result["warnings"]:
        print(f"INCOMPLETE {warning['sourceUrl']}: missing {', '.join(warning['missing'])}")
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
