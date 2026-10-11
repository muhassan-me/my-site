#!/usr/bin/env python3
"""
Simple HTTP server to serve the Space Apps Egypt ranker site.
Handles GET requests for static files and POST /api/ingest for data updates.
"""
import http.server
import json
import os
import urllib.parse
from pathlib import Path
import sys
from datetime import datetime, timezone
from tools.parser import parse_paste_content
from tools.history import compact_history

PORT = 8080
HOST = "127.0.0.1"
MAX_BODY_SIZE = 200 * 1024  # 200 KB


class SpaceAppsHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=".", **kwargs)
     
    def do_GET(self):
        """Serve static files"""
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()
     
    def do_POST(self):
        """Handle POST /api/ingest"""
        if self.path != '/api/ingest':
            self.send_error_json(404, "Not Found")
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
         
        # Determine format and extract countries_dict and captured_at
        captured_at = None
        if 'text' in data and isinstance(data['text'], str):
            # New format: raw text paste
            text = data['text']
            countries_dict = parse_paste_content(text)
            captured_at = data.get('capturedAt')
        elif 'locations' in data and isinstance(data['locations'], list):
            # Old format: assume Egypt-only
            old_locations = data['locations']
            countries_dict = {"Egypt": []}
            seen_names = set()
            for loc in old_locations:
                if not isinstance(loc, dict):
                    self.send_error_json(400, "Each location must be an object")
                    return
                name = loc.get('name', '')
                if not name:
                    continue
                if name in seen_names:
                    continue  # skip duplicates, keep first
                seen_names.add(name)
                countries_dict["Egypt"].append({
                    'name': name,
                    'participants': int(loc.get('participants', 0)),
                    'virtual': bool(loc.get('virtual', False)),
                    'inPerson': bool(loc.get('inPerson', False)),
                    'accepting': bool(loc.get('accepting', False))
                })
            # captured_at remains None (will be set to current time later)
        elif 'countries' in data and isinstance(data['countries'], dict):
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
                        continue
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
            self.send_error_json(400, "Invalid format: expected 'text' string, 'locations' array (old) or 'countries' object (new)")
            return
         
        # Deduplicate within each country by name (keeping the last occurrence)
        processed_countries = {}
        for country, locs in countries_dict.items():
            seen = {}
            for loc in locs:
                seen[loc['name']] = loc
            processed_countries[country] = list(seen.values())
         
        # Build the snapshot
        if captured_at is None:
            captured_at = datetime.now(timezone.utc).isoformat()
        else:
            captured_at = str(captured_at)
        
        snapshot = {
            'timestamp': captured_at,
            'countries': processed_countries
        }
         
        # Update history.json
        data_dir = Path(__file__).parent / 'data'
        history_file = data_dir / 'history.json'
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except Exception:
                history = []
        now = datetime.now(timezone.utc)
        history = compact_history(history, snapshot, now)
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, separators=(",", ":"), ensure_ascii=False)
         
        # Update latest.json
        latest_file = data_dir / 'latest.json'
        latest_data = {
            'capturedAt': captured_at,
            'countries': processed_countries
        }
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(latest_data, f, indent=2)
         
        # Compute total participants and location count
        total_locations = 0
        total_participants = 0
        for country, locs in processed_countries.items():
            total_locations += len(locs)
            total_participants += sum(loc['participants'] for loc in locs)
         
        response_data = {
            'ok': True,
            'count': total_locations,
            'total': total_participants,
            'unmapped': []  # No unmapped in new format
        }
         
        response_body = json.dumps(response_data).encode('utf-8')
        self.send_response(200)
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