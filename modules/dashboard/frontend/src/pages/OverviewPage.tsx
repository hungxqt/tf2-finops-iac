import { useMemo, useState, useRef } from "react";
import { CircleDollarSign, AlertTriangle, DatabaseZap, ShieldCheck, BarChart3, Users } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { DraggableGrid } from "../components/layout/DraggableGrid";
import { KpiTile } from "../components/ui/KpiTile";
import { PanelCard } from "../components/ui/PanelCard";
import { DataQualityBanner } from "../components/ui/DataQualityBanner";
import { FilterBar, type FilterState } from "../components/ui/FilterBar";
import { SpendTrendChart } from "../components/charts/SpendTrendChart";
import { ImpactBarChart } from "../components/charts/ImpactBarChart";
import { formatMoney } from "../lib/utils";
import { pct } from "../lib/format";
import type { DashboardSummary } from "../schema";

interface OverviewPageProps {
  summary: DashboardSummary;
}

type TrendPoint = { date: string; actual: number; baseline: number; anomaly: boolean };

function toTrend(summary: DashboardSummary): TrendPoint[] {
  return summary.spend_trend.map((row) => ({
    date:     row[0],
    actual:   Number(row[1] || 0),
    baseline: Number(row[2] || 0),
    anomaly:  Boolean(row[3])
  }));
}

export function OverviewPage({ summary }: OverviewPageProps) {
  const [filters, setFilters] = useState<FilterState>({ account: "all", service: "all", squad: "all", range: 90 });
  const spendChartRef = useRef<HTMLDivElement>(null);
  const impactChartRef = useRef<HTMLDivElement>(null);

  const filteredAnomalies = useMemo(() =>
    summary.anomalies.filter((item) =>
      (filters.account === "all" || item.account_id === filters.account) &&
      (filters.service === "all" || item.service  === filters.service) &&
      (filters.squad   === "all" || item.squad    === filters.squad)
    ), [filters, summary.anomalies]);

  const trend = useMemo(() => {
    const points = toTrend(summary);
    return points.slice(-Math.max(2, Math.ceil(filters.range / 7)));
  }, [filters.range, summary]);

  const totalSpend    = trend.reduce((s, p) => s + p.actual,   0);
  const baselineSpend = trend.reduce((s, p) => s + p.baseline, 0);
  const wasteImpact   = filteredAnomalies.reduce((s, a) => s + a.cost_delta_usd_per_day, 0);
  const criticalCount = filteredAnomalies.filter((a) => a.severity?.toLowerCase().includes("critical")).length;
  const lowConfidence = filteredAnomalies.some((a) => String(a.data_confidence).toUpperCase() === "LOW");

  return (
    <PageContainer>
      <DataQualityBanner summary={summary} lowConfidence={lowConfidence} />
      <FilterBar summary={summary} filters={filters} onChange={setFilters} />

      {/* KPI Grid (draggable) */}
      <DraggableGrid
        storageKey="finops-kpi-layout"
        baseGridClass="grid grid-cols-4 gap-4 mb-6 max-md:grid-cols-2 max-sm:grid-cols-1"
      >
        <KpiTile index={0}
          icon={<CircleDollarSign />}
          label={`${filters.range}D Spend`}
          value={formatMoney(totalSpend)}
          detail={`${formatMoney(totalSpend - baselineSpend)} vs baseline`}
          tone="info"
        />
        <KpiTile index={1}
          icon={<AlertTriangle />}
          label="Open Anomalies"
          value={String(filteredAnomalies.length)}
          detail={`${criticalCount} critical`}
          tone={criticalCount > 0 ? "critical" : "success"}
        />
        <KpiTile index={2}
          icon={<DatabaseZap />}
          label="Waste Impact"
          value={formatMoney(wasteImpact, "/day")}
          detail={lowConfidence ? "Some telemetry gaps" : "Telemetry complete"}
          tone={lowConfidence ? "warning" : "success"}
        />
        <KpiTile index={3}
          icon={<ShieldCheck />}
          label="Error Budget"
          value={pct(summary.error_budget_remaining_pct)}
          detail={summary.containment_locked ? "Containment locked" : "Containment available"}
          tone={summary.containment_locked ? "warning" : "success"}
        />
      </DraggableGrid>

      {/* Charts grid (draggable) */}
      <DraggableGrid
        storageKey="finops-chart-layout"
        baseGridClass="grid grid-cols-[2fr_1fr] gap-4 max-lg:grid-cols-1"
      >
        <PanelCard
          icon={<BarChart3 />}
          title="Spend Trend"
          description={`Actual cost, expected baseline, and anomaly markers for the last ${filters.range} days.`}
          chartExportRef={spendChartRef}
          chartFilename="spend-trend"
        >
          <div ref={spendChartRef}>
            <SpendTrendChart data={trend} />
          </div>
        </PanelCard>

        <PanelCard
          icon={<Users />}
          title="Top Impacted"
          description="Accounts, services, and squads ranked by daily spend delta."
          chartExportRef={impactChartRef}
          chartFilename="top-impacted"
        >
          <div ref={impactChartRef}>
            <ImpactBarChart items={summary.impacted} />
          </div>
        </PanelCard>
      </DraggableGrid>
    </PageContainer>
  );
}
