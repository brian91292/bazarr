export function isObject(value: unknown): value is object {
  const type = typeof value;
  return (
    value != null &&
    (type === "object" || type === "function") &&
    !Array.isArray(value)
  );
}

export function isEmpty(value: unknown): boolean {
  if (value == null) return true;
  if (Array.isArray(value) || typeof value === "string")
    return value.length === 0;
  if (value instanceof Map || value instanceof Set) return value.size === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return true;
}

export function get(
  obj: unknown,
  path: string | string[],
  defaultValue?: unknown,
): unknown {
  const travel = (regexp: RegExp) =>
    (String.prototype.split.call(path, regexp) as string[])
      .filter(Boolean)
      .reduce(
        (res, key: string) =>
          res !== null && res !== undefined ? (res as LooseObject)[key] : res,
        obj,
      );
  const result = travel(/[,[\]]+?/) || travel(/[,[\].]+?/);
  return result === undefined || result === obj ? defaultValue : result;
}

export function forIn(
  obj: unknown,
  iteratee: (value: unknown, key: string, obj: unknown) => void,
) {
  if (obj === null || typeof obj !== "object") return;
  for (const key in obj as Record<string, unknown>) {
    iteratee((obj as LooseObject)[key], key, obj);
  }
}

export function merge<T = unknown>(target: T, ...sources: unknown[]): T {
  if (!sources.length) return target;
  const source = sources.shift();

  if (isObject(target) && isObject(source)) {
    const t = target as LooseObject;
    const s = source as LooseObject;
    for (const key in s) {
      const sourceValue = s[key];
      if (isObject(sourceValue)) {
        if (!t[key]) Object.assign(t, { [key]: {} });
        merge(t[key], sourceValue);
      } else {
        Object.assign(t, { [key]: sourceValue });
      }
    }
  }

  return merge(target, ...sources);
}

export function cloneDeep<T>(value: T): T {
  if (value === null || typeof value !== "object") {
    return value;
  }

  if (Array.isArray(value)) {
    return value.map((item) => cloneDeep(item)) as LooseObject as T;
  }

  const result = {} as LooseObject;
  for (const key in value) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      result[key] = cloneDeep((value as LooseObject)[key]);
    }
  }
  return result as T;
}
