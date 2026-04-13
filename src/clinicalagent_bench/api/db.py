"""SQLite database for storing benchmark results and leaderboard data."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BenchmarkDB:
    """SQLite-backed storage for benchmark results."""

    def __init__(self, db_path: str | Path = "clinicalagent_bench.db") -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_tables(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                run_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                model TEXT,
                overall_cas REAL NOT NULL,
                total_scenarios INTEGER NOT NULL,
                scored_scenarios INTEGER NOT NULL,
                safety_summary TEXT,
                refusal_summary TEXT,
                domain_breakdown TEXT,
                config TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scenario_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                cas_score REAL NOT NULL,
                safety_score REAL NOT NULL,
                accuracy_score REAL NOT NULL,
                refusal_score REAL NOT NULL,
                efficiency_score REAL NOT NULL,
                consistency_score REAL NOT NULL,
                details TEXT,
                FOREIGN KEY (run_id) REFERENCES benchmark_runs(run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_scenario_scores_run
                ON scenario_scores(run_id);
            CREATE INDEX IF NOT EXISTS idx_scenario_scores_scenario
                ON scenario_scores(scenario_id);
            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_agent
                ON benchmark_runs(agent_name);
            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_cas
                ON benchmark_runs(overall_cas DESC);
        """)
        conn.commit()

    def save_benchmark(self, scores_data: dict[str, Any]) -> str:
        """Save a complete benchmark result."""
        conn = self._get_conn()
        run_id = scores_data["run_id"]

        conn.execute(
            """INSERT OR REPLACE INTO benchmark_runs
            (run_id, agent_name, model, overall_cas, total_scenarios, scored_scenarios,
             safety_summary, refusal_summary, domain_breakdown, config, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                scores_data["agent_name"],
                scores_data.get("model", ""),
                scores_data["overall_cas"],
                scores_data["total_scenarios"],
                scores_data["scored_scenarios"],
                json.dumps(scores_data.get("safety_summary", {})),
                json.dumps(scores_data.get("refusal_summary", {})),
                json.dumps(scores_data.get("domain_breakdown", {})),
                json.dumps(scores_data.get("config", {})),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        # Save individual scenario scores
        for score in scores_data.get("scenario_scores", []):
            conn.execute(
                """INSERT INTO scenario_scores
                (run_id, scenario_id, cas_score, safety_score, accuracy_score,
                 refusal_score, efficiency_score, consistency_score, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    score["scenario_id"],
                    score["cas_score"],
                    score["safety"]["score"],
                    score["accuracy"]["score"],
                    score["refusal"]["score"],
                    score["efficiency"]["score"],
                    score["consistency"]["score"],
                    json.dumps(score),
                ),
            )

        conn.commit()
        return run_id

    def get_leaderboard(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get the top agents by CAS score."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT run_id, agent_name, model, overall_cas, total_scenarios,
                      scored_scenarios, domain_breakdown, safety_summary, refusal_summary, created_at
            FROM benchmark_runs
            ORDER BY overall_cas DESC
            LIMIT ?""",
            (limit,),
        ).fetchall()

        return [
            {
                "run_id": r["run_id"],
                "agent_name": r["agent_name"],
                "model": r["model"],
                "overall_cas": r["overall_cas"],
                "total_scenarios": r["total_scenarios"],
                "scored_scenarios": r["scored_scenarios"],
                "domain_breakdown": json.loads(r["domain_breakdown"] or "{}"),
                "safety_summary": json.loads(r["safety_summary"] or "{}"),
                "refusal_summary": json.loads(r["refusal_summary"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get a specific benchmark run."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM benchmark_runs WHERE run_id = ?", (run_id,)
        ).fetchone()

        if not row:
            return None

        scenario_scores = conn.execute(
            "SELECT * FROM scenario_scores WHERE run_id = ? ORDER BY scenario_id",
            (run_id,),
        ).fetchall()

        return {
            "run_id": row["run_id"],
            "agent_name": row["agent_name"],
            "model": row["model"],
            "overall_cas": row["overall_cas"],
            "total_scenarios": row["total_scenarios"],
            "scored_scenarios": row["scored_scenarios"],
            "domain_breakdown": json.loads(row["domain_breakdown"] or "{}"),
            "safety_summary": json.loads(row["safety_summary"] or "{}"),
            "refusal_summary": json.loads(row["refusal_summary"] or "{}"),
            "config": json.loads(row["config"] or "{}"),
            "created_at": row["created_at"],
            "scenario_scores": [
                {
                    "scenario_id": s["scenario_id"],
                    "cas_score": s["cas_score"],
                    "safety_score": s["safety_score"],
                    "accuracy_score": s["accuracy_score"],
                    "refusal_score": s["refusal_score"],
                    "efficiency_score": s["efficiency_score"],
                    "consistency_score": s["consistency_score"],
                }
                for s in scenario_scores
            ],
        }

    def get_scenario_history(self, scenario_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get score history for a specific scenario across runs."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT ss.*, br.agent_name, br.model, br.created_at
            FROM scenario_scores ss
            JOIN benchmark_runs br ON ss.run_id = br.run_id
            WHERE ss.scenario_id = ?
            ORDER BY br.created_at DESC
            LIMIT ?""",
            (scenario_id, limit),
        ).fetchall()

        return [
            {
                "run_id": r["run_id"],
                "agent_name": r["agent_name"],
                "model": r["model"],
                "cas_score": r["cas_score"],
                "safety_score": r["safety_score"],
                "accuracy_score": r["accuracy_score"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
