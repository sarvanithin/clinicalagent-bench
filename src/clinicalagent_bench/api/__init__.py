"""FastAPI server for leaderboard and benchmark results."""

from clinicalagent_bench.api.db import BenchmarkDB
from clinicalagent_bench.api.server import app

__all__ = ["app", "BenchmarkDB"]
