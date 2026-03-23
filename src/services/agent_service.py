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
from ..agent import CodeAgent
from ..llm.factory import create_from_settings
from ..tools import get_all_tools

logger = logging.getLogger(__name__)


class AgentService:
    """
    Service for managing and executing agents.
    """

    def __init__(self):
        """Initialize the agent service"""
        self.agents: Dict[str, CodeAgent] = {}
        self._llm = None

        logger.info("Initialized AgentService")

    def _get_llm(self):
        """Get or create LLM instance"""
        if self._llm is None:
            logger.info(f"Creating LLM with provider={settings.llm.provider}")
            logger.info(f"Company API key: {settings.llm.company_llm_api_key[:10] if settings.llm.company_llm_api_key else 'None'}...")
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
        result = agent.ask(question, session_id)
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
