(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const makeText = (tag, text, className = "") => {
    const node = document.createElement(tag);
    node.textContent = String(text ?? "");
    if (className) node.className = className;
    return node;
  };
  const addressText = (item) => [
    item.house_number && [item.house_number, item.street].filter(Boolean).join(" "),
    item.area, item.city, item.state, item.postal_code, item.country, item.address
  ].filter(Boolean).join(", ");

  function bind() {
    const assistantForm = byId("assistant-form");
    assistantForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!window.currentUser) { window.showToast("Sign in to use the assistant."); return; }
      const input = byId("assistant-message");
      const list = byId("assistant-messages");
      const text = input.value.trim();
      if (!text) return;
      const submit = byId("assistant-submit");
      submit.disabled = true;
      list.append(makeText("p", `You: ${text}`, "assistant-message assistant-message-user"));
      input.value = "";
      const pending = makeText("p", "Assistant is checking approved places…", "assistant-message assistant-message-bot");
      list.append(pending);
      try {
        const result = await window.WorldMapAPI.askAssistant(text);
        pending.textContent = `Assistant: ${result.reply}`;
      } catch (error) {
        pending.textContent = error.message || "The assistant is currently unavailable.";
      } finally { submit.disabled = false; }
    });

    byId("recommendation-button")?.addEventListener("click", async (event) => {
      if (!window.currentUser) { window.showToast("Sign in to see nearby recommendations."); return; }
      const button = event.currentTarget;
      const list = byId("recommendation-results");
      const center = window.worldMap?.getCenter();
      if (!center) { list.textContent = "The map is still loading."; return; }
      button.disabled = true;
      list.textContent = "Finding nearby approved places…";
      try {
        const result = await window.WorldMapAPI.getRecommendations(
          center.lat, center.lng, Number(byId("recommendation-radius").value), byId("category-filter").value
        );
        list.replaceChildren();
        if (!result.items?.length) { list.textContent = "No matching approved places found in this radius."; return; }
        result.items.forEach((entry) => {
          const item = entry.location;
          const card = makeText("article", undefined, "place-card");
          card.append(makeText("strong", item.name), makeText("p", addressText(item) || "Address not provided"));
          if (entry.distance_km !== undefined) card.append(makeText("small", `${Number(entry.distance_km).toFixed(1)} km away`));
          if (entry.reasons?.length) {
            const why = entry.reasons.map((reason) => reason.replaceAll("_", " ")).join("; ");
            card.append(makeText("small", `Why recommended: ${why}`));
          }
          const focus = makeText("button", "Show on map", "secondary compact");
          focus.type = "button";
          focus.addEventListener("click", () => {
            window.worldMap?.setView([item.lat, item.lng], Math.max(window.worldMap.getZoom(), 15));
            window.mapLayers?.get(item.id)?.openPopup();
          });
          card.append(focus);
          list.append(card);
        });
      } catch (error) { list.textContent = error.message || "Recommendations are unavailable."; }
      finally { button.disabled = false; }
    });

    byId("check-duplicates")?.addEventListener("click", async (event) => {
      const form = byId("location-form");
      const values = new FormData(form);
      const rawLat = String(values.get("lat") || "").trim();
      const rawLng = String(values.get("lng") || "").trim();
      const lat = Number(rawLat);
      const lng = Number(rawLng);
      const results = byId("duplicate-results");
      if (!window.currentUser) { window.showToast("Sign in before checking places."); return; }
      if (!rawLat || !rawLng || !Number.isFinite(lat) || !Number.isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
        results.textContent = "Enter valid coordinates to check for similar places.";
        return;
      }
      const button = event.currentTarget;
      button.disabled = true;
      results.textContent = "Checking public and your own submissions for possible matches…";
      const payload = Object.fromEntries(["name", "category", "address", "house_number", "street", "area", "city", "state", "country", "postal_code"].map((key) => [key, String(values.get(key) || "").trim()]));
      payload.lat = lat;
      payload.lng = lng;
      try {
        const result = await window.WorldMapAPI.checkDuplicates(payload);
        results.replaceChildren();
        const matches = result.candidates || [];
        if (!matches.length) { results.textContent = "No likely matches found. This check is advisory, not a guarantee."; return; }
        results.append(makeText("p", "Possible matches (review before submitting; no record is automatically blocked):"));
        matches.forEach((item) => {
          const card = makeText("article", undefined, "place-card");
          card.append(makeText("strong", item.name), makeText("p", addressText(item) || "Address not provided"));
          if (item.distance_km !== undefined) card.append(makeText("small", `${Number(item.distance_km).toFixed(2)} km away`));
          results.append(card);
        });
      } catch (error) { results.textContent = error.message || "Duplicate check failed."; }
      finally { button.disabled = false; }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind, { once: true });
  else bind();
})();
