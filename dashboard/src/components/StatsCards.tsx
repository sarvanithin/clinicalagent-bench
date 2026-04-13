"use client";

interface StatsCardsProps {
  totalRuns: number;
  totalAgents: number;
  totalScenarios: number;
  avgCas: number;
  avgSafety: number;
}

function StatCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <p className="text-sm text-slate-500 mb-1">{title}</p>
      <p className="text-3xl font-bold text-slate-900">{value}</p>
      {subtitle && (
        <p className="text-xs text-slate-400 mt-1">{subtitle}</p>
      )}
    </div>
  );
}

export default function StatsCards({
  totalRuns,
  totalAgents,
  totalScenarios,
  avgCas,
  avgSafety,
}: StatsCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <StatCard title="Benchmark Runs" value={totalRuns} />
      <StatCard title="Agents Tested" value={totalAgents} />
      <StatCard title="Scenarios" value={totalScenarios} />
      <StatCard
        title="Avg CAS"
        value={avgCas.toFixed(3)}
        subtitle="across all runs"
      />
      <StatCard
        title="Avg Safety"
        value={avgSafety.toFixed(2)}
        subtitle="safety score"
      />
    </div>
  );
}
