export function isMovie(v: object): v is Item.Movie {
  return "radarrId" in v;
}

export function isEpisode(v: object): v is Item.Episode {
  return "sonarrEpisodeId" in v;
}

export function isSeries(v: object): v is Item.Series {
  return "episodeFileCount" in v;
}

export function isNull(v: unknown): v is null {
  return v === null;
}

export function isUndefined(v: unknown): v is undefined {
  return v === undefined;
}

export function isString(v: unknown): v is string {
  return typeof v === "string";
}

export function isNumber(v: unknown): v is number {
  return typeof v === "number" && !isNaN(v);
}

export function isArray(v: unknown): v is unknown[] {
  return Array.isArray(v);
}
