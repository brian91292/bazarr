import { vi } from "vitest";
import { debounce } from "./function";

describe("function utilities", () => {
  describe("debounce", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("should debounce function calls", () => {
      const func = vi.fn();
      const debounced = debounce(func, 100);

      debounced();
      debounced();
      debounced();

      expect(func).not.toHaveBeenCalled();

      vi.advanceTimersByTime(100);
      expect(func).toHaveBeenCalledTimes(1);
    });

    it("should call immediately if specified", () => {
      const func = vi.fn();
      const debounced = debounce(func, 100, true);

      debounced();
      expect(func).toHaveBeenCalledTimes(1);

      debounced();
      expect(func).toHaveBeenCalledTimes(1);

      vi.advanceTimersByTime(100);
      debounced();
      expect(func).toHaveBeenCalledTimes(2);
    });
  });
});
