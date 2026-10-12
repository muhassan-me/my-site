# NASA Space Apps Local Events Archive

An unofficial local dashboard for country and event-location participant totals from NASA Space Apps pages.

## How to Run

### Development Server (Recommended for Bookmarklet Support)

1.  Make sure you have Python 3 installed.
2.  Start or restart the custom server so the updated ingest endpoint is loaded:
    ```bash
    py serve.py
    ```
3.  Open your browser to `http://127.0.0.1:8080`.

### Simple HTTP Server (Alternative)

1.  Make sure you have Python 3 installed.
2.  Start a local HTTP server:
    ```bash
    py -m http.server 8080
    ```
3.  Open your browser to `http://localhost:8080`.

## How to Ingest Data

### Using a Paste (Default, Recommended)

1.  Copy the text from the [Space Apps 2026 Local Events page](https://www.spaceappschallenge.org/2026/local-events/) (or use the provided sample).
2.  Save it to a file, e.g., `paste.txt`.
3.  Run the ingest script:
    ```bash
    py tools/ingest.py paste.txt
    ```
    This will update `data/latest.json` and `data/history.json`.

### Import an event edition with the bookmarklet

The updated server must be running locally at `http://localhost:8080`. If it was already running before this change, restart it first. The exact bookmarklet URL is exported by `tools/capture.js`; print it with `node -p "require('./tools/capture.js')"`, then create a bookmark using that entire output as its URL.

For every listing from 2021 through 2026, the bookmarklet detects the edition from the old hostname or the modern path, then downloads the same JSON manifest containing visible listing text, capture time, listing URL, discovered detail URLs, and card text where rendered. The bookmarklet never fetches location pages cross-origin. Run the same local collector for every year:

```bash
py tools/collect_locations.py space-apps-2021-locations.json
```

Replace the manifest filename with the downloaded file for the desired edition. The collector fetches each same-host Space Apps detail URL over HTTPS, parses fields available on the detail page, and uses an explicitly labeled listing-card count only when the detail page omits that count. It imports through the existing `/api/ingest` endpoint, waiting half a second between pages by default. It never assigns an unknown country or changes current `latest.json` / `history.json`. Missing counts remain `null`.

If a listing has no detail links, the bookmarklet still saves a manifest marked `no-detail-links-found`; the collector writes a retry report and does not treat listing text as imported locations. The live 2024–2026 pages may currently render no location cards; their imports will remain incomplete until official detail links are available. If individual pages fail or cannot be parsed, the collector writes a `.retry.json` containing only failed URLs; rerun it with `py tools/collect_locations.py space-apps-2021-locations.retry.json`. Successfully imported pages can be repeated safely; the archive deduplicates by event year, source page URL, and content hash. Listing and detail URLs/capture times are retained.

Neither capture nor collection executes captured text. Pages that are inaccessible, lack valid headings, or contain invalid explicit counts are reported as failures rather than successful records.

Historical record conflicts use the latest `capturedAt` value; equal timestamps use lexicographically greater source URL. All source URLs and capture times are retained as provenance. A repeated city within the same country and edition is one record; identical city names in different countries remain separate. Workbook rows are lower-priority fallback records and are marked incomplete because their original page URLs and capture times are unavailable.

Each edition uses the same detail-page archive schema. A location without a verified country stays in the archive's `unverified` records and is excluded from country totals until its country can be established from source information. Available teams are stored alongside participants; missing values stay `null` and are displayed as not reported.

`data/archive.json` uses `{ "schemaVersion": 1, "editions": { "2023": { "imports": [...] } } }`. Each import retains its `eventYear`, `sourceUrl`, `capturedAt`, SHA-256 content hash, original visible text, parsed country/city/event-site records, global events, and unverified lines. Edition totals are calculated from deduplicated records; timestamped entries in `data/history.json` are never interpreted as event editions.

## Data Files

-   `data/latest.json`: Current snapshot of locations with capturedAt timestamp.
-   `data/history.json`: Array of timestamped snapshots.
-   `data/archive.json`: Edition-keyed historical imports with source text, page URLs, capture timestamps, parsed records, and duplicate hashes. Historical imports never update current files.
-   `tools/collect_locations.py`: Local HTTPS detail-page collector for all supported editions; writes a retry manifest for failed pages.
-   `data/governorates.json`: Editable map from location name to governorate.
-   `data/past_events.json`: Existing Egypt-only workbook data for 2021-2025; these rows are shown as incomplete-provenance fallback, not as bookmarklet captures.

## Project Structure

```
my-site/
├── index.html
├── style.css
├── script.js
├── serve.py                 # Custom server with API endpoint
├── data/
│   ├── latest.json
│   ├── history.json
│   ├── archive.json
│   ├── governorates.json
│   └── past_events.json
├── js/
│   ├── data.js
│   ├── archive-data.js
│   ├── chrome.js
│   ├── edition.js
│   ├── i18n.js
│   └── render.js
├── tools/
│   ├── collect_locations.py # Local historical detail-page collector
│   ├── historical.py        # URL detection and detail-page parsing
│   ├── test_historical.py   # Historical import regression tests
│   ├── ingest.py            # CLI ingestion tool
│   ├── parser.py            # Shared parsing logic
│   ├── capture.js           # Bookmarklet source
│   └── sample_paste.txt
└── README.md
```