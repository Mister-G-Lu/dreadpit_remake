export function validateCredentials(mode, username, password) {
  const name = String(username || "").trim();
  if (!name || !password) return "Please enter a username and password.";
  if (mode === "register") {
    if (!/^[a-zA-Z0-9_]{3,20}$/.test(name)) {
      return "Username must be 3–20 letters, numbers, or underscores.";
    }
    if (String(password).length < 6) return "Password must be at least 6 characters.";
  }
  return "";
}
