"""
Agent Service

Manages agent instances and executes queries.
"""

import logging
from typing import Dict, Optional, Generator, Any

# 配置文件日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

from ..config import settings
from ..agent import CodeAgent, ContextManager
from ..agent.context_manager import ContextConfig
from ..llm.factory import create_from_settings
from ..tools import get_all_tools
from ..cache import CacheManager, MemoryBackend, DiskBackend
from ..cache import CacheBackendType
from ..services.session_service import SessionService

logger = logging.getLogger(__name__)


class AgentService:
    """
    Service for managing and executing agents.
    """

    def __init__(self, session_service: Optional[SessionService] = None):
        """Initialize the agent service

        Args:
            session_service: Optional session service for conversation history
        """
        self.agents: Dict[str, CodeAgent] = {}
        self._llm = None
        self._cache_manager = None
        self._context_manager: Optional[ContextManager] = None
        self._session_service = session_service

        # Initialize cache
        self._init_cache()

        # Initialize context manager (after LLM is available)
        self._init_context_manager()

        logger.info("Initialized AgentService")

    def _init_cache(self):
        """Initialize the cache manager based on settings."""
        if not settings.cache.enable_cache:
            logger.info("Caching is disabled")
            return

        backend_type = settings.cache.cache_backend

        if backend_type == CacheBackendType.MEMORY:
            backend = MemoryBackend(
                default_ttl=settings.cache.tool_cache_ttl,
                max_size=settings.cache.memory_cache_max_size,
            )
            logger.info(f"Using memory cache (max_size={settings.cache.memory_cache_max_size})")

        elif backend_type == CacheBackendType.DISK:
            backend = DiskBackend(
                cache_path=settings.cache.disk_cache_path,
                default_ttl=settings.cache.tool_cache_ttl,
                max_size=settings.cache.disk_cache_max_size,
            )
            logger.info(f"Using disk cache (path={settings.cache.disk_cache_path})")

        else:  # HYBRID or default
            # Use memory cache for now, could implement hybrid
            backend = MemoryBackend(
                default_ttl=settings.cache.tool_cache_ttl,
                max_size=settings.cache.memory_cache_max_size,
            )
            logger.info(f"Using hybrid cache (memory layer)")

        self._cache_manager = CacheManager(
            backend=backend,
            default_ttl=settings.cache.tool_cache_ttl,
        )

        # Set cache manager for all tools
        from ..tools.base import BaseTool
        BaseTool.set_cache_manager(self._cache_manager)

        logger.info("Cache manager initialized and configured")

    def _init_context_manager(self):
        """Initialize the context manager for conversation history."""
        if self._session_service:
            # Get LLM first (needed for summarization)
            llm = self._get_llm()

            # Create context manager with LLM for summarization
            self._context_manager = ContextManager(
                llm=llm,
                config=ContextConfig(
                    max_recent_messages=6,
                    max_context_tokens=8000,
                    summary_threshold=10,
                )
            )
            logger.info("Context manager initialized with LLM summarization")
        else:
            # No session service, no context manager needed
            logger.info("No session service provided, context manager disabled")

    @property
    def cache(self) -> Optional[CacheManager]:
        """Get the cache manager instance."""
        return self._cache_manager

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self._cache_manager is None:
            return {"enabled": False}

        stats = self._cache_manager.get_stats()
        return {
            "enabled": True,
            "hits": stats.hits,
            "misses": stats.misses,
            "hit_rate": stats.hit_rate,
            "total_requests": stats.total_requests,
        }

    def clear_cache(self, namespace: Optional[str] = None) -> bool:
        """Clear cache."""
        if self._cache_manager is None:
            return False

        if namespace:
            return self._cache_manager.clear_namespace(namespace)
        return self._cache_manager.clear_all()

    def _get_llm(self):
        """Get or create LLM instance"""
        if self._llm is None:
            logger.info(f"Creating LLM with provider={settings.llm.provider}")
            logger.info(f"Company API key: {'***configured***' if settings.llm.company_llm_api_key else 'None'}")
            logger.info(f"Company base URL: {settings.llm.company_llm_base_url}")
            logger.info(f"Company model: {settings.llm.company_llm_model}")
            self._llm = create_from_settings(settings)
            logger.info(f"LLM created: {type(self._llm).__name__}")
        return self._llm

    def get_or_create_agent(self, repo_id: str, repo_path: str) -> CodeAgent:
        """
        Get or create an agent for a repository.

        Args:
            repo_id: Repository ID
            repo_path: Path to the repository

        Returns:
            CodeAgent instance
        """
        if repo_id not in self.agents:
            logger.info(f"Creating new agent for repository {repo_id}")
            llm = self._get_llm()
            tools = get_all_tools(repo_path)

            agent = CodeAgent(
                repo_path=repo_path,
                llm=llm,
                tools=tools,
                max_iterations=settings.max_tool_iterations,
                temperature=settings.agent_temperature,
                context_manager=self._context_manager,
            )

            self.agents[repo_id] = agent

        return self.agents[repo_id]

    def ask(
        self,
        repo_id: str,
        repo_path: str,
        question: str,
        session_id: Optional[str] = None,
    ) -> Dict:
        """
        Ask a question about a repository.

        Args:
            repo_id: Repository ID
            repo_path: Path to the repository
            question: User question
            session_id: Optional session ID

        Returns:
            Agent result as dictionary
        """
        agent = self.get_or_create_agent(repo_id, repo_path)

        # Get session manager if available
        session_manager = None
        if self._session_service:
            session_manager = self._session_service.session_manager

        result = agent.ask(question, session_id, session_manager)
        return result.to_dict()

    def ask_stream(
        self,
        repo_id: str,
        repo_path: str,
        question: str,
        session_id: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Ask a question with streaming progress events.

        Args:
            repo_id: Repository ID
            repo_path: Path to the repository
            question: User question
            session_id: Optional session ID

        Yields:
            Progress event dictionaries
        """
        agent = self.get_or_create_agent(repo_id, repo_path)
        yield from agent.ask_stream(question, session_id)

    def troubleshoot(
        self,
        repo_id: str,
        repo_path: str,
        error_log: str,
        stack_trace: Optional[str] = None,
        context: Dict = None,
    ) -> Dict:
        """
        Troubleshoot an error.

        Args:
            repo_id: Repository ID
            repo_path: Path to the repository
            error_log: Error log
            stack_trace: Optional stack trace
            context: Additional context

        Returns:
            Diagnosis result
        """
        agent = self.get_or_create_agent(repo_id, repo_path)

        # Build troubleshooting question
        question = f"""I need help troubleshooting an error:

Error: {error_log}
"""

        if stack_trace:
            question += f"\nStack Trace:\n{stack_trace}"

        if context:
            question += f"\nContext:\n{context}"

        question += """

Please analyze this error and provide:
1. A diagnosis of what went wrong
2. The root cause
3. A suggested fix
4. Related code that needs to be examined
"""

        result = agent.ask(question)

        # Parse the answer into structured response
        return self._parse_troubleshoot_result(result)

    def _parse_troubleshoot_result(self, result) -> Dict:
        """
        Parse agent result into troubleshoot response.

        Args:
            result: Agent result

        Returns:
            Structured troubleshoot response
        """
        # This is a simplified implementation
        # In production, you'd use structured output or parse the response

        answer = result.answer

        return {
            "diagnosis": answer[:500],  # First part as diagnosis
            "root_cause": "Analysis based on error context",
            "fix_suggestion": answer,
            "related_code": result.sources,
            "similar_issues": [],
            "confidence": result.confidence,
            "estimated_fix_time": "TBD",
        }

    def remove_agent(self, repo_id: str) -> bool:
        """
        Remove an agent from cache.

        Args:
            repo_id: Repository ID

        Returns:
            True if removed
        """
        if repo_id in self.agents:
            del self.agents[repo_id]
            logger.info(f"Removed agent for repository {repo_id}")
            return True
        return False

    # Alert Analysis methods
    def _get_alert_analyzer(self, repo_path: str):
        """Get or create alert analyzer for a repository."""
        from ..alert import AlertAnalyzer

        if not hasattr(self, '_alert_analyzers'):
            self._alert_analyzers = {}

        if repo_path not in self._alert_analyzers:
            self._alert_analyzers[repo_path] = AlertAnalyzer(repo_path)

        return self._alert_analyzers[repo_path]

    def analyze_alert(
        self,
        repo_id: str,
        repo_path: str,
        alert_message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        """
        Analyze an alert/error log using intelligent analysis.

        This is faster than troubleshoot() as it uses pattern matching
        and knowledge base instead of LLM exploration.

        Args:
            repo_id: Repository ID
            repo_path: Path to the repository
            alert_message: The alert/error message
            stack_trace: Optional stack trace
            context: Additional context information

        Returns:
            Analysis result with diagnosis and suggestions
        """
        analyzer = self._get_alert_analyzer(repo_path)

        # Quick pattern-based analysis
        quick_diagnosis = analyzer.quick_diagnose(alert_message)

        # Full analysis with stack trace parsing
        analysis = analyzer.analyze(alert_message, stack_trace, context)

        # Add quick diagnosis to the result
        result = analysis.to_dict()
        result['quick_diagnosis'] = quick_diagnosis

        return result

    def analyze_alert_stream(
        self,
        repo_id: str,
        repo_path: str,
        alert_message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Analyze an alert with streaming progress events.

        Args:
            repo_id: Repository ID
            repo_path: Path to the repository
            alert_message: The alert/error message
            stack_trace: Optional stack trace
            context: Additional context information

        Yields:
            Progress event dictionaries
        """
        analyzer = self._get_alert_analyzer(repo_path)

        yield {"type": "start", "alert_id": self._generate_alert_id(alert_message)}

        # Step 1: Parse stack trace
        yield {"type": "progress", "step": "parsing_stack_trace", "status": "processing"}

        frames = []
        if stack_trace:
            frames = analyzer.stack_parser.parse(stack_trace)
            yield {"type": "progress", "step": "parsing_stack_trace", "status": "complete", "frame_count": len(frames)}

        # Step 2: Match error patterns
        yield {"type": "progress", "step": "matching_patterns", "status": "processing"}

        error_suggestions = analyzer.error_matcher.get_suggestions(alert_message)

        yield {
            "type": "pattern_match",
            "matched": error_suggestions.get('matched', False),
            "category": error_suggestions.get('category', 'unknown'),
            "severity": error_suggestions.get('severity', 'medium'),
        }

        # Step 3: Search knowledge base
        yield {"type": "progress", "step": "searching_knowledge_base", "status": "processing"}

        kb_solutions = analyzer.knowledge_base.find_solutions(alert_message)

        yield {
            "type": "kb_results",
            "count": len(kb_solutions),
            "top_solution": kb_solutions[0].to_dict() if kb_solutions else None,
        }

        # Step 4: Generate final analysis
        yield {"type": "progress", "step": "generating_analysis", "status": "processing"}

        analysis = analyzer.analyze(alert_message, stack_trace, context)

        yield {
            "type": "complete",
            "result": analysis.to_dict(),
        }

    def _generate_alert_id(self, message: str) -> str:
        """Generate a short alert ID."""
        import hashlib
        return hashlib.md5(message.encode()).hexdigest()[:8]

    def get_alert_statistics(self, repo_path: str) -> Dict:
        """
        Get statistics about alert analysis.

        Args:
            repo_path: Path to the repository

        Returns:
            Statistics dictionary
        """
        analyzer = self._get_alert_analyzer(repo_path)
        kb_stats = analyzer.knowledge_base.get_statistics()

        return {
            "knowledge_base_size": kb_stats["total_solutions"],
            "available_categories": kb_stats["by_severity"],
            "supported_languages": kb_stats["by_language"],
        }
