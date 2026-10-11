import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


YEAR_MIN = 2021
YEAR_MAX = 2025


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
        self._heading = 0
        self._title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if not self._skip and tag in ("br", "p", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
        if not self._skip and tag in ("h1", "h2", "h3"):
            self._heading += 1
            self.headings.append("")
        if not self._skip and tag == "title":
            self._title = True
        if tag == "meta" and attrs.get("property", "").lower() == "og:title":
            self.meta_title = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1
        if not self._skip and tag in ("br", "p", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
        if not self._skip and tag in ("h1", "h2", "h3") and self._heading:
            self._heading -= 1
        if tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._skip:
            return
        value = " ".join(data.split())
        if not value:
            return
        self.parts.append(value)
        if self._heading:
            self.headings[-1] += value
        if self._title:
            self.title_parts.append(value)


def parse_historical_detail(html, source_url, event_year):
    text = extract_visible_text(html)
    page = VisiblePageParser()
    page.feed(html)
    fields = _label_fields(text)
    title = page.meta_title or " ".join(page.title_parts) or ""
    location = next((heading.strip() for heading in page.headings if heading.strip()), title.strip())
    location = re.sub(r"\s*[|–-]\s*(NASA Space Apps.*|Space Apps Challenge.*)$", "", location, flags=re.I).strip()
    if fields.get("location"):
        location = fields["location"]
    if not location:
        return None, "No location name found in page title or headings"

    participants = _count_value(text, ("participants?", "people", "attendees?", "participating"))
    teams = _count_value(text, ("teams?",))
    record = {
        "eventYear": event_year,
        "sourceUrl": source_url,
        "locationName": location,
        "country": fields.get("country"),
        "city": fields.get("city"),
        "eventSite": location if not fields.get("city") or location != fields.get("city") else None,
        "participants": participants,
        "teams": teams
    }
    return record, None


def extract_visible_text(html):
    page = VisiblePageParser()
    page.feed(html)
    return "\n".join(line.strip() for line in "".join(page.parts).splitlines() if line.strip())


def _label_fields(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {}
    for index, line in enumerate(lines):
        match = re.match(r"^(country|city|location)\s*[:\-]?\s*(.*)$", line, re.I)
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
    label = "(?:" + "|".join(labels) + ")"
    patterns = (
        rf"(?im)^\s*{label}\s*[:\-]?\s*([\d,]+)\s*$",
        rf"(?im)^\s*([\d,]+)\s+{label}\b[^\r\n]*$",
        rf"(?im)^\s*{label}\s*[:\-]?\s*\r?\n\s*([\d,]+)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                return None
    return None
