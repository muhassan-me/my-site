#!/usr/bin/env python3
"""
Refactored ingestion logic and helper functions.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

def load_governorates(data_dir):
    gov_file = data_dir / 'governorates.json'
    try:
        with open(gov_file, 'r', encoding='utf-8-sig') as f:
            gov_data = json.load(f)
    except Exception as e:
        print(f"Error: Could not read governorates.json: {e}", file=sys.stderr)
        sys.exit(1)
    canonical_map = {}
    governorate_map = {}
    for key, gov in gov_data.items():
        canonical_map[key.lower()] = key
        governorate_map[key] = gov
    return canonical_map, governorate_map

def parse_paste_content(text):
    lines = text.splitlines()
    egypt_indices = [i for i, line in enumerate(lines) if line.strip().lower() == 'egypt']
    locations_dict = {}

    for idx in egypt_indices:
        chunk_lines = []
        j = idx + 1
        while j < len(lines) and (j not in egypt_indices):
            chunk_lines.append(lines[j])
            j += 1
        while chunk_lines and not chunk_lines[0].strip():
            chunk_lines.pop(0)
        if not chunk_lines:
            continue
        location_line = chunk_lines[0].strip()
        participating_line = None
        for line in chunk_lines[1:]:
            if 'participating' in line.lower():
                participating_line = line.strip()
                break
        if participating_line is None:
            continue
        match = re.search(r'[\d,]+', participating_line)
        if not match:
            continue
        try:
            participants = int(match.group(0).replace(',', ''))
        except ValueError:
            continue
        virtual = False
        inPerson = False
        accepting = False
        for line in chunk_lines:
            lower_line = line.lower()
            if not virtual and 'virtual' in lower_line:
                virtual = True
            elif not inPerson and 'in-person' in lower_line:
                inPerson = True
            elif not accepting and 'accepting' in lower_line and 'participants' in lower_line:
                accepting = True
        norm_name = location_line.lower().strip()
        locations_dict[norm_name] = {
            'name': location_line,
            'participants': participants,
            'virtual': virtual,
            'inPerson': inPerson,
            'accepting': accepting
        }
    return list(locations_dict.values())

def process_locations_data(raw_locations, data_dir, captured_at=None):
    """
    Normalizes locations using governorates.json, updates latest.json and history.json.
    Returns (normalized_locations, unmapped_names, total_participants, captured_timestamp).
    """
    canonical_map, governorate_map = load_governorates(data_dir)
    
    normalized_locations = []
    unmapped_names = []
    
    for loc in raw_locations:
        input_name = loc.get('name', '')
        key_lower = input_name.lower()
        if key_lower in canonical_map:
            canonical_name = canonical_map[key_lower]
            governorate = governorate_map.get(canonical_name)
        else:
            canonical_name = input_name
            governorate = None
            if input_name not in unmapped_names:
                unmapped_names.append(input_name)
                
        normalized_locations.append({
            'slug': loc.get('slug', ''),
            'name': canonical_name,
            'participants': int(loc['participants']),
            'virtual': bool(loc.get('virtual', False)),
            'inPerson': bool(loc.get('inPerson', False)),
            'accepting': bool(loc.get('accepting', False)),
            'localLead': bool(loc.get('localLead', False)),
            'governorate': governorate
        })

    snapshot_timestamp = captured_at if captured_at else datetime.now(timezone.utc).isoformat()
    
    snapshot = {
        'timestamp': snapshot_timestamp,
        'locations': normalized_locations
    }

    history_file = data_dir / 'history.json'
    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Could not read {history_file}; original preserved: {e}") from e
        if not isinstance(history, list):
            raise ValueError(f"Invalid history data in {history_file}; original preserved")
    history.append(snapshot)
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

    latest_file = data_dir / 'latest.json'
    latest_data = {
        'capturedAt': snapshot_timestamp,
        'locations': normalized_locations
    }
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, indent=2)

    total_participants = sum(loc['participants'] for loc in normalized_locations)
    return normalized_locations, unmapped_names, total_participants, snapshot_timestamp
