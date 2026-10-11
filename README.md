# Egypt Space Apps Challenge 2026 Ranker

A static site to rank Egyptian locations of the NASA Space Apps Challenge 2026 local events by number of participants.

## How to Run

### Development Server (Recommended for Bookmarklet Support)

1.  Make sure you have Python 3 installed.
2.  Start the custom server:
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

### Using Automatic Fetch (Optional)

> **Warning:** The site disallows bots by default. Use this only if permitted by `robots.txt`.

1.  Ensure the script's User-Agent (`SpaceAppsEgyptRanker/1.0`) is allowed to fetch `/2026/local-events/` in the site's `robots.txt`.
2.  Run with the `--fetch` flag:
    ```bash
    py tools/ingest.py --fetch
    ```
    The script will check `robots.txt` and refuse to run if disallowed. It also enforces a minimum interval of one hour between fetches.

### Capture bookmarklet

```javascript
javascript:(function(){const text=document.body.innerText;const payload={text:text,capturedAt:new Date().toISOString()};const json=JSON.stringify(payload);const encoded=btoa(unescape(encodeURIComponent(json)));window.location="http://localhost:8080/#import="+encoded;})()
```

1.  Create a bookmark with the URL above.
2.  Visit the Space Apps 2026 Local Events page.
3.  Click the bookmarklet to send the data to your local server.

## Data Files

-   `data/latest.json`: Current snapshot of locations with capturedAt timestamp.
-   `data/history.json`: Array of timestamped snapshots.
-   `data/governorates.json`: Editable map from location name to governorate.
-   `data/past_events.json`: Historical data from 2021-2025.

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
│   ├── governorates.json
│   └── past_events.json
├── tools/
│   ├── ingest.py            # CLI ingestion tool
│   ├── parser.py            # Shared parsing logic
│   ├── capture.js           # Bookmarklet source
│   └── sample_paste.txt
└── README.md
```