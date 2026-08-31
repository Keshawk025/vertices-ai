import { app, auth, db, storage, googleProvider, emailProvider } from "../lib/firebase";

describe("Firebase Frontend SDK Initialization", () => {
  it("should initialize Firebase App", () => {
    expect(app).toBeDefined();
    expect(app.name).toEqual("[DEFAULT]");
  });

  it("should initialize Auth module with providers", () => {
    expect(auth).toBeDefined();
    expect(googleProvider).toBeDefined();
    expect(googleProvider.providerId).toEqual("google.com");
    expect(emailProvider).toBeDefined();
    expect(emailProvider.providerId).toEqual("password");
  });

  it("should initialize Firestore module", () => {
    expect(db).toBeDefined();
    expect(db.type).toEqual("firestore");
  });

  it("should initialize Storage module", () => {
    expect(storage).toBeDefined();
  });
});
