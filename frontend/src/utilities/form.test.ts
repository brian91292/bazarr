import FormUtils from "./form";

describe("form utilities", () => {
  describe("validation", () => {
    it("should return null if condition is met", () => {
      const validator = FormUtils.validation(
        (v: number) => v > 0,
        "Error message",
      );
      expect(validator(1)).toBeNull();
    });

    it("should return message if condition is not met", () => {
      const validator = FormUtils.validation(
        (v: number) => v > 0,
        "Error message",
      );
      expect(validator(0)).toBe("Error message");
    });
  });
});
