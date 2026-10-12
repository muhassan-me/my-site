import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path

import serve
from tools.collect_locations import collect_manifest, create_manifest
from tools.historical import detect_event_year, discover_location_urls, parse_historical_detail, parse_listing_card
from tools.parser import parse_event_page


class RequestHarness(serve.SpaceAppsHandler):
    def __init__(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.path = "/api/ingest"
        self.headers = Message()
        self.headers["Content-Length"] = str(len(body))
        self.headers["X-Import"] = "1"
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


class HistoricalImportTests(unittest.TestCase):
    def test_all_required_event_urls(self):
        patterns = {
            "https://2021.spaceappschallenge.org/locations/": 2021,
            "https://2021.spaceappschallenge.org/locations/universal-event": 2021,
            "https://2022.spaceappschallenge.org/locations/": 2022,
            "https://2022.spaceappschallenge.org/locations/universal-event/": 2022,
            "https://www.spaceappschallenge.org/2023/locations/": 2023,
            "https://www.spaceappschallenge.org/nasa-space-apps-2024/2024-local-events/": 2024,
            "https://www.spaceappschallenge.org/2025/local-events/": 2025,
            "https://www.spaceappschallenge.org/2026/local-events/": 2026,
        }
        for url, year in patterns.items():
            with self.subTest(url=url):
                self.assertEqual(detect_event_year(url), year)

    def test_listing_discovery_supports_old_and_modern_routes(self):
        cases = (
            (2021, "https://2021.spaceappschallenge.org/locations/", '<a href="/locations/cairo/">Cairo</a>'),
            (2023, "https://www.spaceappschallenge.org/2023/locations/", '<a href="/2023/locations/abha/">Abha</a>'),
            (2026, "https://www.spaceappschallenge.org/2026/local-events/", '<a href="/2026/local-events/cairo/">Cairo</a>'),
        )
        for year, listing, body in cases:
            with self.subTest(year=year):
                urls = discover_location_urls(f'<a href="/2026/challenges/">ignore</a>{body}{body}', listing, year)
                self.assertEqual(len(urls), 1)
        manifest = create_manifest(
            "https://www.spaceappschallenge.org/2026/local-events/",
            fetcher=lambda url: '<a href="/2026/local-events/cairo/">Cairo</a>',
            captured_at="2026-10-12T10:00:00Z",
        )
        self.assertEqual(manifest["eventYear"], 2026)
        self.assertEqual(manifest["discoveryStatus"], "links-found")

    def test_detail_fields_and_missing_counts(self):
        navigation = "<nav><ul><li>Locations</li><li>Challenges</li></ul></nav>"
        html = (
            "<title>Universal Event - Space Apps Challenge | 2021</title>" + navigation
            + "<h2>Anywhere in the World</h2><h1>Universal Event</h1>"
            + "<p>Teams(453)</p><p>Thank you to the3596people who joined this location.</p>"
        )
        record, error = parse_historical_detail(html, "https://2021.spaceappschallenge.org/locations/universal-event", 2021)
        self.assertIsNone(error)
        self.assertEqual((record["participants"], record["teams"]), (3596, 453))
        self.assertEqual(record["eventYear"], 2021)
        self.assertEqual(record["locationName"], "Universal Event")
        self.assertIsNone(record["country"])
        self.assertEqual(record["scope"], "global")

        ordinary = (
            "<title>Aaruush, Chennai - Space Apps Challenge | 2021</title>" + navigation
            + "<h2>India</h2><h1>Aaruush, Chennai</h1><p>Teams(125)</p>"
            + "<p>Thank you to the1126people who joined this location.</p>"
        )
        city, error = parse_historical_detail(ordinary, "https://2021.spaceappschallenge.org/locations/aaruush-chennai/", 2021)
        self.assertIsNone(error)
        self.assertEqual((city["locationName"], city["country"], city["participants"], city["teams"]),
                         ("Aaruush, Chennai", "India", 1126, 125))

        missing_html = (
            "<title>Bengaluru - Space Apps Challenge | 2022</title>" + navigation
            + "<h2>India</h2><h1>Bengaluru</h1><p>Teams(15)</p>"
            + "<p>Typical teams have 2-6 participants.</p>"
        )
        missing, error = parse_historical_detail(missing_html, "https://2022.spaceappschallenge.org/locations/bengaluru/", 2022)
        self.assertIsNone(error)
        self.assertIsNone(missing["participants"])
        self.assertEqual(missing["teams"], 15)

        failed, error = parse_historical_detail(
            "<title>Space Apps Challenge</title>" + navigation + "<h1>Locations</h1>",
            "https://2022.spaceappschallenge.org/locations/bad/", 2022
        )
        self.assertIsNone(failed)
        self.assertTrue(error)
        invalid_count, error = parse_historical_detail(
            "<h1>Some City</h1><h2>Some Country</h2><p>Participants: -4</p><p>Teams(nope)</p>",
            "https://2022.spaceappschallenge.org/locations/some-city/", 2022
        )
        self.assertIsNone(invalid_count)
        self.assertTrue(error)
        missing_url, error = parse_historical_detail("<h1>Some City</h1>", "", 2022)
        self.assertIsNone(missing_url)
        self.assertIn("source URL", error)

    def test_collector_reports_and_retries_failures(self):
        manifest = {
            "eventYear": 2021,
            "sourceUrl": "https://2021.spaceappschallenge.org/locations/",
            "capturedAt": "2026-10-11T10:00:00Z",
            "locationUrls": ["https://2021.spaceappschallenge.org/locations/good", "https://2021.spaceappschallenge.org/locations/offline"],
        }
        imported = []

        def fetch(url):
            if url.endswith("offline"):
                raise OSError("fixture timeout")
            return "<h1>Example</h1><p>9 Participants</p><p>4 Teams</p>"

        result = collect_manifest(manifest, fetcher=fetch, importer=lambda payload: imported.append(payload) or {"ok": True}, delay=0)
        self.assertEqual(len(imported), 1)
        self.assertEqual(result["failures"][0]["sourceUrl"], manifest["locationUrls"][1])
        self.assertEqual(result["locationUrls"], [manifest["locationUrls"][1]])
        self.assertEqual(imported[0]["records"][0]["participants"], 9)
        self.assertEqual(imported[0]["records"][0]["teams"], 4)
        self.assertEqual(imported[0]["listingCapturedAt"], manifest["capturedAt"])
        self.assertEqual(imported[0]["records"][0]["listingSourceUrl"], manifest["sourceUrl"])
        self.assertEqual(result["status"], "incomplete")

        retried = collect_manifest(result, fetcher=lambda url: "<h1>Recovered</h1><p>2 Participants</p>",
                      importer=lambda payload: imported.append(payload) or {"ok": True}, delay=0)
        self.assertEqual(retried["failures"], [])
        self.assertEqual(len(imported), 2)
        self.assertEqual(retried["status"], "incomplete")

    def test_unified_manifest_collection_uses_card_counts_only_as_fallback(self):
        location_url = "https://www.spaceappschallenge.org/2023/locations/abha/"
        manifest = {
            "eventYear": 2023,
            "sourceUrl": "https://www.spaceappschallenge.org/2023/locations/",
            "capturedAt": "2026-10-12T10:00:00Z",
            "locationUrls": [location_url],
            "locationCards": [{"sourceUrl": location_url, "text": "ABHA\nSAUDI ARABIA\nAbha\n41 Participating\nVirtual"}]
        }
        imported = []
        result = collect_manifest(
            manifest,
            fetcher=lambda url: "<title>Abha - Space Apps Challenge | 2023</title><h2>Saudi Arabia</h2><h1>Abha</h1>",
            importer=lambda payload: imported.append(payload) or {"ok": True},
            delay=0
        )
        record = imported[0]["records"][0]
        self.assertEqual(record["participants"], 41)
        self.assertEqual(record["participantsSource"], "listing-card")
        self.assertIsNone(record["teams"])
        self.assertEqual(record["country"], "Saudi Arabia")
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(parse_listing_card("41 Participating\nTeams(5)"), {"participants": 41, "teams": 5})

    def test_modern_detail_markup_and_joined_participating_count(self):
        html = "<h2>Egypt</h2><h1>6 of October</h1><div>549Participating</div>"
        record, error = parse_historical_detail(
            html, "https://www.spaceappschallenge.org/2026/local-events/6-of-october/", 2026
        )
        self.assertIsNone(error)
        self.assertEqual(record["locationName"], "6 of October")
        self.assertEqual(record["country"], "Egypt")
        self.assertEqual(record["participants"], 549)
        self.assertIsNone(record["teams"])

    def test_listing_without_detail_links_is_incomplete_not_imported(self):
        manifest = {
            "eventYear": 2025,
            "sourceUrl": "https://www.spaceappschallenge.org/2025/local-events/",
            "capturedAt": "2026-10-12T10:00:00Z",
            "text": "Listing text must not become an import",
            "locationUrls": [],
        }
        calls = []
        result = collect_manifest(manifest, importer=lambda payload: calls.append(payload), delay=0)
        self.assertEqual(calls, [])
        self.assertEqual(result["imported"], [])
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["discoveredCount"], 0)
        self.assertIn("No location detail links", result["failures"][0]["error"])

    def test_existing_archive_format_dedup_and_current_data_isolation(self):
        original_module_path = serve.__file__
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            latest = data_dir / "latest.json"
            history = data_dir / "history.json"
            latest.write_text('{"sentinel":"latest"}', encoding="utf-8")
            history.write_text('[{"sentinel":"history"}]', encoding="utf-8")
            serve.__file__ = str(root / "serve.py")
            try:
                record = {
                    "locationName": "Universal Event", "country": None, "city": None,
                    "participants": 3596, "teams": 453,
                    "sourceUrl": "https://2021.spaceappschallenge.org/locations/universal-event"
                }
                payload = {
                    "eventYear": 2021, "sourceUrl": record["sourceUrl"],
                    "listingSourceUrl": "https://2021.spaceappschallenge.org/locations/",
                    "listingCapturedAt": "2026-10-11T09:00:00Z",
                    "capturedAt": "2026-10-11T10:00:00Z", "text": "Universal Event 3596 Participants 453 Teams",
                    "records": [record], "globalEvents": [], "unverified": []
                }
                first = RequestHarness(payload)
                first.do_POST()
                self.assertEqual(first.status, 200)
                repeated = RequestHarness(payload)
                repeated.do_POST()
                self.assertEqual(repeated.status, 200)
                result = json.loads(repeated.wfile.getvalue())
                self.assertTrue(result["duplicate"])
                archive = json.loads((data_dir / "archive.json").read_text(encoding="utf-8"))
                imports = archive["editions"]["2021"]["imports"]
                self.assertEqual(len(imports), 1)
                stored = imports[0]["records"][0]
                self.assertEqual((stored["participants"], stored["teams"]), (3596, 453))
                self.assertIsNone(stored["country"])
                self.assertEqual(stored["eventYear"], 2021)
                self.assertEqual(stored["sourceUrl"], record["sourceUrl"])
                self.assertEqual(imports[0]["listingCapturedAt"], "2026-10-11T09:00:00Z")
                self.assertEqual(latest.read_text(encoding="utf-8"), '{"sentinel":"latest"}')
                self.assertEqual(history.read_text(encoding="utf-8"), '[{"sentinel":"history"}]')
            finally:
                serve.__file__ = original_module_path

    def test_api_rejects_invalid_names_and_counts(self):
        original_module_path = serve.__file__
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            serve.__file__ = str(root / "serve.py")
            try:
                base = {
                    "eventYear": 2021,
                    "sourceUrl": "https://2021.spaceappschallenge.org/locations/valid/",
                    "capturedAt": "2026-10-11T10:00:00Z",
                    "text": "fixture source text",
                    "records": [{"locationName": "Valid Town", "participants": 4, "teams": 2}],
                    "globalEvents": [],
                    "unverified": []
                }
                for record, expected in (({"locationName": "s", "participants": 4}, "Invalid historical location name"),
                                         ({"locationName": "Valid Town", "participants": -1}, "invalid participants value"),
                                         ({"locationName": "Valid Town", "participants": 1, "teams": "many"}, "invalid teams value")):
                    payload = {**base, "records": [record]}
                    request = RequestHarness(payload)
                    request.do_POST()
                    self.assertEqual(request.status, 400)
                    self.assertIn(expected, json.loads(request.wfile.getvalue())["error"])
                self.assertFalse((root / "data" / "archive.json").exists())
            finally:
                serve.__file__ = original_module_path

    def test_listing_text_imports_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_path = serve.__file__
            serve.__file__ = str(root / "serve.py")
            try:
                for year in (2023, 2024, 2025):
                    payload = {
                        "eventYear": year,
                        "sourceUrl": f"https://www.spaceappschallenge.org/{year}/local-events/",
                        "capturedAt": "2026-10-11T10:00:00Z",
                        "text": "Egypt\nCairo\nParticipating: 12\nVirtual\nIn-Person"
                    }
                    request = RequestHarness(payload)
                    request.do_POST()
                    self.assertEqual(request.status, 400)
                    self.assertIn("Listing-page text", json.loads(request.wfile.getvalue())["error"])
                self.assertFalse((root / "data" / "archive.json").exists())
            finally:
                serve.__file__ = old_path

    def test_listing_parser_regression(self):
        parsed = parse_event_page("Egypt\nCairo\nParticipating: 12\nVirtual\nIn-Person")
        self.assertEqual(parsed["countries"]["Egypt"][0]["participants"], 12)
        self.assertTrue(parsed["countries"]["Egypt"][0]["virtual"])


if __name__ == "__main__":
    unittest.main()
