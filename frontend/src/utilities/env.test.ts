import { vi } from "vitest";
import { Environment, isTestEnv } from "./env";

describe("env utilities", () => {
  it("isTestEnv should be true in test environment", () => {
    expect(isTestEnv).toBe(true);
  });

  describe("Environment", () => {
    beforeEach(() => {
      vi.stubGlobal("window", {
        Bazarr: {
          apiKey: "window-api-key",
          canUpdate: true,
          hasUpdate: false,
          baseUrl: "/bazarr/",
        },
      });
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("apiKey should return undefined in test env", () => {
      expect(Environment.apiKey).toBeUndefined();
    });

    it("canUpdate should return false in test env", () => {
      expect(Environment.canUpdate).toBe(false);
    });

    it("hasUpdate should return false in test env", () => {
      expect(Environment.hasUpdate).toBe(false);
    });

    it("baseUrl should return empty string in test env", () => {
      expect(Environment.baseUrl).toBe("");
    });

    it("queryDev should return false in test env", () => {
      expect(Environment.queryDev).toBe(false);
    });
  });
});
