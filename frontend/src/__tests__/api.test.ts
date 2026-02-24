import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getApiUrl, getWsUrl, isSecureContext } from "@/lib/constants";

// We need to mock window.location for these tests
const originalWindow = globalThis.window;

function mockLocation(overrides: Partial<Location>) {
  Object.defineProperty(globalThis, "window", {
    value: {
      ...originalWindow,
      location: {
        ...originalWindow.location,
        ...overrides,
      },
    },
    writable: true,
    configurable: true,
  });
}

describe("constants - URL builders", () => {
  afterEach(() => {
    // Restore original window
    Object.defineProperty(globalThis, "window", {
      value: originalWindow,
      writable: true,
      configurable: true,
    });
  });

  // --- getApiUrl ---

  describe("getApiUrl()", () => {
    it("returns origin + /api for an http host", () => {
      mockLocation({
        origin: "http://localhost:3000",
        protocol: "http:",
        host: "localhost:3000",
        hostname: "localhost",
      });

      expect(getApiUrl()).toBe("http://localhost:3000/api");
    });

    it("returns origin + /api for an https host", () => {
      mockLocation({
        origin: "https://rain.example.com",
        protocol: "https:",
        host: "rain.example.com",
        hostname: "rain.example.com",
      });

      expect(getApiUrl()).toBe("https://rain.example.com/api");
    });
  });

  // --- getWsUrl ---

  describe("getWsUrl()", () => {
    it("returns ws: for http connections", () => {
      mockLocation({
        origin: "http://localhost:3000",
        protocol: "http:",
        host: "localhost:3000",
        hostname: "localhost",
      });

      expect(getWsUrl()).toBe("ws://localhost:3000/ws");
    });

    it("returns wss: for https connections", () => {
      mockLocation({
        origin: "https://rain.example.com",
        protocol: "https:",
        host: "rain.example.com",
        hostname: "rain.example.com",
      });

      expect(getWsUrl()).toBe("wss://rain.example.com/ws");
    });
  });

  // --- isSecureContext ---

  describe("isSecureContext()", () => {
    it("returns true for https", () => {
      mockLocation({
        protocol: "https:",
        hostname: "rain.example.com",
      });

      expect(isSecureContext()).toBe(true);
    });

    it("returns true for localhost (even over http)", () => {
      mockLocation({
        protocol: "http:",
        hostname: "localhost",
      });

      expect(isSecureContext()).toBe(true);
    });

    it("returns true for 127.0.0.1 (even over http)", () => {
      mockLocation({
        protocol: "http:",
        hostname: "127.0.0.1",
      });

      expect(isSecureContext()).toBe(true);
    });

    it("returns false for http on a non-local hostname", () => {
      mockLocation({
        protocol: "http:",
        hostname: "rain.example.com",
      });

      expect(isSecureContext()).toBe(false);
    });
  });
});

// --- API fetch functions ---

describe("API fetch functions", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Mock window.location for getApiUrl()
    mockLocation({
      origin: "http://localhost:8000",
      protocol: "http:",
      host: "localhost:8000",
      hostname: "localhost",
    });

    // Mock global fetch
    fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(globalThis, "window", {
      value: originalWindow,
      writable: true,
      configurable: true,
    });
  });

  it("authenticate() sends PIN in the body", async () => {
    fetchSpy.mockResolvedValue({
      json: () => Promise.resolve({ token: "abc123" }),
    });

    // Dynamic import to get module after mocks are set
    const { authenticate } = await import("@/lib/api");

    const result = await authenticate("1234", "device-1", "My PC");
    expect(result).toEqual({ token: "abc123" });
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/auth",
      expect.objectContaining({
        method: "POST",
        body: expect.any(String),
      })
    );

    // Verify body content
    const callBody = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(callBody.pin).toBe("1234");
    expect(callBody.device_id).toBe("device-1");
    expect(callBody.device_name).toBe("My PC");
  });

  it("fetchMetrics() sends authorization header when token is provided", async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ totals: {}, by_hour: [], by_dow: [], by_day: [], by_month: [] }),
    });

    const { fetchMetrics } = await import("@/lib/api");

    await fetchMetrics("my-token");
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/metrics",
      expect.objectContaining({
        headers: { Authorization: "Bearer my-token" },
      })
    );
  });

  it("fetchMetrics() sends empty headers when token is null", async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ totals: {}, by_hour: [], by_dow: [], by_day: [], by_month: [] }),
    });

    const { fetchMetrics } = await import("@/lib/api");

    await fetchMetrics(null);
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/metrics",
      expect.objectContaining({
        headers: {},
      })
    );
  });

  it("browseDirectory() encodes the path parameter", async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => null },
      json: () => Promise.resolve({ current: "/home", entries: [] }),
    });

    const { browseDirectory } = await import("@/lib/api");

    await browseDirectory("/home/user/my project", "tok");
    const calledUrl = fetchSpy.mock.calls[0][0];
    expect(calledUrl).toContain(encodeURIComponent("/home/user/my project"));
  });

  it("clearMessages() uses DELETE method", async () => {
    fetchSpy.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ deleted: 5 }),
    });

    const { clearMessages } = await import("@/lib/api");

    const result = await clearMessages("/home", "agent-1", "tok");
    expect(result).toEqual({ deleted: 5 });
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/messages"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("deleteConversation() throws on non-ok response", async () => {
    fetchSpy.mockResolvedValue({
      ok: false,
      status: 404,
    });

    const { deleteConversation } = await import("@/lib/api");

    await expect(deleteConversation("conv-1", "tok")).rejects.toThrow(
      "Delete conversation failed: 404"
    );
  });
});
