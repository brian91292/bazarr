import {
  difference,
  differenceWith,
  includes,
  maxBy,
  remove,
  uniq,
  uniqBy,
} from "./array";

describe("array utilities", () => {
  describe("uniq", () => {
    it("should remove duplicate values", () => {
      expect(uniq([1, 2, 2, 3, 1])).toEqual([1, 2, 3]);
    });

    it("should handle empty arrays", () => {
      expect(uniq([])).toEqual([]);
    });
  });

  describe("uniqBy", () => {
    it("should remove duplicates based on iteratee function", () => {
      const input = [{ id: 1 }, { id: 2 }, { id: 1 }];
      expect(uniqBy(input, (item) => item.id)).toEqual([{ id: 1 }, { id: 2 }]);
    });

    it("should remove duplicates based on property name", () => {
      const input = [{ id: 1 }, { id: 2 }, { id: 1 }];
      expect(uniqBy(input, "id")).toEqual([{ id: 1 }, { id: 2 }]);
    });
  });

  describe("remove", () => {
    it("should remove elements that match the predicate and return them", () => {
      const array = [1, 2, 3, 4];
      const removed = remove(array, (n) => n % 2 === 0);
      expect(array).toEqual([1, 3]);
      expect(removed).toEqual([2, 4]);
    });
  });

  describe("includes", () => {
    it("should check if array includes a value", () => {
      expect(includes([1, 2, 3], 2)).toBe(true);
      expect(includes([1, 2, 3], 4)).toBe(false);
    });

    it("should check if string includes a substring", () => {
      expect(includes("hello world", "hello")).toBe(true);
      expect(includes("hello world", "foo")).toBe(false);
    });
  });

  describe("maxBy", () => {
    it("should find the maximum element based on iteratee function", () => {
      const input = [{ n: 1 }, { n: 5 }, { n: 2 }];
      expect(maxBy(input, (o) => o.n)).toEqual({ n: 5 });
    });

    it("should find the maximum element based on property name", () => {
      const input = [{ n: 1 }, { n: 5 }, { n: 2 }];
      expect(maxBy(input, "n")).toEqual({ n: 5 });
    });

    it("should return undefined for empty arrays", () => {
      expect(maxBy([], "n")).toBeUndefined();
    });
  });

  describe("difference", () => {
    it("should return the difference of arrays", () => {
      expect(difference([2, 1], [2, 3])).toEqual([1]);
      expect(difference([1, 2, 1], [2], [3])).toEqual([1, 1]);
    });
  });

  describe("differenceWith", () => {
    it("should return the difference using a comparator", () => {
      const objects = [
        { x: 1, y: 2 },
        { x: 2, y: 1 },
      ];
      const result = differenceWith(
        objects,
        [{ x: 1, y: 2 }],
        (a, b) => a.x === b.x && a.y === b.y,
      );
      expect(result).toEqual([{ x: 2, y: 1 }]);
    });
  });
});
