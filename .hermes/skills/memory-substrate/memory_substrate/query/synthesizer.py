"""
Memory Substrate v1.0 — Query Engine: Synthesizer
Token-optimized answer generation with citations from retrieved sources.
"""

import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from string import Template


class CitationStyle(str, Enum):
    WIKI = "wiki"       # [[source]] style
    MARKDOWN = "markdown"  # [text](url) style
    NUMERIC = "numeric"    # [1], [2] style
    FOOTNOTE = "footnote"  # ¹, ² style


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    PLAIN = "plain"


@dataclass
class SynthesizerConfig:
    model_name: str = "nemotron-3-ultra"
    max_context_tokens: int = 12000
    max_output_tokens: int = 2000
    temperature: float = 0.3
    citation_style: CitationStyle = CitationStyle.WIKI
    output_format: OutputFormat = OutputFormat.MARKDOWN
    include_sources: bool = True
    include_confidence: bool = True
    include_gaps: bool = True
    include_follow_up: bool = True
    system_prompt_template: str = None
    user_prompt_template: str = None
    token_optimization: bool = True  # Use token-optimization pipeline
    
    def __post_init__(self):
        if self.system_prompt_template is None:
            self.system_prompt_template = self._default_system_prompt()
        if self.user_prompt_template is None:
            self.user_prompt_template = self._default_user_prompt()
    
    def _default_system_prompt(self) -> str:
        return """Você é um assistente de conhecimento pessoal avançado. Responda à pergunta usando APENAS o contexto fornecido do Second Brain do usuário.

REGRAS OBRIGATÓRIAS:
1. Responda EM PORTUGUÊS BRASILEIRO
2. Use APENAS informações do contexto fornecido (não invente)
3. CITE fontes usando o formato especificado: [[wiki-link]] para notas, [titulo](url) para externo
4. Se contexto insuficiente: "Não tenho informação suficiente no vault sobre X"
5. Estruture: Resposta direta → Detalhes → Fontes → Lacunas → Próximos passos
6. Tom: profissional, direto, acionável, encorajador

FORMATO DE SAÍDA:
## Resposta
{{resposta sintetizada}}

## Detalhes & Evidências
{{bullet points com claims + fontes}}

## Fontes Consultadas
{{lista numerada com [[links]] e relevância}}

## Lacunas Identificadas
{{o que NÃO foi encontrado no vault}}

## Próximos Passos Sugeridos
{{capturar, destilar, organizar, expressar}}"""

    def _default_user_prompt(self) -> str:
        return """PERGUNTA: {{question}}

CONTEXTO (fontes do vault):
{{context}}

REGRAS:
1. Responda EM PORTUGUÊS BRASILEIRO
2. Use APENAS informações do contexto (não invente)
3. CITE fontes: [[wiki-link]] para notas, [titulo](url) para externo
4. Se contexto insuficiente: "Não tenho informação suficiente no vault sobre X"
5. Estruture: Resposta direta → Detalhes → Fontes → Lacunas → Próximos passos
6. Tom: profissional, direto, acionável, encorajador

FORMATO:
## Resposta
{{resposta sintetizada}}

## Detalhes & Evidências
{{bullet points com claims + fontes}}

## Fontes Consultadas
{{lista numerada com [[links]] e relevância}}

## Lacunas Identificadas
{{o que NÃO foi encontrado no vault}}

## Próximos Passos Sugeridos
{{capturar, destilar, organizar, expressar}}"""


@dataclass
class SynthesizedAnswer:
    """Complete synthesized answer with metadata."""
    answer: str
    citations: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    gaps: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    sources: List[Dict] = field(default_factory=list)
    token_count: int = 0
    latency_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)


class Synthesizer:
    """
    Generates token-optimized answers with citations from retrieved sources.
    Integrates with token-optimization pipeline for budget enforcement.
    """
    
    def __init__(
        self, 
        config: SynthesizerConfig = None,
        token_optimizer = None  # TokenOptimizationPipeline
    ):
        self.config = config or SynthesizerConfig()
        self.token_optimizer = token_optimizer
        self._llm_client = None
    
    def _get_llm(self):
        """Get LLM client (placeholder - integrate with actual LLM)."""
        # This would integrate with the actual LLM provider
        # For now, return a mock that demonstrates the structure
        return self
    
    def synthesize(
        self,
        query: str,
        sources: List[Dict],
        plan = None,
        context: Dict = None
    ) -> SynthesizedAnswer:
        """
        Generate synthesized answer from retrieved sources.
        
        Args:
            query: Original user query
            sources: Retrieved sources with content and metadata
            plan: QueryPlan with intent, entities, etc.
            context: Additional context (conversation history, etc.)
            
        Returns:
            SynthesizedAnswer with answer, citations, gaps, etc.
        """
        start_time = time.time()
        context = context or {}
        
        # 1. Prepare context for LLM
        llm_context = self._prepare_context(sources, query)
        
        # 2. Build prompt
        prompt = self._build_prompt(query, llm_context, plan)
        
        # 3. Apply token optimization if available
        if self.config.token_optimization and self.token_optimizer:
            # Would pass through token optimization pipeline
            pass
        
        # 4. Generate answer (using LLM)
        # For now, we'll use a template-based approach as placeholder
        answer_text = self._generate_answer(query, sources, plan)
        
        # 5. Extract citations and format
        formatted = self._format_output(answer_text, sources)
        
        # 6. Calculate confidence
        confidence = self._calculate_confidence(sources, formatted)
        
        # 7. Identify gaps
        gaps = self._identify_gaps(query, sources, formatted)
        
        # 8. Generate follow-up questions
        follow_ups = self._generate_follow_ups(query, sources, formatted)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return SynthesizedAnswer(
            answer=formatted,
            citations=self._extract_citations(formatted, sources),
            confidence=confidence,
            gaps=gaps,
            follow_up_questions=follow_ups,
            sources=[self._source_to_dict(s) for s in sources],
            token_count=self._estimate_tokens(formatted),
            latency_ms=latency_ms,
            metadata={
                "query": query,
                "source_count": len(sources),
                "plan_intent": plan.intent.value if plan else "unknown"
            }
        )
    
    def _prepare_context(self, sources: List[Dict], query: str) -> str:
        """Prepare context string from sources."""
        if not sources:
            return "Nenhuma fonte encontrada."
        
        context_parts = []
        
        for i, source in enumerate(sources, 1):
            content = source.get("content", "")
            title = source.get("title", f"Fonte {i}")
            source_type = source.get("source", "unknown")
            source_id = source.get("source_id", source.get("id", ""))
            score = source.get("score", 0)
            match_types = source.get("match_types", {})
            
            # Build source reference
            if source_type == "vault":
                ref = f"[[{source_id}]]"
            elif source_type == "mempalace":
                ref = f"[[{source.get('wing', '')}/{source.get('room', '')}/{source_id}]]"
            elif source_type == "skill":
                ref = f"[[skill:{source.get('skill_name', source_id)}]]"
            else:
                ref = f"[{source_id}]"
            
            # Truncate content if too long
            if len(content) > 2000:
                content = content[:2000] + "... [truncado]"
            
            part = f"""---
Fonte {i}: {title} ({source_type})
Referência: {ref}
Score: {score:.3f}
Match: {', '.join(match_types.keys())}
Conteúdo:
{content}
"""
            context_parts.append(part)
        
        return "\n".join(context_parts)
    
    def _build_prompt(self, query: str, context: str, plan) -> str:
        """Build prompt from templates."""
        # Use template substitution
        prompt = self.config.user_prompt_template.replace("{{question}}", query)
        prompt = prompt.replace("{{context}}", context)
        
        if plan:
            prompt = prompt.replace("{{intent}}", plan.intent.value if hasattr(plan, 'intent') else str(plan))
            prompt = prompt.replace("{{entities}}", ", ".join([e.text for e in plan.entities]) if hasattr(plan, 'entities') else "")
        
        return prompt
    
    def _generate_answer(self, query: str, sources: List[Dict], plan) -> str:
        """
        Generate answer using LLM.
        Placeholder - integrates with actual LLM provider.
        """
        # This is where the actual LLM call would happen
        # For now, return a structured template demonstrating the format
        
        if not sources:
            return self._no_sources_response(query)
        
        # Extract key information from sources
        key_points = self._extract_key_points(sources)
        
        # Build response based on intent
        if plan and hasattr(plan, 'intent'):
            intent = plan.intent.value if hasattr(plan.intent, 'value') else str(plan.intent)
        else:
            intent = "general"
        
        # Template-based generation (replace with actual LLM call)
        if intent == "synthesize" or intent == "explain":
            return self._synthesize_explanation(query, sources, key_points)
        elif intent == "list":
            return self._synthesize_list(query, sources, key_points)
        elif intent == "find":
            return self._synthesize_find(query, sources, key_points)
        elif intent == "traverse":
            return self._synthesize_traverse(query, sources, key_points)
        elif intent == "compare":
            return self._synthesize_comparison(query, sources, key_points)
        elif intent == "summarize":
            return self._synthesize_summary(query, sources, key_points)
        elif intent == "count":
            return self._synthesize_count(query, sources, key_points)
        else:
            return self._synthesize_general(query, sources, key_points)
    
    def _no_sources_response(self, query: str) -> str:
        """Response when no sources found."""
        return f"""## Resposta
Não tenho informação suficiente no vault sobre "{query}".

## Detalhes & Evidências
- Busca realizada no vault (Obsidian), MemPalace e skills
- Nenhuma fonte relevante encontrada para a consulta

## Fontes Consultadas
*Nenhuma fonte encontrada*

## Lacunas Identificadas
- Tópico "{query}" não possui documentação no Second Brain
- Nenhuma nota, drawer ou skill relacionado encontrado

## Próximos Passos Sugeridos
- `/capture "Ideia: documentar {query}" #ideia #pesquisa` — Capturar gap
- `/query "{query} conceitos básicos" --sources 10` — Buscar conceitos relacionados
- `/express --type doc --topic "{query}"` — Gerar documento base para preencher"""
    
    def _extract_key_points(self, sources: List[Dict]) -> List[str]:
        """Extract key points from sources."""
        points = []
        for source in sources:
            content = source.get("content", "")
            # Simple extraction: first sentence of each paragraph
            paragraphs = content.split("\n\n")
            for p in paragraphs[:3]:  # Max 3 per source
                p = p.strip()
                if len(p) > 50:
                    points.append(p[:200])
        return points[:10]  # Max 10 points
    
    def _synthesize_explanation(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate explanation-style answer."""
        points_text = "\n".join(f"- {p}" for p in key_points[:5])
        
        sources_list = []
        for i, s in enumerate(sources[:5], 1):
            title = s.get("title", f"Fonte {i}")
            source_id = s.get("source_id", s.get("id", ""))
            if s.get("source") == "vault":
                sources_list.append(f"{i}. [[{source_id}]] — {title}")
            else:
                sources_list.append(f"{i}. [{source_id}] — {title}")
        
        sources_text = "\n".join(sources_list)
        
        return f"""## Resposta
{query} refere-se a {key_points[0] if key_points else 'um conceito documentado no seu Second Brain'}. Baseado nas fontes recuperadas, os pontos principais são:

## Detalhes & Evidências
{points_text}

## Fontes Consultadas
{sources_text}

## Lacunas Identificadas
- Detalhes técnicos específicos podem não estar documentados
- Exemplos práticos de implementação podem faltar

## Próximos Passos Sugeridos
- `/capture "Exemplo prático: {query}" #exemplo #implementação` — Capturar caso de uso
- `/destilar --note "fonte principal" --layer 4` — Avançar para atomic note
- `/query "como implementar {query} na prática" --sources 10` — Buscar exemplos"""
    
    def _synthesize_list(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate list-style answer."""
        items = []
        for i, s in enumerate(sources[:10], 1):
            title = s.get("title", f"Item {i}")
            source_id = s.get("source_id", s.get("id", ""))
            if s.get("source") == "vault":
                items.append(f"{i}. [[{source_id}]] — {title}")
            else:
                items.append(f"{i}. [{source_id}] — {title}")
        
        items_text = "\n".join(items) if items else "Nenhum item encontrado."
        
        return f"""## Resposta
Encontrei {len(sources)} itens relacionados a "{query}":

## Detalhes & Evidências
{items_text}

## Fontes Consultadas
{chr(10).join(items)}

## Lacunas Identificadas
- Lista pode não ser exaustiva
- Itens podem estar desatualizados

## Próximos Passos Sugeridos
- `/organize --auto` — Processar inbox para encontrar mais itens
- `/query "{query} status" --sources 20` — Buscar status de cada item"""
    
    def _synthesize_find(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate find-style answer."""
        if not sources:
            return self._no_sources_response(query)
        
        # Best match
        best = sources[0]
        title = best.get("title", "Documento")
        source_id = best.get("source_id", best.get("id", ""))
        content = best.get("content", "")[:500]
        
        if best.get("source") == "vault":
            ref = f"[[{source_id}]]"
        else:
            ref = f"[{source_id}]"
        
        other_sources = []
        for i, s in enumerate(sources[1:4], 2):
            title = s.get("title", f"Fonte {i}")
            source_id = s.get("source_id", s.get("id", ""))
            if s.get("source") == "vault":
                other_sources.append(f"{i}. [[{source_id}]] — {title}")
            else:
                other_sources.append(f"{i}. [{source_id}] — {title}")
        
        return f"""## Resposta
Encontrei "{title}" ({ref}) como melhor correspondência para "{query}".

**Localização:** {ref}
**Trecho relevante:** {content}...

## Detalhes & Evidências
- Melhor match: {title} (score: {sources[0].get('score', 0):.3f})
- Fontes alternativas: {len(sources)-1} outras

## Fontes Consultadas
1. {ref} — {title}
{chr(10).join(other_sources)}

## Lacunas Identificadas
- Conteúdo pode estar desatualizado
- Caminho exato pode variar se arquivo foi movido

## Próximos Passos Sugeridos
- `/query "conteúdo completo de {title}"` — Ler documento completo
- `/organize --external-scan --dry-run` — Verificar arquivos soltos relacionados"""
    
    def _synthesize_traverse(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate traverse-style answer showing connections."""
        connections = []
        for s in sources[:10]:
            entity = s.get("metadata", {}).get("matched_entity", "")
            source_id = s.get("source_id", s.get("id", ""))
            if entity:
                connections.append(f"- **{entity}** → {s.get('title', 'Item')} ({s.get('source', 'unknown')})")
        
        return f"""## Resposta
Encontrei conexões entre entidades relacionadas a "{query}":

## Detalhes & Evidências
{chr(10).join(connections) if connections else "Nenhuma conexão explícita encontrada"}

## Fontes Consultadas
{chr(10).join(f"{i+1}. {s.get('title', 'Item')}" for i, s in enumerate(sources[:10]))}

## Lacunas Identificadas
- Grafo de conhecimento pode estar incompleto
- Túneles entre wings podem não estar mapeados

## Próximos Passos Sugeridos
- `/query "túneis entre wings" --sources 20` — Explorar conexões MemPalace
- `/capture "Mapear conexões: {query}" #grafo #conexoes` — Documentar descobertas"""
    
    def _synthesize_comparison(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate comparison answer."""
        # Group by source or topic
        topics = {}
        for s in sources:
            topic = s.get("metadata", {}).get("topic", s.get("title", "Tópico"))
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(s)
        
        comparison = []
        for topic, items in topics.items():
            comparison.append(f"\n### {topic}")
            for item in items[:3]:
                title = item.get("title", "Item")
                content = item.get("content", "")[:200]
                comparison.append(f"- **{title}**: {content}...")
        
        return f"""## Resposta
Comparação para "{query}":

{''.join(comparison)}

## Fontes Consultadas
{chr(10).join(f"{i+1}. {s.get('title', 'Fonte')}" for i, s in enumerate(sources[:10]))}

## Lacunas Identificadas
- Comparação pode ser superficial sem análise profunda
- Critérios de comparação não padronizados

## Próximos Passos Sugeridos
- `/capture "Critérios de comparação para {query}" #comparação #critérios`
- `/express --type report --topic "{query}" --sources 15` — Gerar relatório comparativo"""
    
    def _synthesize_summary(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate summary answer."""
        points_text = "\n".join(f"- {p}" for p in key_points[:7])
        
        return f"""## Resposta
Resumo sobre "{query}":

## Detalhes & Evidências
{points_text}

## Fontes Consultadas
{chr(10).join(f"{i+1}. {s.get('title', 'Fonte')} ({s.get('source', 'unknown')})" for i, s in enumerate(sources[:10]))}

## Lacunas Identificadas
- Resumo baseado em {len(sources)} fontes
- Detalhes específicos podem ter sido omitidos

## Próximos Passos Sugeridos
- `/express --type article --topic "{query}" --sources {len(sources)}` — Gerar artigo completo
- `/destilar --note "resumo-{query}" --layer 4` — Criar atomic note"""
    
    def _synthesize_count(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """Generate count answer."""
        count = len(sources)
        
        return f"""## Resposta
Encontrados **{count}** itens para "{query}".

## Detalhes & Evidências
- Total de fontes: {count}
- Distribuição: {self._count_by_source(sources)}

## Fontes Consultadas
{chr(10).join(f"{i+1}. {s.get('title', 'Item')} ({s.get('source', 'unknown')})" for i, s in enumerate(sources[:20]))}

## Lacunas Identificadas
- Contagem baseada em busca atual, pode não ser exaustiva
- Itens arquivados podem não ter sido incluídos

## Próximos Passos Sugeridos
- `/organize --external-scan --dry-run` — Verificar itens fora do PARA
- `/query "{query} lista completa" --sources 50` — Buscar lista mais completa"""
    
    def _synthesize_general(self, query: str, sources: List[Dict], key_points: List[str]) -> str:
        """General purpose synthesis."""
        points_text = "\n".join(f"- {p}" for p in key_points[:5])
        
        return f"""## Resposta
Informações sobre "{query}":

## Detalhes & Evidências
{points_text}

## Fontes Consultadas
{chr(10).join(f"{i+1}. {s.get('title', 'Fonte')} ({s.get('source', 'unknown')})" for i, s in enumerate(sources[:10]))}

## Lacunas Identificadas
- Análise baseada em {len(sources)} fontes recuperadas

## Próximos Passos Sugeridos
- `/query "mais detalhes sobre {query}" --sources 15` — Aprofundar"""
    
    def _count_by_source(self, sources: List[Dict]) -> str:
        """Count sources by type."""
        counts = {}
        for s in sources:
            src = s.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return ", ".join(f"{k}: {v}" for k, v in counts.items())
    
    def _format_output(self, answer: str, sources: List[Dict]) -> str:
        """Format final output with citations."""
        # The answer already includes citations in the template
        return answer
    
    def _extract_citations(self, answer: str, sources: List[Dict]) -> List[Dict]:
        """Extract citations from formatted answer."""
        import re
        
        citations = []
        # Find [[wiki-links]] and [text](url) patterns
        wiki_links = re.findall(r'\[\[([^\]]+)\]\]', answer)
        markdown_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', answer)
        
        for link in wiki_links:
            # Find matching source
            for s in sources:
                if link in s.get("source_id", "") or link in s.get("title", ""):
                    citations.append({
                        "type": "wiki",
                        "reference": link,
                        "source_id": s.get("source_id", ""),
                        "title": s.get("title", ""),
                        "source": s.get("source", "")
                    })
                    break
        
        for text, url in markdown_links:
            citations.append({
                "type": "markdown",
                "text": text,
                "url": url
            })
        
        return citations
    
    def _source_to_dict(self, source: Dict) -> Dict:
        """Convert source to serializable dict."""
        return {
            "id": source.get("id", source.get("source_id", "")),
            "title": source.get("title", ""),
            "source": source.get("source", "unknown"),
            "score": source.get("score", 0),
            "match_types": source.get("match_types", {}),
            "metadata": {k: v for k, v in source.items() 
                        if k not in ["content", "match_types"]}
        }
    
    def _calculate_confidence(self, sources: List[Dict], formatted: str) -> float:
        """Calculate confidence score for the answer."""
        if not sources:
            return 0.0
        
        # Base confidence on number and quality of sources
        avg_score = sum(s.get("score", 0) for s in sources) / len(sources)
        source_count_factor = min(1.0, len(sources) / 5.0)
        
        # Check if answer says "não tenho informação"
        if "não tenho informação suficiente" in formatted.lower():
            return 0.1
        
        confidence = (avg_score * 0.6) + (source_count_factor * 0.4)
        return min(1.0, max(0.0, confidence))
    
    def _identify_gaps(self, query: str, sources: List[Dict], formatted: str) -> List[str]:
        """Identify knowledge gaps."""
        gaps = []
        
        if not sources:
            gaps.append(f"Nenhuma documentação encontrada para '{query}'")
            return gaps
        
        if len(sources) < 3:
            gaps.append("Poucas fontes encontradas — cobertura pode ser incompleta")
        
        # Check for missing perspectives
        source_types = set(s.get("source") for s in sources)
        if len(source_types) == 1:
            gaps.append(f"Apenas fontes do tipo '{list(source_types)[0]}' — perspectivas limitadas")
        
        # Check for recency
        # (would need timestamp metadata)
        
        # Check answer for uncertainty markers
        uncertainty_phrases = ["pode ser", "talvez", "provavelmente", "não sei", "não tenho certeza"]
        for phrase in uncertainty_phrases:
            if phrase in formatted.lower():
                gaps.append(f"Resposta contém incerteza: '{phrase}'")
                break
        
        return gaps
    
    def _generate_follow_ups(self, query: str, sources: List[Dict], formatted: str) -> List[str]:
        """Generate follow-up questions."""
        follow_ups = []
        
        # Based on intent
        follow_ups.append(f"Como implementar {query} na prática?")
        follow_ups.append(f"Quais são as melhores práticas para {query}?")
        follow_ups.append(f"Exemplos de {query} em produção?")
        
        # Based on gaps
        if len(sources) < 5:
            follow_ups.append(f"Onde encontrar mais documentação sobre {query}?")
        
        # Based on source types
        source_types = set(s.get("source") for s in sources)
        if "vault" in source_types and "mempalace" not in source_types:
            follow_ups.append(f"Existe conhecimento no MemPalace sobre {query}?")
        
        return follow_ups[:5]
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation."""
        # ~4 chars per token for Portuguese
        return len(text) // 4


# ============================================================
# FACTORY
# ============================================================

def create_synthesizer(
    config: SynthesizerConfig = None,
    token_optimizer = None
) -> Synthesizer:
    """Create synthesizer with default or custom config."""
    if config is None:
        config = SynthesizerConfig()
    return Synthesizer(config, token_optimizer)