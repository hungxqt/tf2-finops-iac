import { useState, useEffect, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import type { DashboardSummary } from "../../schema";

interface AppShellProps {
  summary: DashboardSummary;
  children: ReactNode;
}

const PAGE_TITLES: Record<string, string> = {
  "/":            "Finance Overview",
  "/engineering": "Engineering Triage",
  "/containment": "Containment & Audit",
  "/collaboration": "Collaboration",
  "/audit":       "Audit Evidence Diffs",
  "/admin":       "Admin Settings",
};

export function AppShell({ summary, children }: AppShellProps) {
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
      <Sidebar expanded={expanded} onToggle={() => setExpanded((v) => !v)} summary={summary} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Topbar summary={summary} pageTitles={PAGE_TITLES} />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
