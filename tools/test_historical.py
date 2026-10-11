import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path

import serve
from tools.collect_locations import collect_manifest
from tools.historical import detect_event_year, parse_historical_detail
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
        }
        for url, year in patterns.items():
            with self.subTest(url=url):
                self.assertEqual(detect_event_year(url), year)

    def test_detail_fields_and_missing_counts(self):
        html = "<title>Universal Event | NASA Space Apps</title><h1>Universal Event</h1><p>3,596 Participants</p><div>453 Teams</div>"
        record, error = parse_historical_detail(html, "https://2021.spaceappschallenge.org/locations/universal-event", 2021)
        self.assertIsNone(error)
        self.assertEqual((record["participants"], record["teams"]), (3596, 453))
        self.assertEqual(record["eventYear"], 2021)
        self.assertEqual(record["locationName"], "Universal Event")
        missing, error = parse_historical_detail("<h1>Small Event</h1>", "https://2022.spaceappschallenge.org/locations/small", 2022)
        self.assertIsNone(error)
        self.assertIsNone(missing["participants"])
        self.assertIsNone(missing["teams"])
        failed, error = parse_historical_detail("<p>unstructured</p>", "https://2022.spaceappschallenge.org/locations/bad", 2022)
        self.assertIsNone(failed)
        self.assertTrue(error)

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

        retried = collect_manifest(result, fetcher=lambda url: "<h1>Recovered</h1><p>2 Participants</p>",
                      importer=lambda payload: imported.append(payload) or {"ok": True}, delay=0)
        self.assertEqual(retried["failures"], [])
        self.assertEqual(len(imported), 2)

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

    def test_2023_to_2025_text_imports_still_archive(self):
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
                    self.assertEqual(request.status, 200)
                archive = json.loads((root / "data" / "archive.json").read_text(encoding="utf-8"))
                self.assertEqual(set(archive["editions"]), {"2023", "2024", "2025"})
                for edition in archive["editions"].values():
                    self.assertEqual(edition["imports"][0]["records"][0]["participants"], 12)
            finally:
                serve.__file__ = old_path

    def test_listing_parser_regression(self):
        parsed = parse_event_page("Egypt\nCairo\nParticipating: 12\nVirtual\nIn-Person")
        self.assertEqual(parsed["countries"]["Egypt"][0]["participants"], 12)
        self.assertTrue(parsed["countries"]["Egypt"][0]["virtual"])


if __name__ == "__main__":
    unittest.main()
