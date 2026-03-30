"""
Context Manager

Manages conversation context to avoid exceeding token limits.
Uses a hybrid strategy: recent messages + summary of older messages.
"""

import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .session import Session, SessionMessage

logger = logging.getLogger(__name__)


@dataclass
class ContextConfig:
    """Configuration for context management."""
    max_recent_messages: int = 6        # Recent messages to keep intact
    max_context_tokens: int = 8000      # Maximum context tokens
    summary_threshold: int = 10         # Start summarizing after this many turns
    summary_max_tokens: int = 500       # Maximum tokens for summary


class ContextManager:
    """
    Manages conversation context using hybrid strategy.

    Strategy:
    1. Recent messages (last N): Keep intact
    2. Older messages: Summarize
    3. If still too long: Truncate from oldest
    """

    def __init__(
        self,
        config: Optional[ContextConfig] = None,
        llm=None,  # LLM provider for summarization
    ):
        """
        Initialize the context manager.

        Args:
            config: Context configuration
            llm: LLM provider for generating summaries
        """
        self.config = config or ContextConfig()
        self._llm = llm
        self._summaries_cache = {}  # session_id -> summary

        logger.info(
            f"Initialized ContextManager: max_recent={self.config.max_recent_messages}, "
            f"max_tokens={self.config.max_context_tokens}"
        )

    def build_context(
        self,
        session: Session,
        current_question: str,
    ) -> Tuple[str, int]:
        """
        Build context string from session history.

        Args:
            session: Session object
            current_question: Current user question

        Returns:
            (context_string, estimated_token_count)
        """
        messages = session.messages

        # No history, return empty context
        if not messages:
            return "", 0

        # Strategy 1: Few messages, keep all
        if len(messages) <= self.config.max_recent_messages:
            context = self._format_messages(messages)
            tokens = self._estimate_tokens(context)
            return context, tokens

        # Strategy 2: Hybrid - recent + summary
        context_parts = []
        total_tokens = 0

        # 2.1 Add summary of older messages
        older_msgs = messages[:-self.config.max_recent_messages]
        if older_msgs:
            summary = self._get_or_create_summary(session.session_id, older_msgs)
            summary_text = f"[对话历史摘要]\n{summary}\n"
            summary_tokens = self._estimate_tokens(summary_text)

            if total_tokens + summary_tokens < self.config.max_context_tokens:
                context_parts.append(summary_text)
                total_tokens += summary_tokens

        # 2.2 Add recent messages intact
        recent_msgs = messages[-self.config.max_recent_messages:]
        recent_text = self._format_messages(recent_msgs, header="[最近对话]")
        recent_tokens = self._estimate_tokens(recent_text)

        if total_tokens + recent_tokens < self.config.max_context_tokens:
            context_parts.append(recent_text)
            total_tokens += recent_tokens
        else:
            # Still too long, need aggressive truncation
            return self._truncate_to_fit(recent_msgs, current_question)

        context = "\n".join(context_parts)

        logger.debug(
            f"Built context: {len(messages)} total messages, "
            f"{total_tokens} estimated tokens"
        )

        return context, total_tokens

    def _get_or_create_summary(
        self,
        session_id: str,
        messages: List[SessionMessage],
    ) -> str:
        """Get cached summary or create new one."""
        # Check cache
        if session_id in self._summaries_cache:
            return self._summaries_cache[session_id]

        # Generate new summary
        summary = self._generate_summary(messages)

        # Cache it
        self._summaries_cache[session_id] = summary

        return summary

    def _generate_summary(self, messages: List[SessionMessage]) -> str:
        """
        Generate summary of conversation using LLM.

        If LLM is not available, use simple rule-based summary.
        """
        if self._llm:
            return self._llm_summary(messages)
        else:
            return self._rule_based_summary(messages)

    def _llm_summary(self, messages: List[SessionMessage]) -> str:
        """Generate summary using LLM."""
        # Take a sample of messages if too many
        sample_msgs = messages[-20:] if len(messages) > 20 else messages
        conversation = self._format_messages(sample_msgs)

        prompt = f"""请将以下对话总结为 2-3 句话，重点保留：
1. 讨论的主题/文件/函数
2. 重要的结论或发现
3. 未解决的问题（如有）

对话内容：
{conversation}

摘要："""

        try:
            summary = self._llm.generate(
                prompt,
                temperature=0.3,
                max_tokens=300,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"LLM summary failed: {e}, falling back to rule-based")
            return self._rule_based_summary(messages)

    def _rule_based_summary(self, messages: List[SessionMessage]) -> str:
        """Generate simple rule-based summary."""
        # Count topics/keywords
        user_questions = [
            m.content for m in messages if m.role == "user"
        ]

        # Extract common topics (simple heuristic)
        topics = set()
        for msg in user_questions:
            # Look for file mentions
            import re
            files = re.findall(r'[\w]+\.(py|js|java|go|rs|cpp|c|h)', msg)
            topics.update(files[:3])  # Max 3 files

        # Build summary
        summary_parts = [f"包含 {len(messages)} 条历史消息"]

        if topics:
            summary_parts.append(f"涉及文件: {', '.join(list(topics)[:5])}")

        return "，".join(summary_parts)

    def _format_messages(
        self,
        messages: List[SessionMessage],
        header: Optional[str] = None,
    ) -> str:
        """Format messages into conversation string."""
        if not messages:
            return ""

        lines = []
        if header:
            lines.append(header)

        for msg in messages:
            role_name = "用户" if msg.role == "user" else "助手"
            # Truncate very long messages
            content = msg.content
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role_name}: {content}")

        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count.

        Rough estimation:
        - Chinese: ~1.5 chars = 1 token
        - English: ~4 chars = 1 token
        """
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars

        return int((chinese_chars / 1.5) + (other_chars / 4))

    def _truncate_to_fit(
        self,
        messages: List[SessionMessage],
        current_question: str,
    ) -> Tuple[str, int]:
        """
        Aggressively truncate to fit token limit.

        Takes most recent messages first.
        """
        max_tokens = self.config.max_context_tokens - 200  # Buffer for current question

        lines = ["[最近对话]"]
        tokens_used = self._estimate_tokens("\n".join(lines))

        # Add messages from newest to oldest
        for msg in reversed(messages):
            role_name = "用户" if msg.role == "user" else "助手"
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            msg_text = f"{role_name}: {content}\n"

            msg_tokens = self._estimate_tokens(msg_text)

            if tokens_used + msg_tokens > max_tokens:
                break

            lines.insert(1, msg_text.strip())  # Insert after header
            tokens_used += msg_tokens

        context = "\n".join(lines)
        return context, tokens_used

    def invalidate_summary(self, session_id: str) -> None:
        """Invalidate cached summary for a session."""
        if session_id in self._summaries_cache:
            del self._summaries_cache[session_id]
            logger.debug(f"Invalidated summary for session {session_id}")

    def clear_cache(self) -> None:
        """Clear all cached summaries."""
        self._summaries_cache.clear()
        logger.debug("Cleared all summary cache")

    def get_stats(self) -> dict:
        """Get context manager statistics."""
        return {
            "cached_summaries": len(self._summaries_cache),
            "config": {
                "max_recent_messages": self.config.max_recent_messages,
                "max_context_tokens": self.config.max_context_tokens,
                "summary_threshold": self.config.summary_threshold,
            }
        }


def create_context_manager(
    max_recent_messages: int = 6,
    max_context_tokens: int = 8000,
    llm=None,
) -> ContextManager:
    """
    Factory function to create a ContextManager.

    Args:
        max_recent_messages: Number of recent messages to keep intact
        max_context_tokens: Maximum context tokens
        llm: Optional LLM provider for summarization

    Returns:
        Configured ContextManager instance
    """
    config = ContextConfig(
        max_recent_messages=max_recent_messages,
        max_context_tokens=max_context_tokens,
    )

    return ContextManager(config=config, llm=llm)
