"use client";

import { useEffect, useState, useCallback } from "react";
import LeaderboardTable from "@/components/LeaderboardTable";
import StatsCards from "@/components/StatsCards";
import CASGauge from "@/components/CASGauge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import DomainRadar from "@/components/DomainRadar";
import ScoreBar from "@/components/ScoreBar";
import { LeaderboardEntry } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEMO_LEADERBOARD: LeaderboardEntry[] = [
  {
    rank: 1,
    agent_name: "MedAssist-Pro",
    model: "gpt-4o",
    cas_score: 0.847,
    safety_score: 0.92,
    accuracy_score: 0.85,
    refusal_score: 0.78,
    efficiency_score: 0.81,
    consistency_score: 0.88,
    scenarios_run: 42,
    timestamp: "2026-04-10T14:30:00Z",
    run_id: "demo-001",
  },
  {
    rank: 2,
    agent_name: "ClinicalCopilot",
    model: "claude-sonnet-4-20250514",
    cas_score: 0.823,
    safety_score: 0.95,
    accuracy_score: 0.79,
    refusal_score: 0.82,
    efficiency_score: 0.72,
    consistency_score: 0.85,
    scenarios_run: 42,
    timestamp: "2026-04-09T10:15:00Z",
    run_id: "demo-002",
  },
  {
    rank: 3,
    agent_name: "HealthAgent-v2",
    model: "gemini-2.0-flash",
    cas_score: 0.756,
    safety_score: 0.88,
    accuracy_score: 0.73,
    refusal_score: 0.65,
    efficiency_score: 0.78,
    consistency_score: 0.72,
    scenarios_run: 42,
    timestamp: "2026-04-08T16:45:00Z",
    run_id: "demo-003",
  },
  {
    rank: 4,
    agent_name: "TriageBot",
    model: "gpt-4o-mini",
    cas_score: 0.691,
    safety_score: 0.75,
    accuracy_score: 0.68,
    refusal_score: 0.59,
    efficiency_score: 0.85,
    consistency_score: 0.65,
    scenarios_run: 42,
    timestamp: "2026-04-07T09:20:00Z",
    run_id: "demo-004",
  },
  {
    rank: 5,
    agent_name: "DocuHealth",
    model: "llama-3.1-70b",
    cas_score: 0.634,
    safety_score: 0.71,
    accuracy_score: 0.62,
    refusal_score: 0.55,
    efficiency_score: 0.69,
    consistency_score: 0.58,
    scenarios_run: 42,
    timestamp: "2026-04-06T11:00:00Z",
    run_id: "demo-005",
  },
];

const DEMO_DOMAIN_SCORES = [
  { domain: "billing_coding", score: 0.82 },
  { domain: "triage", score: 0.91 },
  { domain: "documentation", score: 0.78 },
  { domain: "prior_auth", score: 0.74 },
  { domain: "refusal", score: 0.85 },
  { domain: "care_navigation", score: 0.69 },
  { domain: "clinical_reasoning", score: 0.76 },
  { domain: "multi_agent", score: 0.63 },
];

type TabType = "leaderboard" | "compare" | "scenarios";

export default function Home() {
  const [leaderboard, setLeaderboard] =
    useState<LeaderboardEntry[]>(DEMO_LEADERBOARD);
  const [selectedRun, setSelectedRun] = useState<LeaderboardEntry | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("leaderboard");
  const [isLive, setIsLive] = useState(false);
  const [stats, setStats] = useState({
    totalRuns: 5,
    totalAgents: 5,
    totalScenarios: 42,
    avgCas: 0.75,
    avgSafety: 0.842,
  });

  const fetchLive = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/leaderboard`);
      if (res.ok) {
        const data = await res.json();
        if (data.leaderboard?.length > 0) {
          setLeaderboard(data.leaderboard);
          setIsLive(true);
        }
      }
      const statsRes = await fetch(`${API_BASE}/api/v1/stats`);
      if (statsRes.ok) {
        const s = await statsRes.json();
        setStats({
          totalRuns: s.total_runs || 0,
          totalAgents: s.total_agents || 0,
          totalScenarios: s.total_scenarios || 42,
          avgCas: s.avg_cas || 0,
          avgSafety: s.avg_safety || 0,
        });
      }
    } catch {
      // API not available, keep demo data
    }
  }, []);

  useEffect(() => {
    fetchLive();
  }, [fetchLive]);

  const handleSelectRun = (runId: string) => {
    const entry = leaderboard.find((e) => e.run_id === runId);
    if (entry) setSelectedRun(entry);
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            ClinicalAgent-Bench
          </h1>
          <p className="text-slate-500 mt-1">
            Evaluation leaderboard for healthcare AI agents
          </p>
        </div>
        <div className="flex items-center gap-3">
          {!isLive && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded-full">
              Demo Mode
            </span>
          )}
          {isLive && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
              Live
            </span>
          )}
          <a
            href="https://github.com/sarvanithin/clinicalagent-bench"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-slate-500 hover:text-slate-800 transition-colors"
          >
            GitHub
          </a>
        </div>
      </div>

      {/* Stats */}
      <StatsCards
        totalRuns={stats.totalRuns}
        totalAgents={stats.totalAgents}
        totalScenarios={stats.totalScenarios}
        avgCas={stats.avgCas}
        avgSafety={stats.avgSafety}
      />

      {/* Tabs */}
      <div className="mt-8 border-b border-slate-200">
        <nav className="flex gap-6">
          {(["leaderboard", "compare", "scenarios"] as TabType[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-green-600 text-green-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === "leaderboard" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-4">
                Agent Rankings
              </h2>
              <LeaderboardTable
                entries={leaderboard}
                onSelectRun={handleSelectRun}
              />
            </div>

            <div className="space-y-6">
              {selectedRun ? (
                <>
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-slate-800">
                        {selectedRun.agent_name}
                      </h3>
                      <button
                        onClick={() => setSelectedRun(null)}
                        className="text-xs text-slate-400 hover:text-slate-600"
                      >
                        Close
                      </button>
                    </div>
                    <div className="flex justify-center mb-4">
                      <CASGauge score={selectedRun.cas_score} />
                    </div>
                    <div className="space-y-2">
                      <ScoreBar label="Safety" value={selectedRun.safety_score} />
                      <ScoreBar label="Accuracy" value={selectedRun.accuracy_score} />
                      <ScoreBar label="Refusal" value={selectedRun.refusal_score} />
                      <ScoreBar label="Efficiency" value={selectedRun.efficiency_score} />
                      <ScoreBar label="Consistency" value={selectedRun.consistency_score} />
                    </div>
                  </div>
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                    <h3 className="font-semibold text-slate-800 mb-2">
                      CAS Breakdown
                    </h3>
                    <ScoreBreakdown
                      safety={selectedRun.safety_score}
                      accuracy={selectedRun.accuracy_score}
                      refusal={selectedRun.refusal_score}
                      efficiency={selectedRun.efficiency_score}
                      consistency={selectedRun.consistency_score}
                    />
                  </div>
                </>
              ) : (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                  <h3 className="font-semibold text-slate-800 mb-4">
                    Domain Performance (Top Agent)
                  </h3>
                  <DomainRadar data={DEMO_DOMAIN_SCORES} />
                  <p className="text-xs text-slate-400 text-center mt-2">
                    Click an agent row for detailed breakdown
                  </p>
                </div>
              )}

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="font-semibold text-slate-800 mb-3">
                  CAS Formula
                </h3>
                <div className="bg-slate-50 rounded-lg p-3 font-mono text-xs text-slate-600">
                  CAS = Safety(0.35) + Accuracy(0.25) + Refusal(0.20) +
                  Efficiency(0.10) + Consistency(0.10)
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  Safety-first weighting. Refusal accuracy uniquely measures
                  escalation decision quality.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === "compare" && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center">
            <h2 className="text-lg font-semibold text-slate-800 mb-2">
              Side-by-Side Comparison
            </h2>
            <p className="text-slate-500 mb-6">
              Select two runs from the leaderboard to compare.
            </p>
            {leaderboard.length >= 2 && (
              <div className="max-w-3xl mx-auto">
                <div className="grid grid-cols-2 gap-8">
                  {leaderboard.slice(0, 2).map((entry) => (
                    <div
                      key={entry.run_id}
                      className="border border-slate-200 rounded-xl p-6"
                    >
                      <h3 className="font-bold text-lg mb-1">
                        {entry.agent_name}
                      </h3>
                      <p className="text-xs text-slate-400 mb-4">
                        {entry.model}
                      </p>
                      <div className="flex justify-center mb-4">
                        <CASGauge score={entry.cas_score} size={100} />
                      </div>
                      <div className="space-y-2">
                        <ScoreBar label="Safety" value={entry.safety_score} />
                        <ScoreBar label="Accuracy" value={entry.accuracy_score} />
                        <ScoreBar label="Refusal" value={entry.refusal_score} />
                        <ScoreBar label="Efficiency" value={entry.efficiency_score} />
                        <ScoreBar label="Consistency" value={entry.consistency_score} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "scenarios" && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">
              Scenario Coverage
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { domain: "Billing & Coding", count: 10, color: "bg-blue-100 text-blue-700" },
                { domain: "Triage & Scheduling", count: 10, color: "bg-red-100 text-red-700" },
                { domain: "Documentation", count: 5, color: "bg-purple-100 text-purple-700" },
                { domain: "Prior Authorization", count: 5, color: "bg-orange-100 text-orange-700" },
                { domain: "Refusal & Escalation", count: 5, color: "bg-green-100 text-green-700" },
                { domain: "Care Navigation", count: 3, color: "bg-teal-100 text-teal-700" },
                { domain: "Clinical Reasoning", count: 2, color: "bg-indigo-100 text-indigo-700" },
                { domain: "Multi-Agent", count: 2, color: "bg-pink-100 text-pink-700" },
              ].map((d) => (
                <div
                  key={d.domain}
                  className={`rounded-lg p-4 ${d.color}`}
                >
                  <p className="font-semibold text-sm">{d.domain}</p>
                  <p className="text-2xl font-bold mt-1">{d.count}</p>
                  <p className="text-xs opacity-75">scenarios</p>
                </div>
              ))}
            </div>
            <div className="mt-6 text-center">
              <p className="text-sm text-slate-500">
                42 scenarios across 8 clinical domains.{" "}
                <a
                  href="https://github.com/sarvanithin/clinicalagent-bench"
                  className="text-green-600 hover:underline"
                  target="_blank"
                >
                  Contribute new scenarios
                </a>
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="mt-12 text-center text-xs text-slate-400 pb-8">
        <p>
          ClinicalAgent-Bench &mdash; Open-source evaluation for healthcare AI
          agents
        </p>
        <p className="mt-1">Apache 2.0 License</p>
      </footer>
    </main>
  );
}
