import { vi } from "vitest";
import {
  BuildKey,
  filterSubtitleBy,
  fromPython,
  GetItemId,
  pathJoin,
  Reload,
  ScrollToTop,
  toggleState,
  toPython,
} from "./index";

describe("index utilities", () => {
  describe("Reload", () => {
    it("should call window.location.reload", () => {
      const reloadSpy = vi.fn();
      vi.stubGlobal("location", { reload: reloadSpy });
      Reload();
      expect(reloadSpy).toHaveBeenCalled();
      vi.unstubAllGlobals();
    });
  });

  describe("ScrollToTop", () => {
    it("should call window.scrollTo", () => {
      const scrollToSpy = vi.fn();
      vi.stubGlobal("scrollTo", scrollToSpy);
      ScrollToTop();
      expect(scrollToSpy).toHaveBeenCalledWith(0, 0);
      vi.unstubAllGlobals();
    });
  });
  describe("toggleState", () => {
    it("should toggle state and then back", () => {
      vi.useFakeTimers();
      const dispatch = vi.fn();
      toggleState(dispatch, 100);
      expect(dispatch).toHaveBeenCalledWith(true);
      vi.advanceTimersByTime(100);
      expect(dispatch).toHaveBeenCalledWith(false);
      vi.useRealTimers();
    });
  });

  describe("GetItemId", () => {
    it("should return radarrId for movie", () => {
      expect(GetItemId({ radarrId: 123 })).toBe(123);
    });

    it("should return sonarrEpisodeId for episode", () => {
      expect(GetItemId({ sonarrEpisodeId: 456 })).toBe(456);
    });

    it("should return sonarrSeriesId for series", () => {
      expect(GetItemId({ sonarrSeriesId: 789, episodeFileCount: 1 })).toBe(789);
    });

    it("should return undefined for unknown items", () => {
      expect(GetItemId({ id: 1 })).toBeUndefined();
    });
  });

  describe("BuildKey", () => {
    it("should join arguments with -", () => {
      expect(BuildKey("a", 1, "b")).toBe("a-1-b");
    });
  });

  describe("pathJoin", () => {
    it("should join path parts and normalize separators", () => {
      expect(pathJoin("a", "b", "c")).toBe("a/b/c");
      expect(pathJoin("a/", "/b", "//c")).toBe("a/b/c");
    });
  });

  describe("filterSubtitleBy", () => {
    const subtitles: Subtitle[] = [
      {
        code2: "en",
        path: "/path/to/en",
        name: "English",
        forced: false,
        hi: false,
      },
      { code2: "fr", path: null, name: "French", forced: false, hi: false },
      {
        code2: "es",
        path: "/path/to/es",
        name: "Spanish",
        forced: false,
        hi: false,
      },
    ];

    it("should return subtitles with path if no languages specified", () => {
      const result = filterSubtitleBy(subtitles, []);
      expect(result).toHaveLength(2);
      expect(result.map((s) => s.code2)).toEqual(["en", "es"]);
    });

    it("should return items matching specified languages", () => {
      const result = filterSubtitleBy(subtitles, [
        { code2: "fr", name: "French" },
        { code2: "en", name: "English" },
      ]);
      expect(result).toHaveLength(3);
    });
  });

  describe("fromPythonConversion", () => {
    it("should convert a true value", () => {
      expect(fromPython("True")).toBe(true);
    });

    it("should convert a false value", () => {
      expect(fromPython("False")).toBe(false);
    });

    it("should convert an undefined value", () => {
      expect(fromPython(undefined)).toBe(false);
    });
  });

  describe("toPythonConversion", () => {
    it("should convert a true value", () => {
      expect(toPython(true)).toBe("True");
    });

    it("should convert a false value", () => {
      expect(toPython(false)).toBe("False");
    });
  });
});
