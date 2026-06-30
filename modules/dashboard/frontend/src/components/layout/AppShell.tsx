import { useState, useEffect, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import type { DashboardSummary } from "../../schema";

type PageKey = "overview" | "engineering" | "containment" | "collaboration" | "audit" | "admin";

interface AppShellProps {
  summary: DashboardSummary;
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  children: ReactNode;
  pageTitle: string;
}

export function AppShell({ summary, activePage, onNavigate, children, pageTitle }: AppShellProps) {
  const [expanded, setExpanded] = useState<boolean>(() => {
    try {
      return localStorage.getItem("finops-sidebar") !== "collapsed";
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("finops-sidebar", expanded ? "expanded" : "collapsed");
    } catch {
      // ignore
    }
  }, [expanded]);

  return (
    <div className="flex h-screen overflow-hidden bg-surface-base">
      <Sidebar
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
        activePage={activePage}
        onNavigate={onNavigate}
        summary={summary}
      />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Topbar title={pageTitle} summary={summary} />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
