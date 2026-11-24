(() => {
  "use strict";
  const map = L.map("map", { zoomControl: false, preferCanvas: true }).setView([20, 0], 3);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors", maxZoom: 19, updateWhenIdle: true
  }).addTo(map);
  window.worldMap = map;
  window.mapLayers = new Map();
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  window.showToast = (message) => {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = String(message);
    document.getElementById("toast-region").appendChild(toast);
    window.setTimeout(() => toast.remove(), 4000);
  };
  const addressText = (item) => [
    item.house_number && [item.house_number, item.street].filter(Boolean).join(" "),
    item.area, item.city, item.state, item.postal_code, item.country, item.address
  ].filter(Boolean).join(", ");
  const removeLayers = () => {
    window.mapLayers.forEach((layer) => map.removeLayer(layer));
    window.mapLayers.clear();
  };
  function renderLocation(item) {
    let layer;
    if (item.geometry && typeof item.geometry === "object") {
      layer = L.geoJSON(item.geometry, { style: { color: "#1769aa", weight: 3, fillOpacity: 0.2 } });
    } else {
      const icon = L.divIcon({ className: "map-pin", html: "<span>•</span>", iconSize: [30, 30], iconAnchor: [15, 30] });
      layer = L.marker([item.lat, item.lng], { icon });
    }
    const popup = document.createElement("div");
    popup.className = "location-popup";
    const title = document.createElement("strong"); title.textContent = item.name;
    const address = document.createElement("p"); address.textContent = addressText(item);
    const description = document.createElement("p"); description.textContent = item.description || "";
    popup.append(title, address, description);
    (item.photos || []).forEach((photo) => {
      const image = document.createElement("img");
      image.src = photo.url; image.alt = photo.caption || `Photo of ${item.name}`; image.loading = "lazy";
      popup.append(image);
    });
    layer.bindPopup(popup).addTo(map);
    window.mapLayers.set(item.id, layer);
  }
  const renderMapItems = (items) => {
    removeLayers();
    items.forEach(renderLocation);
    const pins = items.filter((item) => !item.geometry && item.type === "marker").length;
    document.getElementById("statPins").textContent = pins;
    document.getElementById("statStructures").textContent = items.length - pins;
    document.getElementById("statTotal").textContent = items.length;
  };
  window.loadMapLocations = async () => {
    if (!window.currentUser) {
      removeLayers();
      document.getElementById("statPins").textContent = "0";
      document.getElementById("statStructures").textContent = "0";
      document.getElementById("statTotal").textContent = "0";
      return;
    }
    try {
      const result = await WorldMapAPI.getLocations(document.getElementById("category-filter").value);
      renderMapItems(result.items || []);
    } catch (error) { console.error(error); window.showToast(`Unable to load places: ${error.message}`); }
  };
  const locateItem = (item) => {
    map.setView([item.lat, item.lng], Math.max(map.getZoom(), 15));
    window.mapLayers.get(item.id)?.openPopup();
  };
  function addressSummary(item) { return addressText(item) || "Address not provided"; }
  function createSearchResult(item) {
    const button = document.createElement("button");
    button.className = "result-button"; button.type = "button";
    const name = document.createElement("strong"); name.textContent = item.name;
    const detail = document.createElement("span"); detail.textContent = addressSummary(item);
    button.append(name, detail); button.addEventListener("click", () => locateItem(item));
    return button;
  }
  let searchTerm = ""; let searchPage = 1; let searchHasMore = false; let searchResults = [];
  async function runSearch(term, append = false) {
    if (term.length < 2) {
      document.getElementById("search-results").replaceChildren();
      searchResults = []; searchHasMore = false; searchTerm = term; return;
    }
    if (!append) { searchTerm = term; searchPage = 1; searchResults = []; }
    const container = document.getElementById("search-results");
    if (!append) container.textContent = "Searching…";
    try {
      const result = await WorldMapAPI.getLocations("", term, searchPage);
      if (term !== searchTerm) return;
      searchResults = append ? searchResults.concat(result.items || []) : (result.items || []);
      searchHasMore = result.has_more; container.replaceChildren();
      if (!searchResults.length) { container.textContent = "No approved places found. Add a custom place below."; return; }
      searchResults.forEach((item) => container.append(createSearchResult(item)));
      if (searchHasMore) {
        const more = document.createElement("button"); more.className = "secondary"; more.type = "button"; more.textContent = "Load more results";
        more.addEventListener("click", () => { searchPage += 1; runSearch(searchTerm, true); }); container.append(more);
      }
      renderMapItems(searchResults);
    } catch (error) { container.textContent = error.message || "Search failed."; }
  }
  document.getElementById("search-form").addEventListener("submit", (event) => {
    event.preventDefault(); runSearch(document.getElementById("place-search").value.trim());
  });
  let searchTimer;
  document.getElementById("place-search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    const value = event.currentTarget.value.trim();
    if (value.length < 2) { if (!value) window.loadMapLocations(); document.getElementById("search-results").replaceChildren(); return; }
    searchTimer = setTimeout(() => runSearch(value), 350);
  });
  document.getElementById("category-filter").addEventListener("change", window.loadMapLocations);

  const makeEl = (tag, text, className) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; };
  const statusLabel = (status) => ({ pending: "Awaiting review", approved: "Approved", rejected: "Not approved" }[status] || status);
  function makeEditForm(item) {
    const form = makeEl("form", undefined, "stack edit-form");
    const fields = [
      ["name", "Custom place name", item.name], ["house_number", "House number", item.house_number], ["street", "Street", item.street],
      ["area", "Area", item.area], ["city", "City", item.city], ["state", "State", item.state], ["country", "Country", item.country],
      ["postal_code", "Postal code", item.postal_code], ["address", "Additional address text", item.address],
      ["description", "Description", item.description], ["lat", "Latitude", item.lat], ["lng", "Longitude", item.lng]
    ];
    fields.forEach(([name, labelText, value]) => {
      const label = makeEl("label", labelText); const input = name === "description" ? makeEl("textarea") : makeEl("input");
      input.name = name; input.value = value ?? "";
      if (name === "lat" || name === "lng") { input.type = "number"; input.step = "any"; }
      label.append(input); form.append(label);
    });
    const categoryLabel = makeEl("label", "Category");
    const categorySelect = makeEl("select"); categorySelect.name = "category";
    [["home", "Home"], ["business", "Business"], ["landmark", "Landmark"], ["park", "Park"], ["other", "Other"]].forEach(([value, label]) => {
      const option = makeEl("option", label); option.value = value; option.selected = item.category === value; categorySelect.append(option);
    });
    categoryLabel.append(categorySelect); form.append(categoryLabel);
    const actions = makeEl("div", undefined, "button-row");
    const save = makeEl("button", "Save changes"); save.type = "submit";
    const cancel = makeEl("button", "Cancel", "secondary"); cancel.type = "button"; cancel.addEventListener("click", () => form.remove());
    actions.append(save, cancel); form.append(actions);
    form.addEventListener("submit", async (event) => {
      event.preventDefault(); const data = Object.fromEntries(new FormData(form).entries());
      data.lat = Number(data.lat); data.lng = Number(data.lng);
      try { const result = await WorldMapAPI.updateLocation(item.id, data); window.showToast(result.message); await refreshMyPlaces(); await window.loadMapLocations(); }
      catch (error) { window.showToast(error.message); }
    });
    return form;
  }
  async function refreshMyPlaces() {
    const panel = document.getElementById("my-places-panel"); const list = document.getElementById("my-places-list");
    if (!window.currentUser) { panel.classList.add("hidden"); return; }
    panel.classList.remove("hidden"); list.replaceChildren();
    try {
      const items = await WorldMapAPI.getMyLocations();
      if (!items.length) { list.textContent = "You haven’t submitted any places yet."; return; }
      items.forEach((item) => {
        const card = makeEl("article", undefined, "place-card");
        card.append(makeEl("strong", item.name), makeEl("span", statusLabel(item.status), `status status-${item.status}`), makeEl("p", addressSummary(item)));
        const controls = makeEl("div", undefined, "button-row");
        const edit = makeEl("button", "Edit", "secondary compact"); edit.type = "button";
        edit.addEventListener("click", () => { const existing = card.querySelector(".edit-form"); if (existing) existing.remove(); else card.append(makeEditForm(item)); });
        const remove = makeEl("button", "Delete", "danger compact"); remove.type = "button";
        remove.addEventListener("click", async () => { if (!confirm(`Delete “${item.name}” and its photos? This cannot be undone.`)) return; try { await WorldMapAPI.deleteLocation(item.id); window.showToast("Place deleted."); await refreshMyPlaces(); await window.loadMapLocations(); } catch (error) { window.showToast(error.message); } });
        controls.append(edit, remove); card.append(controls);
        const uploadLabel = makeEl("label", "Add a photo (JPEG/PNG/WebP, max 4 MB)"); const file = makeEl("input"); file.type = "file"; file.accept = "image/jpeg,image/png,image/webp";
        file.addEventListener("change", async () => { if (!file.files[0]) return; try { await WorldMapAPI.uploadPhoto(item.id, file.files[0]); window.showToast("Photo submitted for review."); file.value = ""; await refreshMyPlaces(); } catch (error) { window.showToast(error.message); } });
        card.append(uploadLabel); uploadLabel.append(file);
        if (item.photos_pending) card.append(makeEl("small", `${item.photos_pending} photo(s) awaiting review.`));
        list.append(card);
      });
    } catch (error) { list.textContent = error.message; }
  }
  function renderModerationCard(item) {
    const card = makeEl("article", undefined, "place-card");
    card.append(makeEl("strong", item.name), makeEl("p", addressSummary(item)), makeEl("p", item.description || "No description"), makeEl("small", `Coordinates: ${item.lat}, ${item.lng}`));
    const controls = makeEl("div", undefined, "button-row");
    [["Approve", "approved"], ["Reject", "rejected"]].forEach(([label, status]) => {
      const button = makeEl("button", label, status === "rejected" ? "danger compact" : "compact"); button.type = "button";
      button.addEventListener("click", async () => { try { await WorldMapAPI.reviewLocation(item.id, status); window.showToast(`Place ${status}.`); await refreshModeration(); await window.loadMapLocations(); } catch (error) { window.showToast(error.message); } }); controls.append(button);
    });
    const hintsButton = makeEl("button", "Check similar submissions", "secondary compact"); hintsButton.type = "button";
    hintsButton.addEventListener("click", async () => {
      hintsButton.disabled = true;
      let hints = card.querySelector(".duplicate-hints");
      if (!hints) { hints = makeEl("div", undefined, "duplicate-hints"); card.append(hints); }
      hints.textContent = "Checking pending and approved records…";
      try {
        const result = await WorldMapAPI.getDuplicateHints(item.id);
        hints.replaceChildren();
        ["pending_review", "approved_public"].forEach((group) => {
          const entries = result.groups?.[group] || [];
          if (!entries.length) return;
          hints.append(makeEl("strong", group === "pending_review" ? "Other pending submissions" : "Approved public places"));
          entries.forEach((entry) => {
            const line = makeEl("p", `${entry.name} — ${entry.address || "Address not provided"} (${entry.distance_m} m; ${(entry.match_reasons || []).join(", ")})`);
            hints.append(line);
          });
        });
        if (!hints.childElementCount) hints.textContent = "No likely duplicates found.";
        if (result.truncated) hints.append(makeEl("small", "More possible matches exist; showing a limited set."));
      } catch (error) { hints.textContent = error.message || "Duplicate hints unavailable."; }
      finally { hintsButton.disabled = false; }
    });
    controls.append(hintsButton);
    card.append(controls); return card;
  }
  async function refreshModeration() {
    const panel = document.getElementById("moderation-panel");
    if (!window.currentUser || !["admin", "moderator"].includes(window.currentUser.role)) {
      panel.classList.add("hidden");
      document.getElementById("moderation-list").replaceChildren();
      document.getElementById("photo-moderation-list").replaceChildren();
      return;
    }
    panel.classList.remove("hidden");
    const locations = document.getElementById("moderation-list"); const photos = document.getElementById("photo-moderation-list");
    locations.replaceChildren(); photos.replaceChildren();
    try {
      const pending = await WorldMapAPI.getPendingLocations();
      if (!pending.length) locations.textContent = "No location submissions awaiting review.";
      pending.forEach((item) => locations.append(renderModerationCard(item)));
      const pendingPhotos = await WorldMapAPI.getPendingPhotos();
      if (!pendingPhotos.length) photos.textContent = "No photos awaiting review.";
      pendingPhotos.forEach((photo) => {
        const card = makeEl("article", undefined, "place-card"); card.append(makeEl("strong", photo.location_name), makeEl("p", photo.caption || "No caption"));
        const image = makeEl("img", undefined, "moderation-photo"); image.src = photo.url; image.alt = `Submitted photo of ${photo.location_name}`; image.loading = "lazy"; card.append(image);
        const controls = makeEl("div", undefined, "button-row");
        [["Approve", "approved"], ["Reject", "rejected"]].forEach(([label, status]) => { const button = makeEl("button", label, status === "rejected" ? "danger compact" : "compact"); button.type = "button"; button.addEventListener("click", async () => { try { await WorldMapAPI.reviewPhoto(photo.id, status); window.showToast(`Photo ${status}.`); await refreshModeration(); } catch (error) { window.showToast(error.message); } }); controls.append(button); });
        card.append(controls); photos.append(card);
      });
    } catch (error) { locations.textContent = error.message; }
  }
  window.refreshMyPlaces = refreshMyPlaces;
  window.refreshModeration = refreshModeration;
  document.getElementById("refresh-mine").addEventListener("click", refreshMyPlaces);
  document.getElementById("refresh-moderation").addEventListener("click", refreshModeration);
  document.addEventListener("wml:userchange", () => { refreshMyPlaces(); refreshModeration(); });
  window.addEventListener("resize", () => map.invalidateSize({ pan: false }));
  document.addEventListener("wml:userchange", window.loadMapLocations);
  document.addEventListener("DOMContentLoaded", () => { window.loadMapLocations(); map.invalidateSize(); });
})();
