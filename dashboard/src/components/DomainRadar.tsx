"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface DomainRadarProps {
  data: { domain: string; score: number }[];
}

export default function DomainRadar({ data }: DomainRadarProps) {
  const chartData = data.map((d) => ({
    domain: d.domain.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    score: +(d.score * 100).toFixed(1),
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={chartData}>
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis
          dataKey="domain"
          tick={{ fontSize: 11, fill: "#64748b" }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={{ fontSize: 10 }}
        />
        <Radar
          name="Score"
          dataKey="score"
          stroke="#16a34a"
          fill="#22c55e"
          fillOpacity={0.3}
        />
        <Tooltip />
      </RadarChart>
    </ResponsiveContainer>
  );
}
