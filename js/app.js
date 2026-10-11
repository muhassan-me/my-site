let appData = null;
let activeCountry = "";
let regionMode = true;
let language = "ar";
let egyptReady = false;
let appBound = false;

async function initApp() {
  try {
    const loaded = await loadAll();
    appData = { ...loaded, countries: normalizeCountries(loaded.latest) };
    if (!appBound) bindApp();
    if (!egyptReady && appData.past) {
      initEgyptHistory(appData);
      egyptReady = true;
    } else if (egyptReady && appData.past) {
      renderPastYear(appData, document.getElementById("year-select").value);
      renderYearChart(appData);
    }
    renderApp();
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
  document.getElementById("country-search").addEventListener("focus", openCountryOptions);
  document.getElementById("country-search").addEventListener("input", event => {
    renderCountryOptions(appData, event.target.value);
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
    if (link) location.hash = `#/location/${link.dataset.location}`;
  });
  document.getElementById("language-toggle").addEventListener("click", renderPastIfShown);
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
  renderGlobalStats(appData);
  renderLeaderboard(appData);
  renderCountryOptions(appData, "");
  const route = location.hash.replace(/^#\/?/, "").split("/");
  let locationSlug = "";
  let country = "";
  if (route[0] === "country") country = findCountry(route[1]);
  if (route[0] === "location") {
    locationSlug = route[1] || "";
    for (const [name, locations] of Object.entries(appData.countries)) {
      const match = locations.find(item => (item.slug || slugify(item.name)) === locationSlug);
      if (match) { country = name; break; }
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
    const search = document.getElementById("location-search");
    renderCountry(appData, country, search.value, regionMode);
    const egypt = country === "Egypt";
    document.getElementById("egypt-history").classList.toggle("hidden", !egypt);
    if (egypt) renderPastYear(appData, document.getElementById("year-select").value);
    if (locationSlug) openLocation(locationSlug, country);
    else closeDrawer(false);
  }
  document.getElementById("footer-date").textContent = new Date(appData.latest.capturedAt || Date.now()).toLocaleDateString(language === "ar" ? "ar-EG" : "en-US");
}

function applyStrings() {
  document.title = t("brand");
  const labels = {
    "brand-name": "brand", "hero-eyebrow": "brand", "hero-title": "heroTitle", "hero-subtitle": "heroSubtitle",
    "overview-title": "overview", "country-label": "selectCountry", "location-search-label": "searchLocations",
    "past-title": "pastYears", "year-label": "chooseYear", "chart-title": "yearlyComparison", "footer-copy": "footer"
  };
  Object.entries(labels).forEach(([id, key]) => { document.getElementById(id).textContent = t(key); });
  document.getElementById("country-search").placeholder = t("selectCountry");
  document.getElementById("location-search").placeholder = t("searchLocations");
  document.getElementById("language-toggle").textContent = t("languageToggle");
  document.getElementById("back-overview").textContent = t("back");
  document.getElementById("drawer-title").textContent = t("detailDrawer");
  document.getElementById("drawer-close").innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
  document.getElementById("drawer-close").setAttribute("aria-label", t("close"));
  document.getElementById("drawer-scrim").setAttribute("aria-label", t("close"));
  document.querySelector(".topbar").setAttribute("aria-label", t("brand"));
}

function findCountry(slug) {
  return Object.keys(appData.countries).find(name => slugify(name) === slug) || "";
}

function navigateCountry(country) {
  regionMode = Boolean(Object.keys(appData.regions[country] || {}).length);
  document.getElementById("location-search").value = "";
  location.hash = `#/country/${slugify(country)}`;
}

function openCountryOptions() {
  renderCountryOptions(appData, document.getElementById("country-search").value);
  setOptionsOpen(true);
}

function setOptionsOpen(open) {
  const list = document.getElementById("country-options");
  list.classList.toggle("open", open);
  document.getElementById("country-search").setAttribute("aria-expanded", String(open));
}

function openLocation(slug, country) {
  const location = appData.countries[country].find(item => (item.slug || slugify(item.name)) === slug);
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

function renderPastIfShown() {
  if (activeCountry === "Egypt" && appData) {
    renderPastYear(appData, document.getElementById("year-select").value);
    renderYearChart(appData);
  }
}

function showError(message) {
  const notice = document.getElementById("notice");
  if (notice) notice.textContent = message;
}

function showSuccess(message) {
  const notice = document.getElementById("notice");
  if (!notice) return;
  notice.textContent = message;
  setTimeout(() => { if (notice.textContent === message) notice.textContent = ""; }, 5000);
}
