"""FAISS-based semantic scenario retrieval for finding related scenarios."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from clinicalagent_bench.scenario_engine.models import Scenario


class ScenarioRetriever:
    """Semantic search over scenarios using FAISS vector similarity.

    Embeds scenario descriptions and enables finding related scenarios
    by natural language query or by similarity to an existing scenario.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._scenarios: list[Scenario] = []
        self._embeddings: np.ndarray | None = None
        self._index: Any = None
        self._cache_dir = cache_dir
        self._dimension = 384  # Default for sentence-transformers/all-MiniLM-L6-v2

    def _get_scenario_text(self, scenario: Scenario) -> str:
        """Build a rich text representation for embedding."""
        parts = [
            f"Domain: {scenario.domain.value}",
            f"Name: {scenario.name}",
            f"Description: {scenario.description}",
            f"Patient: {scenario.input.patient_context}",
            f"Risk: {scenario.risk_level.value}",
            f"Difficulty: {scenario.difficulty.value}",
        ]
        if scenario.safety_constraints:
            constraints = "; ".join(c.constraint for c in scenario.safety_constraints)
            parts.append(f"Safety: {constraints}")
        if scenario.escalation_triggers:
            triggers = "; ".join(t.condition for t in scenario.escalation_triggers)
            parts.append(f"Escalation: {triggers}")
        if scenario.tags:
            parts.append(f"Tags: {', '.join(scenario.tags)}")
        return " | ".join(parts)

    def _compute_embeddings(self, texts: list[str]) -> np.ndarray:
        """Compute embeddings using a lightweight approach.

        Uses a simple TF-IDF-like hash embedding for zero-dependency operation.
        For production, swap in sentence-transformers or OpenAI embeddings.
        """
        vectors = []
        for text in texts:
            vector = self._hash_embed(text, self._dimension)
            vectors.append(vector)
        return np.array(vectors, dtype=np.float32)

    @staticmethod
    def _hash_embed(text: str, dim: int) -> np.ndarray:
        """Create a deterministic hash-based embedding vector.

        Uses overlapping character n-gram hashing for semantic-ish similarity.
        Words that share substrings will have partially overlapping vectors.
        """
        vector = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        for word in words:
            for n in range(2, min(len(word) + 1, 6)):
                for i in range(len(word) - n + 1):
                    ngram = word[i : i + n]
                    h = int(hashlib.md5(ngram.encode()).hexdigest(), 16)
                    idx = h % dim
                    sign = 1.0 if (h // dim) % 2 == 0 else -1.0
                    vector[idx] += sign * (1.0 / n)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector

    def _cache_path(self) -> Path | None:
        if not self._cache_dir or not self._scenarios:
            return None
        ids = sorted(s.scenario_id for s in self._scenarios)
        key = hashlib.md5(json.dumps(ids).encode()).hexdigest()[:12]
        return self._cache_dir / f"faiss_index_{key}.npz"

    def index(self, scenarios: list[Scenario]) -> None:
        """Build the FAISS index from a list of scenarios."""
        import faiss

        self._scenarios = list(scenarios)

        cache = self._cache_path()
        if cache and cache.exists():
            data = np.load(cache)
            self._embeddings = data["embeddings"]
        else:
            texts = [self._get_scenario_text(s) for s in self._scenarios]
            self._embeddings = self._compute_embeddings(texts)
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                np.savez(cache, embeddings=self._embeddings)

        self._index = faiss.IndexFlatIP(self._dimension)
        faiss.normalize_L2(self._embeddings)
        self._index.add(self._embeddings)

    def search(self, query: str, k: int = 10) -> list[tuple[Scenario, float]]:
        """Search for scenarios similar to a natural language query.

        Args:
            query: Natural language description of what you're looking for.
            k: Number of results to return.

        Returns:
            List of (scenario, similarity_score) tuples, sorted by relevance.
        """
        if self._index is None or not self._scenarios:
            return []

        import faiss

        query_vec = self._compute_embeddings([query])
        faiss.normalize_L2(query_vec)

        k = min(k, len(self._scenarios))
        scores, indices = self._index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                results.append((self._scenarios[idx], float(score)))
        return results

    def find_similar(self, scenario_id: str, k: int = 5) -> list[tuple[Scenario, float]]:
        """Find scenarios similar to an existing scenario.

        Args:
            scenario_id: ID of the scenario to find similar ones for.
            k: Number of results (excluding the query scenario itself).

        Returns:
            List of (scenario, similarity_score) tuples.
        """
        if self._index is None or not self._scenarios:
            return []

        idx = None
        for i, s in enumerate(self._scenarios):
            if s.scenario_id == scenario_id:
                idx = i
                break

        if idx is None:
            return []

        import faiss

        query_vec = self._embeddings[idx : idx + 1].copy()
        faiss.normalize_L2(query_vec)

        scores, indices = self._index.search(query_vec, k + 1)

        results = []
        for score, i in zip(scores[0], indices[0]):
            if i >= 0 and i != idx:
                results.append((self._scenarios[i], float(score)))
        return results[:k]

    def search_by_domain(
        self, query: str, domain: str, k: int = 10
    ) -> list[tuple[Scenario, float]]:
        """Search within a specific domain."""
        all_results = self.search(query, k=k * 3)
        filtered = [(s, score) for s, score in all_results if s.domain.value == domain]
        return filtered[:k]

    @property
    def indexed_count(self) -> int:
        return len(self._scenarios)
