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

### Using Bookmarklet (from Browser)

1.  Create a bookmark with this URL (after replacing `YOUR_BOOKMARKLET_CODE_HERE`):
    ```
    javascript:(function(){fetch('https://www.spaceappschallenge.org/2026/local-events/').then(r=>r.text()).then(t=>{const lines=t.splitlines();const egyptLines=[];let inEgypt=false;for(const line of lines){if(line.trim().toLowerCase()==='egypt'){inEgypt=true;continue;}if(inEgypt&&line.trim()===''){if(egyptLines.length>=3){break;}continue;}if(inEgypt){egyptLines.push(line);}}if(egyptLines.length<3){alert('Could not parse Egypt data');return;}const location=egyptLines[0].trim();const participatingLine=egyptLines[1];const match=participatingLine.match(/[\\d,]+/);if(!match){alert('Could not find participant count');return;}const participants=parseInt(match[0].replace(/,/g,''));const badges={virtual:false,inPerson:false,accepting:false};for(let i=2;i<egyptLines.length;i++){const line=egyptLines[i].toLowerCase();if(!badges.virtual&&line.includes('virtual'))badges.virtual=true;else if(!badges.inPerson&&line.includes('in-person'))badges.inPerson=true;else if(!badges.accepting&&line.includes('accepting')&&line.includes('participants'))badges.accepting=true;}const data={capturedAt:new Date().toISOString(),locations:[{slug:location.toLowerCase().replace(/[^a-z0-9]+/g,'-'),name:location,participants:participants,virtual:badges.virtual,inPerson:badges.inPerson,accepting:badges.accepting,localLead:false}]};const encoded=btoa(unescape(encodeURIComponent(JSON.stringify(data))));window.location='http://127.0.0.1:8080/#import='+encoded;});})()
    ```
    Note: For simplicity, the above bookmarklet is a basic example. A more robust version would parse the full page structure.

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
│   ├── ingest_lib.py        # Shared ingestion logic
│   └── sample_paste.txt
└── README.md
```