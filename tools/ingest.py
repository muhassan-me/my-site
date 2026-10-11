#!/usr/bin/env python3
"""
Ingest script for NASA Space Apps Challenge 2026 multi-country locations.
Parses a text paste of the events page or fetches from the website (with robots.txt check).
Updates history.json and latest.json in the specified data directory.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path

DEFAULT_USER_AGENT = "SpaceAppsEgyptRanker/1.0"
DEFAULT_URL = "https://www.spaceappschallenge.org/2026/local-events/"
FETCH_INTERVAL_SECONDS = 3600  # 1 hour

def parse_paste_content(text):
    """
    Parse the paste text to extract locations for all countries.
    Returns a dict: {country: [location_dicts]} where each location_dict has
    keys: name, participants, virtual, inPerson, accepting.
    Parsing rule: anchor on the "N Participating" line. Location = nearest non-blank line above it.
    Country = the non-blank line above the location. Badges (Virtual / In-Person / Accepting Participants)
    are only the lines directly after. No hardcoded country list. Counts may contain commas.
    Same location twice in one country = keep the last. Ignore everything else.
    """
    lines = text.splitlines()
    result = {}  # country -> list of locations
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for a line that contains "participating" (case-insensitive)
        if 'participating' in line.lower():
            # Found a participating line, now look backwards for location and country
            # Find location line: nearest non-blank line above
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j < 0:
                i += 1
                continue
            location_line = lines[j].strip()
            # Find country line: nearest non-blank line above the location line
            k = j - 1
            while k >= 0 and not lines[k].strip():
                k -= 1
            if k < 0:
                i += 1
                continue
            country_line = lines[k].strip()
            # Extract participant count
            match = re.search(r'[\d,]+', line)
            if not match:
                i += 1
                continue
            try:
                participants = int(match.group(0).replace(',', ''))
            except ValueError:
                i += 1
                continue
            # Initialize badges
            virtual = False
            inPerson = False
            accepting = False
            # Look at the lines directly after the participating line (up to 3 lines)
            # We'll check the next lines for badge keywords
            m = i + 1
            while m < len(lines) and m <= i + 3:  # check up to 3 lines after
                badge_line = lines[m].lower()
                if not virtual and 'virtual' in badge_line:
                    virtual = True
                elif not inPerson and 'in-person' in badge_line:
                    inPerson = True
                elif not accepting and 'accepting' in badge_line and 'participants' in badge_line:
                    accepting = True
                m += 1
            # Create location dict
            loc = {
                'name': location_line,
                'participants': participants,
                'virtual': virtual,
                'inPerson': inPerson,
                'accepting': accepting
            }
            # Add to result under country
            if country_line not in result:
                result[country_line] = []
            # Check if location already exists in this country (by name, case-sensitive? We'll use exact string)
            # We'll keep the last occurrence, so we remove any existing with the same name
            result[country_line] = [loc for loc in result[country_line] if loc['name'] != location_line]
            result[country_line].append(loc)
            # Move i past the lines we've checked
            i = m
        else:
            i += 1
    return result

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
    parser = argparse.ArgumentParser(description='Ingest Space Apps Challenge 2026 multi-country location data.')
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
        countries_dict = parse_paste_content(text)
        snapshot_timestamp = None
    else:
        if not args.input_file:
            print("Error: Either provide an input file or use --fetch.", file=sys.stderr)
            sys.exit(1)
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        if str(input_path).lower().endswith('.json'):
            # Parse JSON input (assumed to be old Egypt-only format)
            try:
                with open(input_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error: Could not read JSON file {input_path}: {e}", file=sys.stderr)
                sys.exit(1)
            if 'locations' not in data:
                print(f"Error: JSON file missing 'locations' key", file=sys.stderr)
                sys.exit(1)
            # Convert old format to new format: assume it's Egypt-only
            old_locations = data['locations']
            countries_dict = {"Egypt": []}
            seen_names = set()
            for loc in old_locations:
                name = loc.get('name', '')
                if not name:
                    continue
                if name in seen_names:
                    continue  # skip duplicates, keep first occurrence
                seen_names.add(name)
                countries_dict["Egypt"].append({
                    'name': name,
                    'participants': int(loc.get('participants', 0)),
                    'virtual': bool(loc.get('virtual', False)),
                    'inPerson': bool(loc.get('inPerson', False)),
                    'accepting': bool(loc.get('accepting', False))
                })
            snapshot_timestamp = data.get('capturedAt')
        else:
            try:
                text = input_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error: Could not read input file: {e}", file=sys.stderr)
                sys.exit(1)
            countries_dict = parse_paste_content(text)
            snapshot_timestamp = None

    # Process the countries_dict to build the new snapshot
    # Deduplicate within each country by location name (keeping the last occurrence)
    processed_countries = {}
    for country, locs in countries_dict.items():
        # Deduplicate by name, keeping the last
        seen = {}
        for loc in locs:
            seen[loc['name']] = loc
        processed_countries[country] = list(seen.values())

    # Build the snapshot
    if snapshot_timestamp is None:
        snapshot_timestamp = datetime.now(timezone.utc).isoformat()
    else:
        # Ensure it's a string
        snapshot_timestamp = str(snapshot_timestamp)

    snapshot = {
        'timestamp': snapshot_timestamp,
        'countries': processed_countries
    }

    # Update history.json
    history_file = data_dir / 'history.json'
    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(snapshot)
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

    # Update latest.json
    latest_file = data_dir / 'latest.json'
    latest_data = {
        'capturedAt': snapshot_timestamp,
        'countries': processed_countries
    }
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, indent=2)

    # Compute total participants and print tables
    total_participants = 0
    for country, locs in processed_countries.items():
        country_total = sum(loc['participants'] for loc in locs)
        total_participants += country_total
        # Print table for this country
        print(f"\nCountry: {country}")
        print(f"{'Name':<30} {'Participants':>12} {'V':>3} {'IP':>3} {'A':>3}")
        print("-" * 60)
        for loc in locs:
            name = loc['name']
            part = loc['participants']
            v = 'X' if loc['virtual'] else ' '
            ip = 'X' if loc['inPerson'] else ' '
            a = 'X' if loc['accepting'] else ' '
            print(f"{name:<30} {part:>12} {v:>3} {ip:>3} {a:>3}")
        print("-" * 60)
        print(f"Total locations in {country}: {len(locs)}")
        print(f"Total participants in {country}: {country_total}")

    print("\n" + "="*60)
    print(f"Total countries: {len(processed_countries)}")
    print(f"Total locations: {sum(len(locs) for locs in processed_countries.values())}")
    print(f"Total participants: {total_participants}")
    print("="*60)

    print(f"Successfully processed locations from {len(processed_countries)} country(ies).")
    print(f"Updated {history_file} and {latest_file}")

if __name__ == '__main__':
    main()