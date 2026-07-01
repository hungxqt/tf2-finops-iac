import {
  Area,
  Brush,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { EmptyState } from "../ui/EmptyState";
import { formatMoney, yAxisMoneyFormatter } from "../../lib/utils";

type TrendPoint = {
  date: string;
  actual: number;
  baseline: number;
  anomaly: boolean;
};

interface SpendTrendChartProps {
  data: TrendPoint[];
}

interface CustomTooltipPayload {
  dataKey?: string;
  value?: number;
  payload?: { anomaly?: boolean };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: CustomTooltipPayload[];
  label?: string;
}

function CustomTooltip({ active, payload: items, label }: CustomTooltipProps) {
  if (!active || !items?.length) return null;

  const actual   = items.find((p) => p.dataKey === "actual")?.value   ?? 0;
  const baseline = items.find((p) => p.dataKey === "baseline")?.value ?? 0;
  const delta    = Number(actual) - Number(baseline);
  const isAnomaly = items[0]?.payload?.anomaly;

  return (
    <div className="bg-surface-elevated border border-border-strong rounded-lg px-3 py-2 text-xs shadow-[var(--shadow-card)] min-w-[160px]">
      <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted mb-2">{label}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-text-secondary">Actual</span>
          <span className="font-semibold text-accent-blue">{formatMoney(Number(actual))}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-text-secondary">Baseline</span>
          <span className="font-semibold text-accent-teal">{formatMoney(Number(baseline))}</span>
        </div>
        <div className="flex justify-between gap-4 pt-1 border-t border-border-subtle">
          <span className="text-text-secondary">Delta</span>
          <span className={`font-bold ${delta >= 0 ? "text-accent-red" : "text-accent-green"}`}>
            {delta >= 0 ? "+" : ""}{formatMoney(delta)}
          </span>
        </div>
        {isAnomaly && (
          <div className="mt-1 pt-1 border-t border-border-subtle">
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase bg-accent-red/10 text-accent-red border border-accent-red/25 px-1.5 py-0.5 rounded">
              ⚠ Anomaly
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function CustomLegend() {
  return (
    <div className="flex items-center justify-center gap-4 pt-2">
      <div className="flex items-center gap-1.5">
        <div className="w-6 h-0.5 bg-accent-blue" />
        <span className="text-[11px] text-text-secondary">Actual</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-6 border-t-2 border-dashed border-accent-teal" />
        <span className="text-[11px] text-text-secondary">Baseline</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-2.5 h-2.5 rounded-full bg-accent-red" />
        <span className="text-[11px] text-text-secondary">Anomaly</span>
      </div>
    </div>
  );
}

interface ScatterDotProps {
  cx?: number;
  cy?: number;
}

function AnomalyDot({ cx = 0, cy = 0 }: ScatterDotProps) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={7} fill="#ef4444" fillOpacity={0.2} />
      <circle cx={cx} cy={cy} r={4} fill="#ef4444" />
    </g>
  );
}

export function SpendTrendChart({ data }: SpendTrendChartProps) {
  if (data.length === 0) {
    return <EmptyState title="No spend trend data" detail="The summary did not include trend rows." />;
  }
  const anomalyPoints = data.filter((d) => d.anomaly);
  // Build the Y-axis formatter from the actual data range so it picks the
  // right precision tier (micro-dollars for sandbox, k/M for production).
  const allValues = data.flatMap((d) => [d.actual, d.baseline]);
  const yFmt = yAxisMoneyFormatter(allValues);

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-panel/50 p-4">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <defs>
            <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" vertical={false} />
          <XAxis
            dataKey="date"
            minTickGap={28}
            tick={{ fill: "#8ba3c7", fontSize: 11 }}
            axisLine={{ stroke: "#1e2d45" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={yFmt}
            tick={{ fill: "#8ba3c7", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={72}
          />

          <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#2d4a6e", strokeWidth: 1, strokeDasharray: "4 4" }} />
          <Area
            type="monotone"
            dataKey="actual"
            fill="url(#actualGradient)"
            stroke="none"
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="baseline"
            stroke="#14b8a6"
            strokeDasharray="6 4"
            strokeWidth={2}
            dot={false}
            name="Baseline"
            isAnimationActive={true}
            animationDuration={1000}
          />
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#3b82f6"
            strokeWidth={2.5}
            dot={false}
            name="Actual"
            isAnimationActive={true}
            animationDuration={1200}
          />
          <Brush
            dataKey="date"
            height={24}
            stroke="#2d4a6e"
            fill="#111827"
            travellerWidth={8}
            strokeWidth={1}
            gap={4}
            padding={{ top: 0, bottom: 0, left: 12, right: 12 }}
          >
            <Area
              type="monotone"
              dataKey="actual"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.15}
              isAnimationActive={false}
            />
          </Brush>
          {anomalyPoints.length > 0 && (
            <Scatter
              data={anomalyPoints}
              dataKey="actual"
              fill="#ef4444"
              name="Anomaly"
              shape={<AnomalyDot />}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <CustomLegend />
    </div>
  );
}
