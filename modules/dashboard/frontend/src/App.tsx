import { useEffect, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { loadDashboardSummary } from "./data";
import { AppShell } from "./components/layout/AppShell";
import { SkeletonLoader } from "./components/ui/SkeletonLoader";
import { ErrorBoundary } from "./components/error/ErrorBoundary";
import { PageErrorFallback } from "./components/error/PageErrorFallback";
import type { DashboardSummary } from "./schema";

import { OverviewPage } from "./pages/OverviewPage";
import { EngineeringPage } from "./pages/EngineeringPage";
import { ContainmentPage } from "./pages/ContainmentPage";
import { CollaborationPage } from "./pages/CollaborationPage";
import { AuditPage } from "./pages/AuditPage";
import { AdminPage } from "./pages/AdminPage";

function PageSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <SkeletonLoader variant="card" height="80px" />
      <div className="grid grid-cols-4 gap-4 max-md:grid-cols-2 max-sm:grid-cols-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonLoader key={i} variant="kpi" />
        ))}
      </div>
      <SkeletonLoader variant="card" height="320px" />
    </div>
  );
}

interface PageWrapperProps {
  children: React.ReactNode;
}

function PageWrapper({ children }: PageWrapperProps) {
  return (
    <ErrorBoundary fallback={<PageErrorFallback />}>
      <Suspense fallback={<PageSkeleton />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

function AdminGuard({ summary, children }: { summary: DashboardSummary; children: React.ReactNode }) {
  const navigate = useNavigate();
  const isAdmin = ["admin", "cdo"].includes(summary.viewer_role.toLowerCase());

  useEffect(() => {
    if (!isAdmin) {
      navigate("/", { replace: true });
    }
  }, [isAdmin, navigate]);

  if (!isAdmin) return null;
  return <>{children}</>;
}

function AppShellLayout() {
  const query = useQuery({ queryKey: ["dashboard-summary"], queryFn: loadDashboardSummary });
  const location = useLocation();

  if (query.isLoading) return <LoadingState />;
  if (query.isError)   return <ErrorState message={query.error instanceof Error ? query.error.message : "Unknown error"} />;
  if (!query.data)     return <ErrorState message="Dashboard summary was empty after loading." />;

  const summary = query.data;

  return (
    <AppShell summary={summary}>
      <Routes location={location} key={location.pathname}>
        <Route index element={<PageWrapper><OverviewPage summary={summary} /></PageWrapper>} />
        <Route path="engineering" element={<PageWrapper><EngineeringPage summary={summary} /></PageWrapper>} />
        <Route path="containment" element={<PageWrapper><ContainmentPage summary={summary} /></PageWrapper>} />
        <Route path="collaboration" element={<PageWrapper><CollaborationPage summary={summary} /></PageWrapper>} />
        <Route path="audit" element={<PageWrapper><AuditPage summary={summary} /></PageWrapper>} />
        <Route path="admin" element={
          <AdminGuard summary={summary}>
            <PageWrapper><AdminPage summary={summary} /></PageWrapper>
          </AdminGuard>
        } />
      </Routes>
    </AppShell>
  );
}

function LoadingState() {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-base">
      <div className="w-60 shrink-0 bg-surface-panel border-r border-border-subtle flex flex-col p-3 gap-3">
        <div className="h-8 mb-2 animate-shimmer rounded-lg" />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-8 animate-shimmer rounded-md" />
        ))}
      </div>
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
  return (
    <BrowserRouter>
      <AppShellLayout />
    </BrowserRouter>
  );
}
