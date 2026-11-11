(() => {
  "use strict";

  const status = document.getElementById("account-status");
  const message = document.getElementById("account-message");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const logoutButton = document.getElementById("logout-button");

  if (!status || !message || !loginForm || !registerForm || !logoutButton) {
    console.error("WorldMapLive: Login elements are missing from the page.");
    return;
  }

  function notify(text) {
    if (typeof window.showToast === "function") {
      window.showToast(text);
    } else {
      message.textContent = text;
    }
  }

  function setSignedIn(user) {
    if (!user || !user.email) {
      throw new Error("The server returned an invalid account response.");
    }

    status.textContent = `Signed in as ${user.name || user.email}`;
    message.textContent = `Welcome, ${user.name || user.email}. You can submit places for review.`;

    loginForm.classList.add("hidden");
    registerForm.closest("details")?.classList.add("hidden");
    logoutButton.classList.remove("hidden");
  }

  function setSignedOut() {
    status.textContent = "Not signed in";
    message.textContent = "Sign in or create an account to submit a place.";

    loginForm.classList.remove("hidden");
    registerForm.closest("details")?.classList.remove("hidden");
    logoutButton.classList.add("hidden");
  }

  async function submitForm(form, action, successMessage) {
    const button = form.querySelector('button[type="submit"]');

    if (button) button.disabled = true;

    try {
      const result = await action(new FormData(form));
      setSignedIn(result.user || result);
      form.reset();
      notify(successMessage);
    } catch (error) {
      console.error("WorldMapLive authentication error:", error);
      notify(error.message || "Authentication failed. Please try again.");
    } finally {
      if (button) button.disabled = false;
    }
  }

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();

    submitForm(
      loginForm,
      (values) => WorldMapAPI.login({
        email: String(values.get("email") || "").trim(),
        password: String(values.get("password") || "")
      }),
      "Signed in successfully."
    );
  });

  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();

    submitForm(
      registerForm,
      (values) => WorldMapAPI.register({
        name: String(values.get("name") || "").trim(),
        email: String(values.get("email") || "").trim(),
        password: String(values.get("password") || "")
      }),
      "Your account has been created."
    );
  });

  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;

    try {
      await WorldMapAPI.logout();
      setSignedOut();
      notify("You have signed out.");
    } catch (error) {
      notify(error.message || "Unable to sign out.");
    } finally {
      logoutButton.disabled = false;
    }
  });

  setSignedOut();

  WorldMapAPI.getCurrentUser()
    .then(setSignedIn)
    .catch(() => setSignedOut());
})();
