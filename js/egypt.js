function initEgyptHistory(data) {
  const select = document.getElementById("year-select");
  const years = Object.keys(data.past?.years || {}).sort((a, b) => Number(b) - Number(a));
  select.replaceChildren();
  years.forEach(year => {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = year;
    select.append(option);
  });
  select.addEventListener("change", () => renderPastYear(data, select.value));
  renderPastYear(data, select.value);
  renderYearChart(data);
}

function renderPastYear(data, year) {
  const entry = data.past?.years?.[year];
  const tbody = document.querySelector("#past-table tbody");
  tbody.replaceChildren();
  if (!entry) return showEmpty(tbody, 4);
  const locations = rankLocations(entry.locations || []);
  const regionMap = data.regions.Egypt || {};
  document.getElementById("past-th-rank").textContent = t("rank");
  document.getElementById("past-th-location").textContent = t("location");
  document.getElementById("past-th-region").textContent = t("governorate");
  document.getElementById("past-th-participants").textContent = t("participants");
  locations.forEach(location => {
    const row = document.createElement("tr");
    [location.rank, location.name, location.governorate || regionMap[location.name] || "", (location.participants || 0).toLocaleString()].forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 0) cell.className = "rank";
      if (index === 3) cell.className = "num";
      row.append(cell);
    });
    tbody.append(row);
  });
}

function renderYearChart(data) {
  const host = document.getElementById("comparison-chart");
  const entries = Object.entries(data.past?.years || {}).map(([year, value]) => [year, value.total || 0]);
  const egypt = data.countries.Egypt || [];
  entries.push(["2026", egypt.reduce((sum, item) => sum + (item.participants || 0), 0)]);
  entries.sort((a, b) => Number(a[0]) - Number(b[0]));
  const max = Math.max(1, ...entries.map(entry => entry[1]));
  host.replaceChildren();
  host.setAttribute("aria-label", t("yearlyComparison"));
  entries.forEach(([year, value]) => {
    const row = document.createElement("div");
    row.className = `chart-row${year === "2026" ? " current" : ""}`;
    const label = document.createElement("span");
    label.className = "chart-year";
    label.textContent = year === "2026" ? `${year} · ${t("currentYear")}` : year;
    const track = document.createElement("span");
    track.className = "chart-track";
    const bar = document.createElement("span");
    bar.className = "chart-bar";
    bar.style.width = `${value / max * 100}%`;
    track.append(bar);
    const total = document.createElement("span");
    total.className = "chart-value";
    total.textContent = value.toLocaleString();
    row.append(label, track, total);
    host.append(row);
  });
}
