window.WorldMapAPI = {
  async request(url, options = {}) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (csrfToken) headers.set("X-CSRFToken", csrfToken);
    const response = await fetch(url, { credentials: "same-origin", ...options, headers });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
    return data;
  },
  getLocations(category = "", q = "", page = 1) {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (q) params.set("q", q);
    params.set("page", page);
    return this.request(`/api/locations?${params}`);
  },
  searchLocations(q) { return this.getLocations("", q); },
  getMyLocations() { return this.request("/api/locations/mine"); },
  getPendingLocations() { return this.request("/api/locations/pending"); },
  getPendingPhotos() { return this.request("/api/locations/photos/pending"); },
  reviewLocation(id, status) {
    return this.request(`/api/locations/${id}/review`, { method: "POST", body: JSON.stringify({ status }) });
  },
  reviewPhoto(id, status) {
    return this.request(`/api/locations/photos/${id}/review`, { method: "POST", body: JSON.stringify({ status }) });
  },
  geocodeAddress(address) { return this.request(`/api/locations/geocode?q=${encodeURIComponent(address)}`); },
  reverseGeocode(lat, lng) {
    return this.request(`/api/locations/reverse-geocode?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`);
  },
  updateLocation(id, item) {
    return this.request(`/api/locations/${id}`, { method: "PATCH", body: JSON.stringify(item) });
  },
  deleteLocation(id) { return this.request(`/api/locations/${id}`, { method: "DELETE" }); },
  uploadPhoto(id, file, caption = "") {
    const body = new FormData();
    body.append("photo", file);
    body.append("caption", caption);
    return this.request(`/api/locations/${id}/photos`, { method: "POST", body });
  },
  getCurrentUser() { return this.request("/api/auth/me"); },
  login(credentials) { return this.request("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) }); },
  register(details) { return this.request("/api/auth/register", { method: "POST", body: JSON.stringify(details) }); },
  logout() { return this.request("/api/auth/logout", { method: "POST" }); },
  createLocation(item) { return this.request("/api/locations", { method: "POST", body: JSON.stringify(item) }); }
};
