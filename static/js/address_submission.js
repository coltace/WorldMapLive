(() => {
  "use strict";

  const form = document.getElementById("location-form");
  const searchForm = document.getElementById("address-search-form");
  const suggestions = document.getElementById("address-suggestions");
  const duplicateResults = document.getElementById("duplicate-results");
  const latInput = document.getElementById("location-lat");
  const lngInput = document.getElementById("location-lng");
  const previewText = document.getElementById("address-preview-text");
  const coordinatePreview = document.getElementById("coordinate-preview");
  const photoInput = document.getElementById("location-photo");
  const photoPreviewContainer = document.getElementById("photo-preview-container");
  const photoPreviewList = document.getElementById("photo-preview-list");
  const photoRetryPanel = document.getElementById("photo-retry-panel");
  const submitButton = document.getElementById("submit-location");
  const duplicateButton = document.getElementById("check-duplicates");
  const appShell = document.getElementById("app-shell");
  const studioOpeners = document.querySelectorAll("[data-open-address-studio]");
  const studioCloser = document.getElementById("close-address-studio");
  const successPanel = document.getElementById("submission-success");
  const flowSteps = [...document.querySelectorAll("[data-flow-step]")];
  const searchButton = searchForm.querySelector("button[type=submit]");
  const fieldNames = ["house_number", "street", "area", "city", "state", "country", "postal_code"];
  const candidateFields = {
    house_number: ["house_number"],
    street: ["road", "residential", "pedestrian", "street", "highway", "path"],
    area: ["neighbourhood", "suburb", "quarter", "city_district", "borough", "district", "hamlet"],
    city: ["city", "town", "village", "municipality"],
    state: ["state", "province", "region", "state_district"],
    country: ["country"],
    postal_code: ["postcode", "postal_code"]
  };

  let submissionPin = null;
  let selectedFormattedAddress = "";
  let selectedCandidateName = "";
  let duplicateCheckedKey = null;
  let photoPreviewUrls = [];
  let pendingPhotoRetries = [];
  let studioReturnFocus = null;

  function setWorkflowStep(step) {
    flowSteps.forEach((item) => {
      const itemStep = Number(item.dataset.flowStep);
      item.classList.toggle("is-current", itemStep === step);
      item.classList.toggle("is-complete", itemStep < step);
      if (itemStep === step) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
  }

  function openAddressStudio(event) {
    studioReturnFocus = event.currentTarget;
    appShell.classList.add("is-address-mode");
    studioOpeners.forEach((button) => button.setAttribute("aria-pressed", "true"));
    window.requestAnimationFrame(() => {
      window.worldMap.invalidateSize({ pan: false });
      const query = document.getElementById("address-query");
      if (window.matchMedia("(max-width: 760px)").matches) query.scrollIntoView({ behavior: "smooth", block: "center" });
      query.focus({ preventScroll: true });
    });
  }

  function closeAddressStudio() {
    appShell.classList.remove("is-address-mode");
    studioOpeners.forEach((button) => button.setAttribute("aria-pressed", "false"));
    window.requestAnimationFrame(() => window.worldMap.invalidateSize({ pan: false }));
    if (studioReturnFocus?.isConnected) studioReturnFocus.focus({ preventScroll: true });
  }

  studioOpeners.forEach((button) => button.addEventListener("click", openAddressStudio));
  studioCloser.addEventListener("click", closeAddressStudio);

  document.getElementById("add-another-place").addEventListener("click", () => {
    successPanel.classList.add("hidden");
    form.classList.remove("hidden");
    setWorkflowStep(1);
    document.getElementById("address-query").focus({ preventScroll: true });
  });

  document.getElementById("view-my-submissions").addEventListener("click", async () => {
    try { await window.refreshMyPlaces?.(); } catch (error) { console.warn(error); }
    closeAddressStudio();
    document.getElementById("my-places-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function currentAddressFields() {
    const values = new FormData(form);
    return Object.fromEntries(fieldNames.map((field) => [field, String(values.get(field) || "").trim()]));
  }

  function formattedAddress() {
    const fields = currentAddressFields();
    const parts = [
      [fields.house_number, fields.street].filter(Boolean).join(" "),
      fields.area,
      fields.city,
      fields.state,
      fields.postal_code,
      fields.country,
      String(new FormData(form).get("address") || "").trim()
    ].filter(Boolean);
    return parts.join(", ") || selectedFormattedAddress || "No formatted address yet. Add address details or choose a search match.";
  }

  function updatePreview() {
    previewText.textContent = formattedAddress();
    const lat = Number(latInput.value);
    const lng = Number(lngInput.value);
    const hasCoordinates = latInput.value.trim() && lngInput.value.trim();
    coordinatePreview.textContent = hasCoordinates && Number.isFinite(lat) && Number.isFinite(lng)
      ? `Pin coordinates: ${lat.toFixed(6)}, ${lng.toFixed(6)}`
      : "No map pin selected.";
  }

  function invalidateDuplicateCheck() {
    duplicateCheckedKey = null;
    submitButton.textContent = "Submit place for review";
    if (duplicateResults.childElementCount) {
      duplicateResults.replaceChildren();
      const note = document.createElement("p");
      note.textContent = "Details changed. Check for similar places again before submitting.";
      duplicateResults.append(note);
    }
  }

  function syncPin(lat, lng, zoomToPin = false) {
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      updatePreview();
      return false;
    }
    latInput.value = lat.toFixed(6);
    lngInput.value = lng.toFixed(6);
    const point = [Number(latInput.value), Number(lngInput.value)];
    if (!submissionPin) {
      const icon = L.divIcon({ className: "map-pin", html: "<span>•</span>", iconSize: [30, 30], iconAnchor: [15, 30] });
      submissionPin = L.marker(point, { icon, draggable: true, title: "Submission pin; drag to refine the location" }).addTo(window.worldMap);
      submissionPin.on("dragend", () => {
        const moved = submissionPin.getLatLng();
        syncPin(moved.lat, moved.lng, false);
      });
    } else {
      submissionPin.setLatLng(point);
    }
    if (zoomToPin) {
      window.worldMap.setView(point, Math.max(17, window.worldMap.getZoom()));
      if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) {
        document.getElementById("map").scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
    setWorkflowStep(2);
    updatePreview();
    invalidateDuplicateCheck();
    return true;
  }

  function addressValue(address, keys) {
    for (const key of keys) {
      const value = address?.[key];
      if (typeof value === "string" && value.trim()) return value.trim();
    }
    return "";
  }

  function populateAddress(address, { onlyEmpty = false } = {}) {
    Object.entries(candidateFields).forEach(([field, keys]) => {
      const input = form.elements.namedItem(field);
      const value = addressValue(address, keys);
      if (value && (!onlyEmpty || !input.value.trim())) input.value = value;
    });
  }

  function chooseCandidate(candidate) {
    const details = candidate.address || {};
    fieldNames.forEach((field) => { form.elements.namedItem(field).value = ""; });
    populateAddress(details);
    selectedFormattedAddress = candidate.formatted_address || "";
    const nameInput = form.elements.namedItem("name");
    if (!nameInput.value.trim() || nameInput.value === selectedCandidateName) {
      nameInput.value = candidate.name || addressValue(details, ["house_name", "building", "amenity"]) || selectedFormattedAddress.split(",")[0] || "Mapped place";
      selectedCandidateName = nameInput.value;
    }
    syncPin(Number(candidate.lat), Number(candidate.lng), true);
    updatePreview();
    invalidateDuplicateCheck();
    setWorkflowStep(2);
    window.showToast("Address match selected. Verify the pin, then review the details.");
  }

  function renderAddressResults(results) {
    suggestions.replaceChildren();
    if (!results.length) {
      const empty = document.createElement("p");
      empty.className = "field-hint";
      empty.textContent = "No mapped matches found. You can still enter the address details and place a pin manually.";
      suggestions.append(empty);
      return;
    }
    results.forEach((candidate) => {
      const card = document.createElement("article");
      card.className = "address-candidate";
      const copy = document.createElement("div");
      copy.className = "address-candidate-copy";
      const title = document.createElement("strong");
      title.textContent = candidate.name || addressValue(candidate.address, ["house_name", "building", "amenity"]) || candidate.formatted_address.split(",")[0] || "Address match";
      const detail = document.createElement("span");
      detail.textContent = candidate.formatted_address;
      const type = document.createElement("small");
      type.textContent = [candidate.category, candidate.type].filter(Boolean).join(" · ") || "Mapped address";
      copy.append(title, detail, type);
      const select = document.createElement("button");
      select.type = "button";
      select.textContent = "Use this match";
      select.addEventListener("click", () => chooseCandidate(candidate));
      card.append(copy, select);
      suggestions.append(card);
    });
  }

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = document.getElementById("address-query").value.trim();
    if (query.length < 2) return;
    searchButton.disabled = true;
    searchButton.textContent = "Searching…";
    suggestions.textContent = "Searching mapped addresses…";
    try {
      const response = await WorldMapAPI.searchAddresses(query);
      renderAddressResults(response.results || []);
    } catch (error) {
      suggestions.textContent = `${error.message || "Address search failed."} You can still add the place by pin.`;
    } finally {
      searchButton.disabled = false;
      searchButton.textContent = "Find";
    }
  });

  window.worldMap.on("click", (event) => syncPin(event.latlng.lat, event.latlng.lng));
  [latInput, lngInput].forEach((input) => input.addEventListener("change", () => {
    const lat = Number(latInput.value);
    const lng = Number(lngInput.value);
    if (latInput.value.trim() && lngInput.value.trim()) syncPin(lat, lng, true);
    else updatePreview();
  }));

  document.getElementById("reverse-pin-lookup").addEventListener("click", async (event) => {
    const lat = Number(latInput.value);
    const lng = Number(lngInput.value);
    if (!latInput.value.trim() || !lngInput.value.trim() || !Number.isFinite(lat) || !Number.isFinite(lng)) {
      window.showToast("Place a valid pin on the map first.");
      return;
    }
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = "Looking up…";
    try {
      const result = await WorldMapAPI.reverseGeocode(lat, lng);
      selectedFormattedAddress = result.address || "";
      populateAddress(result.details || {}, { onlyEmpty: true });
      const name = form.elements.namedItem("name");
      if (!name.value.trim() && result.name) name.value = result.name;
      updatePreview();
      invalidateDuplicateCheck();
      window.showToast("Nearby address looked up. Confirm it matches the pin; map data can be approximate.");
    } catch (error) {
      window.showToast(error.message || "Address lookup failed. You can enter the address manually.");
    } finally {
      button.disabled = false;
      button.textContent = "Look up address at pin";
    }
  });

  function duplicatePayload() {
    const values = new FormData(form);
    const structuredAddress = Object.fromEntries(
      fieldNames.map((field) => [field, String(values.get(field) || "").trim()])
    );
    const supplementalAddress = String(values.get("address") || "").trim();
    const hasStructuredAddress = Object.values(structuredAddress).some(Boolean);
    return {
      name: String(values.get("name") || "").trim(),
      category: values.get("category"),
      ...structuredAddress,
      address: supplementalAddress || (!hasStructuredAddress ? selectedFormattedAddress : ""),
      lat: Number(values.get("lat")),
      lng: Number(values.get("lng"))
    };
  }

  function duplicateKey(payload) {
    return JSON.stringify({
      name: payload.name, category: payload.category, address: payload.address,
      ...Object.fromEntries(fieldNames.map((field) => [field, payload[field]])),
      lat: payload.lat, lng: payload.lng
    });
  }

  function renderDuplicateResults(result) {
    duplicateResults.replaceChildren();
    const matches = result.candidates || [];
    const message = document.createElement("p");
    message.textContent = matches.length
      ? `Found ${matches.length} possible nearby match${matches.length === 1 ? "" : "es"}. These are advisory; review them before deciding whether to submit.`
      : "No likely duplicates found. You can continue with submission.";
    duplicateResults.append(message);
    matches.forEach((match) => {
      const card = document.createElement("article");
      card.className = "duplicate-candidate";
      const text = document.createElement("span");
      text.textContent = `${match.name} — ${match.address || "Address not provided"} (${match.distance_m} m; ${(match.match_reasons || []).join(", ")})`;
      const view = document.createElement("button");
      view.type = "button";
      view.className = "secondary compact";
      view.textContent = "View match";
      view.addEventListener("click", () => window.worldMap.setView([match.lat, match.lng], Math.max(16, window.worldMap.getZoom())));
      card.append(text, view);
      duplicateResults.append(card);
    });
    if (result.truncated) {
      const note = document.createElement("small");
      note.textContent = "Additional possible matches were found; only a limited set is shown.";
      duplicateResults.append(note);
    }
  }

  async function runDuplicateCheck() {
    if (!window.currentUser) {
      window.showToast("Sign in before checking duplicates.");
      return false;
    }
    const payload = duplicatePayload();
    if (!payload.name || !latInput.value.trim() || !lngInput.value.trim()
      || !Number.isFinite(payload.lat) || !Number.isFinite(payload.lng)
      || payload.lat < -90 || payload.lat > 90 || payload.lng < -180 || payload.lng > 180) {
      window.showToast("Add a place name and valid coordinates before checking for duplicates.");
      return false;
    }
    duplicateButton.disabled = true;
    duplicateButton.textContent = "Checking…";
    duplicateResults.textContent = "Checking nearby approved places…";
    try {
      const result = await WorldMapAPI.checkDuplicates(payload);
      renderDuplicateResults(result);
      duplicateCheckedKey = duplicateKey(payload);
      submitButton.textContent = result.candidates?.length ? "Submit anyway for review" : "Submit place for review";
      setWorkflowStep(3);
      return true;
    } catch (error) {
      duplicateCheckedKey = null;
      duplicateResults.textContent = error.message || "Duplicate check failed. Please try again.";
      return false;
    } finally {
      duplicateButton.disabled = false;
      duplicateButton.textContent = "Check for similar places";
    }
  }

  duplicateButton.addEventListener("click", runDuplicateCheck);
  form.addEventListener("input", (event) => {
    if (event.target.name && event.target.name !== "photo") {
      invalidateDuplicateCheck();
      setWorkflowStep(2);
    }
    updatePreview();
  });
  form.addEventListener("change", (event) => {
    if (event.target.name && event.target.name !== "photo") {
      invalidateDuplicateCheck();
      setWorkflowStep(2);
    }
    updatePreview();
  });

  function renderPhotoRetryQueue() {
    photoRetryPanel.replaceChildren();
    if (!pendingPhotoRetries.length) {
      photoRetryPanel.classList.add("hidden");
      return;
    }
    photoRetryPanel.classList.remove("hidden");
    const heading = document.createElement("strong");
    heading.textContent = "Photo upload needs attention";
    photoRetryPanel.append(heading);
    pendingPhotoRetries.forEach((entry) => {
      const card = document.createElement("article");
      card.className = "photo-retry-card";
      const message = document.createElement("p");
      message.textContent = `The place “${entry.locationName}” was submitted, but “${entry.file.name}” was not uploaded. Retry it here; do not submit the place again.`;
      const actions = document.createElement("div");
      actions.className = "button-row";
      const retry = document.createElement("button");
      retry.type = "button";
      retry.textContent = "Retry photo upload";
      retry.addEventListener("click", async () => {
        retry.disabled = true;
        retry.textContent = "Retrying…";
        try {
          await WorldMapAPI.uploadPhoto(entry.locationId, entry.file);
          pendingPhotoRetries = pendingPhotoRetries.filter((item) => item !== entry);
          renderPhotoRetryQueue();
          window.showToast("Photo upload succeeded and is awaiting review.");
          try { await window.refreshMyPlaces?.(); } catch (refreshError) { console.warn(refreshError); }
        } catch (error) {
          message.textContent = `Photo upload still failed: ${error.message}. Retry here or add the photo later from Your places.`;
          retry.disabled = false;
          retry.textContent = "Retry photo upload";
        }
      });
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "secondary compact";
      dismiss.textContent = "Dismiss";
      dismiss.addEventListener("click", () => {
        pendingPhotoRetries = pendingPhotoRetries.filter((item) => item !== entry);
        renderPhotoRetryQueue();
        window.showToast("You can add the photo later from Your places.");
      });
      actions.append(retry, dismiss);
      card.append(message, actions);
      photoRetryPanel.append(card);
    });
  }

  photoInput.addEventListener("change", () => {
    photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
    photoPreviewUrls = [];
    photoPreviewList.replaceChildren();
    photoPreviewContainer.classList.add("hidden");
    const files = Array.from(photoInput.files || []);
    if (!files.length) return;
    if (files.length > 5) {
      photoInput.value = "";
      window.showToast("Choose up to 5 building photos at a time.");
      return;
    }
    const invalid = files.find((file) => !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 4 * 1024 * 1024);
    if (invalid) {
      photoInput.value = "";
      window.showToast(`“${invalid.name}” is not a JPEG, PNG, or WebP image under 4 MB. No photos were selected.`);
      return;
    }
    files.forEach((file) => {
      const url = URL.createObjectURL(file);
      photoPreviewUrls.push(url);
      const card = document.createElement("figure");
      card.className = "photo-preview-card";
      const image = document.createElement("img");
      image.src = url;
      image.alt = `Preview of ${file.name}`;
      const caption = document.createElement("figcaption");
      caption.textContent = file.name;
      card.append(image, caption);
      photoPreviewList.append(card);
    });
    photoPreviewContainer.classList.remove("hidden");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.currentUser) {
      window.showToast("Sign in before submitting a place.");
      return;
    }
    const payload = duplicatePayload();
    const key = duplicateKey(payload);
    if (duplicateCheckedKey !== key) {
      if (await runDuplicateCheck()) window.showToast("Review the duplicate results, then submit again to continue.");
      return;
    }

    const values = new FormData(form);
    submitButton.disabled = true;
    try {
      const result = await WorldMapAPI.createLocation({
        name: payload.name,
        category: payload.category,
        address: payload.address,
        description: String(values.get("description") || "").trim(),
        ...Object.fromEntries(fieldNames.map((field) => [field, payload[field]])),
        lat: payload.lat,
        lng: payload.lng,
        type: "marker"
      });
      const photos = values.getAll("photo").filter((photo) => photo instanceof File && photo.size);
      const failedPhotos = [];
      for (const photo of photos) {
        try {
          await WorldMapAPI.uploadPhoto(result.location.id, photo);
        } catch (error) {
          failedPhotos.push(photo);
          pendingPhotoRetries.push({
            locationId: result.location.id,
            locationName: payload.name,
            file: photo
          });
        }
      }
      const photoUploadFailed = failedPhotos.length > 0;
      if (photoUploadFailed) renderPhotoRetryQueue();
      form.reset();
      selectedFormattedAddress = "";
      selectedCandidateName = "";
      duplicateCheckedKey = null;
      duplicateResults.replaceChildren();
      suggestions.replaceChildren();
      document.getElementById("address-query").value = "";
      if (submissionPin) window.worldMap.removeLayer(submissionPin);
      submissionPin = null;
      photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
      photoPreviewUrls = [];
      photoPreviewList.replaceChildren();
      photoPreviewContainer.classList.add("hidden");
      submitButton.textContent = "Submit place for review";
      document.getElementById("submitted-place-name").textContent = payload.name;
      document.getElementById("submission-success-message").textContent = photoUploadFailed
        ? `Your place is awaiting community approval and will be searchable from any device after approval. ${failedPhotos.length} of ${photos.length} photo uploads need a retry below; do not submit the place again.`
        : "Your place is awaiting community approval. After approval, it will be searchable by name or address from any device.";
      form.classList.add("hidden");
      successPanel.classList.remove("hidden");
      setWorkflowStep(3);
      updatePreview();
      if (photoUploadFailed) window.showToast(`${failedPhotos.length} photo upload(s) failed. Retry them below; your place was submitted successfully.`);
      else window.showToast(result.message || "Place submitted for review.");
      try { await window.refreshMyPlaces?.(); } catch (refreshError) { console.warn(refreshError); }
      try { await window.loadMapLocations?.(); } catch (refreshError) { console.warn(refreshError); }
    } catch (error) {
      window.showToast(error.message || "Place submission failed.");
    } finally {
      submitButton.disabled = false;
    }
  });

  updatePreview();
})();
