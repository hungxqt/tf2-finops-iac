import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { loadDashboardSummary } from "./data";
import { AppShell } from "./components/layout/AppShell";
import { SkeletonLoader } from "./components/ui/SkeletonLoader";
import { OverviewPage }      from "./pages/OverviewPage";
import { EngineeringPage }   from "./pages/EngineeringPage";
import { ContainmentPage }   from "./pages/ContainmentPage";
import { CollaborationPage } from "./pages/CollaborationPage";
import { AuditPage }         from "./pages/AuditPage";
import { AdminPage }         from "./pages/AdminPage";
import type { DashboardSummary } from "./schema";

type PageKey = "overview" | "engineering" | "containment" | "collaboration" | "audit" | "admin";

const PAGE_TITLES: Record<PageKey, string> = {
  overview:      "Finance Overview",
  engineering:   "Engineering Triage",
  containment:   "Containment & Audit",
  collaboration: "Collaboration",
  audit:         "Audit Evidence Diffs",
  admin:         "Admin Settings",
};

function useActivePageState(): [PageKey, (p: PageKey) => void] {
  const [page, setPage] = useState<PageKey>(() => {
    try {
      const saved = localStorage.getItem("finops-active-page");
      if (saved && saved in PAGE_TITLES) return saved as PageKey;
    } catch {
      // ignore
    }
    return "overview";
  });

  const navigate = (p: PageKey) => {
    setPage(p);
    try { localStorage.setItem("finops-active-page", p); } catch { /* ignore */ }
  };

  return [page, navigate];
}

function renderPage(page: PageKey, summary: DashboardSummary) {
  switch (page) {
    case "overview":      return <OverviewPage      summary={summary} />;
    case "engineering":   return <EngineeringPage   summary={summary} />;
    case "containment":   return <ContainmentPage   summary={summary} />;
    case "collaboration": return <CollaborationPage summary={summary} />;
    case "audit":         return <AuditPage         summary={summary} />;
    case "admin":         return <AdminPage         summary={summary} />;
  }
}

function LoadingState() {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-base">
      {/* Sidebar skeleton */}
      <div className="w-60 shrink-0 bg-surface-panel border-r border-border-subtle flex flex-col p-3 gap-3">
        <div className="h-8 mb-2 animate-shimmer rounded-lg" />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-8 animate-shimmer rounded-md" />
        ))}
      </div>
      {/* Main skeleton */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <div className="h-14 bg-surface-panel border-b border-border-subtle animate-shimmer" />
        <div className="flex-1 p-6 space-y-6">
          <div className="h-10 w-64 animate-shimmer rounded-md" />
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonLoader key={i} variant="kpi" />
            ))}
          </div>
          <SkeletonLoader variant="card" height="320px" />
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center min-h-screen bg-surface-base p-4">
      <div className="bg-surface-panel border border-accent-red/30 rounded-xl p-10 max-w-xl w-full text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-accent-red mx-auto" />
        <h1 className="text-xl font-bold text-text-primary">Data Contract Error</h1>
        <p className="text-sm text-text-secondary">{message}</p>
        <div className="bg-surface-base rounded-lg p-3 text-left">
          <code className="font-mono text-xs text-text-muted break-all">
            The production dashboard does not fallback to sample data.
            Publish a valid dashboard-summary.json to the S3 data bucket.
          </code>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const [activePage, navigate] = useActivePageState();
  const query = useQuery({ queryKey: ["dashboard-summary"], queryFn: loadDashboardSummary });

  // Reset to overview if admin page is loaded by non-admin
  useEffect(() => {
    if (query.data && activePage === "admin") {
      const role = query.data.viewer_role.toLowerCase();
      if (!["admin", "cdo"].includes(role)) {
        navigate("overview");
      }
    }
  }, [query.data, activePage, navigate]);

  if (query.isLoading) return <LoadingState />;
  if (query.isError)   return <ErrorState message={query.error instanceof Error ? query.error.message : "Unknown error"} />;
  if (!query.data)     return <ErrorState message="Dashboard summary was empty after loading." />;

  const summary = query.data;

  return (
    <AppShell
      summary={summary}
      activePage={activePage}
      onNavigate={navigate}
      pageTitle={PAGE_TITLES[activePage]}
    >
      {renderPage(activePage, summary)}
    </AppShell>
  );
}
