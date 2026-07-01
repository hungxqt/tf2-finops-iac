/**
 * ManualTriggerButton
 *
 * A self-contained "Run Report Now" button that lets CDO operators manually
 * trigger an ad-hoc FinOps detection run from the dashboard.
 *
 * Quota rule (enforced by the Step Functions CheckAdHocQuota state):
 *   Each tenant is limited to 5 ad-hoc runs per day.
 *   The `quotaUsed` prop (from dashboard-summary.json) reflects today's count.
 *   The button disables itself when quotaUsed >= 5.
 *
 * UX flow:
 *   1. User clicks the button → confirmation dialog appears.
 *   2. User confirms → button enters loading state, POSTs to trigger_api_url.
 *   3a. Success → success toast shows the execution ARN, quota badge increments.
 *   3b. Quota exceeded (backend) → quota-exceeded banner.
 *   3c. Other error → dismissible error message.
 */

import { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { PlayCircle, Loader2, CheckCircle2, AlertTriangle, XCircle, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { triggerAdHocRun } from "../../data";

const QUOTA_MAX = 5;

type TriggerState =
  | { kind: "idle" }
  | { kind: "confirming" }
  | { kind: "loading" }
  | { kind: "success"; executionArn: string }
  | { kind: "quota_exceeded" }
  | { kind: "error"; message: string };

interface ManualTriggerButtonProps {
  /** Tenant ID from the dashboard summary (forwarded to the Step Functions input). */
  tenantId?: string;
  /** Account ID from the dashboard summary. */
  accountId?: string;
  /** How many ad-hoc runs have been used today (0–5), from dashboard-summary.json. */
  quotaUsed: number;
}

export function ManualTriggerButton({ tenantId, accountId, quotaUsed }: ManualTriggerButtonProps) {
  const [state, setState] = useState<TriggerState>({ kind: "idle" });
  // Optimistic local counter: increments on each successful trigger so the badge
  // updates immediately without waiting for a dashboard-summary refresh.
  const [localExtra, setLocalExtra] = useState(0);

  const effectiveUsed = Math.min(quotaUsed + localExtra, QUOTA_MAX);
  const remaining = QUOTA_MAX - effectiveUsed;
  const isExhausted = remaining <= 0;

  const handleClick = useCallback(() => {
    if (isExhausted || state.kind === "loading") return;
    setState({ kind: "confirming" });
  }, [isExhausted, state.kind]);

  const handleCancel = useCallback(() => setState({ kind: "idle" }), []);

  const handleConfirm = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const result = await triggerAdHocRun(tenantId, accountId);
      setLocalExtra((n) => n + 1);
      setState({ kind: "success", executionArn: result.execution_arn });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.toLowerCase().includes("quota") || msg.toLowerCase().includes("exceeded")) {
        setState({ kind: "quota_exceeded" });
      } else {
        setState({ kind: "error", message: msg });
      }
    }
  }, [tenantId, accountId]);

  const handleDismiss = useCallback(() => setState({ kind: "idle" }), []);

  // ─── Quota badge ────────────────────────────────────────────────────────────
  function QuotaBadge() {
    const tone = isExhausted
      ? "bg-accent-red/10 text-accent-red border-accent-red/30"
      : remaining === 1
      ? "bg-accent-amber/10 text-accent-amber border-accent-amber/30"
      : "bg-surface-elevated text-text-secondary border-border-subtle";

    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider border rounded-full px-2 py-0.5",
          tone
        )}
        title={`${effectiveUsed} of ${QUOTA_MAX} manual runs used today`}
        aria-label={`${effectiveUsed} of ${QUOTA_MAX} manual runs used today`}
      >
        {effectiveUsed}/{QUOTA_MAX}
      </span>
    );
  }

  // ─── Trigger button ──────────────────────────────────────────────────────────
  function TriggerBtn() {
    const isLoading = state.kind === "loading";

    return (
      <button
        id="manual-trigger-btn"
        type="button"
        onClick={handleClick}
        disabled={isExhausted || isLoading}
        aria-disabled={isExhausted || isLoading}
        className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border transition-all duration-150 select-none",
          isExhausted
            ? "bg-surface-elevated text-text-muted border-border-subtle cursor-not-allowed opacity-50"
            : isLoading
            ? "bg-accent-blue/10 text-accent-blue border-accent-blue/30 cursor-wait"
            : "bg-accent-blue text-white border-accent-blue hover:bg-accent-blue/90 active:scale-95 shadow-sm"
        )}
        aria-busy={isLoading}
      >
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <PlayCircle className="w-3.5 h-3.5" aria-hidden="true" />
        )}
        {isLoading ? "Starting…" : isExhausted ? "Quota reached" : "Run report now"}
      </button>
    );
  }

  // ─── Confirmation dialog ─────────────────────────────────────────────────────
  function ConfirmDialog() {
    return (
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="trigger-dialog-title"
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      >
        <div className="bg-surface-panel border border-border-subtle rounded-xl shadow-2xl w-full max-w-sm p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-start gap-3">
            <div className="shrink-0 p-2 rounded-lg bg-accent-blue/10">
              <PlayCircle className="w-5 h-5 text-accent-blue" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="trigger-dialog-title"
                className="text-sm font-semibold text-text-primary leading-snug"
              >
                Start ad-hoc detection run?
              </h2>
              <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                This will start an immediate FinOps detection workflow for today's cost
                period. Containment actions remain in{" "}
                <span className="font-semibold text-accent-amber">dry-run mode</span> unless
                the error budget and containment policy permit apply-mode.
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-border-subtle bg-surface-elevated px-3.5 py-2.5 text-xs text-text-secondary space-y-1">
            <div className="flex justify-between">
              <span className="font-medium text-text-primary">Daily quota remaining</span>
              <span className={cn("font-bold", remaining <= 1 ? "text-accent-amber" : "text-accent-green")}>
                {remaining} of {QUOTA_MAX} runs
              </span>
            </div>
            {remaining === 1 && (
              <p className="text-accent-amber text-[11px]">
                This is your last allowed manual run today.
              </p>
            )}
          </div>

          <div className="flex gap-2 justify-end pt-1">
            <button
              id="trigger-dialog-cancel-btn"
              type="button"
              onClick={handleCancel}
              className="px-3.5 py-1.5 text-xs font-semibold rounded-md border border-border-subtle bg-surface-elevated text-text-secondary hover:bg-surface-base transition-colors"
            >
              Cancel
            </button>
            <button
              id="trigger-dialog-confirm-btn"
              type="button"
              onClick={handleConfirm}
              className="px-3.5 py-1.5 text-xs font-semibold rounded-md bg-accent-blue text-white hover:bg-accent-blue/90 active:scale-95 transition-all shadow-sm"
            >
              Confirm &amp; start run
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ─── Success toast ───────────────────────────────────────────────────────────
  function SuccessToast({ arn }: { arn: string }) {
    const shortArn = arn.split(":").slice(-1)[0] ?? arn;
    return (
      <div
        role="status"
        aria-live="polite"
        className="fixed bottom-6 right-6 z-50 flex items-start gap-3 max-w-sm w-full bg-surface-panel border border-accent-green/30 rounded-xl shadow-xl px-4 py-3.5 animate-in slide-in-from-bottom-4 duration-300"
      >
        <CheckCircle2 className="w-5 h-5 text-accent-green shrink-0 mt-0.5" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-text-primary">Run started</p>
          <p className="text-xs text-text-secondary mt-0.5 truncate" title={arn}>
            Execution: <span className="font-mono">{shortArn}</span>
          </p>
          <p className="text-xs text-text-muted mt-0.5">
            Dashboard will refresh after the run completes (~2–5 min).
          </p>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
          className="shrink-0 text-text-muted hover:text-text-primary transition-colors p-0.5 rounded"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  // ─── Error / quota banner ────────────────────────────────────────────────────
  function AlertBanner({ icon, tone, title, detail }: {
    icon: React.ReactNode;
    tone: "error" | "warning";
    title: string;
    detail: string;
  }) {
    const cls = tone === "error"
      ? "border-accent-red/30 bg-accent-red/5 text-accent-red"
      : "border-accent-amber/30 bg-accent-amber/5 text-accent-amber";

    return (
      <div
        role="alert"
        className={cn("fixed bottom-6 right-6 z-50 flex items-start gap-3 max-w-sm w-full border rounded-xl shadow-xl px-4 py-3.5 animate-in slide-in-from-bottom-4 duration-300", cls)}
      >
        <span className="shrink-0 mt-0.5" aria-hidden="true">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{title}</p>
          <p className="text-xs mt-0.5 opacity-80">{detail}</p>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
          className="shrink-0 opacity-70 hover:opacity-100 transition-opacity p-0.5 rounded"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <>
      {/* The inline button + badge shown in the Topbar */}
      <div className="flex items-center gap-2">
        <QuotaBadge />
        <TriggerBtn />
      </div>

      {/* Overlays — rendered outside the button via Portal so they float above everything regardless of Topbar layout constraints */}
      {state.kind === "confirming" && createPortal(<ConfirmDialog />, document.body)}

      {state.kind === "success" && createPortal(
        <SuccessToast arn={state.executionArn} />,
        document.body
      )}

      {state.kind === "quota_exceeded" && createPortal(
        <AlertBanner
          icon={<AlertTriangle className="w-5 h-5" />}
          tone="warning"
          title="Daily quota reached"
          detail={`You have used all ${QUOTA_MAX} manual runs allowed today. Scheduled runs continue automatically.`}
        />,
        document.body
      )}

      {state.kind === "error" && createPortal(
        <AlertBanner
          icon={<XCircle className="w-5 h-5" />}
          tone="error"
          title="Trigger failed"
          detail={state.message}
        />,
        document.body
      )}
    </>
  );
}
