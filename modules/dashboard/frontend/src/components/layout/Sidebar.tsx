import {
  LayoutDashboard,
  Cpu,
  ShieldCheck,
  Users,
  FileSearch,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { DashboardSummary } from "../../schema";

type PageKey = "overview" | "engineering" | "containment" | "collaboration" | "audit" | "admin";

interface SidebarProps {
  expanded: boolean;
  onToggle: () => void;
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  summary: DashboardSummary;
}

interface NavItem {
  key: PageKey;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { key: "overview",      label: "Overview",          icon: LayoutDashboard },
  { key: "engineering",   label: "Engineering Triage", icon: Cpu },
  { key: "containment",   label: "Containment",        icon: ShieldCheck },
  { key: "collaboration", label: "Collaboration",       icon: Users },
  { key: "audit",         label: "Audit Diffs",         icon: FileSearch },
  { key: "admin",         label: "Admin Settings",      icon: Settings, adminOnly: true },
];

function isAdmin(role: string) {
  return ["admin", "cdo"].includes(role.toLowerCase());
}

export function Sidebar({ expanded, onToggle, activePage, onNavigate, summary }: SidebarProps) {
  const userIsAdmin = isAdmin(summary.viewer_role);

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-surface-panel border-r border-border-subtle shrink-0",
        "transition-[width] duration-250 ease-in-out overflow-hidden",
        expanded ? "w-60" : "w-16"
      )}
    >
      {/* Logo area */}
      <div className="flex items-center h-14 px-3 border-b border-border-subtle shrink-0">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-blue to-accent-violet flex items-center justify-center shrink-0">
            <Activity className="w-4 h-4 text-white" />
          </div>
          {expanded && (
            <div className="flex flex-col min-w-0">
              <span className="text-[11px] font-bold text-accent-blue uppercase tracking-widest leading-none">TF2 FinOps</span>
              <span className="text-[10px] text-text-muted leading-none mt-0.5">Watch Dashboard</span>
            </div>
          )}
        </div>
        <button
          onClick={onToggle}
          className="shrink-0 w-6 h-6 flex items-center justify-center rounded text-text-muted hover:text-text-primary hover:bg-surface-elevated transition-colors"
          aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          {expanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto overflow-x-hidden">
        <ul className="space-y-0.5 px-2">
          {NAV_ITEMS.map((item) => {
            if (item.adminOnly && !userIsAdmin) return null;
            const Icon = item.icon;
            const isActive = activePage === item.key;
            return (
              <li key={item.key}>
                <button
                  onClick={() => onNavigate(item.key)}
                  className={cn(
                    "flex items-center gap-3 w-full rounded-md px-2 py-2 text-sm font-medium",
                    "transition-colors duration-150 text-left",
                    isActive
                      ? "bg-accent-blue/10 text-accent-blue border-l-2 border-accent-blue pl-[6px]"
                      : "text-text-secondary hover:bg-surface-elevated hover:text-text-primary border-l-2 border-transparent pl-[6px]"
                  )}
                  aria-current={isActive ? "page" : undefined}
                  title={!expanded ? item.label : undefined}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {expanded && (
                    <span className="truncate">{item.label}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bottom section */}
      <div className="shrink-0 border-t border-border-subtle px-3 py-3 space-y-1.5">
        {expanded ? (
          <>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-accent-blue/10 text-accent-blue border border-accent-blue/25">
                {summary.environment}
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-elevated text-text-muted border border-border-subtle">
                {summary.viewer_role}
              </span>
            </div>
          </>
        ) : (
          <div className="flex justify-center">
            <span
              className="inline-flex items-center justify-center w-7 h-7 rounded bg-accent-blue/10 text-accent-blue text-[9px] font-bold uppercase border border-accent-blue/25"
              title={`${summary.environment} / ${summary.viewer_role}`}
            >
              {summary.environment.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}
