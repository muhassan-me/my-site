function renderGlobalStats(data) {
  const countries = Object.values(data.countries);
  const totals = countryTotals({ countries: data.countries });
  const count = countries.reduce((sum, locations) => sum + locations.length, 0);
  const participants = Object.values(totals).reduce((sum, country) => sum + country.participants, 0);
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
    number.textContent = "0";
    item.append(name, number);
    host.append(item);
    countUp(number, Number(value));
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
  const rows = Object.keys(data.countries).sort((a, b) => totals[b].participants - totals[a].participants);
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
    metric.textContent = totals[country].participants.toLocaleString();
    const detail = document.createElement("small");
    detail.textContent = `${totals[country].locations} ${t("locations")}`;
    metric.append(detail);
    button.append(rank, name, metric);
    host.append(button);
  });
}

function renderCountry(data, country, search, regionMode) {
  const locations = rankLocations(data.countries[country] || []);
  const total = locations.reduce((sum, item) => sum + (item.participants || 0), 0);
  const regions = data.regions[country] || {};
  const hasRegions = Object.keys(regions).length > 0;
  document.getElementById("country-title").textContent = country;
  document.getElementById("country-eyebrow").textContent = t("countryView");
  document.getElementById("country-total").textContent = `${total.toLocaleString()} ${t("participantsShort")}`;
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
    rank.textContent = String(item.rank);
    const name = document.createElement("td");
    const link = document.createElement("button");
    link.className = "location-link";
    link.type = "button";
    link.dataset.location = item.slug || slugify(item.name);
    link.textContent = item.name;
    name.append(link);
    const place = document.createElement("td");
    place.textContent = hasRegions && regionMode ? (regions[item.name] || item.governorate || "") : (item.governorate || "");
    const participants = document.createElement("td");
    participants.className = "num";
    participants.textContent = (item.participants || 0).toLocaleString();
    const share = document.createElement("td");
    share.className = "num";
    share.textContent = `${total ? ((item.participants || 0) / total * 100).toFixed(1) : "0.0"}%`;
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
    .sort((a, b) => totals[b].participants - totals[a].participants).forEach(name => {
      const option = document.createElement("button");
      option.className = "item";
      option.type = "button";
      option.role = "option";
      option.dataset.country = name;
      const label = document.createElement("span");
      label.textContent = name;
      const count = document.createElement("span");
      count.className = "count";
      count.textContent = totals[name].participants.toLocaleString();
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
  count.textContent = `${(location.participants || 0).toLocaleString()} ${t("participants")}`;
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
  countryName.textContent = country;
  body.append(count, chips, countryName);
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
