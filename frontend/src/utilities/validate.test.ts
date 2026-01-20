import {
  isArray,
  isEpisode,
  isMovie,
  isNull,
  isNumber,
  isSeries,
  isString,
  isUndefined,
} from "./validate";

describe("validate utilities", () => {
  it("isMovie should check for radarrId", () => {
    expect(isMovie({ radarrId: 1 })).toBe(true);
    expect(isMovie({ id: 1 })).toBe(false);
  });

  it("isEpisode should check for sonarrEpisodeId", () => {
    expect(isEpisode({ sonarrEpisodeId: 1 })).toBe(true);
    expect(isEpisode({ id: 1 })).toBe(false);
  });

  it("isSeries should check for episodeFileCount", () => {
    expect(isSeries({ episodeFileCount: 1 })).toBe(true);
    expect(isSeries({ id: 1 })).toBe(false);
  });

  it("isNull should check for null", () => {
    expect(isNull(null)).toBe(true);
    expect(isNull(undefined)).toBe(false);
  });

  it("isUndefined should check for undefined", () => {
    expect(isUndefined(undefined)).toBe(true);
    expect(isUndefined(null)).toBe(false);
  });

  it("isString should check for string", () => {
    expect(isString("")).toBe(true);
    expect(isString(1)).toBe(false);
  });

  it("isNumber should check for number", () => {
    expect(isNumber(1)).toBe(true);
    expect(isNumber(NaN)).toBe(false);
    expect(isNumber("1")).toBe(false);
  });

  it("isArray should check for array", () => {
    expect(isArray([])).toBe(true);
    expect(isArray({})).toBe(false);
  });
});
