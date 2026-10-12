const assert = require("assert");
const vm = require("vm");
const NativeURL = URL;
const bookmarklet = require("./capture.js");
const source = bookmarklet.slice("javascript:".length);

new Function(source);

async function run(url, cardLinks = []) {
  const parsed = new NativeURL(url);
  const downloads = [];
  const requests = [];
  const state = {};
  const root = {
    id: parsed.pathname.includes("2024-local-events") ? "2024-local-events" :
      parsed.pathname.includes("local-events") ? "local-events" : "locations",
    querySelector: () => cardLinks.length ? {} : null,
    querySelectorAll: () => cardLinks.map(card => ({
      href: card.href,
      innerText: card.text,
      closest: () => card.eventCard ? { className: "local-event" } : null
    }))
  };
  class BlobStub {
    constructor(parts) { this.text = parts.join(""); }
  }
  class URLStub extends NativeURL {
    static createObjectURL(blob) { state.blob = blob; return "blob:test"; }
    static revokeObjectURL() {}
  }
  const context = {
    location: { href: url, hostname: parsed.hostname, pathname: parsed.pathname },
    document: {
      body: { innerText: "captured listing text" },
      querySelectorAll: () => [root],
      createElement: () => ({ click() { downloads.push(this); }, set href(value) { this._href = value; }, set download(value) { this._download = value; } })
    },
    URL: URLStub,
    Blob: BlobStub,
    setTimeout() {},
    Date,
    prompt: () => null,
    alert() {},
    fetch: async (...args) => { requests.push(args); return { ok: true, json: async () => ({ ok: true }) }; }
  };
  await vm.runInNewContext(source, context);
  return { downloads, requests, manifest: state.blob && JSON.parse(state.blob.text) };
}

(async () => {
  const cases = [
    ["https://2021.spaceappschallenge.org/locations/", 2021, "https://2021.spaceappschallenge.org/locations/a/", true],
    ["https://2022.spaceappschallenge.org/locations/", 2022, "https://2022.spaceappschallenge.org/locations/a/", true],
    ["https://www.spaceappschallenge.org/2023/locations/", 2023, "https://www.spaceappschallenge.org/2023/locations/a/", true],
    ["https://www.spaceappschallenge.org/nasa-space-apps-2024/2024-local-events/", 2024, "https://www.spaceappschallenge.org/nasa-space-apps-2024/2024-local-events/a/", true],
    ["https://www.spaceappschallenge.org/2025/local-events/", 2025, "https://www.spaceappschallenge.org/2025/local-events/a/", true],
    ["https://www.spaceappschallenge.org/2026/local-events/", 2026, null, false]
  ];
  for (const [listing, year, detail, hasCard] of cases) {
    const cards = detail ? [{ href: detail, text: "A location\nCountry\n42 Participating", eventCard: hasCard }] : [];
    const result = await run(listing, cards);
    assert.equal(result.downloads.length, 1, listing);
    assert.equal(result.requests.length, 0, "bookmarklet only creates the common manifest");
    assert.equal(result.manifest.eventYear, year);
    assert.equal(result.manifest.sourceUrl, listing);
    assert.equal(result.manifest.text, "captured listing text");
    assert.equal(result.manifest.locationUrls.length, detail ? 1 : 0);
    assert.equal(result.manifest.discoveryStatus, detail ? "links-found" : "no-detail-links-found");
    if (detail && year >= 2023) assert.equal(result.manifest.locationCards[0].text, "A location\nCountry\n42 Participating");
  }
  const detailPage = await run("https://2022.spaceappschallenge.org/locations/universal-event/");
  assert.equal(detailPage.manifest.eventYear, 2022);
  assert.deepEqual(detailPage.manifest.locationUrls, ["https://2022.spaceappschallenge.org/locations/universal-event/"]);
  console.log("PASS: generated bookmarklet emits a common manifest for 2021–2026 and flags empty listings");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
