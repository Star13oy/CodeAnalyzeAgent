"""
Alert Analyzer

Main analyzer for code alerts and error logs.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .stack_parser import StackParser, StackFrame, StackLanguage
from .error_patterns import ErrorMatcher, ErrorCategory
from .knowledge_base import KnowledgeBase, Solution

logger = logging.getLogger(__name__)


@dataclass
class AlertAnalysis:
    """Result of analyzing an alert."""
    alert_id: str
    error_message: str
    error_category: Optional[str] = None
    severity: str = "medium"
    root_cause: str = ""
    suggested_fix: str = ""
    related_files: List[str] = field(default_factory=list)
    stack_frames: List[StackFrame] = field(default_factory=list)
    suggested_solutions: List[Solution] = field(default_factory=list)
    code_examples: List[str] = field(default_factory=list)
    similar_alerts: List[str] = field(default_factory=list)

    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "error_message": self.error_message,
            "error_category": self.error_category,
            "severity": self.severity,
            "root_cause": self.root_cause,
            "suggested_fix": self.suggested_fix,
            "related_files": self.related_files,
            "stack_trace": [str(f) for f in self.stack_frames],
            "suggested_solutions": [
                {
                    "problem": s.problem,
                    "solution": s.solution,
                    "tags": s.tags,
                    "code_example": s.code_example,
                }
                for s in self.suggested_solutions
            ],
            "code_examples": self.code_examples,
            "analyzed_at": self.analyzed_at.isoformat(),
            "confidence": self.confidence,
        }


class AlertAnalyzer:
    """
    Analyzes code alerts and error logs to provide actionable insights.

    Combines:
    - Stack trace parsing
    - Error pattern matching
    - Knowledge base lookup
    - Code context analysis
    """

    def __init__(
        self,
        repo_path: str,
        knowledge_base_path: Optional[str] = None,
    ):
        """
        Initialize the alert analyzer.

        Args:
            repo_path: Path to the code repository
            knowledge_base_path: Optional path to persistent knowledge base
        """
        self.repo_path = repo_path
        self.stack_parser = StackParser()
        self.error_matcher = ErrorMatcher()
        self.knowledge_base = KnowledgeBase(knowledge_base_path)

        logger.info(f"Initialized AlertAnalyzer for {repo_path}")

    def analyze(
        self,
        alert_message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AlertAnalysis:
        """
        Analyze an alert and provide actionable insights.

        Args:
            alert_message: The alert/error message
            stack_trace: Optional stack trace
            context: Additional context (environment, variables, etc.)

        Returns:
            AlertAnalysis with findings and suggestions
        """
        alert_id = self._generate_alert_id(alert_message)

        # Parse stack trace if provided
        frames = []
        if stack_trace:
            frames = self.stack_parser.parse(stack_trace)
            logger.debug(f"Parsed {len(frames)} stack frames")

        # Match error patterns
        error_suggestions = self.error_matcher.get_suggestions(alert_message)
        error_category = error_suggestions.get('category', 'unknown')
        severity = error_suggestions.get('severity', 'medium')

        # Find solutions in knowledge base
        kb_solutions = self.knowledge_base.find_solutions(
            problem=alert_message,
            severity=severity,
        )

        # Extract related files from stack trace
        related_files = list(set([f.file_path for f in frames]))

        # Build analysis
        analysis = AlertAnalysis(
            alert_id=alert_id,
            error_message=alert_message,
            error_category=error_category,
            severity=severity,
            stack_frames=frames,
            related_files=related_files,
            suggested_solutions=kb_solutions,
        )

        # Determine root cause
        if error_suggestions.get('matched'):
            causes = error_suggestions.get('common_causes', [])
            if causes:
                analysis.root_cause = causes[0]

        # Determine suggested fix
        solutions = error_suggestions.get('solutions', [])
        if solutions:
            analysis.suggested_fix = solutions[0]
            analysis.code_examples = error_suggestions.get('code_example', [None] if error_suggestions.get('code_example') else [])

        # Add KB solutions if pattern match failed
        if not error_suggestions.get('matched') and kb_solutions:
            top_solution = kb_solutions[0]
            analysis.suggested_fix = top_solution.solution
            analysis.code_examples = [top_solution.code_example]

        # Calculate confidence
        analysis.confidence = self._calculate_confidence(analysis, error_suggestions)

        # Format summary
        analysis.root_cause = self._format_root_cause(analysis)
        analysis.suggested_fix = self._format_fix(analysis)

        return analysis

    def quick_diagnose(self, error_message: str) -> str:
        """
        Get a quick one-line diagnosis for an error.

        Args:
            error_message: The error message

        Returns:
            Quick diagnosis string
        """
        suggestions = self.error_matcher.get_suggestions(error_message)

        if suggestions.get('matched'):
            cause = suggestions.get('common_causes', ['Unknown'])[0]
            fix = suggestions.get('solutions', ['Check error details'])[0]
            return f"{cause}. Suggestion: {fix}"

        # Try knowledge base
        kb_solutions = self.knowledge_base.find_solutions(error_message)
        if kb_solutions:
            solution = kb_solutions[0]
            return f"{solution.problem}: {solution.solution}"

        return "No specific pattern matched. Please provide more context."

    def find_similar_alerts(
        self,
        alert_message: str,
        history: List[Dict[str, Any]],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find similar historical alerts.

        Args:
            alert_message: Current alert message
            history: Historical alert data
            limit: Maximum results

        Returns:
            List of similar alerts
        """
        similar = []

        # Simple keyword matching for now
        alert_words = set(alert_message.lower().split())

        for alert in history:
            alert_words_lower = alert.get('message', '').lower().split()
            alert_words_set = set(alert_words_lower)

            intersection = alert_words & alert_words_set
            if len(intersection) >= 2:  # At least 2 matching keywords
                similarity = len(intersection) / max(len(alert_words), len(alert_words_set))
                similar.append({
                    **alert,
                    'similarity': similarity,
                })

        # Sort by similarity and return top results
        similar.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return similar[:limit]

    def get_fix_from_kb(self, error_message: str) -> Optional[str]:
        """
        Get a fix from the knowledge base.

        Args:
            error_message: The error message

        Returns:
            Fix suggestion or None
        """
        solutions = self.knowledge_base.find_solutions(error_message)

        if solutions:
            solution = solutions[0]
            return f"{solution.solution}"

        return None

    def _generate_alert_id(self, message: str) -> str:
        """Generate a unique ID for the alert."""
        import hashlib
        return hashlib.md5(f"{message}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

    def _calculate_confidence(
        self,
        analysis: AlertAnalysis,
        error_suggestions: Dict,
    ) -> float:
        """Calculate confidence score for the analysis."""
        confidence = 0.5

        # High confidence if pattern matched
        if error_suggestions.get('matched'):
            confidence += 0.3

        # High confidence if stack trace is available
        if analysis.stack_frames:
            confidence += 0.15

        # High confidence if KB has solutions
        if analysis.suggested_solutions:
            confidence += 0.1

        # High confidence if related files found
        if analysis.related_files:
            confidence += 0.05

        return min(confidence, 1.0)

    def _format_root_cause(self, analysis: AlertAnalysis) -> str:
        """Format the root cause explanation."""
        if analysis.root_cause:
            return analysis.root_cause

        if analysis.stack_frames:
            root_frame = self.stack_parser.get_root_cause_frame(analysis.stack_frames)
            if root_frame:
                return f"Error occurred in {root_frame.function_name} at {root_frame.file_path}:{root_frame.line_number}"

        return "Unable to determine root cause from available information"

    def _format_fix(self, analysis: AlertAnalysis) -> str:
        """Format the suggested fix."""
        if analysis.suggested_fix:
            return analysis.suggested_fix

        if analysis.suggested_solutions:
            solution = analysis.suggested_solutions[0]
            return f"{solution.solution}"

        return "No specific fix available. Please check the error message and stack trace for details."

    def to_report(self, analysis: AlertAnalysis) -> str:
        """
        Generate a human-readable report for the alert analysis.

        Args:
            analysis: The analysis result

        Returns:
            Formatted report string
        """
        lines = [
            f"Alert Analysis Report",
            f"=" * 40,
            f"Error: {analysis.error_message}",
            f"Category: {analysis.error_category}",
            f"Severity: {analysis.severity}",
            "",
            f"Root Cause: {analysis.root_cause}",
            "",
            f"Suggested Fix: {analysis.suggested_fix}",
        ]

        if analysis.related_files:
            lines.append("")
            lines.append("Related Files:")
            for file_path in analysis.related_files[:5]:  # Limit to 5 files
                lines.append(f"  - {file_path}")

        if analysis.stack_frames:
            lines.append("")
            lines.append("Stack Trace:")
            for i, frame in enumerate(analysis.stack_frames[:5]):  # Limit to 5 frames
                lines.append(f"  [{i}] {frame}")

        if analysis.code_examples and analysis.code_examples[0]:
            lines.append("")
            lines.append("Code Example:")
            lines.append("```" + analysis.code_examples[0] + "```")

        return "\n".join(lines)


def analyze_alert(
    repo_path: str,
    alert_message: str,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to analyze an alert.

    Args:
        repo_path: Path to the code repository
        alert_message: The alert/error message
        stack_trace: Optional stack trace
        context: Additional context

    Returns:
        Analysis result as dictionary
    """
    analyzer = AlertAnalyzer(repo_path)
    analysis = analyzer.analyze(alert_message, stack_trace, context)
    return analysis.to_dict()
