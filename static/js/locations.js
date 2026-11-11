window.WorldMapAPI = {
  async request(url, options = {}) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (csrfToken) headers.set("X-CSRFToken", csrfToken);

    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : null;

    if (!response.ok) {
      throw new Error(data?.error || `Request failed (${response.status})`);
    }
    return data;
  },

  getLocations(category = "") {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    return this.request(`/api/locations${query}`);
  },

  geocodeAddress(address) {
    return this.request(
      `/api/locations/geocode?q=${encodeURIComponent(address)}`
    );
  },

  reverseGeocode(lat, lng) {
    return this.request(
      `/api/locations/reverse-geocode?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`
    );
  },

  updateLocation(id, item) {
    return this.request(`/api/locations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(item)
    });
  },

  getCurrentUser() { return this.request("/api/auth/me"); },
  login(credentials) {
    return this.request("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) });
  },
  register(details) {
    return this.request("/api/auth/register", { method: "POST", body: JSON.stringify(details) });
  },
  logout() { return this.request("/api/auth/logout", { method: "POST" }); },
  createLocation(item) {
    return this.request("/api/locations", { method: "POST", body: JSON.stringify(item) });
  }
};
