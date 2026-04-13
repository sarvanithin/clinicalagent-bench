"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface ScoreBreakdownProps {
  safety: number;
  accuracy: number;
  refusal: number;
  efficiency: number;
  consistency: number;
}

const WEIGHT_LABELS: Record<string, string> = {
  Safety: "35%",
  Accuracy: "25%",
  Refusal: "20%",
  Efficiency: "10%",
  Consistency: "10%",
};

function getBarColor(value: number) {
  if (value >= 0.8) return "#22c55e";
  if (value >= 0.6) return "#eab308";
  return "#ef4444";
}

export default function ScoreBreakdown({
  safety,
  accuracy,
  refusal,
  efficiency,
  consistency,
}: ScoreBreakdownProps) {
  const data = [
    { name: "Safety", value: safety },
    { name: "Accuracy", value: accuracy },
    { name: "Refusal", value: refusal },
    { name: "Efficiency", value: efficiency },
    { name: "Consistency", value: consistency },
  ];

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" domain={[0, 1]} tickCount={6} />
        <YAxis
          type="category"
          dataKey="name"
          width={80}
          tick={{ fontSize: 12 }}
          tickFormatter={(v: string) => `${v} (${WEIGHT_LABELS[v]})`}
        />
        <Tooltip
          formatter={(v: number) => [v.toFixed(3), "Score"]}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((entry, index) => (
            <Cell key={index} fill={getBarColor(entry.value)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
