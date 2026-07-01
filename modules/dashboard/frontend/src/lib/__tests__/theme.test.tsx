import { describe, it, expect } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { ThemeProvider } from "../theme";
import { useTheme } from "../theme-context";
import type { ReactNode } from "react";

function wrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

describe("useTheme", () => {
  it("provides dark theme by default in test environment", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("dark");
  });

  it("toggles theme", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    act(() => {
      result.current.toggle();
    });
    expect(result.current.theme).toBe("light");
    act(() => {
      result.current.toggle();
    });
    expect(result.current.theme).toBe("dark");
  });
});
