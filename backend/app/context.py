"""Context Engine (TASK 5).

Turns a loaded repository into AI-friendly context: line-aware chunks with stable
IDs (5.1), markdown summaries (5.2), JSON metadata with symbols/imports/exports
(5.3), a compact TOON-style representation (5.4), a dependency graph (5.5), and
content-hash-based refresh so changed files re-analyze (5.6).

Metadata extraction is deterministic (regex-based, no AI) so it is fast, offline,
and testable; AI-generated summaries can layer on top later.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path
from typing import Iterator, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import AppConfig
from app.repo import _is_ignored, _load_gitignore

router = APIRouter()

# Skip files larger than this when analyzing (avoid pulling blobs into memory).
_MAX_FILE_BYTES = 512 * 1024

_EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
    ".sh": "shell",
}


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Chunk(BaseModel):
    id: str
    path: str
    start_line: int
    end_line: int
    text: str


class Symbol(BaseModel):
    name: str
    kind: str  # function | class | method | interface | enum


class FileMetadata(BaseModel):
    path: str
    language: str
    lines: int
    size: int
    content_hash: str
    imports: list[str] = []
    exports: list[str] = []
    symbols: list[Symbol] = []


class RepoContext(BaseModel):
    root: str
    module: Optional[str] = None
    files: list[FileMetadata] = []


# --------------------------------------------------------------------------- #
# 5.1 — Chunking
# --------------------------------------------------------------------------- #
def chunk_content(rel_path: str, content: str, size_lines: int) -> list[Chunk]:
    """Split content into line-aware chunks with stable, content-derived IDs."""
    lines = content.splitlines()
    if not lines:
        return []
    size = max(1, size_lines)
    chunks: list[Chunk] = []
    for i in range(0, len(lines), size):
        block = lines[i : i + size]
        start, end = i + 1, i + len(block)
        chunks.append(
            Chunk(
                id=f"{rel_path}#{start}-{end}",
                path=rel_path,
                start_line=start,
                end_line=end,
                text="\n".join(block),
            )
        )
    return chunks


# --------------------------------------------------------------------------- #
# 5.3 — Language-aware metadata extraction
# --------------------------------------------------------------------------- #
def detect_language(rel_path: str) -> str:
    return _EXT_LANG.get(Path(rel_path).suffix.lower(), "text")


_PY_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
# Indent must be spaces/tabs only ([ \t], not \s which would swallow blank lines).
_PY_DEF = re.compile(r"^([ \t]*)(def|class)\s+(\w+)", re.MULTILINE)

_JS_IMPORT = re.compile(r"""(?:import[^'"]*from\s+|require\(\s*)['"]([^'"]+)['"]""")
_JS_EXPORT = re.compile(
    r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+(\w+)"
)
_JS_SYMBOL = re.compile(
    r"\b(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)"
    r"|\bclass\s+(\w+)"
    r"|\b(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\("
)

_JAVA_IMPORT = re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE)
_JAVA_TYPE = re.compile(r"\b(class|interface|enum)\s+(\w+)")


def _extract_python(content: str) -> tuple[list[str], list[str], list[Symbol]]:
    imports = [m.group(1) or m.group(2) for m in _PY_IMPORT.finditer(content)]
    symbols: list[Symbol] = []
    exports: list[str] = []
    for indent, keyword, name in _PY_DEF.findall(content):
        kind = "class" if keyword == "class" else ("method" if indent else "function")
        symbols.append(Symbol(name=name, kind=kind))
        if not indent:
            exports.append(name)
    return imports, exports, symbols


def _extract_js(content: str) -> tuple[list[str], list[str], list[Symbol]]:
    imports = _JS_IMPORT.findall(content)
    exports = _JS_EXPORT.findall(content)
    symbols: list[Symbol] = []
    for fn, cls, const in _JS_SYMBOL.findall(content):
        if fn:
            symbols.append(Symbol(name=fn, kind="function"))
        elif cls:
            symbols.append(Symbol(name=cls, kind="class"))
        elif const:
            symbols.append(Symbol(name=const, kind="function"))
    return imports, exports, symbols


def _extract_java(content: str) -> tuple[list[str], list[str], list[Symbol]]:
    imports = _JAVA_IMPORT.findall(content)
    symbols = [Symbol(name=name, kind=kind) for kind, name in _JAVA_TYPE.findall(content)]
    exports = [s.name for s in symbols if s.kind in ("class", "interface", "enum")]
    return imports, exports, symbols


def extract_metadata(rel_path: str, content: str) -> FileMetadata:
    """Extract path/language/lines/imports/exports/symbols for a file (5.3)."""
    language = detect_language(rel_path)
    if language == "python":
        imports, exports, symbols = _extract_python(content)
    elif language in ("javascript", "typescript"):
        imports, exports, symbols = _extract_js(content)
    elif language == "java":
        imports, exports, symbols = _extract_java(content)
    else:
        imports, exports, symbols = [], [], []

    return FileMetadata(
        path=rel_path,
        language=language,
        lines=len(content.splitlines()),
        size=len(content.encode("utf-8")),
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        imports=imports,
        exports=exports,
        symbols=symbols,
    )


# --------------------------------------------------------------------------- #
# 5.2 — Markdown summaries
# --------------------------------------------------------------------------- #
def render_markdown(ctx: RepoContext) -> str:
    lines = [f"# Context for {Path(ctx.root).name}"]
    if ctx.module:
        lines.append(f"_Module focus: `{ctx.module}`_")

    # Per-module (directory) rollup.
    modules: dict[str, list[FileMetadata]] = {}
    for meta in ctx.files:
        module = str(Path(meta.path).parent) if "/" in meta.path else "."
        modules.setdefault(module, []).append(meta)

    lines.append("\n## Modules")
    for module in sorted(modules):
        metas = modules[module]
        langs = sorted({m.language for m in metas})
        lines.append(f"- `{module}` — {len(metas)} files ({', '.join(langs)})")

    lines.append("\n## Files")
    for meta in ctx.files:
        lines.append(f"\n### `{meta.path}`")
        lines.append(f"- language: {meta.language}, lines: {meta.lines}")
        if meta.symbols:
            lines.append("- symbols: " + ", ".join(s.name for s in meta.symbols[:20]))
        if meta.imports:
            lines.append("- imports: " + ", ".join(meta.imports[:10]))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 5.4 — TOON-style compact context
# --------------------------------------------------------------------------- #
def render_toon(ctx: RepoContext) -> str:
    """One compact line per file — token-lean context for prompts."""
    out: list[str] = []
    for meta in ctx.files:
        parts = [meta.path, meta.language, f"L{meta.lines}"]
        if meta.symbols:
            parts.append("sym:" + ",".join(s.name for s in meta.symbols[:12]))
        if meta.imports:
            parts.append("imp:" + ",".join(meta.imports[:8]))
        out.append("|".join(parts))
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# 5.5 — Dependency graph
# --------------------------------------------------------------------------- #
def _resolve_import(imp: str, source: FileMetadata, paths: set[str]) -> Optional[str]:
    """Best-effort resolution of an import string to a repo file path."""
    lang = source.language
    if lang == "python":
        base = imp.replace(".", "/")
        for candidate in (f"{base}.py", f"{base}/__init__.py"):
            if candidate in paths:
                return candidate
    elif lang in ("javascript", "typescript"):
        if imp.startswith("."):
            base = os.path.normpath(os.path.join(str(Path(source.path).parent), imp))
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                if f"{base}{ext}" in paths:
                    return f"{base}{ext}"
                if f"{base}/index{ext}" in paths:
                    return f"{base}/index{ext}"
    return None


def build_graph(ctx: RepoContext) -> dict:
    """Nodes for files + modules, edges for resolved imports and containment."""
    paths = {m.path for m in ctx.files}
    nodes: list[dict] = []
    edges: list[dict] = []
    modules: set[str] = set()

    for meta in ctx.files:
        nodes.append(
            {
                "id": meta.path,
                "type": "file",
                "label": Path(meta.path).name,
                "language": meta.language,
            }
        )
        module = str(Path(meta.path).parent) if "/" in meta.path else "."
        if module not in modules:
            modules.add(module)
            nodes.append({"id": f"module:{module}", "type": "module", "label": module})
        edges.append({"from": f"module:{module}", "to": meta.path, "kind": "contains"})

    for meta in ctx.files:
        for imp in meta.imports:
            target = _resolve_import(imp, meta, paths)
            if target and target != meta.path:
                edges.append({"from": meta.path, "to": target, "kind": "import"})

    return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# 5.6 — Engine with content-hash refresh
# --------------------------------------------------------------------------- #
def _iter_repo_files(
    root: Path, config: AppConfig, module: Optional[str]
) -> Iterator[tuple[str, str]]:
    ignore_names = set(config.ignore_paths)
    gitignore = _load_gitignore(root)

    def walk(dir_path: Path, rel: str) -> Iterator[tuple[str, str]]:
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name.lower())
        except OSError:
            return
        for entry in entries:
            child_rel = f"{rel}/{entry.name}" if rel else entry.name
            if _is_ignored(child_rel, entry.name, ignore_names, gitignore):
                continue
            if entry.is_dir(follow_symlinks=False):
                yield from walk(Path(entry.path), child_rel)
            elif entry.is_file(follow_symlinks=False):
                if module and not (child_rel == module or child_rel.startswith(f"{module}/")):
                    continue
                try:
                    if entry.stat().st_size > _MAX_FILE_BYTES:
                        continue
                    content = Path(entry.path).read_text(errors="ignore")
                except OSError:
                    continue
                yield child_rel, content

    yield from walk(root, "")


class ContextEngine:
    """Analyzes files and caches results by content hash (5.6)."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, FileMetadata]] = {}

    def analyze_file(self, rel_path: str, content: str) -> FileMetadata:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        cached = self._cache.get(rel_path)
        if cached and cached[0] == digest:
            return cached[1]  # unchanged — reuse (SUBTASK 5.6)
        meta = extract_metadata(rel_path, content)
        self._cache[rel_path] = (digest, meta)
        return meta

    def is_cached(self, rel_path: str, content: str) -> bool:
        cached = self._cache.get(rel_path)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return bool(cached and cached[0] == digest)

    def build(self, root: Path, config: AppConfig, module: Optional[str] = None) -> RepoContext:
        files = [
            self.analyze_file(rel, content)
            for rel, content in _iter_repo_files(root, config, module)
        ]
        return RepoContext(root=str(root), module=module, files=files)


def default_context_engine() -> ContextEngine:
    return ContextEngine()


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
class BuildContextRequest(BaseModel):
    module: Optional[str] = None
    format: str = "markdown"  # markdown | json | toon | graph


@router.post("/api/context/build")
def build_context(request: BuildContextRequest, http_request: Request) -> dict:
    """Build context for the loaded repo in the requested format."""
    repo = http_request.app.state.session_store.load_repo()
    if not repo:
        raise HTTPException(status_code=400, detail="No repository loaded")

    config: AppConfig = http_request.app.state.config
    engine: ContextEngine = http_request.app.state.context_engine
    ctx = engine.build(Path(repo.path), config, module=request.module)

    size = config.context.chunk_size_lines
    chunk_count = sum(max(1, math.ceil(m.lines / size)) for m in ctx.files if m.lines)

    result: dict = {
        "module": request.module,
        "format": request.format,
        "file_count": len(ctx.files),
        "chunk_count": chunk_count,
    }
    if request.format == "markdown":
        result["content"] = render_markdown(ctx)
    elif request.format == "toon":
        result["content"] = render_toon(ctx)
    elif request.format == "json":
        result["data"] = ctx.model_dump()
    elif request.format == "graph":
        result["data"] = build_graph(ctx)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {request.format}")
    return result
