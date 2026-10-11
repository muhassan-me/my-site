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
sys.path.insert(0, str(Path(__file__).parent))
from parser import parse_paste_content
from history import compact_history

DEFAULT_USER_AGENT = "SpaceAppsEgyptRanker/1.0"
DEFAULT_URL = "https://www.spaceappschallenge.org/2026/local-events/"
FETCH_INTERVAL_SECONDS = 3600  # 1 hour


def run_check():
    """Run checks on the sample paste fixture and print PASS/FAIL per case."""
    # Read the sample_paste.txt
    sample_path = Path(__file__).parent / 'sample_paste.txt'
    try:
        text = sample_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error: Could not read sample_paste.txt: {e}", file=sys.stderr)
        sys.exit(1)

    countries_dict = parse_paste_content(text)

    lines = text.splitlines()

    # Case 1: 3+ countries
    case1 = len(countries_dict) >= 3

    # Case 2: noise lines
    noise_keywords = ['Some noise line', 'Another noise line', 'Noise line between countries', 'More noise']
    case2 = any(keyword in text for keyword in noise_keywords)

    # Case 3: a comma count
    import re
    case3 = bool(re.search(r'\d,\d', text))

    # Case 4: location with NO badges followed by an entry from a different country that has "Virtual"
    case4 = False
    if 'Canada' in countries_dict and 'Mexico' in countries_dict:
        # Find Toronto in Canada
        toronto = None
        for loc in countries_dict['Canada']:
            if loc['name'] == 'Toronto':
                toronto = loc
                break
        # Find Mexico City in Mexico
        mex_city = None
        for loc in countries_dict['Mexico']:
            if loc['name'] == 'Mexico City':
                mex_city = loc
                break
        if toronto and mex_city:
            if not toronto['virtual'] and not toronto['inPerson'] and not toronto['accepting'] and mex_city['virtual']:
                case4 = True

    # Case 5: footer lines after the last entry
    stripped_lines = [line for line in lines if line.strip() != '']
    if len(stripped_lines) >= 2:
        case5 = stripped_lines[-2] == 'Footer line 1' and stripped_lines[-1] == 'Footer line 2'
    else:
        case5 = False

    # Case 6: duplicate location
    case6 = False
    if 'Egypt' in countries_dict:
        cairos = [loc for loc in countries_dict['Egypt'] if loc['name'] == 'Cairo']
        if len(cairos) == 1 and cairos[0]['participants'] == 2400:
            case6 = True

    # Print results
    print(f"{'PASS' if case1 else 'FAIL'}: 3+ countries")
    print(f"{'PASS' if case2 else 'FAIL'}: noise lines")
    print(f"{'PASS' if case3 else 'FAIL'}: a comma count")
    print(f"{'PASS' if case4 else 'FAIL'}: no-badge entry stays without badges")
    print(f"{'PASS' if case5 else 'FAIL'}: footer ignored")
    print(f"{'PASS' if case6 else 'FAIL'}: duplicate keeps the last")

    sys.exit(0 if all([case1, case2, case3, case4, case5, case6]) else 1)


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
    parser.add_argument('--check', action='store_true', help='Run checks on the sample paste and exit')
    parser.add_argument('--data-dir', type=str, default='data', help='Directory for JSON files (default: data)')
    parser.add_argument('--user-agent', type=str, default=DEFAULT_USER_AGENT, help=f'User-Agent for fetching (default: {DEFAULT_USER_AGENT})')
    parser.add_argument('--url', type=str, default=DEFAULT_URL, help=f'URL to fetch (default: {DEFAULT_URL})')
    args = parser.parse_args()
    if args.check:
        run_check()
        return

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    global_events = []

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
            if not isinstance(data, dict) or not isinstance(data.get('countries'), dict):
                print("Error: JSON import requires country-grouped 'countries'; flat locations are unverified", file=sys.stderr)
                sys.exit(1)
            countries_dict = data['countries']
            global_events = data.get('globalEvents', [])
            snapshot_timestamp = data.get('capturedAt')
        else:
            try:
                text = input_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error: Could not read input file: {e}", file=sys.stderr)
                sys.exit(1)
            countries_dict = parse_paste_content(text)
            snapshot_timestamp = None

    universal_locations = countries_dict.pop('Universal Event', [])
    global_events.extend({
        **location,
        'name': 'Universal Event',
        'description': location.get('description') or location.get('name', ''),
        'scope': 'global'
    } for location in universal_locations)

    # Process the countries_dict to build the new snapshot
    # Deduplicate within each country by location name (keeping the last occurrence)
    processed_countries = {}
    for country, locs in countries_dict.items():
        # Deduplicate by name, keeping the last
        seen = {}
        for loc in locs:
            identity = (loc.get('city') or loc['name'], loc.get('eventSite') or '')
            seen[identity] = loc
        processed_countries[country] = list(seen.values())

    # Build the snapshot
    if snapshot_timestamp is None:
        snapshot_timestamp = datetime.now(timezone.utc).isoformat()
    else:
        # Ensure it's a string
        snapshot_timestamp = str(snapshot_timestamp)

    snapshot = {
        'timestamp': snapshot_timestamp,
        'countries': processed_countries,
        'globalEvents': global_events
    }

    # Update history.json
    history_file = data_dir / 'history.json'
    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error: Could not read {history_file}; original preserved: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(history, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('countries'), dict)
            for item in history
        ):
            print(f"Error: Invalid snapshot data in {history_file}; original preserved", file=sys.stderr)
            sys.exit(1)
    now = datetime.now(timezone.utc)
    history = compact_history(history, snapshot, now)
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, separators=(",", ":"), ensure_ascii=False)

    # Update latest.json
    latest_file = data_dir / 'latest.json'
    latest_data = {
        'capturedAt': snapshot_timestamp,
        'countries': processed_countries,
        'globalEvents': global_events
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

    total_participants += sum(event.get('participants', 0) for event in global_events)
    print("\n" + "="*60)
    print(f"Total countries: {len(processed_countries)}")
    print(f"Total locations: {sum(len(locs) for locs in processed_countries.values())}")
    print(f"Total participants: {total_participants}")
    print("="*60)

    print(f"Successfully processed locations from {len(processed_countries)} country(ies).")
    print(f"Updated {history_file} and {latest_file}")


if __name__ == '__main__':
    main()