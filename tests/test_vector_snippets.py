"""Tests for vector_snippets.py"""
import pytest
from vector_snippets import (
    _cosine_similarity,
    store_snippet,
    search_snippets,
    get_snippet_count,
    format_snippets_for_prompt,
    init_snippet_db,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 1]) == 0.0


class TestSnippetStorage:
    def test_store_and_search(self):
        init_snippet_db()
        emb = [1.0, 0.0, 0.0]
        sid = store_snippet(
            code="circle = Circle()",
            topic="Geometry",
            description="Basic circle",
            embedding=emb,
        )
        assert sid
        assert get_snippet_count() > 0

        results = search_snippets([1.0, 0.0, 0.0], top_k=3, min_similarity=0.5)
        assert len(results) >= 1
        assert results[0]["code"] == "circle = Circle()"
        assert results[0]["similarity"] == pytest.approx(1.0, abs=0.01)

    def test_search_no_match(self):
        init_snippet_db()
        # Search with orthogonal vector should find nothing above threshold
        results = search_snippets([0.0, 1.0, 0.0], top_k=3, min_similarity=0.99)
        assert len(results) == 0


class TestFormatSnippetsForPrompt:
    def test_empty(self):
        assert format_snippets_for_prompt([]) == ""

    def test_formatting(self):
        snippets = [
            {"topic": "Math", "similarity": 0.85, "code": "x = 1"},
        ]
        result = format_snippets_for_prompt(snippets)
        assert "RELEVANT CODE EXAMPLES" in result
        assert "x = 1" in result
        assert "0.85" in result
