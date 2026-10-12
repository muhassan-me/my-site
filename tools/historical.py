import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit


YEAR_MIN = 2021
YEAR_MAX = datetime.now().year


def detect_event_year(url):
    parts = urlsplit(url)
    hostname = (parts.hostname or "").lower()
    host_match = re.match(r"^(2021|2022)\.", hostname)
    if host_match:
        return int(host_match.group(1))
    for segment in parts.path.split("/"):
        match = re.match(r"^(?:nasa-space-apps-)?(20\d{2})(?:-local-events)?$", segment, re.I)
        if match and YEAR_MIN <= int(match.group(1)) <= YEAR_MAX:
            return int(match.group(1))
    return None


class VisiblePageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.headings = []
        self.title_parts = []
        self.meta_title = ""
        self._skip = 0
        self._heading_stack = []
        self._title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if not self._skip and tag in ("br", "p", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
        if not self._skip and tag in ("h1", "h2", "h3"):
            self.headings.append({"tag": tag, "text": ""})
            self._heading_stack.append(len(self.headings) - 1)
        if not self._skip and tag == "title":
            self._title = True
        if tag == "meta" and attrs.get("property", "").lower() == "og:title":
            self.meta_title = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1
        if not self._skip and tag in ("br", "p", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
        if not self._skip and tag in ("h1", "h2", "h3") and self._heading_stack:
            self._heading_stack.pop()
        if tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._skip:
            return
        value = " ".join(data.split())
        if not value:
            return
        self.parts.append(value)
        if self._heading_stack:
            self.headings[self._heading_stack[-1]]["text"] += value
        if self._title:
            self.title_parts.append(value)


def parse_historical_detail(html, source_url, event_year):
    if not isinstance(source_url, str) or urlsplit(source_url).scheme not in ("http", "https"):
        return None, "Missing or invalid source URL"
    text = extract_visible_text(html)
    page = VisiblePageParser()
    page.feed(html)
    fields = _label_fields(text)
    headings = [(entry["tag"], entry["text"].strip()) for entry in page.headings]
    h1 = next((value for tag, value in headings if tag == "h1" and _valid_location_name(value)), "")
    h2_values = [value for tag, value in headings if tag == "h2" and value.strip()]
    meta_title = re.sub(r"^location\s*:\s*", "", page.meta_title, flags=re.I)
    title = " ".join(page.title_parts)
    location = fields.get("location") or h1 or meta_title or title
    location = re.sub(r"\s*[|–-]\s*(NASA Space Apps.*|Space Apps Challenge.*)$", "", location, flags=re.I).strip()
    if not _valid_location_name(location):
        return None, f"Invalid or generic location name: {location!r}"

    participants = _count_value(text, ("participants?", "people", "attendees?", "participating"))
    teams = _count_value(text, ("teams?",))
    if participants is None and _has_invalid_explicit_count(text, "participants"):
        return None, "Invalid participant count format"
    if teams is None and _has_invalid_explicit_count(text, "teams"):
        return None, "Invalid team count format"
    global_event = location.casefold() == "universal event" or "universal-event" in source_url.casefold()
    country = fields.get("country")
    if not country and not global_event:
        country = next((value for value in h2_values if _valid_country_name(value)), None)
    city = fields.get("city")
    record = {
        "eventYear": event_year,
        "sourceUrl": source_url,
        "locationName": location,
        "country": None if global_event else country,
        "city": city,
        "eventSite": location if not city or location != city else None,
        "participants": participants,
        "teams": teams,
        "scope": "global" if global_event else "local",
        "eventType": "global" if global_event else "unknown"
    }
    return record, None


def extract_visible_text(html):
    page = VisiblePageParser()
    page.feed(html)
    return "\n".join(line.strip() for line in "".join(page.parts).splitlines() if line.strip())


def parse_listing_card(text):
    """Read only explicitly labeled counts from one location card."""
    result = {"participants": None, "teams": None}
    for line in str(text or "").splitlines():
        if result["participants"] is None:
            match = re.search(r"(?<![\d-])([\d,]+)\s+Participating\b", line, re.I)
            if match:
                result["participants"] = int(match.group(1).replace(",", ""))
        if result["teams"] is None:
            match = re.search(r"\bTeams?\s*\(\s*([\d,]+)\s*\)", line, re.I)
            if match:
                result["teams"] = int(match.group(1).replace(",", ""))
    return result


def _label_fields(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {}
    for index, line in enumerate(lines):
        match = re.match(r"^(country|city|location)\b\s*[:\-]?\s*(.*)$", line, re.I)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip()
        if not value and index + 1 < len(lines):
            value = lines[index + 1]
        if value:
            result[key] = value
    return result


def _count_value(text, labels):
    lines = text.splitlines()
    is_teams = "teams?" in labels
    if is_teams:
        patterns = (
            r"\bteams?\s*\(\s*([\d,]+)\s*\)",
            r"\bteams?\s*[:=]\s*([\d,]+)\b",
            r"\bteams?\s*([\d,]+)\b",
            r"(?<![\d-])([\d,]+)\s*teams?\b",
            r"\bhard work of\s*([\d,]+)\s*teams?\b",
        )
    else:
        patterns = (
            r"\bthank you to the\s*([\d,]+)\s*people\b",
            r"\bthe\s*([\d,]+)\s*people\s+who\s+(?:joined|participated|attended)\b",
            r"\bparticipants?\s*[:=]\s*\(?\s*([\d,]+)\s*\)?\b",
            r"\battendees?\s*[:=]\s*([\d,]+)\b",
            r"(?<![\d-])([\d,]+)\s*(?:people|participants?|attendees?)\b",
        )
    for line in lines:
        for pattern in patterns:
            match = re.search(pattern, line, re.I)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except ValueError:
                    return None
    return None


def _has_invalid_explicit_count(text, kind):
    if kind == "teams":
        markers = (r"\bteams?\s*\([^)]*\)", r"\bteams?\s*[:=]\s*[^\s,.;]+")
    else:
        markers = (r"\bparticipants?\s*[:=]\s*[^\s,.;]+", r"\battendees?\s*[:=]\s*[^\s,.;]+")
    return any(re.search(pattern, line, re.I) for line in text.splitlines() for pattern in markers)


def _valid_location_name(value):
    normalized = " ".join(str(value or "").split()).casefold()
    if len(normalized) < 2:
        return False
    generic = {
        "about", "welcome", "locations", "location", "challenges", "resources",
        "event info", "teams", "the collective", "anywhere in the world",
        "space apps challenge", "s"
    }
    return normalized not in generic and not re.fullmatch(r"teams\s*\(?\s*\d+\s*\)?", normalized)


def _valid_country_name(value):
    normalized = " ".join(str(value or "").split()).casefold()
    return _valid_location_name(value) and normalized not in {
        "universal event", "anywhere in the world", "welcome", "event info"
    }
