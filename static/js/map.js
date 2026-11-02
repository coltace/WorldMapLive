const map = L.map("map", {
    zoomControl: false
}).setView([20, 0], 3);

L.control.zoom({
    position: "bottomright"
}).addTo(map);

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution:
            '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }
).addTo(map);


window.worldMap = map;

window.mapMarkers = new Map();


window.categoryConfig = {

    home: {
        icon: "🏠",
        color: "#3b82f6"
    },

    business: {
        icon: "🏢",
        color: "#8b5cf6"
    },

    landmark: {
        icon: "🗽",
        color: "#f59e0b"
    },

    park: {
        icon: "🌳",
        color: "#10b981"
    },

    other: {
        icon: "📍",
        color: "#6b7280"
    }

};


window.showToast = function(message) {

    const toast = document.createElement("div");

    toast.className = "toast";

    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);

};


window.escapeHTML = function(value) {

    const element = document.createElement("span");

    element.textContent = String(value ?? "");

    return element.innerHTML;

};


window.loadMapLocations = async function() {

    try {

        const locations =
            await WorldMapAPI.getLocations();

        window.mapMarkers.forEach(marker => {
            window.worldMap.removeLayer(marker);
        });

        window.mapMarkers.clear();

        locations.forEach(item => {

            const config =
                window.categoryConfig[item.category]
                || window.categoryConfig.other;

            const marker = L.marker(
                [item.lat, item.lng]
            ).addTo(window.worldMap);

            const popup = document.createElement("div");

            const title = document.createElement("strong");

            title.textContent = item.name;

            const address = document.createElement("p");

            address.textContent = item.address || "";

            popup.append(title, address);

            marker.bindPopup(popup);

            window.mapMarkers.set(
                item.id,
                marker
            );

        });

        const pins =
            locations.filter(x => x.type === "marker").length;

        const structures =
            locations.filter(x => x.type !== "marker").length;

        document.getElementById("statPins").textContent =
            pins;

        document.getElementById("statStructures").textContent =
            structures;

        document.getElementById("statTotal").textContent =
            locations.length;

    } catch (error) {

        console.error(error);

        window.showToast(
            "Unable to load map locations."
        );

    }

};


document.addEventListener(
    "DOMContentLoaded",
    () => {
        window.loadMapLocations();
    }
);
