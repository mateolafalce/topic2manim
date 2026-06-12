"""Vector database for reusable Manim code snippets.

Stores Manim code snippets with embeddings for semantic search.
Uses SQLite for persistence and supports OpenAI / Ollama embeddings.
"""

import json
import math
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DB_PATH = Path(__file__).parent.parent / "content" / "snippets.db"


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_snippet_db():
    """Create snippets table if it doesn't exist."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snippets (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            topic TEXT,
            description TEXT,
            embedding TEXT,
            source_job_id TEXT,
            scene_index INTEGER,
            created_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_snippets_topic ON snippets(topic)"
    )
    conn.commit()
    conn.close()


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_text(text: str, client, provider: str, model: Optional[str] = None) -> Optional[List[float]]:
    """Generate embedding vector for text.

    Supports OpenAI and Ollama embeddings.
    """
    if not text or not text.strip():
        return None

    text = text.strip()[:8000]  # Truncate for safety

    try:
        if provider == "openai":
            emb_model = model or "text-embedding-3-small"
            response = client.embeddings.create(input=text, model=emb_model)
            return response.data[0].embedding

        elif provider == "ollama":
            import ssl
            import urllib.request

            emb_model = model or "nomic-embed-text"
            url = f"{client.base_url}/api/embeddings"
            payload = json.dumps({"model": emb_model, "prompt": text}).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if getattr(client, "api_key", None):
                headers["Authorization"] = f"Bearer {client.api_key}"

            request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            ctx = ssl.create_default_context()
            lowered = (client.base_url or "").lower()
            if any(token in lowered for token in ("localhost", "127.0.0.1", "host.docker.internal", ":11434")):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(request, timeout=60, context=ctx) as response:
                body = json.loads(response.read().decode("utf-8"))
                return body.get("embedding")

        else:
            # For other OpenAI-compatible providers, try embeddings endpoint
            emb_model = model or "text-embedding-3-small"
            response = client.embeddings.create(input=text, model=emb_model)
            return response.data[0].embedding

    except Exception as exc:
        print(f"[WARN] Embedding failed ({provider}): {exc}")
        return None


def store_snippet(
    code: str,
    topic: str = "",
    description: str = "",
    embedding: Optional[List[float]] = None,
    source_job_id: str = "",
    scene_index: int = 0,
) -> str:
    """Store a Manim code snippet. Returns snippet ID."""
    snippet_id = str(uuid.uuid4())
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO snippets (id, code, topic, description, embedding, source_job_id, scene_index, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snippet_id,
            code,
            topic,
            description,
            json.dumps(embedding) if embedding else None,
            source_job_id,
            scene_index,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return snippet_id


def search_snippets(
    query_embedding: List[float],
    top_k: int = 3,
    min_similarity: float = 0.65,
) -> List[Dict]:
    """Search snippets by cosine similarity. Returns top-k matches."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT id, code, topic, description, embedding, source_job_id, scene_index FROM snippets WHERE embedding IS NOT NULL"
    ).fetchall()
    conn.close()

    scored = []
    for row in rows:
        try:
            emb = json.loads(row[4])
            score = _cosine_similarity(query_embedding, emb)
            if score >= min_similarity:
                scored.append((score, row))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, row in scored[:top_k]:
        results.append(
            {
                "id": row[0],
                "code": row[1],
                "topic": row[2],
                "description": row[3],
                "similarity": round(score, 3),
                "source_job_id": row[5],
                "scene_index": row[6],
            }
        )
    return results


def search_snippets_by_text(
    query: str,
    client,
    provider: str,
    model: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict]:
    """Embed query text and search snippets."""
    embedding = embed_text(query, client, provider, model)
    if not embedding:
        return []
    return search_snippets(embedding, top_k=top_k)


def extract_snippets_from_job(
    job_data: Dict,
    client,
    provider: str,
    model: Optional[str] = None,
) -> List[str]:
    """Extract and store Manim code snippets from a completed job.

    Returns list of stored snippet IDs.
    """
    topic = job_data.get("topic", "")
    script = job_data.get("script", [])
    job_id = job_data.get("job_id", "")
    stored = []

    for i, scene in enumerate(script):
        code = scene.get("code", "").strip()
        if not code:
            continue

        description = f"Scene {i + 1}: {scene.get('title', '') or scene.get('text', '')[:80]}"
        text_to_embed = f"{topic}\n{scene.get('text', '')}\n{scene.get('animation', '')}"
        embedding = embed_text(text_to_embed, client, provider, model)

        sid = store_snippet(
            code=code,
            topic=topic,
            description=description,
            embedding=embedding,
            source_job_id=job_id,
            scene_index=i + 1,
        )
        stored.append(sid)
        print(f"[OK] Stored snippet {sid} (scene {i + 1})")

    return stored


def get_snippet_count() -> int:
    """Return total number of stored snippets."""
    conn = _get_connection()
    row = conn.execute("SELECT COUNT(*) FROM snippets").fetchone()
    conn.close()
    return row[0] if row else 0


def format_snippets_for_prompt(snippets: List[Dict]) -> str:
    """Format retrieved snippets as prompt context."""
    if not snippets:
        return ""
    lines = ["\nRELEVANT CODE EXAMPLES (use as inspiration for style and technique):"]
    for s in snippets:
        lines.append(f"\n# Example from '{s['topic']}' (similarity: {s['similarity']}):")
        lines.append(s["code"])
    lines.append("\n# End examples — write original code for THIS scene, do not copy verbatim.")
    return "\n".join(lines)


# Auto-init on import
init_snippet_db()
