const getImportMetaEnv = (): ImportMeta["env"] => {
  try {
    return import.meta.env;
  } catch {
    return {} as unknown as ImportMeta["env"];
  }
};

const env = getImportMetaEnv();

export const isDevEnv = env.MODE === "development";
export const isProdEnv = env.MODE === "production";
export const isTestEnv = env.MODE === "test" || process.env.NODE_ENV === "test";

export const Environment = {
  get apiKey(): string | undefined {
    if (isDevEnv) {
      return env.VITE_API_KEY;
    } else if (isTestEnv) {
      return undefined;
    } else {
      return window.Bazarr.apiKey;
    }
  },
  get canUpdate(): boolean {
    if (isDevEnv) {
      return env.VITE_CAN_UPDATE === "true";
    } else if (isTestEnv) {
      return false;
    } else {
      return window.Bazarr.canUpdate;
    }
  },
  get hasUpdate(): boolean {
    if (isDevEnv) {
      return env.VITE_HAS_UPDATE === "true";
    } else if (isTestEnv) {
      return false;
    } else {
      return window.Bazarr.hasUpdate;
    }
  },
  get baseUrl(): string {
    if (isDevEnv || isTestEnv) {
      return "";
    } else {
      let url = window.Bazarr.baseUrl;
      if (url.endsWith("/")) {
        url = url.slice(0, -1);
      }
      return url;
    }
  },
  get queryDev(): boolean {
    if (isDevEnv) {
      return env.VITE_QUERY_DEV === "true";
    }
    return false;
  },
};
