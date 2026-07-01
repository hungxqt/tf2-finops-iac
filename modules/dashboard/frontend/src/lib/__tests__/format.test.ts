import { describe, it, expect } from "vitest";
import { currency, pct, formatDateTime, relativeTime } from "../format";

describe("currency", () => {
  it("formats zero", () => {
    expect(currency(0)).toBe("$0");
  });

  it("formats positive values", () => {
    const result = currency(1234.56);
    expect(result).toContain("$");
    expect(result).toContain("1");
  });

  it("formats very small values", () => {
    const result = currency(0.000123);
    expect(result).toContain("0.000123");
  });

  it("appends suffix", () => {
    const result = currency(100, "/day");
    expect(result).toContain("/day");
  });
});

describe("pct", () => {
  it("formats percentage", () => {
    expect(pct(75.3)).toBe("75.3%");
  });

  it("handles zero", () => {
    expect(pct(0)).toBe("0%");
  });
});

describe("formatDateTime", () => {
  it("returns fallback for undefined", () => {
    expect(formatDateTime(undefined)).toBe("not published");
  });

  it("formats a valid ISO string", () => {
    const result = formatDateTime("2026-07-01T12:00:00Z");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });
});

describe("relativeTime", () => {
  it("returns empty for undefined", () => {
    expect(relativeTime(undefined)).toBe("");
  });
});
