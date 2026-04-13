"use client";

interface CASGaugeProps {
  score: number;
  size?: number;
}

export default function CASGauge({ score, size = 120 }: CASGaugeProps) {
  const pct = Math.min(100, score * 100);
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  const color =
    pct >= 80
      ? "stroke-green-500"
      : pct >= 60
        ? "stroke-yellow-500"
        : "stroke-red-500";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="8"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold">{score.toFixed(2)}</span>
        <span className="text-xs text-slate-500">CAS</span>
      </div>
    </div>
  );
}
