import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface PageContainerProps {
  children: ReactNode;
  className?: string;
}

export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div className={cn("max-w-screen-2xl mx-auto px-6 py-6 animate-page-enter", className)}>
      {children}
    </div>
  );
}
