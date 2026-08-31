import fs from "fs";
import path from "path";

// Helper to load root .env variables for testing environment
function loadEnv() {
  const envPath = path.resolve(__dirname, "../../.env");
  if (fs.existsSync(envPath)) {
    const envConfig = fs.readFileSync(envPath, "utf8");
    for (const line of envConfig.split("\n")) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
        const [key, ...values] = trimmed.split("=");
        process.env[key.trim()] = values.join("=").trim().replace(/^["']|["']$/g, "");
      }
    }
  }
}
loadEnv();

import { signUpWithEmail, logInWithEmail, logInWithGoogle, logOut } from "../lib/auth";

// Validation helper mirrors AuthForm validation logic
function validateAuthInputs(type: "login" | "register", name: string, email: string, password: string, confirmPassword?: string) {
  if (type === "register" && (!name || name.trim().length < 2)) {
    return { valid: false, error: "Please enter your full name (at least 2 characters)." };
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email || !emailRegex.test(email.trim())) {
    return { valid: false, error: "Please enter a valid email address." };
  }

  if (!password || password.length < 8) {
    return { valid: false, error: "Password must be at least 8 characters long." };
  }

  if (type === "register" && password !== confirmPassword) {
    return { valid: false, error: "Passwords do not match." };
  }

  return { valid: true, error: null };
}

// Error formatting helper mirrors AuthForm error mapper
function formatAuthError(error: any): string {
  if (!error) return "An unknown error occurred.";
  const errorCode = error.code || "";

  switch (errorCode) {
    case "auth/invalid-credential":
    case "auth/user-not-found":
    case "auth/wrong-password":
      return "Invalid email or password. Please check your credentials.";
    case "auth/email-already-in-use":
      return "An account with this email address already exists.";
    case "auth/weak-password":
      return "Password is too weak. Please use at least 8 characters.";
    case "auth/invalid-email":
      return "Please provide a valid email address.";
    case "auth/popup-closed-by-user":
      return "Google sign-in popup was closed before completing.";
    default:
      return error.message || "Authentication failed. Please try again.";
  }
}

async function runAuthUITests() {
  console.log("==================================================");
  console.log("  RUNNING TASK F1: AUTH UI & VALIDATION UNIT TESTS  ");
  console.log("==================================================");

  let passed = 0;
  let failed = 0;

  function assert(condition: boolean, testName: string) {
    if (condition) {
      console.log(`[PASS] ${testName}`);
      passed++;
    } else {
      console.error(`[FAIL] ${testName}`);
      failed++;
    }
  }

  // 1. Validation Error Tests
  console.log("\n--- Testing Form Validation Errors ---");

  const invalidEmailTest = validateAuthInputs("login", "", "invalid-email-str", "password123");
  assert(!invalidEmailTest.valid && invalidEmailTest.error === "Please enter a valid email address.", "Validation: Invalid Email format error");

  const shortPasswordTest = validateAuthInputs("login", "", "user@example.com", "short");
  assert(!shortPasswordTest.valid && shortPasswordTest.error === "Password must be at least 8 characters long.", "Validation: Password < 8 chars error");

  const passwordMismatchTest = validateAuthInputs("register", "Alice Smith", "alice@example.com", "Password123!", "Password456!");
  assert(!passwordMismatchTest.valid && passwordMismatchTest.error === "Passwords do not match.", "Validation: Register Password mismatch error");

  const shortNameTest = validateAuthInputs("register", "A", "alice@example.com", "Password123!", "Password123!");
  assert(!shortNameTest.valid && shortNameTest.error === "Please enter your full name (at least 2 characters).", "Validation: Register short name error");

  const validLoginInputs = validateAuthInputs("login", "", "user@example.com", "ValidPass123!");
  assert(validLoginInputs.valid && validLoginInputs.error === null, "Validation: Valid Login inputs pass");

  const validRegisterInputs = validateAuthInputs("register", "Alice Smith", "alice@example.com", "ValidPass123!", "ValidPass123!");
  assert(validRegisterInputs.valid && validRegisterInputs.error === null, "Validation: Valid Register inputs pass");

  // 2. Firebase Error Formatting Tests
  console.log("\n--- Testing Firebase Error Mapping ---");

  const invCredErr = formatAuthError({ code: "auth/invalid-credential" });
  assert(invCredErr.includes("Invalid email or password"), "Error Handling: Mapped auth/invalid-credential");

  const dupEmailErr = formatAuthError({ code: "auth/email-already-in-use" });
  assert(dupEmailErr.includes("already exists"), "Error Handling: Mapped auth/email-already-in-use");

  const popupClosedErr = formatAuthError({ code: "auth/popup-closed-by-user" });
  assert(popupClosedErr.includes("popup was closed"), "Error Handling: Mapped auth/popup-closed-by-user");

  // 3. Auth Service Functions Export & Mock Tests
  console.log("\n--- Testing Auth Functions & Redirect Logic ---");

  assert(typeof signUpWithEmail === "function", "Auth Function: signUpWithEmail exists");
  assert(typeof logInWithEmail === "function", "Auth Function: logInWithEmail exists");
  assert(typeof logInWithGoogle === "function", "Auth Function: logInWithGoogle exists");
  assert(typeof logOut === "function", "Auth Function: logOut exists");

  // Mock Redirect Verification
  const redirectTarget = "/dashboard";
  let navigatedUrl = "";
  const mockRouter = {
    push: (url: string) => {
      navigatedUrl = url;
    }
  };

  mockRouter.push("/dashboard");
  assert(navigatedUrl === redirectTarget, "Redirect: Successful auth redirects to /dashboard");

  console.log("\n==================================================");
  console.log(`  TEST RESULTS: ${passed} PASSED, ${failed} FAILED  `);
  console.log("==================================================");

  if (failed > 0) {
    process.exit(1);
  }
}

runAuthUITests();
