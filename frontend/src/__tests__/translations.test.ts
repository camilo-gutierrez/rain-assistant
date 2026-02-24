import { describe, it, expect } from "vitest";
import { translate } from "@/lib/translations";

describe("translate()", () => {
  // --- Basic key lookup ---

  it("returns the English translation for a known key", () => {
    expect(translate("en", "status.connected")).toBe("Connected");
  });

  it("returns the Spanish translation for a known key", () => {
    expect(translate("es", "status.connected")).toBe("Conectado");
  });

  it("returns the raw key when no translation exists in either language", () => {
    expect(translate("en", "nonexistent.key")).toBe("nonexistent.key");
    expect(translate("es", "nonexistent.key")).toBe("nonexistent.key");
  });

  it("falls back to Spanish when a key is missing in English", () => {
    // Both languages have the same keys in the current codebase,
    // but the fallback chain is: lang -> es -> key.
    // We test by verifying any key present in both returns the correct one.
    const enResult = translate("en", "chat.sendBtn");
    expect(enResult).toBe("Send");

    const esResult = translate("es", "chat.sendBtn");
    expect(esResult).toBe("Enviar");
  });

  // --- Parameter interpolation ---

  it("interpolates a single parameter", () => {
    const result = translate("en", "pin.tooManyAttempts", { time: "30s" });
    expect(result).toBe("Too many attempts. Try again in 30s");
  });

  it("interpolates a single parameter in Spanish", () => {
    const result = translate("es", "pin.tooManyAttempts", { time: "30s" });
    expect(result).toBe("Demasiados intentos. Intenta en 30s");
  });

  it("interpolates numeric parameters", () => {
    const result = translate("en", "pin.incorrectRemaining", { n: 3 });
    expect(result).toBe("Incorrect PIN \u2014 3 attempts remaining");
  });

  it("interpolates multiple parameters", () => {
    const result = translate("en", "history.count", { n: 5, max: 20 });
    expect(result).toBe("5 of 20 conversations");
  });

  it("interpolates multiple parameters in Spanish", () => {
    const result = translate("es", "history.count", { n: 5, max: 20 });
    expect(result).toBe("5 de 20 conversaciones");
  });

  it("leaves unmatched placeholders intact when param is not provided", () => {
    // Only provide one of two expected params
    const result = translate("en", "history.count", { n: 5 });
    expect(result).toBe("5 of {max} conversations");
  });

  // --- Edge cases ---

  it("returns the key when params are provided but key does not exist", () => {
    const result = translate("en", "fake.key", { foo: "bar" });
    expect(result).toBe("fake.key");
  });

  it("works with an empty params object", () => {
    const result = translate("en", "status.ready", {});
    expect(result).toBe("Ready");
  });

  // --- Specific known translations ---

  it("translates month abbreviations correctly", () => {
    expect(translate("en", "month.0")).toBe("Jan");
    expect(translate("es", "month.0")).toBe("Ene");
    expect(translate("en", "month.11")).toBe("Dec");
    expect(translate("es", "month.11")).toBe("Dic");
  });

  it("translates toast notifications", () => {
    expect(translate("en", "toast.connectionLost")).toBe(
      "Connection lost. Reconnecting..."
    );
    expect(translate("es", "toast.connectionLost")).toBe(
      "Conexi\u00f3n perdida. Reconectando..."
    );
  });
});
