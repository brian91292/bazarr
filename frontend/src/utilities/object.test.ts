import { cloneDeep, forIn, get, isEmpty, isObject, merge } from "./object";

describe("object utilities", () => {
  describe("isObject", () => {
    it("should return true for objects and functions", () => {
      expect(isObject({})).toBe(true);
      expect(isObject(() => undefined)).toBe(true);
      expect(isObject(new Date())).toBe(true);
    });

    it("should return false for arrays, null, and primitives", () => {
      expect(isObject([])).toBe(false);
      expect(isObject(null)).toBe(false);
      expect(isObject(1)).toBe(false);
      expect(isObject("a")).toBe(false);
      expect(isObject(true)).toBe(false);
    });

    it("should return false for undefined", () => {
      expect(isObject(undefined)).toBe(false);
    });
  });

  describe("isEmpty", () => {
    it("should return true for empty values", () => {
      expect(isEmpty(null)).toBe(true);
      expect(isEmpty(undefined)).toBe(true);
      expect(isEmpty("")).toBe(true);
      expect(isEmpty([])).toBe(true);
      expect(isEmpty({})).toBe(true);
      expect(isEmpty(new Map())).toBe(true);
      expect(isEmpty(new Set())).toBe(true);
    });

    it("should return false for non-empty values", () => {
      expect(isEmpty("a")).toBe(false);
      expect(isEmpty([1])).toBe(false);
      expect(isEmpty({ a: 1 })).toBe(false);
      const map = new Map();
      map.set("a", 1);
      expect(isEmpty(map)).toBe(false);
    });
  });

  describe("get", () => {
    const obj = { a: [{ b: { c: 3 } }] };

    it("should get a value at a path", () => {
      expect(get(obj, "a[0].b.c")).toBe(3);
      expect(get(obj, ["a", "0", "b", "c"])).toBe(3);
    });

    it("should return default value if path does not exist", () => {
      expect(get(obj, "a.b.c", "default")).toBe("default");
    });
  });

  describe("forIn", () => {
    it("should iterate over object properties", () => {
      const obj = { a: 1, b: 2 };
      const keys: string[] = [];
      const values: number[] = [];
      forIn(obj, (value, key) => {
        keys.push(key);
        values.push(value as number);
      });
      expect(keys).toEqual(["a", "b"]);
      expect(values).toEqual([1, 2]);
    });

    it("should handle null/non-object", () => {
      let called = false;
      forIn(null, () => {
        called = true;
      });
      expect(called).toBe(false);
    });
  });

  describe("merge", () => {
    it("should deeply merge objects", () => {
      const target = { a: { b: 1 } };
      const source = { a: { c: 2 }, d: 3 };
      const result = merge(target, source);
      expect(result).toEqual({ a: { b: 1, c: 2 }, d: 3 });
    });

    it("should handle multiple sources", () => {
      const target = { a: 1 };
      const result = merge(target, { b: 2 }, { c: 3 });
      expect(result).toEqual({ a: 1, b: 2, c: 3 });
    });
  });

  describe("cloneDeep", () => {
    it("should deeply clone an object", () => {
      const obj = { a: { b: 1 }, c: [1, 2] };
      const clone = cloneDeep(obj);
      expect(clone).toEqual(obj);
      expect(clone).not.toBe(obj);
      expect(clone.a).not.toBe(obj.a);
      expect(clone.c).not.toBe(obj.c);
    });

    it("should handle primitives", () => {
      expect(cloneDeep(1)).toBe(1);
      expect(cloneDeep("a")).toBe("a");
      expect(cloneDeep(null)).toBe(null);
    });
  });
});
