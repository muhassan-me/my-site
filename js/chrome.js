function applyStrings() {
  document.title = t("brand");
  const labels = {
    "brand-name": "brand", "hero-eyebrow": "brand", "hero-title": "heroTitle", "hero-subtitle": "heroSubtitle",
    "overview-title": "overview", "country-label": "selectCountry", "location-search-label": "searchLocations",
    "edition-label": "edition", "chart-title": "yearlyComparison"
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
