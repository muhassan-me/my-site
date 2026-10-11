#!/usr/bin/env python3
"""
Simple HTTP server to serve the Space Apps Egypt ranker site.
Handles GET requests for static files and POST /api/ingest for data updates.
"""
import http.server
import hashlib
import json
import os
import tempfile
import urllib.parse
from pathlib import Path
import sys
from datetime import datetime, timezone
from tools.parser import parse_event_page
from tools.history import compact_history

PORT = 8080
HOST = "127.0.0.1"
MAX_BODY_SIZE = 2 * 1024 * 1024  # 2 MB


def _write_json_atomic(path, value, indent=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         delete=False, suffix='.tmp') as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, indent=indent, ensure_ascii=False,
                      separators=None if indent else (',', ':'))
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def archive_historical_page(data_dir, event_year, source_url, captured_at,
                            text, parsed_page):
    """Append one deduplicated source-page import without touching current data."""
    archive_file = data_dir / 'archive.json'
    if archive_file.exists():
        try:
            with open(archive_file, 'r', encoding='utf-8') as archive_handle:
                archive = json.load(archive_handle)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Historical archive is unreadable; original preserved: {error}")
        if (not isinstance(archive, dict) or archive.get('schemaVersion') != 1
                or not isinstance(archive.get('editions'), dict)):
            raise ValueError('Historical archive has an unsupported schema; original preserved')
    else:
        archive = {'schemaVersion': 1, 'editions': {}}

    content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    edition = archive['editions'].setdefault(str(event_year), {'imports': []})
    if not isinstance(edition, dict) or not isinstance(edition.get('imports'), list):
        raise ValueError(f"Edition {event_year} has an unsupported schema; original preserved")
    matching_import = next((
        item for item in edition['imports']
        if isinstance(item, dict) and item.get('sourceUrl') == source_url
        and item.get('contentHash') == content_hash
    ), None)
    duplicate = matching_import is not None

    records = list(parsed_page.get('records', []))
    if 'records' not in parsed_page:
        for country, locations in parsed_page['countries'].items():
            for location in locations:
                records.append({
                    'country': country,
                    'city': location.get('city') or location.get('name', ''),
                    'locationName': location.get('name', ''),
                    'eventSite': location.get('eventSite'),
                    'participants': location.get('participants'),
                    'teams': location.get('teams'),
                    'virtual': bool(location.get('virtual', False)),
                    'inPerson': bool(location.get('inPerson', False)),
                    'accepting': bool(location.get('accepting', False)),
                    'scope': location.get('scope', 'local'),
                    'eventType': location.get('eventType', 'unknown')
                })
    for record in records:
        record.setdefault('eventYear', event_year)
        record.setdefault('sourceUrl', source_url)
        record.setdefault('participants', None)
        record.setdefault('teams', None)
    global_events = parsed_page.get('globalEvents', [])

    if not duplicate:
        edition['imports'].append({
            'eventYear': event_year,
            'sourceUrl': source_url,
            'listingSourceUrl': parsed_page.get('listingSourceUrl'),
            'listingCapturedAt': parsed_page.get('listingCapturedAt'),
            'capturedAt': captured_at,
            'contentHash': content_hash,
            'sourceText': text,
            'records': records,
            'globalEvents': global_events,
            'unverified': parsed_page.get('unverified', [])
        })
        _write_json_atomic(archive_file, archive, indent=2)
    else:
        capture_times = matching_import.setdefault('captureTimes', [matching_import['capturedAt']])
        if captured_at not in capture_times:
            capture_times.append(captured_at)
            _write_json_atomic(archive_file, archive, indent=2)

    participant_values = [record.get('participants') for record in records]
    total = sum(participant_values) if all(value is not None for value in participant_values) else None
    return {
        'ok': True,
        'eventYear': event_year,
        'duplicate': duplicate,
        'records': len(records),
        'globalEvents': len(global_events),
        'total': total,
        'sourceUrl': source_url
    }


class SpaceAppsHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=".", **kwargs)
     
    def do_GET(self):
        """Serve static files"""
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

    def do_OPTIONS(self):
        if self.path != '/api/ingest' or not self._allowed_import_origin():
            self.send_error(403, "Origin not allowed")
            return
        self.send_response(204)
        self._add_import_cors_headers()
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Import')
        if self.headers.get('Access-Control-Request-Private-Network') == 'true':
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def _allowed_import_origin(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        parsed = urllib.parse.urlsplit(origin)
        host = (parsed.hostname or '').lower()
        return host in ('localhost', '127.0.0.1') or host == 'spaceappschallenge.org' or host.endswith('.spaceappschallenge.org')

    def _add_import_cors_headers(self):
        origin = self.headers.get('Origin')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
     
    def do_POST(self):
        """Handle POST /api/ingest"""
        if self.path != '/api/ingest':
            self.send_error_json(404, "Not Found")
            return
        if not self._allowed_import_origin():
            self.send_error_json(403, "Origin not allowed")
            return
         
        content_length = self.headers.get('Content-Length')
        if content_length is None:
            self.send_error_json(411, "Length Required")
            return
         
        try:
            content_length = int(content_length)
        except ValueError:
            self.send_error_json(400, "Invalid Content-Length")
            return
         
        if content_length > MAX_BODY_SIZE:
            self.send_error_json(413, "Payload Too Large")
            return
         
        x_import = self.headers.get('X-Import')
        if x_import != '1':
            self.send_error_json(403, "Forbidden: Missing or invalid X-Import header")
            return
         
        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            self.send_error_json(400, f"Invalid JSON: {str(e)}")
            return
        except UnicodeDecodeError:
            self.send_error_json(400, "Invalid UTF-8 encoding")
            return
        except Exception as e:
            self.send_error_json(400, f"Error reading request: {str(e)}")
            return
         
        if not isinstance(data, dict):
            self.send_error_json(400, "Request body must be a JSON object")
            return

        if 'eventYear' in data or 'text' in data or 'records' in data:
            event_year = data.get('eventYear')
            text = data.get('text')
            source_url = data.get('sourceUrl')
            captured_at = data.get('capturedAt')
            if not isinstance(text, str):
                self.send_error_json(400, "Historical import requires captured text")
                return
            if isinstance(event_year, bool) or not isinstance(event_year, int):
                self.send_error_json(400, "Historical import requires an explicit eventYear")
                return
            if event_year < 2021 or event_year > datetime.now().year:
                self.send_error_json(400, "eventYear must be between 2021 and the current year")
                return
            if not isinstance(source_url, str) or urllib.parse.urlsplit(source_url).scheme not in ('http', 'https'):
                self.send_error_json(400, "Historical import requires the source page URL")
                return
            if not isinstance(captured_at, str):
                self.send_error_json(400, "Historical import requires a capture timestamp")
                return
            try:
                datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
            except ValueError:
                self.send_error_json(400, "capturedAt must be an ISO timestamp")
                return
            if isinstance(data.get('records'), list):
                if not isinstance(text, str):
                    self.send_error_json(400, "Structured historical import requires captured page text")
                    return
                records = data['records']
                for index, record in enumerate(records):
                    if not isinstance(record, dict) or not record.get('locationName'):
                        self.send_error_json(400, f"Record {index} requires a locationName")
                        return
                    for field in ('participants', 'teams'):
                        value = record.get(field)
                        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                            self.send_error_json(400, f"Record {index} has an invalid {field} value")
                            return
                parsed_page = {
                    'records': records,
                    'globalEvents': data.get('globalEvents', []),
                    'unverified': data.get('unverified', []),
                    'listingSourceUrl': data.get('listingSourceUrl'),
                    'listingCapturedAt': data.get('listingCapturedAt')
                }
            else:
                if not isinstance(text, str):
                    self.send_error_json(400, "Historical import requires text or structured records")
                    return
                parsed_page = parse_event_page(text)
            if not isinstance(parsed_page.get('globalEvents'), list) or not isinstance(parsed_page.get('unverified'), list):
                self.send_error_json(400, "globalEvents and unverified must be arrays")
                return
            data_dir = Path(__file__).parent / 'data'
            try:
                response_data = archive_historical_page(
                    data_dir, event_year, source_url, captured_at, text, parsed_page
                )
            except ValueError as error:
                self.send_error_json(500, str(error))
                return
            response_body = json.dumps(response_data).encode('utf-8')
            self.send_response(200)
            self._add_import_cors_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            return
         
        # Determine format and extract countries_dict and captured_at
        captured_at = None
        if 'locations' in data and isinstance(data['locations'], list):
            self.send_error_json(400, "Flat locations lack verified country assignment")
            return
        if 'countries' in data and isinstance(data['countries'], dict):
            # New format
            countries_dict = data['countries']
            # Validate each country's locations
            for country, locs in countries_dict.items():
                if not isinstance(locs, list):
                    self.send_error_json(400, f"Locations for country '{country}' must be an array")
                    return
                for i, loc in enumerate(locs):
                    if not isinstance(loc, dict):
                        self.send_error_json(400, f"Location at index {i} in country '{country}' must be an object")
                        return
                    name = loc.get('name', '')
                    if not name:
                        self.send_error_json(400, f"Location at index {i} in country '{country}' requires a name")
                        return
                    if 'participants' not in loc:
                        self.send_error_json(400, f"Location at index {i} in country '{country}' missing 'participants' field")
                        return
                    try:
                        participants = int(loc['participants'])
                        if participants < 0:
                            raise ValueError("Negative participants")
                    except (ValueError, TypeError):
                        self.send_error_json(400, f"Location at index {i} in country '{country}' has invalid participants value: {loc['participants']}")
                        return
            captured_at = data.get('capturedAt')
        else:
            self.send_error_json(400, "Invalid format: expected an explicit countries object")
            return

        global_events = data.get('globalEvents', [])
        if not isinstance(global_events, list):
            self.send_error_json(400, "globalEvents must be an array")
            return
        for category in list(countries_dict):
            if category.strip().lower() == 'universal event':
                global_events.extend({
                    **location,
                    'name': 'Universal Event',
                    'description': location.get('description') or location.get('name', ''),
                    'scope': 'global'
                } for location in countries_dict.pop(category))
         
        # Deduplicate within each country by name (keeping the last occurrence)
        processed_countries = {}
        for country, locs in countries_dict.items():
            seen = {}
            for loc in locs:
                identity = (loc.get('city') or loc['name'], loc.get('eventSite') or '')
                seen[identity] = loc
            processed_countries[country] = list(seen.values())
         
        # Build the snapshot
        if captured_at is None:
            captured_at = datetime.now(timezone.utc).isoformat()
        else:
            captured_at = str(captured_at)
        
        snapshot = {
            'timestamp': captured_at,
            'countries': processed_countries,
            'globalEvents': global_events
        }
         
        # Update history.json
        data_dir = Path(__file__).parent / 'data'
        history_file = data_dir / 'history.json'
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except (OSError, json.JSONDecodeError) as error:
                self.send_error_json(500, f"history.json is unreadable; original preserved: {error}")
                return
            if not isinstance(history, list):
                self.send_error_json(500, "history.json must contain a list; original preserved")
                return
            if any(not isinstance(item, dict) or not isinstance(item.get('countries'), dict) for item in history):
                self.send_error_json(500, "history.json contains an invalid snapshot; original preserved")
                return
        now = datetime.now(timezone.utc)
        history = compact_history(history, snapshot, now)
        _write_json_atomic(history_file, history)
         
        # Update latest.json
        latest_file = data_dir / 'latest.json'
        latest_data = {
            'capturedAt': captured_at,
            'countries': processed_countries,
            'globalEvents': global_events
        }
        _write_json_atomic(latest_file, latest_data, indent=2)
         
        # Compute total participants and location count
        total_locations = 0
        total_participants = 0
        for country, locs in processed_countries.items():
            total_locations += len(locs)
            total_participants += sum(loc['participants'] for loc in locs)
        total_participants += sum(event.get('participants', 0) for event in global_events)
         
        response_data = {
            'ok': True,
            'count': total_locations,
            'total': total_participants,
            'unmapped': []  # No unmapped in new format
        }
         
        response_body = json.dumps(response_data).encode('utf-8')
        self.send_response(200)
        self._add_import_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)
     
    def send_error_json(self, status_code, message):
        """Send a JSON error response with proper Content-Type and Content-Length"""
        error_data = {
            'ok': False,
            'error': message
        }
        try:
            response_body = json.dumps(error_data).encode('utf-8')
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
        except Exception as e:
            print(f"Error sending error response: {e}", file=sys.stderr)
 
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        if len(args) >= 2 and (args[1] != '200' or '/api/ingest' not in args[0]):
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(),
                                                   self.log_date_time_string(),
                                                   format % args))
 
def run_server(port=PORT, host=HOST):
    server_address = (host, port)
    httpd = http.server.HTTPServer(server_address, SpaceAppsHandler)
    print(f"Serving on http://{host}:{port}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
 
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run the Space Apps Egypt ranker server')
    parser.add_argument('--port', type=int, default=PORT, help=f'Port to serve on (default: {PORT})')
    parser.add_argument('--host', type=str, default=HOST, help=f'Host to bind to (default: {HOST})')
    args = parser.parse_args()
    
    run_server(port=args.port, host=args.host)