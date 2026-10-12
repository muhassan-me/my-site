#!/usr/bin/env python3
"""Build a non-destructive, reviewable candidate for historical re-collection.

This tool never writes data/archive.json and deliberately has no promotion mode.
Review the candidate and comparison before using the normal ingestion endpoint.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .collect_locations import fetch_page
    from .historical import parse_historical_detail
except ImportError:
    from collect_locations import fetch_page
    from historical import parse_historical_detail


def imports_needing_recollection(archive):
    for year, edition in archive.get("editions", {}).items():
        for item in edition.get("imports", []):
            records = item.get("records", [])
            if any(str(record.get("locationName", "")).strip().casefold() == "s" for record in records):
                yield int(year), item


def build_candidate(archive, fetcher=fetch_page):
    candidate, failures, comparisons = [], [], []
    for year, item in imports_needing_recollection(archive):
        url = item.get("sourceUrl", "")
        try:
            record, error = parse_historical_detail(fetcher(url), url, year)
            if error:
                raise ValueError(error)
            candidate.append({
                "eventYear": year, "sourceUrl": url,
                "listingSourceUrl": item.get("listingSourceUrl"),
                "capturedAt": datetime.now(timezone.utc).isoformat(),
                "record": record,
            })
            comparisons.append({"sourceUrl": url, "previous": item.get("records", []), "candidate": record})
        except Exception as error:
            failures.append({"eventYear": year, "sourceUrl": url, "error": str(error)})
    return {"candidateRecords": candidate, "failures": failures, "comparison": comparisons}


def main():
    parser = argparse.ArgumentParser(description="Prepare, but never promote, a historical re-collection candidate")
    parser.add_argument("--archive", type=Path, default=Path("data/archive.json"))
    parser.add_argument("--output", type=Path, default=Path("data_test/historical-recollection-candidate.json"))
    args = parser.parse_args()
    archive = json.loads(args.archive.read_text(encoding="utf-8"))
    result = build_candidate(archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Candidate: {len(result['candidateRecords'])}; failures: {len(result['failures'])}; production archive untouched: {args.output}")


if __name__ == "__main__":
    main()
