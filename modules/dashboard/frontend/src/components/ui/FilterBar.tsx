import { cn } from "../../lib/utils";
import type { DashboardSummary, Anomaly } from "../../schema";

type FilterState = {
  account: string;
  service: string;
  squad: string;
  range: number;
};

interface FilterBarProps {
  summary: DashboardSummary;
  filters: FilterState;
  onChange: (next: FilterState) => void;
}

function uniqueValues(items: Anomaly[], key: keyof Pick<Anomaly, "account_id" | "service" | "squad">) {
  return Array.from(new Set(items.map((item) => item[key]).filter(Boolean))).sort();
}

const RANGE_OPTIONS = [
  { label: "14D", value: 14 },
  { label: "30D", value: 30 },
  { label: "90D", value: 90 },
];

const selectClass = cn(
  "bg-surface-elevated border border-border-subtle rounded-md",
  "px-3 py-1.5 text-sm text-text-primary",
  "hover:border-border-strong focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/20",
  "outline-none cursor-pointer transition-colors duration-150"
);

interface SelectControlProps {
  label: string;
  value: string;
  values: string[];
  onChange: (value: string) => void;
}

function SelectControl({ label, value, values, onChange }: SelectControlProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{label}</label>
      <select className={selectClass} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="all">All</option>
        {values.map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>
    </div>
  );
}

export function FilterBar({ summary, filters, onChange }: FilterBarProps) {
  const accounts = uniqueValues(summary.anomalies, "account_id");
  const services = uniqueValues(summary.anomalies, "service");
  const squads   = uniqueValues(summary.anomalies, "squad");

  return (
    <div className="flex flex-wrap gap-4 items-end mb-6">
      <SelectControl label="Account" value={filters.account} values={accounts} onChange={(account) => onChange({ ...filters, account })} />
      <SelectControl label="Service" value={filters.service} values={services} onChange={(service) => onChange({ ...filters, service })} />
      <SelectControl label="Squad"   value={filters.squad}   values={squads}   onChange={(squad)   => onChange({ ...filters, squad })} />

      {/* Range toggle group */}
      <div className="flex flex-col gap-1">
        <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Range</span>
        <div className="flex border border-border-subtle rounded-md overflow-hidden">
          {RANGE_OPTIONS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => onChange({ ...filters, range: value })}
              className={cn(
                "px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                filters.range === value
                  ? "bg-accent-blue text-white"
                  : "bg-surface-elevated text-text-secondary hover:bg-surface-panel hover:text-text-primary"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export type { FilterState };
