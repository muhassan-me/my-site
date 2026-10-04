#!/usr/bin/env python3
"""
Ingest script for NASA Space Apps Challenge 2026 Egypt locations.
Parses a text paste of the events page or fetches from the website (with robots.txt check).
Updates history.json and latest.json in the specified data directory.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path

# Import our library
from tools.ingest_lib import process_locations_data, load_governorates

DEFAULT_USER_AGENT = "SpaceAppsEgyptRanker/1.0"
DEFAULT_URL = "https://www.spaceappschallenge.org/2026/local-events/"
FETCH_INTERVAL_SECONDS = 3600  # 1 hour

def parse_paste_content(text):
    """
    Parse the paste text to extract Egypt locations.
    Returns a list of location dicts.
    """
    lines = text.splitlines()
    # Find indices of lines that (case-insensitive) and stripped equal "egypt"
    egypt_indices = [i for i, line in enumerate(lines) if line.strip().lower() == 'egypt']
    locations_dict = {}  # key: normalized name (lowercase, stripped)

    for idx in egypt_indices:
        # The chunk is the lines after this index until the next egypt index or end of file
        chunk_lines = []
        j = idx + 1
        while j < len(lines) and (j not in egypt_indices):
            chunk_lines.append(lines[j])
            j += 1
        # Skip empty lines at the start
        while chunk_lines and not chunk_lines[0].strip():
            chunk_lines.pop(0)
        if not chunk_lines:
            continue
        location_line = chunk_lines[0].strip()
        # Now find the participating line
        participating_line = None
        for line in chunk_lines[1:]:
            if 'participating' in line.lower():
                participating_line = line.strip()
                break
        if participating_line is None:
            continue
        # Extract number from participating_line
        match = re.search(r'[\d,]+', participating_line)
        if not match:
            continue
        try:
            participants = int(match.group(0).replace(',', ''))
        except ValueError:
            continue
        # Initialize badges
        virtual = False
        inPerson = False
        accepting = False
        # Look for badge lines in the entire chunk_lines
        for line in chunk_lines:
            lower_line = line.lower()
            if not virtual and 'virtual' in lower_line:
                virtual = True
            elif not inPerson and 'in-person' in lower_line:
                inPerson = True
            elif not accepting and 'accepting' in lower_line and 'participants' in lower_line:
                accepting = True
        # Store in dictionary, overwriting any previous entry with the same normalized name
        norm_name = location_line.lower().strip()
        locations_dict[norm_name] = {
            'name': location_line,
            'participants': participants,
            'virtual': virtual,
            'inPerson': inPerson,
            'accepting': accepting
        }

    return list(locations_dict.values())

def check_and_fetch(url, user_agent, data_dir):
    """
    Check robots.txt and fetch the URL if allowed and not fetched in the last hour.
    Returns the fetched text or None if fetch is not allowed or too soon.
    """
    rp = urllib.robotparser.RobotFileParser()
    robots_url = urllib.request.urljoin(url, '/robots.txt')
    try:
        req = urllib.request.Request(robots_url, headers={'User-Agent': user_agent})
        with urllib.request.urlopen(req, timeout=10) as resp:
            robots_content = resp.read().decode('utf-8')
        rp.parse(robots_content.splitlines())
    except Exception as e:
        print(f"Warning: Could not fetch or parse robots.txt: {e}", file=sys.stderr)
        # If we can't check robots.txt, we assume disallowed to be safe.
        return None

    if not rp.can_fetch(user_agent, url):
        print(f"Error: Fetching {url} is disallowed by robots.txt for User-Agent: {user_agent}", file=sys.stderr)
        return None

    # Check last fetch time
    last_fetch_file = data_dir / '.last_fetch'
    now = time.time()
    if last_fetch_file.exists():
        try:
            last_fetch = float(last_fetch_file.read_text().strip())
            if now - last_fetch < FETCH_INTERVAL_SECONDS:
                remaining = int(FETCH_INTERVAL_SECONDS - (now - last_fetch))
                print(f"Error: Last fetch was less than an hour ago. Try again in {remaining} seconds.", file=sys.stderr)
                return None
        except ValueError:
            pass  # Ignore invalid timestamp

    # Fetch the page
    try:
        req = urllib.request.Request(url, headers={'User-Agent': user_agent})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                print(f"Error: Failed to fetch {url}: HTTP {resp.status}", file=sys.stderr)
                return None
            content = resp.read().decode('utf-8')
    except Exception as e:
        print(f"Error: Failed to fetch {url}: {e}", file=sys.stderr)
        return None

    # Update last fetch time
    try:
        last_fetch_file.write_text(str(now))
    except Exception as e:
        print(f"Warning: Could not update last fetch timestamp: {e}", file=sys.stderr)

    return content

def main():
    parser = argparse.ArgumentParser(description='Ingest Space Apps Egypt location data.')
    parser.add_argument('input_file', nargs='?', help='Path to paste text file (if not using --fetch)')
    parser.add_argument('--fetch', action='store_true', help='Fetch from the website instead of using a paste file')
    parser.add_argument('--data-dir', type=str, default='data', help='Directory for JSON files (default: data)')
    parser.add_argument('--user-agent', type=str, default=DEFAULT_USER_AGENT, help=f'User-Agent for fetching (default: {DEFAULT_USER_AGENT})')
    parser.add_argument('--url', type=str, default=DEFAULT_URL, help=f'URL to fetch (default: {DEFAULT_URL})')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.fetch:
        if args.input_file:
            print("Warning: Ignoring input file because --fetch is set.", file=sys.stderr)
        text = check_and_fetch(args.url, args.user_agent, data_dir)
        if text is None:
            sys.exit(1)
        # Parse as paste
        locations = parse_paste_content(text)
        snapshot_timestamp = None  # Will be generated in process_locations_data
    else:
        if not args.input_file:
            print("Error: Either provide an input file or use --fetch.", file=sys.stderr)
            sys.exit(1)
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        if str(input_path).lower().endswith('.json'):
            # Parse JSON input
            try:
                with open(input_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error: Could not read JSON file {input_path}: {e}", file=sys.stderr)
                sys.exit(1)
            if 'locations' not in data:
                print(f"Error: JSON file missing 'locations' key", file=sys.stderr)
                sys.exit(1)
            locations = data['locations']
            snapshot_timestamp = data.get('capturedAt')
        else:
            try:
                text = input_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error: Could not read input file: {e}", file=sys.stderr)
                sys.exit(1)
            locations = parse_paste_content(text)
            snapshot_timestamp = None

    # Process locations using shared logic
    try:
        normalized_locations, unmapped_names, total_participants, captured_timestamp = process_locations_data(
            locations, data_dir, snapshot_timestamp
        )
    except Exception as e:
        print(f"Error processing locations: {e}", file=sys.stderr)
        sys.exit(1)

    # Print unmapped warnings
    for name in unmapped_names:
        print(f"unmapped: {name}")

    # Print table
    print(f"{'Name':<20} {'Governorate':<15} {'Participants':>12} {'V':>3} {'IP':>3} {'A':>3} {'LL':>3}")
    print("-" * 80)
    for loc in normalized_locations:
        name = loc['name']
        gov = loc['governorate'] if loc['governorate'] is not None else ''
        part = loc['participants']
        v = 'X' if loc['virtual'] else ' '
        ip = 'X' if loc['inPerson'] else ' '
        a = 'X' if loc['accepting'] else ' '
        ll = 'X' if loc['localLead'] else ' '
        print(f"{name:<20} {gov:<15} {part:>12} {v:>3} {ip:>3} {a:>3} {ll:>3}")
    print("-" * 80)
    print(f"Total locations: {len(normalized_locations)}")
    print(f"Total participants: {total_participants}")

    print(f"Successfully processed {len(normalized_locations)} locations from Egypt.")
    print(f"Updated {data_dir / 'history.json'} and {data_dir / 'latest.json'}")

if __name__ == '__main__':
    main()