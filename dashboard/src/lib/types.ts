export interface LeaderboardEntry {
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
}

export interface DomainScore {
  domain: string;
  score: number;
  scenarios_count: number;
}

export interface RunDetail {
  run_id: string;
  agent_name: string;
  model: string;
  cas_score: number;
  safety_score: number;
  accuracy_score: number;
  refusal_score: number;
  efficiency_score: number;
  consistency_score: number;
  domain_scores: DomainScore[];
  scenario_scores: ScenarioResult[];
  timestamp: string;
  config: Record<string, unknown>;
}

export interface ScenarioResult {
  scenario_id: string;
  scenario_name: string;
  domain: string;
  score: number;
  safety_score: number;
  flags: string[];
}

export interface BenchmarkStats {
  total_runs: number;
  total_agents: number;
  total_scenarios: number;
  avg_cas: number;
  avg_safety: number;
  top_agent: string;
  domains: string[];
}

export interface ComparisonData {
  runs: RunDetail[];
  metrics: string[];
}
