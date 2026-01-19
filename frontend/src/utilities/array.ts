export function uniq<T>(array: T[]): T[] {
  return [...new Set(array)];
}

export function uniqBy<T>(
  array: T[],
  iteratee: ((value: T) => unknown) | keyof T,
): T[] {
  const seen = new Set();
  return array.filter((item) => {
    const key =
      typeof iteratee === "function" ? iteratee(item) : item[iteratee];
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function remove<T>(array: T[], predicate: (value: T) => boolean): T[] {
  const removed: T[] = [];
  let i = array.length;
  while (i--) {
    if (predicate(array[i])) {
      removed.push(...array.splice(i, 1));
    }
  }
  return removed.reverse();
}

export function includes<T>(array: T[] | string, value: T | string): boolean {
  if (typeof array === "string") {
    return array.includes(value as string);
  }
  return array.includes(value as T);
}

export function maxBy<T>(
  array: T[],
  iteratee: ((value: T) => unknown) | keyof T,
): T | undefined {
  if (array.length === 0) return undefined;
  return array.reduce((max, current) => {
    const v1 =
      typeof iteratee === "function" ? iteratee(current) : current[iteratee];
    const v2 = typeof iteratee === "function" ? iteratee(max) : max[iteratee];
    return (v1 as number) > (v2 as number) ? current : max;
  });
}

export function difference<T>(array: T[], ...values: T[][]): T[] {
  const valuesSet = new Set(values.flat());
  return array.filter((item) => !valuesSet.has(item));
}

export function differenceWith<T, U>(
  array: T[],
  values: U[],
  comparator: (a: T, b: U) => boolean,
): T[] {
  return array.filter((a) => !values.some((b) => comparator(a, b)));
}
