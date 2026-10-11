// Data loading and helpers
async function loadAll() {
  const [latest, history, regions, past] = await Promise.all([
    fetch("data/latest.json").then(r => r.json()),
    fetch("data/history.json").then(r => r.json()),
    fetch("data/regions.json").then(r => r.json()),
    fetch("data/past_events.json").then(r => r.json()).catch(() => null)
  ]);
  return { latest, history, regions, past };
}

function rankLocations(list) {
  const sorted = [...list].sort((a, b) => (b.participants || 0) - (a.participants || 0));
  let rank = 1;
  let prev = null;
  let same = 0;
  return sorted.map((loc, i) => {
    const p = loc.participants || 0;
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
  const totals = {};
  for (const country in latest.countries) {
    const locs = latest.countries[country];
    totals[country] = {
      locations: locs.length,
      participants: locs.reduce((s, l) => s + (l.participants || 0), 0)
    };
  }
  return totals;
}

function slugify(name) {
  return name.toString().toLowerCase().trim()
    .replace(/\s+/g, "-")
    .replace(/[^\w\-]+/g, "")
    .replace(/\-\-+/g, "-");
}

function groupByRegion(list, regionsForCountry) {
  if (!regionsForCountry) return { Ungrouped: list };
  const groups = {};
  for (const loc of list) {
    const region = regionsForCountry[loc.name] || "Ungrouped";
    if (!groups[region]) groups[region] = [];
    groups[region].push(loc);
  }
  return groups;
}