"use client";

import { LeaderboardEntry } from "@/lib/types";

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
  onSelectRun?: (runId: string) => void;
}

function getRankBadge(rank: number) {
  if (rank === 1) return "bg-yellow-100 text-yellow-800 border-yellow-300";
  if (rank === 2) return "bg-slate-100 text-slate-700 border-slate-300";
  if (rank === 3) return "bg-amber-50 text-amber-800 border-amber-300";
  return "bg-white text-slate-600 border-slate-200";
}

function getScoreColor(score: number) {
  if (score >= 0.9) return "text-green-600 font-bold";
  if (score >= 0.7) return "text-green-500";
  if (score >= 0.5) return "text-yellow-600";
  return "text-red-600";
}

export default function LeaderboardTable({
  entries,
  onSelectRun,
}: LeaderboardTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b-2 border-slate-200">
            <th className="text-left py-3 px-4 font-semibold text-slate-500">
              Rank
            </th>
            <th className="text-left py-3 px-4 font-semibold text-slate-500">
              Agent
            </th>
            <th className="text-left py-3 px-4 font-semibold text-slate-500">
              Model
            </th>
            <th className="text-center py-3 px-4 font-semibold text-slate-500">
              CAS
            </th>
            <th className="text-center py-3 px-4 font-semibold text-slate-500">
              Safety
            </th>
            <th className="text-center py-3 px-4 font-semibold text-slate-500">
              Accuracy
            </th>
            <th className="text-center py-3 px-4 font-semibold text-slate-500">
              Refusal
            </th>
            <th className="text-center py-3 px-4 font-semibold text-slate-500">
              Efficiency
            </th>
            <th className="text-center py-3 px-4 font-semibold text-slate-500">
              Scenarios
            </th>
            <th className="text-right py-3 px-4 font-semibold text-slate-500">
              Date
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr
              key={entry.run_id}
              className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
              onClick={() => onSelectRun?.(entry.run_id)}
            >
              <td className="py-3 px-4">
                <span
                  className={`inline-flex items-center justify-center w-8 h-8 rounded-full border text-sm font-bold ${getRankBadge(entry.rank)}`}
                >
                  {entry.rank}
                </span>
              </td>
              <td className="py-3 px-4 font-medium text-slate-900">
                {entry.agent_name}
              </td>
              <td className="py-3 px-4">
                <code className="text-xs bg-slate-100 px-2 py-0.5 rounded">
                  {entry.model}
                </code>
              </td>
              <td
                className={`py-3 px-4 text-center font-mono ${getScoreColor(entry.cas_score)}`}
              >
                {entry.cas_score.toFixed(3)}
              </td>
              <td
                className={`py-3 px-4 text-center font-mono ${getScoreColor(entry.safety_score)}`}
              >
                {entry.safety_score.toFixed(2)}
              </td>
              <td
                className={`py-3 px-4 text-center font-mono ${getScoreColor(entry.accuracy_score)}`}
              >
                {entry.accuracy_score.toFixed(2)}
              </td>
              <td
                className={`py-3 px-4 text-center font-mono ${getScoreColor(entry.refusal_score)}`}
              >
                {entry.refusal_score.toFixed(2)}
              </td>
              <td
                className={`py-3 px-4 text-center font-mono ${getScoreColor(entry.efficiency_score)}`}
              >
                {entry.efficiency_score.toFixed(2)}
              </td>
              <td className="py-3 px-4 text-center text-slate-600">
                {entry.scenarios_run}
              </td>
              <td className="py-3 px-4 text-right text-slate-500 text-xs">
                {new Date(entry.timestamp).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {entries.length === 0 && (
        <div className="text-center py-12 text-slate-400">
          No benchmark results yet. Run{" "}
          <code className="bg-slate-100 px-2 py-0.5 rounded">
            cab run --model gpt-4o
          </code>{" "}
          to get started.
        </div>
      )}
    </div>
  );
}
