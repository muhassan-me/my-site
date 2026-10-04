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

# Import our ingestion logic
sys.path.append(str(Path(__file__).parent / 'tools'))
from ingest_lib import process_locations_data

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
        
        if 'locations' not in data:
            self.send_error_json(400, "Missing 'locations' field")
            return
        
        if not isinstance(data['locations'], list):
            self.send_error_json(400, "'locations' must be an array")
            return
        
        for i, loc in enumerate(data['locations']):
            if not isinstance(loc, dict):
                self.send_error_json(400, f"Location at index {i} must be an object")
                return
            if 'participants' not in loc:
                self.send_error_json(400, f"Location at index {i} missing 'participants' field")
                return
            try:
                participants = int(loc['participants'])
                if participants < 0:
                    raise ValueError("Negative participants")
            except (ValueError, TypeError):
                self.send_error_json(400, f"Location at index {i} has invalid participants value: {loc['participants']}")
                return
        
        try:
            data_dir = Path(__file__).parent / 'data'
            normalized_locations, unmapped_names, total_participants, captured_timestamp = process_locations_data(
                data['locations'], data_dir, data.get('capturedAt')
            )
            
            response_data = {
                'ok': True,
                'count': len(normalized_locations),
                'total': total_participants,
                'unmapped': unmapped_names
            }
            
            response_body = json.dumps(response_data).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            
        except Exception as e:
            print(f"Error processing ingest: {e}", file=sys.stderr)
            self.send_error_json(500, f"Internal Server Error: {str(e)}")
    
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