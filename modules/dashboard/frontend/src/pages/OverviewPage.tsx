import { useMemo, useState } from "react";
import { CircleDollarSign, AlertTriangle, DatabaseZap, ShieldCheck, BarChart3, Users } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { KpiTile } from "../components/ui/KpiTile";
import { PanelCard } from "../components/ui/PanelCard";
import { DataQualityBanner } from "../components/ui/DataQualityBanner";
import { FilterBar, type FilterState } from "../components/ui/FilterBar";
import { SpendTrendChart } from "../components/charts/SpendTrendChart";
import { ImpactBarChart } from "../components/charts/ImpactBarChart";
import { formatMoney } from "../lib/utils";
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

const pct = (v: number) =>
  `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Number(v || 0))}%`;

export function OverviewPage({ summary }: OverviewPageProps) {
  const [filters, setFilters] = useState<FilterState>({ account: "all", service: "all", squad: "all", range: 90 });

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

      {/* KPI Grid */}
      <div className="grid grid-cols-4 gap-4 mb-6 max-md:grid-cols-2 max-sm:grid-cols-1">
        <KpiTile
          icon={<CircleDollarSign />}
          label={`${filters.range}D Spend`}
          value={formatMoney(totalSpend)}
          detail={`${formatMoney(totalSpend - baselineSpend)} vs baseline`}
          tone="info"
        />
        <KpiTile
          icon={<AlertTriangle />}
          label="Open Anomalies"
          value={String(filteredAnomalies.length)}
          detail={`${criticalCount} critical`}
          tone={criticalCount > 0 ? "critical" : "success"}
        />
        <KpiTile
          icon={<DatabaseZap />}
          label="Waste Impact"
          value={formatMoney(wasteImpact, "/day")}
          detail={lowConfidence ? "Some telemetry gaps" : "Telemetry complete"}
          tone={lowConfidence ? "warning" : "success"}
        />
        <KpiTile
          icon={<ShieldCheck />}
          label="Error Budget"
          value={pct(summary.error_budget_remaining_pct)}
          detail={summary.containment_locked ? "Containment locked" : "Containment available"}
          tone={summary.containment_locked ? "warning" : "success"}
        />
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-[2fr_1fr] gap-4 max-lg:grid-cols-1">
        <PanelCard
          icon={<BarChart3 />}
          title="Spend Trend"
          description={`Actual cost, expected baseline, and anomaly markers for the last ${filters.range} days.`}
        >
          <SpendTrendChart data={trend} />
        </PanelCard>

        <PanelCard
          icon={<Users />}
          title="Top Impacted"
          description="Accounts, services, and squads ranked by daily spend delta."
        >
          <ImpactBarChart items={summary.impacted} />
        </PanelCard>
      </div>
    </PageContainer>
  );
}
