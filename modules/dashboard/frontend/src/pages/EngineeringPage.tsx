import { useMemo, useState } from "react";
import { AlertTriangle, FileSearch } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { PanelCard } from "../components/ui/PanelCard";
import { FilterBar, type FilterState } from "../components/ui/FilterBar";
import { StatusPill } from "../components/ui/StatusPill";
import { AnomalyQueue } from "../components/anomaly/AnomalyQueue";
import { AnomalyDetail } from "../components/anomaly/AnomalyDetail";
import type { DashboardSummary } from "../schema";

interface EngineeringPageProps {
  summary: DashboardSummary;
}

type Tone = "neutral" | "success" | "warning" | "critical" | "info" | "ai";

function severityTone(severity?: string): Tone {
  const s = String(severity || "").toLowerCase();
  if (s.includes("critical")) return "critical";
  if (s.includes("warn"))     return "warning";
  return "neutral";
}

export function EngineeringPage({ summary }: EngineeringPageProps) {
  const [filters, setFilters] = useState<FilterState>({ account: "all", service: "all", squad: "all", range: 90 });
  const [selectedId, setSelectedId] = useState(summary.anomalies[0]?.anomaly_id ?? "");

  const filteredAnomalies = useMemo(() =>
    summary.anomalies.filter((item) =>
      (filters.account === "all" || item.account_id === filters.account) &&
      (filters.service === "all" || item.service  === filters.service) &&
      (filters.squad   === "all" || item.squad    === filters.squad)
    ), [filters, summary.anomalies]);

  const selectedAnomaly = filteredAnomalies.find((a) => a.anomaly_id === selectedId) ?? filteredAnomalies[0];

  return (
    <PageContainer>
      <FilterBar summary={summary} filters={filters} onChange={setFilters} />

      <div className="grid grid-cols-[1fr_1.2fr] gap-4 max-lg:grid-cols-1">
        {/* Left: Anomaly Queue */}
        <PanelCard
          icon={<AlertTriangle />}
          title="Anomaly Queue"
          description={`${filteredAnomalies.length} anomalies match filters. Click to inspect.`}
        >
          <AnomalyQueue
            anomalies={filteredAnomalies}
            selectedId={selectedAnomaly?.anomaly_id ?? ""}
            onSelect={setSelectedId}
          />
        </PanelCard>

        {/* Right: Anomaly Detail */}
        <PanelCard
          icon={<FileSearch />}
          title="Engineering Triage"
          description="Resource, owner, business context, and telemetry details for the selected anomaly."
          aside={selectedAnomaly ? (
            <StatusPill tone={severityTone(selectedAnomaly.severity)} label={selectedAnomaly.severity} dot />
          ) : undefined}
        >
          <AnomalyDetail anomaly={selectedAnomaly} />
        </PanelCard>
      </div>
    </PageContainer>
  );
}
