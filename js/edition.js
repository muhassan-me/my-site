function renderGlobalEvents(data) {
  renderSimpleRecords("global-events-section", "global-events", "globalEvents", data.globalEvents,
    event => event.name || "Universal Event", event => recordDetails(event, event.description || ""));
}

function renderUnverified(data) {
  renderSimpleRecords("unverified-section", "unverified-list", "unverified", data.unverified,
    record => record.name || record.locationName || record.city || t("unknownLocation"),
    record => recordDetails(record, record.reasonKey ? t(record.reasonKey) : record.reason || t("unverified")));
}

function recordDetails(record, detail) {
  const values = [detail];
  if (Number.isFinite(record.teams)) values.push(`${record.teams.toLocaleString()} ${t("teams")}`);
  return values.filter(Boolean).join(" · ");
}

function renderSimpleRecords(sectionId, hostId, titleKey, records, nameOf, detailOf) {
  const section = document.getElementById(sectionId);
  const host = document.getElementById(hostId);
  host.replaceChildren();
  section.classList.toggle("hidden", !records.length);
  document.getElementById(`${hostId}-title`).textContent = t(titleKey);
  records.forEach(record => {
    const row = document.createElement("div");
    row.className = "leader-row global-event-row";
    [nameOf(record), detailOf(record), Number.isFinite(record.participants) ? record.participants.toLocaleString() : t("notReported")].forEach((value, index) => {
      const cell = document.createElement("span");
      cell.className = index === 0 ? "leader-country" : index === 2 ? "leader-metric" : "leader-rank";
      cell.textContent = value;
      row.append(cell);
    });
    host.append(row);
  });
}

function renderEditionChart(data) {
  const host = document.getElementById("comparison-chart");
  const rows = editionYears(data).map(year => {
    const edition = resolveEdition(data, year);
    const locations = Object.values(edition.countries).flat();
    const unknown = locations.some(location => !Number.isFinite(location.participants)) ||
      edition.globalEvents.some(event => !Number.isFinite(event.participants));
    const total = locations.reduce((sum, location) => sum + (Number.isFinite(location.participants) ? location.participants : 0), 0) +
      edition.globalEvents.reduce((sum, event) => sum + (Number.isFinite(event.participants) ? event.participants : 0), 0);
    return { year, available: edition.available, total, unknown };
  });
  const max = Math.max(1, ...rows.filter(row => row.available && !row.unknown).map(row => row.total));
  host.replaceChildren();
  host.setAttribute("aria-label", t("yearlyComparison"));
  rows.forEach(({ year, available, total, unknown }) => {
    const row = document.createElement("div");
    row.className = `chart-row${available && year === String(new Date().getFullYear()) ? " current" : ""}`;
    if (!available) row.classList.add("unavailable");
    const label = document.createElement("span");
    label.className = "chart-year";
    label.textContent = year;
    const track = document.createElement("span");
    track.className = "chart-track";
    if (available && !unknown) {
      const bar = document.createElement("span");
      bar.className = "chart-bar";
      bar.style.width = `${total / max * 100}%`;
      track.append(bar);
    }
    const value = document.createElement("span");
    value.className = "chart-value";
    value.textContent = !available ? t("unavailable") : unknown ? t("partialTotal") : total.toLocaleString();
    row.append(label, track, value);
    host.append(row);
  });
}

function populateEditionOptions(appData, selectedEdition) {
  const select = document.getElementById("edition-select");
  select.replaceChildren();
  const current = document.createElement("option");
  current.value = "current";
  current.textContent = t("latest");
  select.append(current);
  editionYears(appData).forEach(year => {
    const edition = resolveEdition(appData, year);
    const option = document.createElement("option");
    option.value = year;
    option.textContent = edition.available ? `${year}${edition.imports ? "" : ` · ${t("incomplete")}`}` : `${year} · ${t("unavailable")}`;
    select.append(option);
  });
  select.value = [...select.options].some(option => option.value === selectedEdition) ? selectedEdition : "current";
  return select.value;
}

function editionProvenance(data, year) {
  const edition = resolveEdition(data, year);
  if (!edition.available) return t("unavailable");
  return edition.imports ? t("sourceCaptured") : t("workbookIncomplete");
}

function editionStatus(data, year) {
  if (year === "current") return t("currentData");
  return editionProvenance(data, year);
}

function renderEmptyOverview(show) {
  const empty = document.getElementById("overview-empty");
  empty.classList.toggle("hidden", !show);
  empty.textContent = t("historicalEmpty");
}
