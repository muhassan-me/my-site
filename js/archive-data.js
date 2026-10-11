function canonicalCountryName(country, names) {
  const normalized = country.toLocaleLowerCase();
  if (!names.has(normalized)) names.set(normalized, country);
  return names.get(normalized);
}

function dedupeCountries(countries) {
  const result = {};
  for (const [country, locations] of Object.entries(countries)) {
    const unique = new Map();
    for (const location of locations) {
      const identity = JSON.stringify([
        String(location.slug || location.name || "").trim().toLocaleLowerCase(),
        String(location.eventSite || "").trim().toLocaleLowerCase()
      ]);
      unique.set(identity, location);
    }
    result[country] = [...unique.values()];
  }
  return result;
}

function editionYears(data) {
  const currentYear = new Date().getFullYear();
  const years = new Set(Object.keys(data.past?.years || {}));
  Object.keys(data.archive?.editions || {}).forEach(year => years.add(year));
  for (let year = 2023; year <= currentYear; year += 1) years.add(String(year));
  return [...years].sort((a, b) => Number(a) - Number(b));
}

function resolveEdition(data, year) {
  const records = new Map();
  const globalEvents = [];
  const unverified = [];
  const legacy = data.past?.years?.[year];
  if (legacy) {
    for (const location of legacy.locations || []) {
      mergeEditionRecord(records, {
        country: "Egypt",
        city: location.name,
        eventSite: null,
        name: location.name,
        participants: location.participants || 0,
        governorate: location.governorate,
        provenance: [{ type: "workbook", source: data.past.source || "Past_Local_Events.xlsx" }],
        verification: "incomplete"
      });
    }
  }

  const imports = data.archive?.editions?.[year]?.imports || [];
  for (const page of imports) {
    const provenance = { type: "page", sourceUrl: page.sourceUrl, capturedAt: page.capturedAt };
    for (const record of page.records || []) {
      if (!record.country) {
        unverified.push({ ...record, name: record.locationName || record.city, reasonKey: "unverifiedCountry", provenance: [provenance] });
        continue;
      }
      mergeEditionRecord(records, {
        ...record,
        name: record.locationName || record.city || record.eventSite,
        city: record.city || "",
        provenance: [provenance],
        verification: "captured"
      });
    }
    globalEvents.push(...(page.globalEvents || []).map(event => ({ ...event, provenance: [provenance] })));
    unverified.push(...(page.unverified || []).map(record => ({ ...record, provenance: [provenance] })));
  }
  const uniqueGlobal = dedupeTracked(globalEvents, event => `${event.name}|${event.provenance[0]?.sourceUrl || ""}`);
  const uniqueUnverified = dedupeTracked(unverified, record =>
    `${record.provenance[0]?.sourceUrl || ""}|${record.locationName || record.name || record.city || JSON.stringify(record.sourceLines || [])}`
  );

  const countries = {};
  const countryNames = new Map();
  for (const record of records.values()) {
    const key = record.country.trim().toLocaleLowerCase();
    if (!countryNames.has(key)) countryNames.set(key, record.country);
  }
  for (const record of records.values()) {
    const country = countryNames.get(record.country.trim().toLocaleLowerCase());
    countries[country] ||= [];
    countries[country].push({ ...record, country });
  }
  return { countries, globalEvents: uniqueGlobal, unverified: uniqueUnverified, available: records.size > 0 || uniqueGlobal.length > 0 || uniqueUnverified.length > 0 || imports.length > 0, imports: imports.length };
}

function dedupeTracked(items, keyOf) {
  const merged = new Map();
  for (const item of items) {
    const key = keyOf(item);
    const previous = merged.get(key);
    if (!previous) {
      merged.set(key, item);
      continue;
    }
    const provenance = [...previous.provenance, ...item.provenance];
    const previousTime = Date.parse(previous.provenance[0]?.capturedAt || "") || 0;
    const itemTime = Date.parse(item.provenance[0]?.capturedAt || "") || 0;
    merged.set(key, { ...(itemTime >= previousTime ? item : previous), provenance });
  }
  return [...merged.values()];
}

function mergeEditionRecord(records, incoming) {
  const normalize = value => String(value || "").trim().toLocaleLowerCase();
  const key = JSON.stringify([normalize(incoming.country), normalize(incoming.city), normalize(incoming.eventSite)]);
  const existing = records.get(key);
  if (!existing) {
    records.set(key, incoming);
    return;
  }
  const provenance = [...existing.provenance, ...incoming.provenance];
  const stamp = record => record.provenance.reduce((latest, source) => {
    const time = Date.parse(source.capturedAt || "") || 0;
    return Math.max(latest, time);
  }, 0);
  const existingStamp = stamp(existing);
  const incomingStamp = stamp(incoming);
  const incomingSource = incoming.provenance[0].sourceUrl || "";
  const existingSource = existing.provenance[0].sourceUrl || "";
  const wins = incomingStamp > existingStamp ||
    (incomingStamp === existingStamp && incomingSource.localeCompare(existingSource) > 0);
  records.set(key, { ...(wins ? incoming : existing), provenance });
}
