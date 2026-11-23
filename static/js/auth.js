(() => {
  "use strict";

  const authScreen = document.getElementById("auth-screen");
  const appShell = document.getElementById("app-shell");
  const status = document.getElementById("account-status");
  const message = document.getElementById("account-message");
  const dashboardName = document.getElementById("dashboard-user-name");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const logoutButton = document.getElementById("logout-button");
  const loginTab = document.getElementById("sign-in-tab");
  const registerTab = document.getElementById("create-account-tab");

  if (!authScreen || !appShell || !status || !message || !dashboardName || !loginForm || !registerForm || !logoutButton) {
    console.error("AceMap Changer: account elements are missing from the page.");
    return;
  }

  window.currentUser = window.currentUser || null;

  function notify(text) {
    if (typeof window.showToast === "function") window.showToast(text);
    else message.textContent = text;
  }

  function setAuthMode(mode) {
    const registering = mode === "register";
    loginForm.classList.toggle("hidden", registering);
    registerForm.classList.toggle("hidden", !registering);
    loginTab?.classList.toggle("active", !registering);
    registerTab?.classList.toggle("active", registering);
    loginTab?.setAttribute("aria-selected", String(!registering));
    registerTab?.setAttribute("aria-selected", String(registering));
    document.getElementById("auth-title").textContent = registering ? "Create your community account." : "Make a place for what matters.";
    message.textContent = registering ? "Create an account to add and manage places on the atlas." : "Sign in to explore and contribute to the community atlas.";
  }

  function setSignedIn(user) {
    if (!user || !user.email) throw new Error("The server returned an invalid account response.");
    window.currentUser = user;
    authScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    status.textContent = `Signed in as ${user.name || user.email}`;
    dashboardName.textContent = user.name || user.email;
    message.textContent = `Your atlas is ready, ${user.name || user.email}.`;
    logoutButton.classList.remove("hidden");
    document.dispatchEvent(new CustomEvent("wml:userchange"));
    window.requestAnimationFrame?.(() => window.worldMap?.invalidateSize({ pan: false }));
  }

  function setSignedOut() {
    window.currentUser = null;
    authScreen.classList.remove("hidden");
    appShell.classList.add("hidden");
    status.textContent = "Not signed in";
    message.textContent = "Sign in to explore and contribute to the community atlas.";
    logoutButton.classList.add("hidden");
    setAuthMode("login");
    document.dispatchEvent(new CustomEvent("wml:userchange"));
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
      console.error("AceMap Changer authentication error:", error);
      notify(error.message || "Authentication failed. Please try again.");
    } finally {
      if (button) button.disabled = false;
    }
  }

  loginTab?.addEventListener("click", () => setAuthMode("login"));
  registerTab?.addEventListener("click", () => setAuthMode("register"));

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitForm(loginForm, (values) => window.WorldMapAPI.login({
      email: String(values.get("email") || "").trim(),
      password: String(values.get("password") || ""),
    }), "Signed in successfully.");
  });

  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitForm(registerForm, (values) => window.WorldMapAPI.register({
      name: String(values.get("name") || "").trim(),
      email: String(values.get("email") || "").trim(),
      password: String(values.get("password") || ""),
    }), "Your account has been created.");
  });

  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
      await window.WorldMapAPI.logout();
      setSignedOut();
      notify("You have signed out.");
    } catch (error) {
      notify(error.message || "Unable to sign out.");
    } finally {
      logoutButton.disabled = false;
    }
  });

  const initiallyAuthenticated = appShell.dataset.initiallyAuthenticated === "true";
  if (initiallyAuthenticated) {
    status.textContent = "Checking account…";
  } else {
    setSignedOut();
  }

  window.WorldMapAPI.getCurrentUser().then(setSignedIn).catch(setSignedOut);
})();
