(() => {
  const status = document.getElementById("account-status");
  const message = document.getElementById("account-message");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const logoutButton = document.getElementById("logout-button");

  function setSignedIn(user) {
    status.textContent = `Signed in as ${user.name}`;
    message.textContent = `Signed in as ${user.email}. You can submit places for review.`;
    loginForm.classList.add("hidden");
    registerForm.closest("details").classList.add("hidden");
    logoutButton.classList.remove("hidden");
  }

  function setSignedOut() {
    status.textContent = "Not signed in";
    message.textContent = "Sign in or create an account to submit a place.";
    loginForm.classList.remove("hidden");
    registerForm.closest("details").classList.remove("hidden");
    logoutButton.classList.add("hidden");
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(loginForm);
    try {
      const result = await WorldMapAPI.login({ email: values.get("email"), password: values.get("password") });
      setSignedIn(result.user);
      loginForm.reset();
      window.showToast("Signed in successfully.");
    } catch (error) {
      window.showToast(error.message);
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(registerForm);
    try {
      const result = await WorldMapAPI.register({
        name: values.get("name"),
        email: values.get("email"),
        password: values.get("password")
      });
      setSignedIn(result.user);
      registerForm.reset();
      window.showToast("Account created.");
    } catch (error) {
      window.showToast(error.message);
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      await WorldMapAPI.logout();
      setSignedOut();
      window.showToast("Signed out.");
    } catch (error) {
      window.showToast(error.message);
    }
  });

  WorldMapAPI.getCurrentUser().then(setSignedIn).catch(setSignedOut);
})();
