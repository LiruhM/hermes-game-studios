"""
Memory Substrate v1.0 — Query Engine: Context Builder
Assembles retrieved chunks into optimized LLM context with token budget enforcement.
"""

import json
import yaml
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import tiktoken
from pathlib import Path


class ContextPriority(int, Enum):
    SYSTEM_PROMPT = 1      # Never truncate
    CURRENT_TASK = 2       # Query + immediate context
    ACTIVE_FILES = 3       # Files in focus
    RECENT_TOOLS = 4       # Last 3 tool results
    ROLLING_SUMMARY = 5    # Compressed history
    MEMORIES = 6           # Semantic memory retrieval
    OLDER_HISTORY = 7      # Truncate first


@dataclass
class ContextSegment:
    """A segment of context with priority and token count."""
    priority: int
    name: str
    content: str
    tokens: int
    required: bool = False  # If True, never truncate
    metadata: Dict = field(default_factory=dict)
    
    def __lt__(self, other):
        return self.priority < other.priority


@dataclass
class PrimacyRecencyConfig:
    """Configuration for primacy/recency weighting in context assembly.
    
    Primacy effect: First items in a list are remembered better
    Recency effect: Last items in a list are remembered better
    """
    enabled: bool = True
    primacy_weight: float = 1.2       # Weight for early segments (primacy)
    recency_weight: float = 1.5       # Weight for recent segments (recency)
    middle_weight: float = 1.0        # Baseline weight for middle segments
    decay_rate: float = 0.1           # Exponential decay rate
    apply_to: List[str] = field(default_factory=lambda: [
        "memories", 
        "conversation_history", 
        "active_files"
    ])
    strategy: str = "exponential"     # exponential | linear | step
    
    def __post_init__(self):
        if self.strategy not in ["exponential", "linear", "step"]:
            raise ValueError(f"Unknown strategy: {self.strategy}")


@dataclass
class ContextBuilderConfig:
    max_context_tokens: int = 12000
    reserved_for_response: int = 4000
    encoder_name: str = "cl100k_base"  # GPT-4 / GPT-3.5-turbo encoding
    priority_order: Dict[str, int] = field(default_factory=lambda: {
        "system_prompt": 1,
        "current_task": 2,
        "active_files": 3,
        "recent_tools": 4,
        "rolling_summary": 5,
        "memories": 6,
        "older_history": 7
    })
    truncation_strategy: str = "priority"  # priority | proportional | sliding_window
    min_segment_tokens: int = 100  # Minimum tokens to keep a segment
    # Primacy/Recency weighting (NEW)
    primacy_recency: PrimacyRecencyConfig = field(default_factory=PrimacyRecencyConfig)


class ContextBuilder:
    """
    Builds optimized LLM context from retrieved sources.
    Handles token budgeting, prioritization, and truncation.
    """

    def __init__(self, config: ContextBuilderConfig = None, config_path: str = None):
        # Load from YAML if path provided
        if config_path:
            config = self._load_config_from_yaml(config_path)
        self.config = config or ContextBuilderConfig()
        self.encoder = tiktoken.get_encoding(self.config.encoder_name)
        self.hard_limit = self.config.max_context_tokens - self.config.reserved_for_response

    def _load_config_from_yaml(self, config_path: str) -> ContextBuilderConfig:
        """Load ContextBuilderConfig from YAML file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Extract context_builder section
        cb_data = data.get('context_builder', {})
        
        # Build PrimacyRecencyConfig
        pr_data = cb_data.get('primacy_recency', {})
        primacy_recency = PrimacyRecencyConfig(
            enabled=pr_data.get('enabled', True),
            primacy_weight=pr_data.get('primacy_weight', 1.2),
            recency_weight=pr_data.get('recency_weight', 1.5),
            middle_weight=pr_data.get('middle_weight', 1.0),
            decay_rate=pr_data.get('decay_rate', 0.1),
            apply_to=pr_data.get('apply_to', ["memories", "conversation_history", "active_files"]),
            strategy=pr_data.get('strategy', 'exponential')
        )
        
        # Build ContextBuilderConfig
        return ContextBuilderConfig(
            max_context_tokens=cb_data.get('max_context_tokens', 12000),
            reserved_for_response=cb_data.get('reserved_for_response', 4000),
            encoder_name=cb_data.get('encoder_name', 'cl100k_base'),
            priority_order=cb_data.get('priority_order', {
                "system_prompt": 1,
                "current_task": 2,
                "active_files": 3,
                "recent_tools": 4,
                "rolling_summary": 5,
                "memories": 6,
                "older_history": 7
            }),
            truncation_strategy=cb_data.get('truncation_strategy', 'priority'),
            min_segment_tokens=cb_data.get('min_segment_tokens', 100),
            primacy_recency=primacy_recency
        )

    def _calculate_position_weight(self, index: int, total: int, segment_type: str) -> float:
        """Calculate primacy/recency weight for a segment based on its position.
        
        Primacy effect: Early items (low index) get higher weight
        Recency effect: Late items (high index) get higher weight
        Middle items get baseline weight
        """
        pr_config = self.config.primacy_recency
        
        # Check if this segment type should have primacy/recency applied
        if not pr_config.enabled or segment_type not in pr_config.apply_to:
            return 1.0
        
        if total <= 1:
            return 1.0
        
        # Normalized position (0.0 to 1.0)
        position = index / (total - 1)
        
        if pr_config.strategy == "exponential":
            # Exponential decay from both ends
            primacy_factor = pr_config.primacy_weight * (1 - position) ** pr_config.decay_rate
            recency_factor = pr_config.recency_weight * position ** pr_config.decay_rate
            # Middle weight as baseline
            middle_factor = pr_config.middle_weight * (1 - abs(position - 0.5) * 2)
            return max(primacy_factor, recency_factor, middle_factor)
        
        elif pr_config.strategy == "linear":
            # Linear interpolation
            if position <= 0.5:
                # First half: primacy to middle
                return pr_config.primacy_weight * (1 - position * 2) + pr_config.middle_weight * (position * 2)
            else:
                # Second half: middle to recency
                return pr_config.middle_weight * (2 - position * 2) + pr_config.recency_weight * (position * 2 - 1)
        
        elif pr_config.strategy == "step":
            # Step function: primacy for first 25%, recency for last 25%, middle for 50%
            if position < 0.25:
                return pr_config.primacy_weight
            elif position > 0.75:
                return pr_config.recency_weight
            else:
                return pr_config.middle_weight
        
        return 1.0

    def _apply_primacy_recency_weights(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """Apply primacy/recency weights to segments by adjusting their effective priority."""
        # Group segments by type for position calculation
        type_groups = {}
        for i, seg in enumerate(segments):
            seg_type = seg.metadata.get('segment_type', seg.name.split('_')[0] if '_' in seg.name else 'other')
            if seg_type not in type_groups:
                type_groups[seg_type] = []
            type_groups[seg_type].append((i, seg))
        
        # Apply weights
        weighted_segments = []
        for seg_type, group in type_groups.items():
            total = len(group)
            for idx, (original_idx, seg) in enumerate(group):
                weight = self._calculate_position_weight(idx, total, seg_type)
                # Adjust priority by weight (lower priority = higher importance)
                # We multiply the priority by inverse of weight so higher weight = lower priority number = higher importance
                adjusted_priority = max(1, int(seg.priority / weight))
                weighted_seg = ContextSegment(
                    priority=adjusted_priority,
                    name=seg.name,
                    content=seg.content,
                    tokens=seg.tokens,
                    required=seg.required,
                    metadata={**seg.metadata, 'primacy_recency_weight': weight, 'position_index': idx}
                )
                weighted_segments.append(weighted_seg)
        
        return weighted_segments
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))
    
    def build_context(
        self,
        query: str,
        sources: List[Dict],
        system_prompt: str = "",
        conversation_history: List[Dict] = None,
        active_files: List[Dict] = None,
        recent_tools: List[Dict] = None,
        rolling_summary: str = None,
        plan = None
    ) -> Dict:
        """
        Build optimized context for LLM.
        
        Returns dict with:
        - context: Final context string
        - segments: List of included segments
        - tokens_used: Total tokens
        - truncated: Whether truncation occurred
        - budget: Token budget info
        """
        segments = []
        
        # 1. System Prompt (highest priority, required)
        if system_prompt:
            tokens = self._count_tokens(system_prompt)
            segments.append(ContextSegment(
                priority=ContextPriority.SYSTEM_PROMPT,
                name="system_prompt",
                content=system_prompt,
                tokens=tokens,
                required=True
            ))
        
        # 2. Current Task (query)
        task_content = f"USER QUERY: {query}"
        tokens = self._count_tokens(task_content)
        segments.append(ContextSegment(
            priority=ContextPriority.CURRENT_TASK,
            name="current_task",
            content=task_content,
            tokens=tokens,
            required=True
        ))
        
        # 3. Active Files
        if active_files:
            for i, f in enumerate(active_files[:5]):  # Max 5 active files
                content = f"FILE: {f.get('path', f'file_{i}')}\n{f.get('content', '')}"
                tokens = self._count_tokens(content)
                segments.append(ContextSegment(
                    priority=ContextPriority.ACTIVE_FILES,
                    name=f"active_file_{i}",
                    content=content,
                    tokens=tokens,
                    metadata={"path": f.get("path"), "segment_type": "active_files"}
                ))
        
        # 4. Recent Tools
        if recent_tools:
            for i, t in enumerate(recent_tools[-3:]):  # Last 3 tools
                content = f"TOOL: {t.get('name', f'tool_{i}')}\n{t.get('output', '')}"
                tokens = self._count_tokens(content)
                segments.append(ContextSegment(
                    priority=ContextPriority.RECENT_TOOLS,
                    name=f"recent_tool_{i}",
                    content=content,
                    tokens=tokens,
                    metadata={"tool_name": t.get("name")}
                ))
        
        # 5. Rolling Summary (if exists)
        if rolling_summary:
            tokens = self._count_tokens(rolling_summary)
            segments.append(ContextSegment(
                priority=ContextPriority.ROLLING_SUMMARY,
                name="rolling_summary",
                content=f"[COMPRESSED HISTORY]: {rolling_summary}",
                tokens=tokens,
                metadata={"compressed": True}
            ))
        
        # 6. Memories / Retrieved Sources
        for i, source in enumerate(sources):
            content = self._format_source_for_context(source, i)
            tokens = self._count_tokens(content)
            segments.append(ContextSegment(
                priority=ContextPriority.MEMORIES,
                name=f"memory_{i}",
                content=content,
                tokens=tokens,
                metadata={
                    "source_id": source.get("source_id", source.get("id", "")),
                    "source_type": source.get("source", "unknown"),
                    "score": source.get("score", 0),
                    "segment_type": "memories"
                }
            ))
        
        # 6b. Memories from sources (if separate)
        if sources:
            for source in sources:
                memories = source.get("memories", [])
                for i, mem in enumerate(memories[:3]):  # Max 3 per source
                    content = f"MEMORY: {mem.get('content', '')}"
                    tokens = self._count_tokens(content)
                    segments.append(ContextSegment(
                        priority=ContextPriority.MEMORIES,
                        name=f"source_memory_{i}",
                        content=content,
                        tokens=tokens,
                        metadata={"segment_type": "memories"}
                    ))
        
        # 7. Conversation History (non-compressed)
        if conversation_history:
            for i, turn in enumerate(conversation_history[-5:]):  # Last 5 turns
                role = turn.get("role", "unknown")
                content = turn.get("content", "")
                if content:
                    segment_content = f"{role.upper()}: {content}"
                    tokens = self._count_tokens(segment_content)
                    segments.append(ContextSegment(
                        priority=ContextPriority.OLDER_HISTORY,
                        name=f"history_{i}",
                        content=segment_content,
                        tokens=tokens,
                        metadata={"role": role, "segment_type": "conversation_history"}
                    ))
        
        # 8. Apply primacy/recency weights (NEW)
        segments = self._apply_primacy_recency_weights(segments)
        
        # 9. Enforce budget
        final_segments = self._enforce_budget(segments)
        
        # 10. Reconstruct context
        context = self._reconstruct_context(final_segments, query)
        
        # Calculate totals
        total_tokens = sum(s.tokens for s in final_segments)
        truncated = len(final_segments) < len(segments)
        
        return {
            "context": context,
            "segments": [
                {
                    "name": s.name,
                    "priority": s.priority,
                    "tokens": s.tokens,
                    "required": s.required
                }
                for s in final_segments
            ],
            "tokens_used": total_tokens,
            "budget_limit": self.hard_limit,
            "truncated": truncated,
            "dropped_segments": len(segments) - len(final_segments)
        }
    
    def _format_source_for_context(self, source: Dict, index: int) -> str:
        """Format a retrieved source for context inclusion."""
        title = source.get("title", f"Fonte {index}")
        content = source.get("content", "")
        source_type = source.get("source", "unknown")
        source_id = source.get("source_id", source.get("id", ""))
        score = source.get("score", 0)
        
        # Build reference
        if source_type == "vault":
            ref = f"[[{source_id}]]"
        elif source_type == "mempalace":
            wing = source.get("wing", "")
            room = source.get("room", "")
            ref = f"[[{wing}/{room}/{source_id}]]"
        elif source_type == "skill":
            ref = f"[[skill:{source.get('skill_name', source_id)}]]"
        else:
            ref = f"[{source_id}]"
        
        # Truncate content if too long
        max_content = 2000
        if len(content) > max_content:
            content = content[:max_content] + "... [TRUNCATED]"
        
        return f"""---
Fonte {index+1}: {title} ({source_type})
Referência: {ref}
Score: {score:.3f}
Conteúdo:
{content}"""
    
    def _enforce_budget(self, segments: List[ContextSegment]) -> List[ContextSegment]:
        """Truncate segments by priority until under budget."""
        # Sort by priority (lower = higher priority)
        sorted_segments = sorted(segments, key=lambda s: s.priority)
        
        # Calculate required tokens (segments that can't be truncated)
        required_tokens = sum(s.tokens for s in sorted_segments if s.required)
        available = self.hard_limit - required_tokens
        
        if available < 0:
            # Required segments exceed budget - this shouldn't happen with good config
            # But handle gracefully by truncating even required segments
            available = 0
        
        result = []
        used = 0
        
        for seg in sorted_segments:
            if seg.required:
                result.append(seg)
                used += seg.tokens
                continue
            
            if used + seg.tokens <= self.hard_limit:
                # Fits completely
                result.append(seg)
                used += seg.tokens
            else:
                # Try to truncate
                remaining = self.hard_limit - used
                if remaining > self.config.min_segment_tokens:
                    truncated = self._truncate_segment(seg, remaining)
                    result.append(truncated)
                    used += truncated.tokens
                # If no space, skip this and all lower priority segments
                break
        
        return result
    
    def _truncate_segment(self, segment: ContextSegment, max_tokens: int) -> ContextSegment:
        """Truncate a segment to fit within token budget."""
        truncated_content = self._truncate_text(segment.content, max_tokens)
        return ContextSegment(
            priority=segment.priority,
            name=segment.name,
            content=truncated_content + "\n[...TRUNCATED...]",
            tokens=max_tokens,
            required=segment.required,
            metadata={**segment.metadata, "truncated": True}
        )
    
    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to max tokens using encoder."""
        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoder.decode(tokens[:max_tokens])
    
    def _reconstruct_context(self, segments: List[ContextSegment], query: str) -> str:
        """Reconstruct context string from segments."""
        # Sort by priority for output
        sorted_segments = sorted(segments, key=lambda s: s.priority)
        
        parts = []
        for seg in sorted_segments:
            if seg.priority == ContextPriority.SYSTEM_PROMPT:
                parts.append(seg.content)
            elif seg.priority == ContextPriority.CURRENT_TASK:
                parts.append(f"\n{seg.content}\n")
            else:
                parts.append(f"\n{seg.content}\n")
        
        return "\n".join(parts)
    
    def estimate_tokens(self, segments: List[ContextSegment]) -> int:
        """Estimate total tokens for segments."""
        return sum(s.tokens for s in segments)
    
    def get_budget_info(self) -> Dict:
        """Get current budget configuration."""
        return {
            "max_context_tokens": self.config.max_context_tokens,
            "reserved_for_response": self.config.reserved_for_response,
            "hard_limit": self.hard_limit,
            "priority_order": {k.name: v for k, v in self.config.priority_order.items()},
            "encoder": self.config.encoder_name
        }


# ============================================================
# FACTORY
# ============================================================

def create_context_builder(config: ContextBuilderConfig = None) -> ContextBuilder:
    """Create context builder with default or custom config."""
    if config is None:
        config = ContextBuilderConfig()
    return ContextBuilder(config)