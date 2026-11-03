(() => {
  const map = L.map("map", { zoomControl: false }).setView([20, 0], 3);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19
  }).addTo(map);

  window.worldMap = map;
  window.mapLayers = new Map();
  window.showToast = (message) => {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = String(message);
    document.getElementById("toast-region").appendChild(toast);
    window.setTimeout(() => toast.remove(), 3500);
  };

  function renderLocation(item) {
    let layer;
    if (item.geometry && typeof item.geometry === "object") {
      layer = L.geoJSON(item.geometry, {
        style: { color: "#1769aa", weight: 3, fillOpacity: 0.2 },
        pointToLayer: (_feature, latlng) => L.marker(latlng)
      });
    } else {
      const icon = L.divIcon({
        className: "map-pin",
        html: `<span>${window.escapeHTML ? window.escapeHTML("•") : "•"}` + "</span>",
        iconSize: [30, 30],
        iconAnchor: [15, 30]
      });
      layer = L.marker([item.lat, item.lng], { icon });
    }

    const popup = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.name;
    const address = document.createElement("p");
    address.textContent = item.address || "";
    const description = document.createElement("p");
    description.textContent = item.description || "";
    popup.append(title, address, description);
    layer.bindPopup(popup).addTo(map);
    window.mapLayers.set(item.id, layer);
  }

  window.loadMapLocations = async () => {
    try {
      const category = document.getElementById("category-filter").value;
      const locations = await WorldMapAPI.getLocations(category);
      window.mapLayers.forEach((layer) => map.removeLayer(layer));
      window.mapLayers.clear();
      locations.forEach(renderLocation);

      const pins = locations.filter((item) => !item.geometry && item.type === "marker").length;
      document.getElementById("statPins").textContent = pins;
      document.getElementById("statStructures").textContent = locations.length - pins;
      document.getElementById("statTotal").textContent = locations.length;
    } catch (error) {
      console.error(error);
      window.showToast(`Unable to load map locations: ${error.message}`);
    }
  };

  map.on("click", (event) => {
    document.getElementById("location-lat").value = event.latlng.lat.toFixed(6);
    document.getElementById("location-lng").value = event.latlng.lng.toFixed(6);
  });

  document.getElementById("category-filter").addEventListener("change", window.loadMapLocations);
  document.getElementById("location-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    try {
      const result = await WorldMapAPI.createLocation({
        name: values.get("name"),
        category: values.get("category"),
        address: values.get("address"),
        description: values.get("description"),
        lat: Number(values.get("lat")),
        lng: Number(values.get("lng")),
        type: "marker"
      });
      form.reset();
      window.showToast(result.message || "Place submitted for review.");
    } catch (error) {
      window.showToast(error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", window.loadMapLocations, { once: true });
})();
