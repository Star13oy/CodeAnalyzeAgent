"""
Code Agent Core

Implements the Agentic Loop for code exploration and question answering.
"""

import json
import logging
import re
import uuid
from typing import Dict, Any, List, Optional, Generator, Callable
from dataclasses import dataclass, field

from ..llm.base import LLMProvider, Message, LLMResponse
from ..tools.base import BaseTool
from .parallel import ParallelExecutor, ToolCall, ToolResult
from .context_manager import ContextManager
from .session import SessionManager

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from agent execution"""
    answer: str
    sources: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    session_id: str = ""
    tokens_used: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "tool_calls": self.tool_calls,
            "confidence": self.confidence,
            "session_id": self.session_id,
            "tokens_used": self.tokens_used,
        }


@dataclass
class ToolCallRecord:
    """Record of a tool call"""
    name: str
    arguments: Dict[str, Any]
    result: str
    iteration: int
    success: bool


class CodeAgent:
    """
    Agentic Code Assistant.

    Uses an LLM with tool capabilities to autonomously explore
    code repositories and answer questions.
    """

    # System prompt for code exploration
    SYSTEM_PROMPT = """You are an expert code analyst. Help users understand their codebase efficiently.

IMPORTANT - Tool Usage Limits:
- Use at most 3-5 tool calls before providing your answer
- After gathering sufficient information, respond WITHOUT using tools
- Prioritize the most relevant files first

When to STOP exploring and ANSWER:
- You have found the main implementation files
- You understand the core logic/pattern
- Additional files would only provide marginal details

Answer format:
1. Direct answer to the question
2. Key file paths and line numbers
3. Brief code snippets if helpful

Be concise. A good answer with 3-5 file references is better than exhaustive exploration."""

    def __init__(
        self,
        repo_path: str,
        llm: LLMProvider,
        tools: List[BaseTool],
        max_iterations: int = 10,
        temperature: float = 0.7,
        enable_parallel: bool = True,
        max_parallel_workers: int = 5,
        context_manager: Optional[ContextManager] = None,
    ):
        """
        Initialize the agent.

        Args:
            repo_path: Path to the code repository
            llm: LLM provider instance
            tools: List of available tools
            max_iterations: Maximum tool use iterations
            temperature: LLM temperature (0-1)
            enable_parallel: Enable parallel tool execution
            max_parallel_workers: Maximum parallel tool executions
            context_manager: Optional context manager for conversation history
        """
        self.repo_path = repo_path
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.enable_parallel = enable_parallel
        self.context_manager = context_manager

        # Initialize parallel executor
        self.parallel_executor = None
        if enable_parallel:
            self.parallel_executor = ParallelExecutor(max_workers=max_parallel_workers)

        logger.info(
            f"Initialized CodeAgent for {repo_path} "
            f"with {len(tools)} tools, max_iterations={max_iterations}, "
            f"parallel={enable_parallel}"
        )

    def ask(
        self,
        question: str,
        session_id: Optional[str] = None,
        session_manager: Optional[SessionManager] = None,
    ) -> AgentResult:
        """
        Answer a question about the codebase.

        Args:
            question: User's question
            session_id: Optional session ID for multi-turn conversations
            session_manager: Optional session manager for conversation history

        Returns:
            AgentResult: Answer with sources and metadata
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        logger.info(f"Processing question for session {session_id}: {question[:100]}...")

        # Build conversation context if session manager is provided
        conversation_context = ""
        if session_manager and self.context_manager:
            session = session_manager.get(session_id)
            if session and session.messages:
                conversation_context, token_count = self.context_manager.build_context(
                    session, question
                )
                logger.info(f"Built conversation context: {token_count} tokens")

        # Build messages - combine system prompt + context + question
        if conversation_context:
            enhanced_question = (
                f"{self.SYSTEM_PROMPT}\n\n"
                f"{conversation_context}\n\n"
                f"当前问题: {question}"
            )
        else:
            enhanced_question = f"{self.SYSTEM_PROMPT}\n\n{self._enhance_question(question)}"

        messages = [
            Message(role="user", content=enhanced_question),
        ]

        tool_call_records: List[ToolCallRecord] = []

        # Agentic loop
        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{self.max_iterations}")

            # Early stop: when near max iterations, force LLM to answer without tools
            remaining_iterations = self.max_iterations - iteration
            if remaining_iterations <= 2 and tool_call_records:
                logger.info(f"Near max iterations, requesting final answer (remaining: {remaining_iterations})")
                # Add a user message forcing the LLM to stop using tools
                messages.append(Message(
                    role="user",
                    content="STOP using tools. Based on the information you've gathered, provide your final answer now."
                ))

            # Call LLM
            response = self.llm.chat(
                messages=messages,
                tools=[t.to_dict() for t in self.tools.values()],
                temperature=self.temperature,
            )

            # Check if done
            if response.finish_reason == "stop":
                logger.info(f"Agent finished after {iteration} iterations")
                result = self._build_result(
                    answer=response.content,
                    tool_calls=tool_call_records,
                    session_id=session_id,
                    usage=response.usage,
                )
                self._save_to_session(session_manager, session_id, question, result.answer)
                return result

            # Process tool calls
            if not response.tool_calls:
                logger.warning("No tool calls but not finished, returning partial answer")
                result = self._build_result(
                    answer=response.content or "Unable to complete the analysis.",
                    tool_calls=tool_call_records,
                    session_id=session_id,
                    usage=response.usage,
                    confidence=0.3,
                )
                self._save_to_session(session_manager, session_id, question, result.answer)
                return result

            # Execute tools
            assistant_message = Message(
                role="assistant",
                content=response.content or "",
            )
            messages.append(assistant_message)

            # Execute tools (parallel if enabled and multiple tools)
            records = self._execute_tool_calls(response.tool_calls, iteration)
            tool_call_records.extend(records)

            # Add tool results to messages
            for record in records:
                messages.append(Message(
                    role="user",
                    content=record.result,
                ))

        # Max iterations reached
        logger.warning(f"Reached max iterations ({self.max_iterations})")
        result = self._build_result(
            answer="I reached the maximum number of iterations. The analysis was not fully completed.",
            tool_calls=tool_call_records,
            session_id=session_id,
            confidence=0.2,
        )
        self._save_to_session(session_manager, session_id, question, result.answer)
        return result

    def _save_to_session(
        self,
        session_manager: Optional[SessionManager],
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        """
        Save Q&A to session history.

        Args:
            session_manager: Session manager instance
            session_id: Session ID
            question: User question
            answer: Agent answer
        """
        if not session_manager:
            return

        session = session_manager.get(session_id)
        if not session:
            logger.debug(f"Session {session_id} not found, skipping message save")
            return

        session.add_message("user", question)
        session.add_message("assistant", answer)
        logger.debug(f"Saved messages to session {session_id}")

    def _enhance_question(self, question: str) -> str:
        """
        Enhance the user's question with context.

        Args:
            question: Original question

        Returns:
            str: Enhanced question
        """
        return f"""Repository path: {self.repo_path}

Question: {question}

Please explore the codebase to answer this question. Use the available tools to:
- Search for relevant code
- Read file contents
- Look up symbols and their definitions

Provide a detailed answer with specific references to files and line numbers."""

    def ask_stream(
        self,
        question: str,
        session_id: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Answer a question with streaming progress events.

        Yields progress events with format:
        {"type": "progress", "iteration": 1, "max_iterations": 10, "tool": "file_read", "status": "executing"}
        {"type": "tool_result", "tool": "file_read", "success": True, "result_preview": "..."}
        {"type": "thinking", "content": "LLM partial response..."}
        {"type": "complete", "result": {...}}
        {"type": "error", "message": "..."}

        Args:
            question: User's question
            session_id: Optional session ID

        Yields:
            Dict with progress/event information
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        yield {"type": "start", "session_id": session_id, "max_iterations": self.max_iterations}

        enhanced_question = f"{self.SYSTEM_PROMPT}\n\n{self._enhance_question(question)}"
        messages = [Message(role="user", content=enhanced_question)]
        tool_call_records: List[ToolCallRecord] = []

        try:
            for iteration in range(self.max_iterations):
                # Progress event
                yield {
                    "type": "progress",
                    "iteration": iteration + 1,
                    "max_iterations": self.max_iterations,
                    "status": "thinking"
                }

                # Early stop
                remaining = self.max_iterations - iteration
                if remaining <= 2 and tool_call_records:
                    yield {"type": "force_stop", "reason": "Approaching iteration limit"}
                    messages.append(Message(
                        role="user",
                        content="STOP using tools. Based on the information you've gathered, provide your final answer now."
                    ))

                # Call LLM
                response = self.llm.chat(
                    messages=messages,
                    tools=[t.to_dict() for t in self.tools.values()],
                    temperature=self.temperature,
                )

                # Check if done
                if response.finish_reason == "stop":
                    result = self._build_result(
                        answer=response.content,
                        tool_calls=tool_call_records,
                        session_id=session_id,
                        usage=response.usage,
                    )
                    yield {"type": "complete", "result": result.to_dict()}
                    return

                # Process tool calls
                if not response.tool_calls:
                    result = self._build_result(
                        answer=response.content or "Unable to complete.",
                        tool_calls=tool_call_records,
                        session_id=session_id,
                        usage=response.usage,
                        confidence=0.3,
                    )
                    yield {"type": "complete", "result": result.to_dict()}
                    return

                # Execute tools
                messages.append(Message(role="assistant", content=response.content or ""))

                # Execute tools (parallel if enabled)
                records = self._execute_tool_calls(response.tool_calls, iteration)
                tool_call_records.extend(records)

                # Yield tool results
                for record in records:
                    yield {
                        "type": "tool_call",
                        "tool": record.name,
                        "arguments": record.arguments,
                        "iteration": iteration + 1
                    }
                    yield {
                        "type": "tool_result",
                        "tool": record.name,
                        "success": record.success,
                        "result_preview": record.result[:200] + "..." if len(record.result) > 200 else record.result
                    }
                    messages.append(Message(role="user", content=record.result))

            # Max iterations
            yield {
                "type": "warning",
                "message": f"Reached max iterations ({self.max_iterations})"
            }
            result = self._build_result(
                answer="I reached the maximum number of iterations. Based on what I've gathered so far...",
                tool_calls=tool_call_records,
                session_id=session_id,
                confidence=0.2,
            )
            yield {"type": "complete", "result": result.to_dict()}

        except Exception as e:
            logger.exception("Error in ask_stream")
            yield {"type": "error", "message": str(e)}

    def _execute_tool_call(self, tool_call, iteration: int) -> ToolCallRecord:
        """
        Execute a tool call.

        Args:
            tool_call: Tool call from LLM
            iteration: Current iteration number

        Returns:
            ToolCallRecord: Record of the tool execution
        """
        tool_name = tool_call.name
        arguments = tool_call.arguments

        logger.debug(f"Executing tool: {tool_name} with args: {arguments}")

        tool = self.tools.get(tool_name)
        if not tool:
            return ToolCallRecord(
                name=tool_name,
                arguments=arguments,
                result=f"Error: Tool '{tool_name}' not found",
                iteration=iteration,
                success=False,
            )

        try:
            result = tool.execute(arguments)
            logger.debug(f"Tool {tool_name} succeeded, result length: {len(result)}")
            return ToolCallRecord(
                name=tool_name,
                arguments=arguments,
                result=result,
                iteration=iteration,
                success=True,
            )
        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(f"Tool {tool_name} failed: {e}")
            return ToolCallRecord(
                name=tool_name,
                arguments=arguments,
                result=error_msg,
                iteration=iteration,
                success=False,
            )

    def _execute_tool_calls(self, tool_calls, iteration: int) -> List[ToolCallRecord]:
        """
        Execute multiple tool calls, with parallel execution if enabled.

        Args:
            tool_calls: List of tool calls from LLM
            iteration: Current iteration number

        Returns:
            List[ToolCallRecord]: Records of the tool executions
        """
        if not tool_calls:
            return []

        # Single tool call - execute directly
        if len(tool_calls) == 1:
            return [self._execute_tool_call(tool_calls[0], iteration)]

        # Multiple tools - check if parallel execution is possible
        if self.enable_parallel and self.parallel_executor:
            # Check if all tools are different (can parallelize)
            tool_names = [tc.name for tc in tool_calls]
            if len(tool_names) == len(set(tool_names)):
                # All tools are different - execute in parallel
                return self._execute_parallel(tool_calls, iteration)
            else:
                # Duplicate tools - execute sequentially
                logger.debug("Duplicate tool names detected, executing sequentially")
                return [self._execute_tool_call(tc, iteration) for tc in tool_calls]
        else:
            # Parallel disabled - execute sequentially
            return [self._execute_tool_call(tc, iteration) for tc in tool_calls]

    def _execute_parallel(self, tool_calls, iteration: int) -> List[ToolCallRecord]:
        """
        Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of tool calls from LLM
            iteration: Current iteration number

        Returns:
            List[ToolCallRecord]: Records of the tool executions
        """
        # Convert LLM tool calls to parallel executor format
        parallel_calls = [
            ToolCall(
                name=tc.name,
                arguments=tc.arguments,
                call_id=f"{iteration}_{i}",
            )
            for i, tc in enumerate(tool_calls)
        ]

        logger.info(f"Executing {len(tool_calls)} tools in parallel")

        # Execute in parallel
        results = self.parallel_executor.execute_parallel(parallel_calls, self.tools)

        # Convert results back to ToolCallRecord format
        records = []
        for i, result in enumerate(results):
            records.append(ToolCallRecord(
                name=result.name,
                arguments=tool_calls[i].arguments,
                result=result.result if result.success else f"Error: {result.error}",
                iteration=iteration,
                success=result.success,
            ))

            logger.debug(
                f"Parallel tool {result.name} completed in {result.duration_ms:.1f}ms, "
                f"success={result.success}"
            )

        return records

    def _build_result(
        self,
        answer: str,
        tool_calls: List[ToolCallRecord],
        session_id: str,
        usage: Any = None,
        confidence: float = 0.5,
    ) -> AgentResult:
        """
        Build the final result.

        Args:
            answer: The answer text
            tool_calls: List of tool call records
            session_id: Session ID
            usage: Token usage info
            confidence: Confidence score

        Returns:
            AgentResult: Final result
        """
        # Extract sources from tool results
        sources = self._extract_sources(tool_calls)

        # Build tool calls for response
        tool_calls_summary = [
            {
                "name": tc.name,
                "arguments": tc.arguments,
                "iteration": tc.iteration,
                "success": tc.success,
            }
            for tc in tool_calls
        ]

        # Calculate confidence
        calculated_confidence = self._calculate_confidence(tool_calls)
        final_confidence = min(confidence, calculated_confidence)

        # Token usage
        tokens_used = {}
        if usage:
            tokens_used = {
                "input": usage.input_tokens,
                "output": usage.output_tokens,
                "total": usage.total_tokens,
            }

        return AgentResult(
            answer=answer,
            sources=sources,
            tool_calls=tool_calls_summary,
            confidence=final_confidence,
            session_id=session_id,
            tokens_used=tokens_used,
        )

    def _extract_sources(self, tool_calls: List[ToolCallRecord]) -> List[str]:
        """
        Extract source file references from tool calls.

        Only extracts from tool call arguments (most reliable).
        Does NOT extract from LLM text responses to avoid hallucinations.

        Args:
            tool_calls: List of tool call records

        Returns:
            List[str]: List of valid source references
        """
        sources = set()

        for tc in tool_calls:
            if not tc.success:
                continue

            # Only extract from tool call arguments (most reliable)
            args = tc.arguments
            if isinstance(args, dict):
                # file_read tool
                if 'path' in args:
                    self._add_valid_source(sources, args['path'])
                # symbol_lookup tool
                if 'file' in args:
                    self._add_valid_source(sources, args['file'])
                # file_find tool - extract pattern if it looks like a real file
                if 'pattern' in args:
                    pattern = args['pattern']
                    # Only add if it looks like a real file path, not a wildcard or example
                    if ('*' not in pattern and '?' not in pattern and
                        '.' in pattern and '/' in pattern and
                        not pattern.startswith(('file.', 'test.', 'example.'))):
                        self._add_valid_source(sources, pattern)

        return sorted(list(sources))

    def _add_valid_source(self, sources: set, path: str) -> None:
        """
        Add a source path if it's valid.

        Filters out:
        - URLs (http, https, ftp)
        - Empty strings
        - Obvious non-file patterns
        - Paths with invalid characters

        Args:
            sources: Set to add to
            path: Path to validate and add
        """
        if not path or not isinstance(path, str):
            return

        path = path.strip()

        # Skip URLs
        if path.startswith(('http://', 'https://', 'ftp://')):
            return

        # Skip JSON-like strings
        if any(c in path for c in ['{', '}', '"', "'", '\\n', '\\t']):
            return

        # Skip single characters or obviously wrong patterns
        if len(path) <= 2 or path in ['c', 'h', 'js', 'py', 'java']:
            return

        # Skip obvious placeholder/example paths
        if 'path/to/' in path or '/example' in path or '/file.' in path.replace('/src/file.', ''):
            return

        # Skip paths that start with generic patterns
        if path.startswith(('file.', 'src/file.', 'path/to/')):
            return

        # Only add if it looks like a real file path
        # Must have at least one directory separator and a meaningful name
        if '/' in path or '\\' in path:
            # Check if it has a reasonable structure (at least 2 segments)
            parts = path.replace('\\', '/').split('/')
            if len(parts) >= 2 and any(len(p) > 2 for p in parts):
                sources.add(path)

    def _calculate_confidence(self, tool_calls: List[ToolCallRecord]) -> float:
        """
        Calculate confidence based on tool execution results.

        Args:
            tool_calls: List of tool call records

        Returns:
            float: Confidence score (0-1)
        """
        if not tool_calls:
            return 0.5

        # Success rate
        successful = sum(1 for tc in tool_calls if tc.success)
        total = len(tool_calls)
        success_rate = successful / total if total > 0 else 0

        # Base confidence from success rate
        confidence = 0.3 + (success_rate * 0.5)

        # Boost for multiple successful tool calls
        if successful >= 3:
            confidence = min(confidence + 0.15, 0.95)

        # Penalty for consecutive failures
        consecutive_failures = 0
        for tc in reversed(tool_calls):
            if not tc.success:
                consecutive_failures += 1
            else:
                break

        if consecutive_failures > 2:
            confidence -= 0.2

        return max(0.0, min(confidence, 1.0))
