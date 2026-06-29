import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { sampleDashboardData } from "./sampleData";

function renderWithClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe("App", () => {
  it("renders the read-only action policy and never calls mutation endpoints", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("dashboard_runtime_config.json")) {
        return Response.json({ data_prefix: "/summaries/" });
      }
      if (path.includes("/summaries/dashboard-summary.json")) {
        return Response.json(sampleDashboardData);
      }
      throw new Error(`unexpected fetch ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<App />);

    // Sidebar nav items should be present
    expect(await screen.findByText("Finance Overview")).toBeInTheDocument();

    // No /v1/* calls
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/v1/"),
      expect.anything()
    );
  });
});
