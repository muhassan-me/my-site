import re

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