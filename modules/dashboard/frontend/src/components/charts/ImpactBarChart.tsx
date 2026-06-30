import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState } from "../ui/EmptyState";
import type { DashboardSummary } from "../../schema";

type ImpactedItem = DashboardSummary["impacted"][number];

interface ImpactBarChartProps {
  items: ImpactedItem[];
}

const moneyFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const currency = (v: number) => moneyFmt.format(Number(v || 0));

const BAR_COLORS = ["#14b8a6", "#3b82f6", "#8b5cf6", "#f59e0b", "#06b6d4"];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0]?.payload as ImpactedItem;
  return (
    <div className="bg-surface-elevated border border-border-strong rounded-lg px-3 py-2 text-xs shadow-[var(--shadow-card)]">
      <p className="font-semibold text-text-primary mb-1">{item.name}</p>
      <div className="flex items-center gap-2">
        <span className="text-text-secondary">{item.type}</span>
        <span className="font-bold text-accent-teal">{currency(item.spend_delta_usd_per_day)}/day</span>
      </div>
      <span className={`mt-1 inline-flex text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
        item.owner_tag_status === "valid"
          ? "bg-accent-green/10 text-accent-green border-accent-green/25"
          : "bg-accent-amber/10 text-accent-amber border-accent-amber/25"
      }`}>
        {item.owner_tag_status}
      </span>
    </div>
  );
}

export function ImpactBarChart({ items }: ImpactBarChartProps) {
  if (items.length === 0) {
    return <EmptyState title="No impacted owners" detail="No impacted account, service, or squad records were published." />;
  }

  const sorted = [...items].sort((a, b) => b.spend_delta_usd_per_day - a.spend_delta_usd_per_day);
  const barHeight = 36;
  const chartHeight = Math.max(160, sorted.length * barHeight + 20);

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart layout="vertical" data={sorted} margin={{ top: 4, right: 60, bottom: 4, left: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          width={110}
          tick={{ fill: "#8ba3c7", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        <Bar dataKey="spend_delta_usd_per_day" radius={[0, 4, 4, 0]} isAnimationActive={true} animationDuration={900}>
          {sorted.map((_, index) => (
            <Cell key={index} fill={BAR_COLORS[index % BAR_COLORS.length]} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
