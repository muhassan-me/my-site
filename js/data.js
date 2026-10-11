// Data loading and helpers
async function loadAll() {
  const localJson = path => fetch(`${path}?v=${Date.now()}`, { cache: "no-store" }).then(response => {
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  });
  const [latest, history, regions, past, archive] = await Promise.all([
    localJson("data/latest.json"),
    localJson("data/history.json"),
    localJson("data/regions.json"),
    localJson("data/past_events.json").catch(() => null),
    localJson("data/archive.json").catch(() => ({ schemaVersion: 1, editions: {} }))
  ]);
  return { latest, history, regions, past, archive };
}

function normalizeCurrent(latest) {
  const source = latest.countries && typeof latest.countries === "object" ? latest.countries : {};
  const universal = source["Universal Event"] || [];
  const inverted = universal.some(location => /anywhere|world/i.test(location.name || ""));
  const countries = {};
  const countryNames = new Map();
  const globalEvents = Array.isArray(latest.globalEvents) ? [...latest.globalEvents] : [];
  const unverified = [];

  if (inverted) {
    for (const [city, locations] of Object.entries(source)) {
      for (const location of locations || []) {
        if (city === "Universal Event") {
          globalEvents.push({ ...location, name: "Universal Event", description: location.name || "", scope: "global", eventType: "global" });
          continue;
        }
        const rawCountry = String(location.country || location.name || "").trim();
        const country = canonicalCountryName(rawCountry, countryNames);
        if (!country || /anywhere|world/i.test(country)) {
          unverified.push({ name: city, participants: location.participants || 0, reasonKey: "unverifiedCountry" });
          continue;
        }
        if (!countries[country]) countries[country] = [];
        countries[country].push({ ...location, name: city, city, country, scope: "local",
          eventType: location.virtual && location.inPerson ? "hybrid" : location.inPerson ? "in-person" : location.virtual ? "virtual" : "unknown" });
      }
    }
    return { countries: dedupeCountries(countries), globalEvents, unverified };
  }

  if (latest.locations) {
    latest.locations.forEach(location => unverified.push({
      ...location,
      reasonKey: "unverifiedCountry"
    }));
    return { countries, globalEvents, unverified };
  }

  for (const [country, locations] of Object.entries(source)) {
    if (country === "Universal Event") {
      (locations || []).forEach(location => globalEvents.push({
        ...location,
        name: "Universal Event",
        description: location.description || location.name || "",
        scope: "global",
        eventType: "global"
      }));
      continue;
    }
    const canonical = canonicalCountryName(country, countryNames);
    countries[canonical] ||= [];
    countries[canonical].push(
      ...(locations || []).map(location => ({
        ...location,
        country: canonical,
        scope: "local",
        eventType: location.eventType || (location.virtual && location.inPerson ? "hybrid" : location.inPerson ? "in-person" : location.virtual ? "virtual" : "unknown")
      }))
    );
  }
  return { countries: dedupeCountries(countries), globalEvents, unverified };
}

function getLocationSlug(location, siblings) {
  const base = location.slug || slugify(location.name);
  const duplicate = siblings.filter(item => (item.slug || slugify(item.name)) === base).length > 1;
  return duplicate && location.eventSite ? `${base}-${slugify(location.eventSite)}` : base;
}

function rankLocations(list) {
  const sorted = [...list].sort((a, b) => {
    const aKnown = Number.isFinite(a.participants);
    const bKnown = Number.isFinite(b.participants);
    if (!aKnown || !bKnown) return aKnown ? -1 : bKnown ? 1 : 0;
    return b.participants - a.participants;
  });
  let rank = 1;
  let prev = null;
  let same = 0;
  return sorted.map(loc => {
    if (!Number.isFinite(loc.participants)) return { ...loc, rank: null, sameRank: false };
    const p = loc.participants;
    if (prev !== null && p !== prev) {
      rank += same;
      same = 0;
    }
    if (prev !== null && p === prev) {
      same += 1;
    } else {
      same = 1;
    }
    prev = p;
    return { ...loc, rank, sameRank: same > 1 };
  });
}

function countryTotals(latest) {
  return Object.fromEntries(Object.entries(latest.countries).map(([country, locations]) => [country, {
    locations: locations.length,
    participants: locations.every(location => Number.isFinite(location.participants)) ?
      locations.reduce((sum, location) => sum + location.participants, 0) : null
  }]));
}

function slugify(name) { return name.toString().toLowerCase().trim().replace(/\s+/g, "-").replace(/[^\w\-]+/g, "").replace(/\-\-+/g, "-"); }
