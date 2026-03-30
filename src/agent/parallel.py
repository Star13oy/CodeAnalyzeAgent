"""
Parallel Tool Executor

Executes multiple tools concurrently for better performance.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A tool call to be executed."""
    name: str
    arguments: Dict[str, Any]
    call_id: str


@dataclass
class ToolResult:
    """Result of a tool execution."""
    name: str
    call_id: str
    success: bool
    result: str
    duration_ms: float
    error: Optional[str] = None


class ParallelExecutor:
    """
    Executes multiple tool calls in parallel.

    Benefits:
    - Reduces total wait time when multiple tools are independent
    - Better resource utilization (I/O bound operations)
    - Faster response to user queries
    """

    def __init__(self, max_workers: int = 5):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum number of concurrent tool executions
        """
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create thread pool executor."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def execute_parallel(
        self,
        tool_calls: List[ToolCall],
        tools: Dict[str, Any],
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of tool calls to execute
            tools: Dictionary mapping tool names to tool instances

        Returns:
            List of tool results in the same order as inputs
        """
        if not tool_calls:
            return []

        if len(tool_calls) == 1:
            # Single call - execute directly
            return [self._execute_single(tool_calls[0], tools)]

        # Multiple calls - execute in parallel
        logger.info(f"Executing {len(tool_calls)} tools in parallel")
        results = []
        futures = {}

        executor = self._get_executor()

        # Submit all tasks
        for call in tool_calls:
            future = executor.submit(self._execute_single, call, tools)
            futures[future] = call

        # Collect results as they complete
        for future in as_completed(futures):
            call = futures[future]
            try:
                result = future.result(timeout=60)
                results.append(result)
            except Exception as e:
                logger.error(f"Tool execution failed: {call.name}: {e}")
                results.append(ToolResult(
                    name=call.name,
                    call_id=call.call_id,
                    success=False,
                    result="",
                    error=str(e),
                    duration_ms=0,
                ))

        # Sort results by original order
        results.sort(key=lambda r: next(
            i for i, c in enumerate(tool_calls) if c.call_id == r.call_id
        ))

        return results

    def _execute_single(
        self,
        call: ToolCall,
        tools: Dict[str, Any],
    ) -> ToolResult:
        """Execute a single tool call."""
        start = datetime.now()

        try:
            tool = tools.get(call.name)
            if tool is None:
                raise ValueError(f"Tool not found: {call.name}")

            # Execute tool
            if hasattr(tool, 'run'):
                result = tool.run(call.arguments)
            else:
                result = tool.execute(call.arguments)

            duration = (datetime.now() - start).total_seconds() * 1000

            logger.debug(f"Tool {call.name} completed in {duration:.1f}ms")

            return ToolResult(
                name=call.name,
                call_id=call.call_id,
                success=True,
                result=result,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            logger.error(f"Tool {call.name} failed: {e}")

            return ToolResult(
                name=call.name,
                call_id=call.call_id,
                success=False,
                result="",
                error=str(e),
                duration_ms=duration,
            )

    async def execute_parallel_async(
        self,
        tool_calls: List[ToolCall],
        tools: Dict[str, Any],
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls asynchronously.

        Args:
            tool_calls: List of tool calls to execute
            tools: Dictionary mapping tool names to tool instances

        Returns:
            List of tool results
        """
        if not tool_calls:
            return []

        # Create tasks for all tool calls
        tasks = [
            self._execute_single_async(call, tools)
            for call in tool_calls
        ]

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to ToolResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ToolResult(
                    name=tool_calls[i].name,
                    call_id=tool_calls[i].call_id,
                    success=False,
                    result="",
                    error=str(result),
                    duration_ms=0,
                ))
            else:
                final_results.append(result)

        return final_results

    async def _execute_single_async(
        self,
        call: ToolCall,
        tools: Dict[str, Any],
    ) -> ToolResult:
        """Execute a single tool call asynchronously."""
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._execute_single(call, tools)
        )

    def shutdown(self):
        """Shutdown the executor."""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    def __del__(self):
        """Cleanup on deletion."""
        self.shutdown()


class ParallelToolBatch:
    """
    Batches tool calls for parallel execution.

    Analyzes tool calls to determine which can be executed in parallel
    (independent calls) vs sequentially (dependent calls).
    """

    @staticmethod
    def can_parallelize(calls: List[ToolCall]) -> bool:
        """
        Check if a list of tool calls can be parallelized.

        Rules:
        - All calls must be to different tools (no duplicate tool names)
        - No tool call should depend on another's result

        Args:
            calls: List of tool calls to analyze

        Returns:
            True if calls can be executed in parallel
        """
        if len(calls) <= 1:
            return False

        # Check for duplicate tool names
        tool_names = [c.name for c in calls]
        if len(tool_names) != len(set(tool_names)):
            return False

        # All calls are to different tools - can parallelize
        return True

    @staticmethod
    def create_batches(
        calls: List[ToolCall],
        tools: Dict[str, Any],
    ) -> List[List[ToolCall]]:
        """
        Create batches of tool calls for optimal execution.

        Args:
            calls: List of tool calls to batch
            tools: Available tools

        Returns:
            List of batches, each batch can be executed in parallel
        """
        if not calls:
            return []

        # Simple strategy: one batch of all parallelizable calls
        # Future enhancement: analyze dependencies

        if ParallelToolBatch.can_parallelize(calls):
            return [calls]

        # If not parallelizable, execute sequentially
        return [[call] for call in calls]
