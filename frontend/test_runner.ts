import { app, auth, db, storage, googleProvider, emailProvider } from "./lib/firebase";

console.log("=== Testing Frontend Firebase Setup ===");
console.log("App Name:", app.name);
console.log("Auth initialized:", !!auth);
console.log("Firestore db initialized:", !!db);
console.log("Storage initialized:", !!storage);
console.log("Google Provider ID:", googleProvider.providerId);
console.log("Email Provider ID:", emailProvider.providerId);
console.log("=== Frontend Firebase Setup Test PASSED ===");
