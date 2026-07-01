import { ConfidenceGauge } from "./ConfidenceGauge";
import { EmptyState } from "../ui/EmptyState";
import { cn } from "../../lib/utils";
import { currency, formatDateLabel } from "../../lib/format";
import type { Anomaly } from "../../schema";

interface AnomalyDetailProps {
  anomaly: Anomaly | undefined;
}

function confidenceLabel(value?: string) {
  const v = String(value || "").toUpperCase();
  if (v === "HIGH") return "Complete telemetry";
  if (v === "LOW")  return "Telemetry gap";
  return "Unknown";
}

interface FieldProps { label: string; value: string; mono?: boolean; }
function Field({ label, value, mono }: FieldProps) {
  return (
    <div className="grid grid-cols-[100px_1fr] gap-2 py-2 border-b border-border-subtle/50 last:border-0">
      <dt className="text-[10px] font-bold uppercase tracking-wider text-text-muted self-start pt-0.5">{label}</dt>
      <dd className={cn("text-sm text-text-primary break-words", mono && "font-mono text-xs text-accent-cyan")}>{value}</dd>
    </div>
  );
}

interface CollapsibleBlockProps {
  title: string;
  value?: Record<string, unknown>;
}
function CollapsibleBlock({ title, value }: CollapsibleBlockProps) {
  const entries = Object.entries(value || {});
  if (entries.length === 0) return null;
  return (
    <details className="mt-3 rounded-lg border border-border-subtle overflow-hidden">
      <summary className="flex items-center justify-between px-4 py-2.5 cursor-pointer text-xs font-semibold text-text-secondary hover:bg-surface-elevated transition-colors select-none list-none">
        <span>{title}</span>
        <span className="text-text-muted">{entries.length} fields</span>
      </summary>
      <div className="px-4 py-3 bg-surface-base/50">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          {entries.map(([k, v]) => (
            <div key={k}>
              <dt className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{k}</dt>
              <dd className="text-xs text-text-primary mt-0.5">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </div>
    </details>
  );
}

export function AnomalyDetail({ anomaly }: AnomalyDetailProps) {
  if (!anomaly) {
    return (
      <EmptyState
        title="No anomaly selected"
        detail="Click an anomaly in the queue to see engineering triage details."
      />
    );
  }

  return (
    <div className="space-y-1">
      {/* Confidence gauge centered */}
      <div className="flex justify-center border-b border-border-subtle pb-3">
        <ConfidenceGauge score={anomaly.confidence_score} />
      </div>

      {/* Fields */}
      <dl className="pt-2">
        <Field label="Account"    value={`${anomaly.account_name} (${anomaly.account_id})`} />
        <Field label="Service"    value={anomaly.service} />
        <Field label="Squad"      value={anomaly.squad} />
        <Field label="Evidence"   value={`${formatDateLabel(anomaly.evidence_window_start)} → ${formatDateLabel(anomaly.evidence_window_end)}`} />
        <Field label="Cost delta" value={`${currency(anomaly.cost_delta_usd_per_day)}/day`} />
        <Field label="Data conf"  value={`${confidenceLabel(anomaly.data_confidence)} (${anomaly.data_confidence})`} />
        <Field label="Owner tag"  value={anomaly.owner_tag_status} />
        <Field label="Explanation" value={anomaly.explanation} />
      </dl>

      <CollapsibleBlock title="Business context"  value={anomaly.business_context} />
      <CollapsibleBlock title="Telemetry quality" value={anomaly.telemetry_quality} />
    </div>
  );
}
