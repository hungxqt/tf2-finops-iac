import { AlertTriangle } from "lucide-react";

interface PageErrorFallbackProps {
  error?: Error | null;
}

export function PageErrorFallback({ error }: PageErrorFallbackProps) {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px] p-4">
      <div className="bg-surface-panel border border-accent-red/30 rounded-xl p-10 max-w-lg w-full text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-accent-red mx-auto" />
        <h1 className="text-lg font-bold text-text-primary">Page Error</h1>
        <p className="text-sm text-text-secondary">
          {error?.message || "This page encountered an unexpected error."}
        </p>
        <p className="text-xs text-text-muted">
          Try navigating to another page and back. If the problem persists, check the dashboard data contract.
        </p>
      </div>
    </div>
  );
}
