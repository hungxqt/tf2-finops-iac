import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface ScrollAreaProps {
  children: ReactNode;
  maxHeight?: string;
  className?: string;
}

export function ScrollArea({ children, maxHeight = "400px", className }: ScrollAreaProps) {
  return (
    <div
      className={cn("overflow-y-auto", className)}
      style={{ maxHeight }}
    >
      {children}
    </div>
  );
}
