import { useEffect, useRef } from "react";

interface ConfidenceGaugeProps {
  score: number; // 0–1
}

function scoreColor(score: number): string {
  if (score >= 0.8) return "#14b8a6"; // teal
  if (score >= 0.6) return "#f59e0b"; // amber
  return "#ef4444";                    // red
}

export function ConfidenceGauge({ score }: ConfidenceGaugeProps) {
  const arcRef = useRef<SVGCircleElement>(null);
  const pct = Math.round(score * 100);
  const r = 30;
  const circumference = 2 * Math.PI * r;
  const color = scoreColor(score);

  useEffect(() => {
    const el = arcRef.current;
    if (!el) return;
    const target = circumference - (pct / 100) * circumference;
    // start full (empty)
    el.style.strokeDashoffset = String(circumference);
    el.style.transition = "none";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.style.transition = "stroke-dashoffset 900ms cubic-bezier(0.4,0,0.2,1)";
        el.style.strokeDashoffset = String(target);
      });
    });
  }, [pct, circumference]);

  return (
    <div className="flex flex-col items-center gap-1 py-2">
      <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-label={`AI confidence: ${pct}%`}>
        {/* Track */}
        <circle
          cx="40" cy="40" r={r}
          stroke="#1e2d45"
          strokeWidth="8"
          fill="none"
        />
        {/* Progress arc */}
        <circle
          ref={arcRef}
          cx="40" cy="40" r={r}
          stroke={color}
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference}
          transform="rotate(-90 40 40)"
          style={{ filter: `drop-shadow(0 0 6px ${color}66)` }}
        />
        {/* Center text */}
        <text x="40" y="37" textAnchor="middle" fill={color} fontSize="14" fontWeight="700" fontFamily="Inter,sans-serif">
          {pct}%
        </text>
        <text x="40" y="50" textAnchor="middle" fill="#4d6a8a" fontSize="8" fontFamily="Inter,sans-serif">
          AI CONF
        </text>
      </svg>
    </div>
  );
}
