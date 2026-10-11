let importHandled = false;

function handleImportHash() {
  if (importHandled) return;
  importHandled = true;
  const hash = window.location.hash;
  if (!hash.startsWith("#import=")) return;
  try {
    const encoded = hash.slice(8);
    const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
    const importData = JSON.parse(new TextDecoder("utf-8").decode(bytes));
    const sourceUrl = importData.sourceUrl || prompt("Source event page URL:", "");
    if (!sourceUrl) return;
    const eventYear = Number(importData.eventYear || detectImportYear(sourceUrl) || prompt("Event edition year (2021 or later):", ""));
    if (!Number.isInteger(eventYear) || eventYear < 2021 || eventYear > new Date().getFullYear()) {
      showError("Import failed: a valid event year is required.");
      return;
    }
    const text = typeof importData.text === "string" ? importData.text : JSON.stringify(importData);
    const records = Array.isArray(importData.records) ? importData.records : legacyRecords(importData);
    if (!text || (!records.length && !importData.text)) {
      showError("Import failed: no captured page text or location records found.");
      return;
    }
    const payload = {
      eventYear,
      sourceUrl,
      capturedAt: importData.capturedAt || new Date().toISOString(),
      text,
      globalEvents: Array.isArray(importData.globalEvents) ? importData.globalEvents : [],
      unverified: Array.isArray(importData.unverified) ? importData.unverified : []
    };
    if (records.length || !importData.text) payload.records = records;
    history.replaceState(null, "", window.location.pathname + window.location.search);
    fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Import": "1" },
      body: JSON.stringify(payload)
    }).then(async response => {
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || `Server returned ${response.status}`);
      showSuccess(`${result.duplicate ? "Already imported" : "Imported"} edition ${result.eventYear}: ${result.records} records.`);
      initApp();
    }).catch(error => showError(`Import failed: ${error.message}`));
  } catch (error) {
    showError(`Import failed: ${error.message}`);
  }
}

function detectImportYear(sourceUrl) {
  try {
    const parsed = new URL(sourceUrl);
    const firstHostPart = parsed.hostname.split(".")[0];
    if (firstHostPart === "2021" || firstHostPart === "2022") return Number(firstHostPart);
    const segments = parsed.pathname.split("/").filter(Boolean);
    for (const segment of segments) {
      const year = Number(segment.startsWith("nasa-space-apps-") ? segment.slice(16) : segment.endsWith("-local-events") ? segment.slice(0, -13) : segment);
      if (Number.isInteger(year) && year >= 2021 && year <= new Date().getFullYear()) return year;
    }
  } catch (error) {
    return null;
  }
  return null;
}

function legacyRecords(importData) {
  const records = [];
  if (Array.isArray(importData.locations)) {
    importData.locations.forEach(location => {
      if (!location || typeof location !== "object" || !location.name) return;
      records.push({
        locationName: location.name,
        country: location.country || null,
        city: location.city || null,
        eventSite: location.eventSite || null,
        participants: Number.isFinite(location.participants) ? location.participants : null,
        teams: Number.isFinite(location.teams) ? location.teams : null,
        sourceUrl: importData.sourceUrl
      });
    });
  }
  if (importData.countries && typeof importData.countries === "object") {
    Object.entries(importData.countries).forEach(([country, locations]) => {
      if (!Array.isArray(locations)) return;
      locations.forEach(location => {
        if (!location || typeof location !== "object" || !location.name) return;
        records.push({
          locationName: location.locationName || location.name,
          country: country.toLowerCase() === "universal event" ? null : country,
          city: location.city || location.name,
          eventSite: location.eventSite || null,
          participants: Number.isFinite(location.participants) ? location.participants : null,
          teams: Number.isFinite(location.teams) ? location.teams : null,
          sourceUrl: importData.sourceUrl
        });
      });
    });
  }
  return records;
}
