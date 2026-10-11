import re


def parse_event_page(text):
    """Parse a captured event page into local records and separate global events."""
    lines = text.splitlines()
    records = []
    global_events = []
    unverified = []
    for index, line in enumerate(lines):
        if 'participating' not in line.lower():
            continue
        nearest = _previous_nonblank(lines, index - 1)
        before = _previous_nonblank(lines, nearest[0] - 1) if nearest else None
        if not nearest or not before:
            count_match = re.search(r'[\d,]+', line)
            if count_match:
                unverified.append({
                    'sourceLines': [nearest[1]] if nearest else [],
                    'participants': int(count_match.group(0).replace(',', '')),
                    'reasonKey': 'unverifiedParse'
                })
            continue
        first, second = before[1], nearest[1]
        count_match = re.search(r'[\d,]+', line)
        if not count_match:
            continue
        participants = int(count_match.group(0).replace(',', ''))
        flags = _read_badges(lines, index)

        is_global = any(
            marker in value.lower()
            for value in (first, second)
            for marker in ('universal event', 'anywhere in the world')
        )
        if is_global:
            description = second if 'universal event' in first.lower() else first
            global_events.append({
                'name': 'Universal Event',
                'description': description,
                'participants': participants,
                **flags,
                'scope': 'global',
                'eventType': 'global'
            })
            continue

        if _looks_uppercase(second) and not _looks_uppercase(first):
            city, country = first, second
        else:
            country, city = first, second
        if not country.strip() or not city.strip():
            unverified.append({'sourceLines': [first, second], 'participants': participants})
            continue
        records.append({
            'country': country.strip(),
            'city': city.strip(),
            'eventSite': None,
            'name': city.strip(),
            'participants': participants,
            **flags,
            'scope': 'local',
            'eventType': _event_type(flags)
        })

    countries = {}
    seen = {}
    for record in records:
        key = (record['country'], record['city'], record['eventSite'] or '')
        seen[key] = record
    for record in seen.values():
        countries.setdefault(record['country'], []).append(record)
    return {'countries': countries, 'globalEvents': global_events, 'unverified': unverified}


def _previous_nonblank(lines, index):
    while index >= 0 and not lines[index].strip():
        index -= 1
    return (index, lines[index].strip()) if index >= 0 else None


def _read_badges(lines, index):
    flags = {'virtual': False, 'inPerson': False, 'accepting': False}
    for badge_line in lines[index + 1:index + 4]:
        lower_line = badge_line.lower()
        if 'virtual' in lower_line:
            flags['virtual'] = True
        if 'in-person' in lower_line:
            flags['inPerson'] = True
        if 'accepting' in lower_line and 'participants' in lower_line:
            flags['accepting'] = True
    return flags


def _looks_uppercase(value):
    letters = [character for character in value if character.isalpha()]
    return bool(letters) and value == value.upper()


def _event_type(flags):
    if flags['virtual'] and flags['inPerson']:
        return 'hybrid'
    if flags['inPerson']:
        return 'in-person'
    if flags['virtual']:
        return 'virtual'
    return 'unknown'

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