function renderGlobalStats(data) {
  const countries = Object.values(data.countries);
  const totals = countryTotals({ countries: data.countries });
  const count = countries.reduce((sum, locations) => sum + locations.length, 0);
  const locationRows = countries.flat();
  const unknownCounts = locationRows.some(location => !Number.isFinite(location.participants)) ||
    data.globalEvents.some(event => !Number.isFinite(event.participants));
  const localParticipants = Object.values(totals).reduce((sum, country) => sum + (country.participants || 0), 0);
  const globalParticipants = data.globalEvents.reduce((sum, event) => sum + (event.participants || 0), 0);
  const participants = unknownCounts ? t("notReported") : localParticipants + globalParticipants;
  const stats = [
    [t("totalParticipants"), participants],
    [t("totalCountries"), countries.length],
    [t("totalLocations"), count]
  ];
  const host = document.getElementById("global-stats");
  host.replaceChildren();
  stats.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "global-stat";
    const name = document.createElement("span");
    name.className = "label";
    name.textContent = label;
    const number = document.createElement("span");
    number.className = "value nums";
    number.dataset.count = value;
    number.textContent = typeof value === "number" ? "0" : value;
    item.append(name, number);
    host.append(item);
    if (typeof value === "number") countUp(number, value);
  });
}

function countUp(element, end) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || end === 0) {
    element.textContent = end.toLocaleString();
    return;
  }
  const start = performance.now();
  const tick = now => {
    const progress = Math.min((now - start) / 800, 1);
    element.textContent = Math.round(end * (1 - Math.pow(1 - progress, 3))).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function renderLeaderboard(data) {
  const host = document.getElementById("leaderboard");
  const totals = countryTotals({ countries: data.countries });
  const rows = Object.keys(data.countries).sort((a, b) => {
    const aTotal = totals[a].participants;
    const bTotal = totals[b].participants;
    if (!Number.isFinite(aTotal) || !Number.isFinite(bTotal)) return Number.isFinite(aTotal) ? -1 : Number.isFinite(bTotal) ? 1 : a.localeCompare(b);
    return bTotal - aTotal;
  });
  host.replaceChildren();
  if (!rows.length) return showEmpty(host, 1);
  rows.forEach((country, index) => {
    const button = document.createElement("button");
    button.className = "leader-row";
    button.type = "button";
    button.dataset.country = country;
    const rank = document.createElement("span");
    rank.className = "leader-rank";
    rank.textContent = String(index + 1).padStart(2, "0");
    const name = document.createElement("span");
    name.className = "leader-country";
    name.textContent = country;
    const metric = document.createElement("span");
    metric.className = "leader-metric";
    metric.textContent = Number.isFinite(totals[country].participants) ? totals[country].participants.toLocaleString() : t("notReported");
    const detail = document.createElement("small");
    detail.textContent = `${totals[country].locations} ${t("locations")}`;
    metric.append(detail);
    button.append(rank, name, metric);
    host.append(button);
  });
}

function renderCountry(data, country, search, regionMode) {
  const locations = rankLocations(data.countries[country] || []);
  const hasUnknownCounts = locations.some(item => !Number.isFinite(item.participants));
  const total = locations.reduce((sum, item) => sum + (Number.isFinite(item.participants) ? item.participants : 0), 0);
  const regionKey = Object.keys(data.regions).find(name => name.toLocaleLowerCase() === country.toLocaleLowerCase());
  const regions = regionKey ? data.regions[regionKey] : {};
  const hasRegions = Object.keys(regions).length > 0;
  document.getElementById("country-title").textContent = country;
  document.getElementById("country-eyebrow").textContent = t("countryView");
  document.getElementById("country-total").textContent = `${hasUnknownCounts ? t("partialTotal") : total.toLocaleString()} ${t("participantsShort")}`;
  document.getElementById("country-provenance").textContent = data.provenanceLabel || "";
  document.getElementById("region-toggle").classList.toggle("hidden", !hasRegions);
  document.getElementById("region-toggle").textContent = regionMode ? t("showGovernorates") : t("showRegions");
  document.getElementById("th-rank").textContent = t("rank");
  document.getElementById("th-location").textContent = t("location");
  document.getElementById("th-region").textContent = hasRegions && regionMode ? t("region") : t("governorate");
  document.getElementById("th-participants").textContent = t("participants");
  document.getElementById("th-share").textContent = t("share");
  const tbody = document.querySelector("#location-table tbody");
  tbody.replaceChildren();
  const term = search.trim().toLocaleLowerCase();
  const shown = locations.filter(item => `${item.name} ${item.governorate || ""} ${regions[item.name] || ""}`.toLocaleLowerCase().includes(term));
  if (!shown.length) return showEmpty(tbody, 5);
  shown.forEach(item => {
    const row = document.createElement("tr");
    const rank = document.createElement("td");
    rank.className = "rank";
    rank.textContent = item.rank === null ? "-" : String(item.rank);
    const name = document.createElement("td");
    const link = document.createElement("button");
    link.className = "location-link";
    link.type = "button";
    link.dataset.location = getLocationSlug(item, locations);
    link.textContent = item.name;
    name.append(link);
    if (item.eventSite) {
      const site = document.createElement("small");
      site.className = "record-source";
      site.textContent = item.eventSite;
      name.append(site);
    }
    if (item.verification) {
      const source = item.provenance?.find(entry => entry.sourceUrl);
      const sourceLabel = source && /^https?:\/\//i.test(source.sourceUrl) ? document.createElement("a") : document.createElement("small");
      sourceLabel.className = "record-source";
      sourceLabel.textContent = source ? source.sourceUrl : t(item.verification === "incomplete" ? "workbookIncompleteShort" : "sourceCapturedShort");
      if (sourceLabel.tagName === "A") {
        sourceLabel.href = source.sourceUrl;
        sourceLabel.target = "_blank";
        sourceLabel.rel = "noopener noreferrer";
      }
      name.append(sourceLabel);
    }
    const place = document.createElement("td");
    place.textContent = hasRegions && regionMode ? (regions[item.name] || item.governorate || "") : (item.governorate || "");
    const participants = document.createElement("td");
    participants.className = "num";
    participants.textContent = Number.isFinite(item.participants) ? item.participants.toLocaleString() : t("notReported");
    const share = document.createElement("td");
    share.className = "num";
    share.textContent = Number.isFinite(item.participants) && total && !hasUnknownCounts ? `${(item.participants / total * 100).toFixed(1)}%` : t("notReported");
    row.append(rank, name, place, participants, share);
    tbody.append(row);
  });
}

function renderCountryOptions(data, query) {
  const host = document.getElementById("country-options");
  const totals = countryTotals({ countries: data.countries });
  const term = query.trim().toLocaleLowerCase();
  host.replaceChildren();
  Object.keys(data.countries).filter(name => name.toLocaleLowerCase().includes(term))
    .sort((a, b) => {
      const aTotal = totals[a].participants;
      const bTotal = totals[b].participants;
      if (!Number.isFinite(aTotal) || !Number.isFinite(bTotal)) return Number.isFinite(aTotal) ? -1 : Number.isFinite(bTotal) ? 1 : a.localeCompare(b);
      return bTotal - aTotal;
    }).forEach(name => {
      const option = document.createElement("button");
      option.className = "item";
      option.type = "button";
      option.role = "option";
      option.dataset.country = name;
      const label = document.createElement("span");
      label.textContent = name;
      const count = document.createElement("span");
      count.className = "count";
      count.textContent = Number.isFinite(totals[name].participants) ? totals[name].participants.toLocaleString() : t("notReported");
      option.append(label, count);
      host.append(option);
    });
  if (!host.childElementCount) showEmpty(host, 1);
}

function renderDrawer(location, country) {
  document.getElementById("drawer-title").textContent = location.name;
  const body = document.getElementById("drawer-body");
  body.replaceChildren();
  const count = document.createElement("p");
  count.className = "drawer-stat nums";
  count.textContent = `${Number.isFinite(location.participants) ? location.participants.toLocaleString() : t("notReported")} ${t("participants")}`;
  const chips = document.createElement("div");
  chips.className = "drawer-chips";
  [["virtual", location.virtual], ["inPerson", location.inPerson], ["accepting", location.accepting]].forEach(([key, active]) => {
    if (!active) return;
    const chip = document.createElement("span");
    chip.className = `chip-text ${key === "inPerson" ? "inperson" : key}`;
    chip.textContent = t(key);
    chips.append(chip);
  });
  const countryName = document.createElement("p");
  countryName.className = "drawer-country";
  countryName.textContent = `${location.city || ""}${location.city ? ", " : ""}${country}`;
  body.append(count);
  if (Number.isFinite(location.teams)) {
    const teams = document.createElement("p");
    teams.className = "drawer-country";
    teams.textContent = `${location.teams.toLocaleString()} ${t("teams")}`;
    body.append(teams);
  }
  body.append(chips, countryName);
  const source = location.provenance?.find(entry => entry.sourceUrl);
  if (source && /^https?:\/\//i.test(source.sourceUrl)) {
    const sourceLink = document.createElement("a");
    sourceLink.className = "record-source";
    sourceLink.href = source.sourceUrl;
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    sourceLink.textContent = source.sourceUrl;
    body.append(sourceLink);
  }
}

function showEmpty(host, columns) {
  if (host.tagName === "TBODY") {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns;
    cell.className = "empty-cell";
    cell.textContent = t("noResults");
    row.append(cell);
    host.append(row);
    return;
  }
  const empty = document.createElement("p");
  empty.className = "empty-cell";
  empty.textContent = t("noResults");
  host.append(empty);
}
