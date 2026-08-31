import { signUpWithEmail, logInWithEmail, logInWithGoogle, logOut } from "./lib/auth";

async function testFrontendAuth() {
  console.log("=== Testing Frontend Firebase Auth SDK Functions ===");
  
  try {
    console.log("Testing signUpWithEmail export...");
    console.log("typeof signUpWithEmail:", typeof signUpWithEmail);

    console.log("Testing logInWithEmail export...");
    console.log("typeof logInWithEmail:", typeof logInWithEmail);

    console.log("Testing logInWithGoogle export...");
    console.log("typeof logInWithGoogle:", typeof logInWithGoogle);

    console.log("Testing logOut export...");
    console.log("typeof logOut:", typeof logOut);

    console.log("=== Frontend Auth SDK Functions Check PASSED ===");
  } catch (err) {
    console.error("Frontend Auth test failed:", err);
    process.exit(1);
  }
}

testFrontendAuth();
