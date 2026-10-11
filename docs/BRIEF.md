# BRIEF: Space Apps Local Events Tracker

Product: unofficial dashboard that ranks NASA Space Apps Challenge 2026 local-event locations by participants, for every country on the public local-events page, with change over time. Tone: calm, confident, human.

## Hard rules
- No emoji, no emoji flags. Icons only as inline SVG in one stroke style.
- No frameworks, no external CDNs or fonts, no network calls except local data files.
- Arabic RTL default plus English toggle; all strings in one i18n object.
- Test data only in data_test/. One phase at a time, then list changed files and stop.

## Data (already built, do not change shape)
- data/history.json: [{timestamp, countries:{Country:[{name, participants, virtual, inPerson, accepting}]}}], compact, see tools/history.py
- data/latest.json: {capturedAt, countries:{...}}
- data/regions.json: {Country:{Location:Governorate/Region}}, Egypt prefilled
- data/past_events.json: Egypt past years, keep as is
- Import: bookmarklet -> #import= -> /api/ingest (serve.py), parser in tools/parser.py
- localLead was dropped in the migration; do not re-add unless I ask.

## Keep from the current UI
- Egypt "Past years" section (year selector + table) and the yearly comparison bar chart with the current year highlighted. Egypt view only.
- Governorate column and share-of-total percentage.

## Change from the current UI
- Remove the "الرموز" chips column. Virtual / In-person / Accepting appear as small text chips inside the location detail drawer only.
- Show names exactly as in the data; no automatic translation.

## Design direction
- Mission control meets editorial. Dark navy base, lime accent, one warm accent for "rising". Subtle CSS-only starfield, thin orbit-line SVG motif in the hero, no stock images.
- System font stack, tabular numbers, strong size hierarchy, 8px grid, generous whitespace.
- Motion: count-up numbers, staggered row reveal, smooth rank changes; respect prefers-reduced-motion.
- Real human copy in Arabic and English, useful empty states, honest footer: "Unofficial. Counts copied from the public Space Apps page on <date>."
- Layout: top bar, hero with global totals, searchable country selector (participants per country), country view, location detail drawer, footer.
- Inline SVG favicon, WCAG AA contrast, mobile-first, check 360px and 1280px.

## Features (priority)
P1 Country selector + country view: tie-aware ranks, share of country total, governorate/region toggle only when regions.json has entries for that country.
P1 Global overview: total participants, countries, locations, countries leaderboard.
P1 Deep links: #/country/<slug>, #/location/<slug>.
P2 Trends: change vs previous snapshot and ~24h, rank movement, biggest riser, New tag, sparklines.
P2 Pin my location (across countries). P2 Global search.
P3 Compare up to 3 locations (inline SVG chart). P3 Data freshness warning (older than 24h).
P3 CSV export, print stylesheet, copy-summary button, goal progress per location (localStorage).