import { describe, expect, it } from "vitest";
import { sliceTrendForRange } from "./OverviewPage";

const points = Array.from({ length: 100 }, (_, index) => ({
  date: `day-${index + 1}`,
  actual: index,
  baseline: index,
  anomaly: false
}));

describe("sliceTrendForRange", () => {
  it.each([14, 30, 90])("returns the latest %i daily points", (range) => {
    const result = sliceTrendForRange(points, range);

    expect(result).toHaveLength(range);
    expect(result[0].date).toBe(`day-${101 - range}`);
    expect(result.at(-1)?.date).toBe("day-100");
  });

  it("does not invent points when less history is available", () => {
    expect(sliceTrendForRange(points.slice(0, 6), 90)).toHaveLength(6);
  });
});
