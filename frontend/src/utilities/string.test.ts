import { capitalize, startCase, uniqueId } from "./string";

describe("string utilities", () => {
  describe("uniqueId", () => {
    it("should generate unique IDs", () => {
      const id1 = uniqueId();
      const id2 = uniqueId();
      expect(id1).not.toBe(id2);
    });

    it("should use prefix", () => {
      const id = uniqueId("prefix_");
      expect(id).toMatch(/^prefix_\d+$/);
    });
  });

  describe("capitalize", () => {
    it("should capitalize the first letter and lowercase the rest", () => {
      expect(capitalize("fOO")).toBe("Foo");
      expect(capitalize("BAR")).toBe("Bar");
    });

    it("should handle empty strings", () => {
      expect(capitalize("")).toBe("");
    });
  });

  describe("startCase", () => {
    it("should convert string to start case", () => {
      expect(startCase("foo_bar")).toBe("Foo Bar");
      expect(startCase("fooBar")).toBe("Foo Bar");
      expect(startCase("__foo_bar__")).toBe("  Foo Bar  ");
    });

    it("should handle empty strings", () => {
      expect(startCase("")).toBe("");
    });
  });
});
