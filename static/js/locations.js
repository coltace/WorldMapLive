const WorldMapAPI = {

    async request(url, options = {}) {

        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": window.WORLD_MAP_CSRF,
                ...options.headers
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Request failed"
            );
        }

        return data;
    },


    async getLocations() {

        return this.request("/api/locations");
    },


    async createLocation(item) {

        return this.request("/api/locations", {
            method: "POST",
            body: JSON.stringify(item)
        });
    },


    async updateLocation(id, item) {

        return this.request(
            `/api/locations/${id}`,
            {
                method: "PATCH",
                body: JSON.stringify(item)
            }
        );
    },


    async deleteLocation(id) {

        return this.request(
            `/api/locations/${id}`,
            {
                method: "DELETE"
            }
        );
    }

};
