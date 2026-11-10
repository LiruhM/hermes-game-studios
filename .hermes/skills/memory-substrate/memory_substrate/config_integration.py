"""
Memory Substrate v1.0 — Config Integration
Fase 2 do PCM (Integração Viva) — onda 1.

Indexa a configuração viva de um agente (SOUL + Carta + Skills + config-deus)
no Memory Substrate e detecta drift entre memória e configuração.

DIVERGÊNCIAS BLUEPRINT (L449-492 do PRINCIPIO-CONFIGURACAO-MAXIMA-ARQUITETURA-v3.md)
vs API REAL dos adapters — a API real vence (documentadas aqui):

1. Blueprint chamava `vault_adapter.index_batch(chunks)` como função livre de
   módulo. API REAL: `vault_adapter` é uma CLASSE (VaultAdapter) de operações
   de arquivo Obsidian (read/write/search), SEM indexação. A indexação real
   vive em `indexing.VectorStore.add_batch()` (sqlite-vec/FAISS + FTS5).
   → index_configuration() usa VectorStore.add_batch() com EmbeddingEngine.

2. Blueprint chamava `mempalace_adapter.query(...)` retornando
   `.patterns` com `.in_soul`, `.rule_text`, `.evidence_chunks`, `.confidence`.
   API REAL: `MemPalaceAdapter.search(query, limit)` faz busca semântica MCP
   e retorna List[Dict] (sem análise de padrões/frequência). A detecção de
   repetição/agregação NÃO existe no adapter — é responsabilidade deste
   módulo agrupar resultados e computar frequência.
   → detect_config_drift() usa MemPalaceAdapter.search() (quando o servidor
   MCP está no ar) e agrega padrões localmente; fallback: busca lexical no
   VectorStore (mesma base que index_configuration escreveu).

3. Blueprint usava `skill_adapter.query()`. API REAL: SkillAdapter só expõe
   manifest/list/load — sem query. Skills são lidas via
   `get_all_skills_as_chunks()` / `list_skills()`.
   → skill manifest entra na indexação; para drift de processos usamos a
   busca no VectorStore/MemPalace.

4. Blueprint: `config_loader.load_soul/load_carta/load_skill_manifest`.
   → Mantido o contrato (duck typing), mas implementamos também um
   FileSystemConfigLoader DEFAULT que lê dos caminhos reais do Hermes_Brain:
   - SOUL:    90-Sistema/Setores/SOUL-{AGENTE}.md
   - Carta:   CARTA-{SETOR}.md (raiz do vault)
   - Skills:  90-Sistema/CONFIG-DEUS/config-deus-{agente}.yaml (yaml.safe_load)
              → campos `skills` (lista de skills declaradas)
   - config-deus carregado junto (yaml) como chunk type="config_deus".

Correções E1 (funções livres, não classe) e E4 (sem API Gateway, porta 8766)
aplicadas conforme blueprint.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import Counter
from datetime import datetime

from .adapters import (
    VaultAdapter, VaultAdapterConfig,
    MemPalaceAdapter, MemPalaceAdapterConfig,
    SkillAdapter, SkillAdapterConfig,
)
from .indexing import (
    VectorStore, VectorStoreConfig,
    EmbeddingEngine,
    Chunker, ChunkerConfig, ChunkingStrategy,
)
from .models import SourceType, PARALayer, PARACategory


# ============================================================
# CAMINHOS REAIS DO VAULT (Hermes_Brain)
# ============================================================

HERMES_BRAIN = os.environ.get(
    "HERMES_BRAIN_PATH",
    r"C:/Users/mathe/Hermes_Brain",
)
SOUL_DIR = os.path.join(HERMES_BRAIN, "90-Sistema", "Setores")
CARTA_DIR = HERMES_BRAIN  # CARTA-{SETOR}.md na raiz do vault
CONFIG_DEUS_DIR = os.path.join(HERMES_BRAIN, "90-Sistema", "CONFIG-DEUS")
INDEX_DIR = os.path.join(HERMES_BRAIN, "90-Sistema", "_embeddings")


# ============================================================
# CONFIG LOADER — carrega dos caminhos reais
# ============================================================

class ConfigDoc:
    """Documento de configuração carregado (duck-typed p/ qualquer loader)."""

    def __init__(self, name: str, path: Optional[str], raw: str, data: Optional[dict] = None):
        self.name = name
        self.path = path
        self.raw = raw          # texto bruto (md) ou YAML serializado (yaml)
        self.data = data or {}  # parsed (yaml) ou frontmatter+text (md)
        self.exists = path is not None and os.path.exists(path) and bool(raw)


class FileSystemConfigLoader:
    """
    Loader padrão: lê dos caminhos reais do Hermes_Brain.

    - SOUL:    90-Sistema/Setores/SOUL-{AGENTE}.md
    - Carta:   CARTA-{SETOR}.md na raiz do vault
    - config-deus: 90-Sistema/CONFIG-DEUS/config-deus-{agente}.yaml (yaml.safe_load)
    """

    def __init__(self, brain_path: str = None):
        self.brain_path = Path(brain_path or HERMES_BRAIN)
        if not self.brain_path.exists():
            raise ValueError(f"Hermes_Brain não encontrado: {self.brain_path}")

    def _resolve_agente_case(self, agent_id: str) -> str:
        """Resolve SOUL-{agente}.md ignorando case (Windows/NTFS)."""
        soul_dir = self.brain_path / "90-Sistema" / "Setores"
        for cand in (soul_dir.glob(f"SOUL-{agent_id}.md")):
            return cand
        for cand in soul_dir.glob("SOUL-*.md"):
            if cand.stem.lower() == f"soul-{agent_id.lower()}".strip().lower():
                return cand
        return soul_dir / f"SOUL-{agent_id}.md"  # path inexistente p/ upstream decidir

    def load_soul(self, agent_id: str) -> ConfigDoc:
        path = self._resolve_agente_case(agent_id)
        if not path.exists():
            return ConfigDoc(f"SOUL-{agent_id}", str(path), "", {})
        raw = path.read_text(encoding="utf-8", errors="replace")
        return ConfigDoc(f"SOUL-{agent_id}", str(path), raw)

    def load_carta(self, agent_id: str, setor: str = None) -> ConfigDoc:
        """
        Carta do setor: 90-Sistema/Setores/CARTA-{SETOR}.md (caminho real
        no Hermes_Brain; fallback: raiz do vault). Se `setor` não for
        passado, tenta inferir do SOUL do agente (frontmatter `setor:`).
        """
        if not setor:
            setor = self._infer_setor(agent_id)
        if not setor:
            return ConfigDoc(f"CARTA-{agent_id}", None, "", {})
        # tenta primeiro em 90-Sistema/Setores/ (real), depois na raiz
        candidates = [
            self.brain_path / "90-Sistema" / "Setores" / f"CARTA-{setor}.md",
            self.brain_path / f"CARTA-{setor}.md",
        ]
        path = None
        for cand in candidates:
            if cand.exists():
                path = cand
                break
        if path is None:
            # fallback case-insensitive em ambos os diretórios
            for folder in (self.brain_path / "90-Sistema" / "Setores", self.brain_path):
                if not folder.exists():
                    continue
                for f in folder.glob("CARTA-*.md"):
                    if f.stem.lower() == f"carta-{setor.lower()}":
                        path = f
                        break
                if path:
                    break
        if path is None:
            return ConfigDoc(f"CARTA-{setor}", str(candidates[0]), "", {})
        raw = path.read_text(encoding="utf-8", errors="replace")
        return ConfigDoc(f"CARTA-{setor}", str(path), raw)

    def load_config_deus(self, agent_id: str) -> ConfigDoc:
        path = self.brain_path / "90-Sistema" / "CONFIG-DEUS" / f"config-deus-{agent_id}.yaml"
        if not path.exists():
            for cand in (self.brain_path / "90-Sistema" / "CONFIG-DEUS").glob("config-deus-*.yaml"):
                if cand.name.lower() == f"config-deus-{agent_id.lower()}".lower():
                    path = cand
                    break
        if not path.exists():
            return ConfigDoc(f"config-deus-{agent_id}", str(path), "", {})
        raw = path.read_text(encoding="utf-8", errors="replace")
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            data = {}
        return ConfigDoc(f"config-deus-{agent_id}", str(path), raw, data)

    def load_skill_manifest(self, agent_id: str) -> List[ConfigDoc]:
        """
        Skills declaradas no config-deus do agente. API REAL do
        config-deus-nephy.yaml: campo `skills_on_demand` (lista de strings
        "nome: descrição"); também aceita `skills` (lista ou dicts).
        Cada skill vira um ConfigDoc com raw = descrição + SKILL.md real
        quando existir no registry.
        """
        config_deus = self.load_config_deus(agent_id)
        skills: List[ConfigDoc] = []
        raw_yaml = config_deus.data
        if not raw_yaml:
            return skills
        entries = raw_yaml.get("skills_on_demand") or raw_yaml.get("skills") or []
        if isinstance(entries, str):
            entries = [entries]
        if not isinstance(entries, list):
            return skills
        for entry in entries:
            if isinstance(entry, dict):
                name = str(entry.get("name") or entry.get("skill") or "").strip()
                desc = str(entry.get("description") or entry.get("desc") or "").strip()
            else:
                # formato real: "nome: descrição" (primeiro ':' separa)
                s = str(entry).strip()
                name, _, desc = s.partition(":")
                name, desc = name.strip(), desc.strip()
            if not name:
                continue
            # Tenta ler SKILL.md da skill no registry local p/ conteúdo rico
            skill_md = self._find_skill_md(name)
            raw_parts = [f"Skill: {name}"]
            if desc:
                raw_parts.append(f"Descrição: {desc}")
            if skill_md:
                try:
                    extra = skill_md.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    extra = ""
                if extra:
                    raw_parts.append(extra)
            skills.append(ConfigDoc(name, str(skill_md) if skill_md else None,
                                     "\n\n".join(raw_parts)))
        return skills

    def _find_skill_md(self, skill_name: str) -> Optional[Path]:
        """Localiza SKILL.md da skill no registry (skills/ do Hermes)."""
        roots = [
            Path(os.environ.get("HERMES_SKILLS_DIR",
                                r"C:/Users/mathe/AppData/Local/hermes/skills")),
        ]
        for root in roots:
            if not root.exists():
                continue
            # match direto e case-insensitive
            direct = root / skill_name / "SKILL.md"
            if direct.exists():
                return direct
            for child in root.iterdir():
                if child.is_dir() and child.name.lower() == skill_name.lower():
                    md = child / "SKILL.md"
                    if md.exists():
                        return md
        return None

    def _infer_setor(self, agent_id: str) -> Optional[str]:
        """Tenta inferir o setor do agente a partir do SOUL (frontmatter/texto)."""
        soul = self.load_soul(agent_id)
        if not soul.raw:
            return None
        m = re.search(r"(?im)^setor\s*[:=]\s*(.+)$", soul.raw)
        if m:
            return m.group(1).strip().strip('"').strip("'")
        m = re.search(r"(?im)^\s*-\s*setor\s*:\s*(.+)$", soul.raw)
        if m:
            return m.group(1).strip().strip('"').strip("'")
        return None


# ============================================================
# INDEXAÇÃO — index_configuration (função livre, correção E1)
# ============================================================

def _make_vector_store() -> VectorStore:
    """VectorStore apontando para o índice real da Fase 1 (90-Sistema/_embeddings)."""
    config = VectorStoreConfig(
        db_path=os.path.join(INDEX_DIR, "memory_substrate.db"),
        index_type="hnsw",
        dimensions=384,
    )
    return VectorStore(config)


def _make_embedder() -> EmbeddingEngine:
    """EmbeddingEngine reutilizando o cache real de embeddings da Fase 1."""
    from .indexing.embedding_engine import EmbeddingConfig
    config = EmbeddingConfig(
        embedding_cache_path=os.path.join(INDEX_DIR, "embedding_cache.json"),
    )
    return EmbeddingEngine(config)


def _make_chunker() -> Chunker:
    return Chunker(ChunkerConfig(strategy=ChunkingStrategy.SEMANTIC))


def _source_type_for(doc_type: str) -> str:
    return {"soul": "vault", "carta": "vault", "skill": "skill", "config_deus": "vault"}[doc_type]


def index_configuration(agent_id: str, config_loader=None, setor: str = None,
                        vault_adapter=None, vector_store=None, embedder=None,
                        chunker=None, write_sidecar: bool = True) -> Dict[str, Any]:
    """
    Indexa SOUL + Carta + Skills + config-deus do agente no Memory Substrate.

    Blueprint L458: `vault_adapter.index_batch(chunks)` — API REAL: não existe
    index_batch no VaultAdapter; a indexação real é VectorStore.add_batch()
    (divergência #1 no cabeçalho do módulo). Metadados ricos preservados:
    type=soul/carta/skill/config_deus, agent, layer, skill (nome).

    Retorna dict com contagens por tipo + ids gerados.
    """
    loader = config_loader or FileSystemConfigLoader()

    soul = loader.load_soul(agent_id)
    carta = loader.load_carta(agent_id, setor=setor)
    config_deus = loader.load_config_deus(agent_id)
    skills = loader.load_skill_manifest(agent_id)

    # ---- monta chunks com metadados ricos (blueprint L464-470) ----
    docs: List[Dict[str, Any]] = []
    if soul.raw:
        docs.append({"type": "soul", "doc": soul, "layer": 0})
    if carta.raw:
        docs.append({"type": "carta", "doc": carta, "layer": 1})
    if config_deus.raw:
        docs.append({"type": "config_deus", "doc": config_deus, "layer": 0})
    for s in skills:
        if s.raw:
            docs.append({"type": "skill", "doc": s, "layer": 2})

    if not docs:
        return {"agent_id": agent_id, "indexed": 0, "chunks": 0,
                "counts": {}, "chunk_ids": [], "missing": _missing_docs(loader, agent_id, setor)}

    # ---- chunking + embeddings + add_batch real ----
    store = vector_store or _make_vector_store()
    emb = embedder or _make_embedder()
    ch = chunker or _make_chunker()

    flat_chunks: List[Dict] = []
    for spec in docs:
        pieces = ch.chunk(spec["doc"].raw, metadata={"agent": agent_id, "type": spec["type"]})
        for piece in pieces:
            content = piece.get("content", piece) if isinstance(piece, dict) else piece
            if isinstance(content, dict):
                content = content.get("content", "")
            flat_chunks.append({
                "content": content,
                "source": _source_type_for(spec["type"]),
                "source_id": spec["doc"].path or spec["doc"].name,
                "title": f"{spec['doc'].name} [{agent_id}/{spec['type']}]",
                "summary": (content or "")[:200],
                "para_layer": spec["layer"],
                "para_category": "system",
                "tags": [f"agent:{agent_id}", f"type:{spec['type']}", "fase2-pcm"],
                "metadata": {
                    "type": spec["type"],
                    "agent": agent_id,
                    "layer": spec["layer"],
                    **({"skill": spec["doc"].name} if spec["type"] == "skill" else {}),
                    **({"setor": setor} if setor else {}),
                },
            })

    # embeddings em batch (uma passada, leve p/ 12GB RAM)
    texts = [c["content"] for c in flat_chunks]
    embeddings = emb.encode(texts, show_progress=False) if texts else []

    chunk_ids: List[str] = []
    for chunk, embedding in zip(flat_chunks, embeddings):
        # dict do chunk já bate 1:1 com os kwargs de VectorStore.add()
        chunk_id = store.add(embedding=embedding, **chunk)
        chunk_ids.append(chunk_id)

    counts = Counter(spec["type"] for spec in docs)

    result = {
        "agent_id": agent_id,
        "indexed": len(docs),
        "chunks": len(chunk_ids),
        "counts": dict(counts),
        "chunk_ids": chunk_ids,
        "missing": _missing_docs(loader, agent_id, setor),
    }

    if write_sidecar:
        _write_index_sidecar(agent_id, result)

    return result


def _missing_docs(loader, agent_id: str, setor: Optional[str]) -> List[str]:
    missing = []
    checks = {
        "soul": lambda: loader.load_soul(agent_id).raw,
        "carta": lambda: loader.load_carta(agent_id, setor=setor).raw,
        "config_deus": lambda: loader.load_config_deus(agent_id).raw,
    }
    for name, fn in checks.items():
        try:
            if not fn():
                missing.append(name)
        except Exception:
            missing.append(name)
    return missing


def _write_index_sidecar(agent_id: str, result: Dict[str, Any]) -> None:
    """Grava log da indexação junto ao índice real da Fase 1 (auditoria)."""
    try:
        import json
        path = os.path.join(INDEX_DIR, "config_integration_log.jsonl")
        entry = {
            "ts": datetime.now().isoformat(),
            "agent_id": agent_id,
            "indexed": result["indexed"],
            "chunks": result["chunks"],
            "counts": result["counts"],
            "chunk_ids": result["chunk_ids"],
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ============================================================
# DETECÇÃO DE DRIFT — detect_config_drift (função livre, correção E1)
# ============================================================

def _mempalace_alive(adapter: MemPalaceAdapter) -> bool:
    """Verifica se o servidor MCP MemPalace está acessível.

    Check rápido de porta TCP (2s) ANTES do status() — evita esperar
    os 3 retries x 30s de timeout do adapter quando o servidor está fora.
    """
    try:
        import socket
        from urllib.parse import urlparse
        u = urlparse(adapter.endpoint if hasattr(adapter, "endpoint") else adapter.config.mcp_endpoint)
        host, port = u.hostname or "localhost", u.port or 8765
        with socket.create_connection((host, port), timeout=2):
            pass
    except Exception:
        return False
    try:
        status = adapter.status()
        return isinstance(status, dict) and (
            status.get("status") in ("ok", "healthy", "running", "connected")
            or "drawers" in status or "wings" in status  # payload real do mempalace_status
        )
    except Exception:
        return False


def _normalize_drift(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um candidato de drift (API real retorna dicts, não objetos)."""
    return {
        "type": d.get("type", "unknown"),
        "suggestion": d.get("suggestion", ""),
        "evidence": d.get("evidence", []) or [],
        "confidence": float(d.get("confidence", 0.0)),
    }


def detect_config_drift(
    agent_id: str,
    min_decision_freq: int = 5,
    min_proc_freq: int = 3,
    min_error_freq: int = 2,
    config_loader=None,
    mempalace_adapter: Optional[MemPalaceAdapter] = None,
    vector_store: Optional[VectorStore] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Detecta padrões na memória que sugerem evolução da config.
    Retorna lista de drift candidates (NÃO aplica — só detecta).

    Blueprint L473-492: `mempalace_adapter.query(...).patterns` com
    `.in_soul/.rule_text/.confidence`. API REAL: MemPalaceAdapter.search()
    retorna List[Dict] sem agregação de padrões (divergência #2). A agregação
    por frequência e a checagem `in_soul` são feitas AQUI.

    Regras (blueprint):
      1. Decisões repetidas (≥ min_decision_freq) → soul_rule
      2. Procedimentos repetidos (≥ min_proc_freq) → skill
      3. Erros repetidos (≥ min_error_freq) → guardrail
    """
    loader = config_loader or FileSystemConfigLoader()
    soul = loader.load_soul(agent_id)
    soul_text = (soul.raw or "").lower()

    drifts: List[Dict[str, Any]] = []
    backends = []  # (nome, resultados-brutos)

    # ---- fonte 1: MemPalace MCP (se no ar) ----
    palace = mempalace_adapter
    if palace is None:
        # só instancia se a porta responder (check TCP barato)
        try:
            import socket
            with socket.create_connection(("localhost", 8765), timeout=2):
                pass
            palace = MemPalaceAdapter(MemPalaceAdapterConfig())
        except Exception:
            palace = None
    if palace is not None and _mempalace_alive(palace):
        for label, query in [
            ("decision", f"Decisões do agente {agent_id}"),
            ("procedure", f"Procedimentos executados por {agent_id}"),
            ("error", f"Erros e falhas do agente {agent_id}"),
        ]:
            try:
                results = palace.search(query, limit=limit)
            except Exception:
                results = []
            backends.append((label, _as_dicts(results)))
    else:
        palace = None

    # ---- fonte 2 (fallback / complemento): VectorStore lexical ----
    store = vector_store or _make_vector_store()
    for label, query in [
        ("decision", f"decisão {agent_id}"),
        ("procedure", f"procedimento {agent_id}"),
        ("error", f"erro {agent_id}"),
    ]:
        try:
            lexical = store.search_lexical(query, k=limit)
            backends.append((label, [
                {"content": "", "id": cid, "text": "", **(store.get(cid) or {})}
                for cid, _score in lexical
            ]))
        except Exception:
            pass

    # ---- agregação de padrões por frequência (responsabilidade local) ----
    type_cfg = {
        "decision": ("soul_rule", min_decision_freq, "Adicionar regra ao SOUL"),
        "procedure": ("skill", min_proc_freq, "Promover procedimento a skill"),
        "error": ("guardrail", min_error_freq, "Adicionar guardrail"),
    }
    for label, (drift_type, min_freq, action) in type_cfg.items():
        items = [items for l, items in backends if l == label]
        items = [it for sub in items for it in sub]
        # agrupa por texto normalizado do chunk
        groups: Dict[str, List[Dict]] = {}
        for it in items:
            text = _norm_text(it.get("content") or it.get("text") or "")
            if not text:
                continue
            groups.setdefault(text, []).append(it)
        for text, group in groups.items():
            freq = len(group)
            if freq < min_freq:
                continue
            in_soul = text in soul_text
            if in_soul:
                continue  # já consolidado no SOUL — não é drift
            drifts.append(_normalize_drift({
                "type": drift_type,
                "suggestion": f"{action}: {text[:120]}",
                "evidence": [
                    {"id": g.get("id", ""), "source": g.get("source", ""),
                     "source_id": g.get("source_id", ""),
                     "excerpt": (g.get("content") or g.get("text") or "")[:200]}
                    for g in group[:5]
                ],
                "confidence": min(1.0, 0.3 + 0.1 * freq),
            }))

    return drifts


def _norm_text(s: str) -> str:
    """Normalização simples p/ agrupar ocorrências semelhantes."""
    s = re.sub(r"\s+", " ", (s or "").strip().lower())
    return s[:200]


def _as_dicts(results) -> List[Dict]:
    out = []
    for r in results or []:
        if isinstance(r, dict):
            out.append(r)
        else:
            out.append({"content": getattr(r, "content", ""), "id": getattr(r, "id", ""), "text": ""})
    return out

