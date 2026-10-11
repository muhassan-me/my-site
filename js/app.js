let appData = null;
let viewData = null;
let activeCountry = "";
let selectedEdition = "current";
let language = "ar";
let regionMode = false;
let appBound = false;
let archivePollerStarted = false;

async function initApp() {
  try {
    const loaded = await loadAll();
    appData = { ...loaded, ...normalizeCurrent(loaded.latest) };
    selectedEdition = populateEditionOptions(appData, selectedEdition);
    if (!appBound) bindApp();
    renderApp();
    if (!archivePollerStarted) startArchivePolling();
  } catch (error) {
    showError(`${t("error")} ${error.message}`);
  }
}

function bindApp() {
  appBound = true;
  document.getElementById("language-toggle").addEventListener("click", () => {
    language = language === "ar" ? "en" : "ar";
    renderApp();
  });
  document.getElementById("edition-select").addEventListener("change", event => {
    selectedEdition = event.target.value;
    renderApp();
  });
  document.getElementById("country-search").addEventListener("focus", openCountryOptions);
  document.getElementById("country-search").addEventListener("input", event => {
    renderCountryOptions(viewData, event.target.value);
    setOptionsOpen(true);
  });
  document.getElementById("country-options").addEventListener("click", event => {
    const option = event.target.closest("[data-country]");
    if (option) navigateCountry(option.dataset.country);
  });
  document.getElementById("leaderboard").addEventListener("click", event => {
    const row = event.target.closest("[data-country]");
    if (row) navigateCountry(row.dataset.country);
  });
  document.getElementById("back-overview").addEventListener("click", () => { location.hash = "#/"; });
  document.getElementById("location-search").addEventListener("input", renderApp);
  document.getElementById("region-toggle").addEventListener("click", () => {
    regionMode = !regionMode;
    renderApp();
  });
  document.querySelector("#location-table tbody").addEventListener("click", event => {
    const link = event.target.closest("[data-location]");
    if (link) location.hash = `#/location/${slugify(activeCountry)}/${link.dataset.location}`;
  });
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("drawer-scrim").addEventListener("click", closeDrawer);
  document.getElementById("country-search").addEventListener("keydown", event => {
    if (event.key === "Escape") setOptionsOpen(false);
    if (event.key === "Enter") {
      const first = document.querySelector("#country-options [data-country]");
      if (first) navigateCountry(first.dataset.country);
    }
  });
  document.addEventListener("click", event => {
    if (!event.target.closest(".country-picker")) setOptionsOpen(false);
  });
  window.addEventListener("hashchange", renderApp);
  window.addEventListener("popstate", renderApp);
}

function renderApp() {
  if (!appData) return;
  setLang(language);
  applyStrings();
  viewData = selectedEdition === "current" ? {
    ...appData,
    available: true,
    imports: 0,
    provenanceLabel: t("currentData")
  } : {
    ...appData,
    ...resolveEdition(appData, selectedEdition),
    provenanceLabel: editionProvenance(selectedEdition)
  };
  document.getElementById("edition-select").value = selectedEdition;
  document.getElementById("edition-status").textContent = editionStatus(viewData, selectedEdition);
  renderGlobalStats(viewData);
  renderLeaderboard(viewData);
  renderGlobalEvents(viewData);
  renderUnverified(viewData);
  renderEditionChart(appData);
  renderCountryOptions(viewData, "");

  const hasCountries = Object.keys(viewData.countries).length > 0;
  renderEmptyOverview(selectedEdition !== "current" && !hasCountries);

  const route = location.hash.replace(/^#\/?/, "").split("/");
  let country = "";
  let locationSlug = "";
  if (route[0] === "country") country = findCountry(route[1], viewData);
  if (route[0] === "location") {
    const qualifiedCountry = route.length > 2 ? findCountry(route[1], viewData) : "";
    locationSlug = route.length > 2 ? route[2] : (route[1] || "");
    for (const [name, locations] of Object.entries(viewData.countries)) {
      const match = locations.find(item => getLocationSlug(item, locations) === locationSlug);
      if (match && (!qualifiedCountry || qualifiedCountry === name)) { country = name; break; }
    }
  }
  activeCountry = country;
  document.getElementById("overview-section").classList.toggle("hidden", Boolean(country));
  document.getElementById("country-section").classList.toggle("hidden", !country);
  document.getElementById("back-overview").classList.toggle("hidden", !country);
  document.getElementById("country-search").value = country;
  setOptionsOpen(false);
  if (!country) closeDrawer(false);
  if (country) {
    renderCountry(viewData, country, document.getElementById("location-search").value, regionMode);
    if (locationSlug) openLocation(locationSlug, country);
    else closeDrawer(false);
  }
  document.getElementById("footer-copy").textContent = selectedEdition === "current" ? t("footer") : t("editionFooter");
  document.getElementById("footer-date").textContent = selectedEdition === "current" ?
    new Date(appData.latest.capturedAt || Date.now()).toLocaleDateString(language === "ar" ? "ar-EG" : "en-US") : selectedEdition;
}

function findCountry(slug, data = viewData) {
  return Object.keys(data.countries).find(name => slugify(name) === slug) || "";
}

function navigateCountry(country) {
  const regionKey = Object.keys(appData.regions).find(name => name.toLocaleLowerCase() === country.toLocaleLowerCase());
  regionMode = Boolean(regionKey && Object.keys(appData.regions[regionKey]).length);
  document.getElementById("location-search").value = "";
  location.hash = `#/country/${slugify(country)}`;
}

function openCountryOptions() {
  renderCountryOptions(viewData, document.getElementById("country-search").value);
  setOptionsOpen(true);
}

function setOptionsOpen(open) {
  const list = document.getElementById("country-options");
  list.classList.toggle("open", open);
  document.getElementById("country-search").setAttribute("aria-expanded", String(open));
}

function openLocation(slug, country) {
  const location = viewData.countries[country].find(item => (item.slug || slugify(item.name)) === slug);
  if (!location) return;
  renderDrawer(location, country);
  document.getElementById("location-drawer").classList.add("open");
  document.getElementById("location-drawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawer-scrim").classList.add("open");
}

function closeDrawer(updateRoute = true) {
  document.getElementById("location-drawer").classList.remove("open");
  document.getElementById("location-drawer").setAttribute("aria-hidden", "true");
  document.getElementById("drawer-scrim").classList.remove("open");
  if (updateRoute && location.hash.includes("/location/")) location.hash = `#/country/${slugify(activeCountry)}`;
}

function startArchivePolling() {
  archivePollerStarted = true;
  let signature = JSON.stringify(appData.archive);
  window.setInterval(async () => {
    try {
      const response = await fetch(`data/archive.json?check=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      const archive = await response.json();
      const nextSignature = JSON.stringify(archive);
      if (nextSignature === signature) return;
      signature = nextSignature;
      const loaded = await loadAll();
      appData = { ...loaded, ...normalizeCurrent(loaded.latest) };
      selectedEdition = populateEditionOptions(appData, selectedEdition);
      renderApp();
    } catch (error) {
      showError(`${t("error")} ${error.message}`);
    }
  }, 10000);
}

function showError(message) {
  const notice = document.getElementById("notice");
  if (notice) notice.textContent = message;
}

function showSuccess(message) {
  const notice = document.getElementById("notice");
  if (!notice) return;
  notice.textContent = message;
  setTimeout(() => { if (notice.textContent === message) notice.textContent = ""; }, 7000);
}
