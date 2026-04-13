"use client";

interface ScoreBarProps {
  label: string;
  value: number;
  maxValue?: number;
  color?: string;
}

export default function ScoreBar({
  label,
  value,
  maxValue = 1.0,
  color,
}: ScoreBarProps) {
  const pct = Math.min(100, (value / maxValue) * 100);
  const bg =
    color ||
    (pct >= 80 ? "bg-green-500" : pct >= 60 ? "bg-yellow-500" : "bg-red-500");

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-600 w-24 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-200 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full ${bg}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-mono font-semibold w-12 text-right">
        {value.toFixed(2)}
      </span>
    </div>
  );
}
