const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getLeaderboard() {
  return fetchAPI<{
    leaderboard: Array<{
      rank: number;
      agent_name: string;
      model: string;
      cas_score: number;
      safety_score: number;
      accuracy_score: number;
      refusal_score: number;
      efficiency_score: number;
      consistency_score: number;
      scenarios_run: number;
      timestamp: string;
      run_id: string;
    }>;
  }>("/api/v1/leaderboard");
}

export async function getRun(runId: string) {
  return fetchAPI<Record<string, unknown>>(`/api/v1/runs/${runId}`);
}

export async function getStats() {
  return fetchAPI<{
    total_runs: number;
    total_agents: number;
    total_scenarios: number;
    avg_cas: number;
    avg_safety: number;
    domains: string[];
  }>("/api/v1/stats");
}

export async function getScenarios() {
  return fetchAPI<{
    scenarios: Array<{
      scenario_id: string;
      name: string;
      domain: string;
      difficulty: string;
      risk_level: string;
    }>;
    total: number;
  }>("/api/v1/scenarios");
}

export async function getCompare(runIds: string[]) {
  return fetchAPI<Record<string, unknown>>(
    `/api/v1/compare?run_ids=${runIds.join(",")}`
  );
}
