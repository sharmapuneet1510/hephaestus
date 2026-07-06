"""Tests for the Context Engine (TASK 5)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.context import (
    ContextEngine,
    RepoContext,
    build_graph,
    chunk_content,
    extract_metadata,
    render_markdown,
    render_toon,
)
from app.main import create_app
from app.repo import SessionStore

PY_SAMPLE = """\
import os
from app.config import load_config


def top_level():
    return 1


class Widget:
    def method(self):
        return 2
"""

JS_SAMPLE = """\
import { load } from './config';
export function render() {}
export const helper = () => {};
class Panel {}
"""


def _config():
    return load_config(environ={})


# --------------------------------------------------------------------------- #
# 5.1 — Chunking
# --------------------------------------------------------------------------- #
def test_chunk_content_splits_large_file_with_stable_ids():
    content = "\n".join(f"line {i}" for i in range(1000))
    chunks = chunk_content("big.py", content, size_lines=400)
    assert len(chunks) == 3  # 400 + 400 + 200
    assert chunks[0].id == "big.py#1-400"
    assert chunks[1].id == "big.py#401-800"
    assert chunks[2].id == "big.py#801-1000"
    # Stable: same input -> same IDs.
    assert [c.id for c in chunk_content("big.py", content, 400)] == [c.id for c in chunks]


def test_chunk_empty_content():
    assert chunk_content("empty.py", "", 400) == []


# --------------------------------------------------------------------------- #
# 5.3 — Metadata extraction
# --------------------------------------------------------------------------- #
def test_extract_python_metadata():
    meta = extract_metadata("app/mod.py", PY_SAMPLE)
    assert meta.language == "python"
    assert "os" in meta.imports and "app.config" in meta.imports
    names = {s.name for s in meta.symbols}
    assert {"top_level", "Widget", "method"} <= names
    assert "top_level" in meta.exports and "Widget" in meta.exports
    assert meta.content_hash  # populated


def test_extract_js_metadata():
    meta = extract_metadata("src/panel.ts", JS_SAMPLE)
    assert meta.language == "typescript"
    assert "./config" in meta.imports
    assert {"render", "helper"} <= set(meta.exports)


def test_metadata_json_round_trips_through_schema():
    """model_dump() JSON re-validates against FileMetadata (SUBTASK 5.3)."""
    meta = extract_metadata("app/mod.py", PY_SAMPLE)
    from app.context import FileMetadata

    dumped = meta.model_dump()
    assert set(["path", "language", "lines", "imports", "exports", "symbols"]) <= dumped.keys()
    assert FileMetadata(**dumped) == meta


# --------------------------------------------------------------------------- #
# 5.2 / 5.4 — Markdown + TOON
# --------------------------------------------------------------------------- #
def _ctx() -> RepoContext:
    return RepoContext(
        root="/repo",
        files=[
            extract_metadata("app/mod.py", PY_SAMPLE),
            extract_metadata("src/panel.ts", JS_SAMPLE),
        ],
    )


def test_render_markdown_has_per_file_summaries():
    md = render_markdown(_ctx())
    assert "## Files" in md
    assert "`app/mod.py`" in md and "`src/panel.ts`" in md
    assert "symbols: " in md


def test_toon_is_shorter_and_keeps_key_facts():
    ctx = _ctx()
    toon = render_toon(ctx)
    markdown = render_markdown(ctx)
    assert len(toon) < len(markdown)  # SUBTASK 5.4
    assert "app/mod.py" in toon and "top_level" in toon  # key facts kept


# --------------------------------------------------------------------------- #
# 5.5 — Graph
# --------------------------------------------------------------------------- #
def test_build_graph_resolves_import_edges():
    ctx = RepoContext(
        root="/repo",
        files=[
            extract_metadata("app/main.py", "from app.config import load_config\n"),
            extract_metadata("app/config.py", "def load_config():\n    return {}\n"),
        ],
    )
    graph = build_graph(ctx)
    file_ids = {n["id"] for n in graph["nodes"] if n["type"] == "file"}
    assert {"app/main.py", "app/config.py"} <= file_ids
    import_edges = [(e["from"], e["to"]) for e in graph["edges"] if e["kind"] == "import"]
    assert ("app/main.py", "app/config.py") in import_edges
    # module containment edges exist too
    assert any(e["kind"] == "contains" for e in graph["edges"])


# --------------------------------------------------------------------------- #
# 5.6 — Refresh
# --------------------------------------------------------------------------- #
def test_engine_caches_unchanged_and_refreshes_changed():
    engine = ContextEngine()
    m1 = engine.analyze_file("f.py", "def a():\n    pass\n")
    assert engine.is_cached("f.py", "def a():\n    pass\n")
    # Same content -> same cached object.
    assert engine.analyze_file("f.py", "def a():\n    pass\n") is m1

    # Changed content -> invalidated + re-extracted (new symbol).
    changed = "def a():\n    pass\n\ndef b():\n    pass\n"
    assert not engine.is_cached("f.py", changed)
    m2 = engine.analyze_file("f.py", changed)
    assert m2 is not m1
    assert {s.name for s in m2.symbols} == {"a", "b"}
    assert m2.content_hash != m1.content_hash


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "main.py").write_text("from app.config import load_config\n")
    (repo / "app" / "config.py").write_text("def load_config():\n    return {}\n")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "x.js").write_text("bloat")
    return repo


def _client(tmp_path: Path, repo: Path) -> TestClient:
    app = create_app(config=_config())
    store = SessionStore(tmp_path / "state" / "session.json")
    from app.repo import load_repository

    metadata, _ = load_repository(str(repo), _config())
    store.save_repo(metadata)
    app.state.session_store = store
    return TestClient(app)


def test_context_endpoint_formats(tmp_path):
    repo = _make_repo(tmp_path)
    client = _client(tmp_path, repo)

    md = client.post("/api/context/build", json={"format": "markdown"}).json()
    assert md["file_count"] == 2  # node_modules excluded
    assert "## Files" in md["content"]

    graph = client.post("/api/context/build", json={"format": "graph"}).json()
    edges = [(e["from"], e["to"]) for e in graph["data"]["edges"] if e["kind"] == "import"]
    assert ("app/main.py", "app/config.py") in edges

    toon = client.post("/api/context/build", json={"format": "toon"}).json()
    assert "app/main.py" in toon["content"]


def test_context_endpoint_requires_loaded_repo():
    app = create_app(config=_config())
    app.state.session_store = SessionStore(Path("/nonexistent/session.json"))
    resp = TestClient(app).post("/api/context/build", json={})
    assert resp.status_code == 400
    assert "No repository loaded" in resp.json()["detail"]
