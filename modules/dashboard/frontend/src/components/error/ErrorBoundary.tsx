import { Component, type ReactNode, type ErrorInfo } from "react";
import { AlertTriangle } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex items-center justify-center h-full min-h-[240px] p-4">
          <div className="bg-surface-panel border border-accent-red/30 rounded-xl p-8 max-w-md w-full text-center space-y-3">
            <AlertTriangle className="w-8 h-8 text-accent-red mx-auto" />
            <h2 className="text-base font-bold text-text-primary">Something went wrong</h2>
            <p className="text-xs text-text-secondary">
              {this.state.error?.message || "An unexpected error occurred in this section."}
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
