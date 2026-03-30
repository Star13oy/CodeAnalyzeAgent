"""
Stack Trace Parser

Parses stack traces from various programming languages.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StackLanguage(Enum):
    """Programming language for stack trace."""
    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    C_CPP = "c_cpp"
    GO = "go"
    RUST = "rust"
    RUBY = "ruby"
    PHP = "php"
    UNKNOWN = "unknown"


@dataclass
class StackFrame:
    """A single frame in a stack trace."""
    language: str
    file_path: str
    line_number: int
    function_name: str
    module: Optional[str] = None
    code_context: Optional[str] = None

    def __str__(self) -> str:
        if self.module:
            return f"at {self.module}.{self.function_name} ({self.file_path}:{self.line_number})"
        return f"at {self.function_name} ({self.file_path}:{self.line_number})"


class StackParser:
    """
    Parser for stack traces from multiple languages.

    Supports:
    - Python tracebacks
    - Java stack traces
    - JavaScript/Node.js errors
    - C/C++ stack traces
    - Go panics
    - Rust backtraces
    """

    # Language-specific patterns
    PATTERNS = {
        StackLanguage.PYTHON: [
            # File "test.py", line 42, in <module>
            r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\S+)',
            # test.py:42:func
            r'([^:]+):(\d+):(\w+)',
        ],
        StackLanguage.JAVA: [
            # at com.example.MyClass.myMethod(MyClass.java:42)
            r'at\s+([\w.]+)\.(\w+)\(([^:]+)\.java:(\d+)\)',
            # com.example.MyClass.myMethod(MyClass.java:42)
            r'([\w.]+)\.(\w+)\(([^:]+)\.java:(\d+)\)',
        ],
        StackLanguage.JAVASCRIPT: [
            # at func (/path/to/file.js:42:15)
            r'at\s+(\w+)\s+\(([^:]+):(\d+):\d+\)',
            # at /path/to/file.js:42:15
            r'at\s+([^:]+):(\d+):\d+',
        ],
        StackLanguage.GO: [
            # main.go:42: main.func1
            r'([^:]+):(\d+):\s+(\S+)',
        ],
        StackLanguage.RUST: [
            # at src/main.rs:42:5
            r'\s+at\s+([^:]+):(\d+):(\d+)',
        ],
        StackLanguage.C_CPP: [
            # #0 0x123456 in func () at file.cpp:42
            r'#\d+\s+0x[\da-fA-F]+\s+in\s+(\S+)\s+\(\)\s+at\s+([^:]+):(\d+)',
        ],
        StackLanguage.RUBY: [
            # test.rb:42:in `block'
            r'\s([^:]+):(\d+):in\s+`([^`]+)`',
        ],
        StackLanguage.PHP: [
            # #0 {main}() called at [/path/to/file.php:42]
            r'called at\s+\[([^:]+\.php):(\d+)\]',
        ],
    }

    def __init__(self):
        """Initialize the stack parser."""
        self.language_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[StackLanguage, List[re.Pattern]]:
        """Compile regex patterns for each language."""
        compiled = {}
        for lang, patterns in self.PATTERNS.items():
            compiled[lang] = [re.compile(p) for p in patterns]
        return compiled

    def parse(self, stack_trace: str, language: Optional[str] = None) -> List[StackFrame]:
        """
        Parse a stack trace.

        Args:
            stack_trace: The raw stack trace string
            language: Optional language hint (auto-detect if None)

        Returns:
            List of StackFrame objects
        """
        if not stack_trace or not stack_trace.strip():
            return []

        # Auto-detect language if not specified
        if language is None:
            language = self._detect_language(stack_trace)

        try:
            lang_enum = StackLanguage(language)
        except ValueError:
            lang_enum = StackLanguage.UNKNOWN

        # Parse using language-specific patterns
        frames = []
        patterns = self.language_patterns.get(lang_enum, [])

        for line in stack_trace.split('\n'):
            line = line.strip()
            if not line:
                continue

            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    frame = self._create_frame(match, lang_enum)
                    if frame:
                        frames.append(frame)
                    break

        return frames

    def _create_frame(self, match: re.Match, language: StackLanguage) -> Optional[StackFrame]:
        """Create a StackFrame from a regex match."""
        groups = match.groups()

        if language == StackLanguage.PYTHON:
            # Pattern: File "path", line 42, in function
            if len(groups) == 3:
                return StackFrame(
                    language="python",
                    file_path=groups[0],
                    line_number=int(groups[1]),
                    function_name=groups[2],
                )
            # Pattern: path:42:function
            elif len(groups) == 3:
                return StackFrame(
                    language="python",
                    file_path=groups[0],
                    line_number=int(groups[1]),
                    function_name=groups[2],
                )

        elif language == StackLanguage.JAVA:
            # Pattern: at com.example.MyClass.myMethod(MyClass.java:42)
            if len(groups) == 4:
                return StackFrame(
                    language="java",
                    file_path=f"{groups[2]}.java",
                    line_number=int(groups[3]),
                    function_name=groups[1],
                    module=groups[0],
                )

        elif language == StackLanguage.JAVASCRIPT:
            # Pattern: at func (path.js:42:15) - 3 groups
            if len(groups) == 3:
                return StackFrame(
                    language="javascript",
                    file_path=groups[1],
                    line_number=int(groups[2]),
                    function_name=groups[0],
                )
            # Pattern: at path.js:42:15 - 2 groups (no function name)
            elif len(groups) == 2:
                return StackFrame(
                    language="javascript",
                    file_path=groups[0],
                    line_number=int(groups[1]),
                    function_name="unknown",
                )

        elif language == StackLanguage.GO:
            # Pattern: main.go:42: main.func1
            if len(groups) == 3:
                return StackFrame(
                    language="go",
                    file_path=groups[0],
                    line_number=int(groups[1]),
                    function_name=groups[2],
                )

        elif language == StackLanguage.RUST:
            # Pattern: path.rs:42:5
            if len(groups) == 3:
                return StackFrame(
                    language="rust",
                    file_path=groups[0],
                    line_number=int(groups[1]),
                    function_name="unknown",
                )

        return None

    def _detect_language(self, stack_trace: str) -> str:
        """
        Auto-detect the programming language from stack trace.

        Args:
            stack_trace: The raw stack trace

        Returns:
            Language name string
        """
        # Language-specific keywords
        indicators = {
            StackLanguage.PYTHON: ['Traceback', 'File "', 'in <module>', 'Python'],
            StackLanguage.JAVA: ['Exception in thread', 'at java.', 'at com.', '.java:'],
            StackLanguage.JAVASCRIPT: ['at ', '.js:', '.ts:', 'Node.js'],
            StackLanguage.GO: ['panic:', 'goroutine', '.go:'],
            StackLanguage.RUST: ['panicked at', 'stack backtrace:', '.rs:'],
            StackLanguage.RUBY: ['from ', ':in `', 'Ruby'],
            StackLanguage.PHP: ['PHP Fatal error', '.php:'],
            StackLanguage.C_CPP: ['#0 ', '0x', 'in ', '.cpp:', '.cc:'],
        }

        # Count matches
        scores = {}
        trace_lower = stack_trace.lower()

        for lang, keywords in indicators.items():
            score = sum(1 for kw in keywords if kw.lower() in trace_lower)
            if score > 0:
                scores[lang] = score

        if scores:
            return max(scores, key=scores.get).value

        return StackLanguage.UNKNOWN.value

    def extract_error_message(self, stack_trace: str) -> Optional[str]:
        """
        Extract the error message from a stack trace.

        Args:
            stack_trace: The raw stack trace

        Returns:
            Error message or None
        """
        lines = stack_trace.split('\n')
        for line in lines:
            line = line.strip()
            # Look for common error patterns
            if any(err in line for err in [
                'Error:', 'Exception:', 'Exception', 'Error',
                'Exception in thread', 'panic:', 'FATAL:',
                'Fatal Error', 'WARNING:', 'WARN:',
            ]):
                return line

        # Return first line if no error pattern found
        if lines:
            return lines[0].strip()

        return None

    def get_root_cause_frame(self, frames: List[StackFrame]) -> Optional[StackFrame]:
        """
        Find the root cause frame (usually the deepest application frame).

        Args:
            frames: List of stack frames

        Returns:
            Root cause frame or None
        """
        if not frames:
            return None

        # Skip system/library frames
        system_prefixes = [
            '/usr/lib/',
            '/usr/local/lib/',
            'node_modules/',
            'site-packages/',
            '<',
        ]

        # Find the last frame that's not in system code
        for frame in reversed(frames):
            if not any(prefix in frame.file_path for prefix in system_prefixes):
                return frame

        return frames[-1]

    def format_frame(self, frame: StackFrame) -> str:
        """Format a stack frame for display."""
        return f"  at {frame.function_name} ({frame.file_path}:{frame.line_number})"

    def format_trace(self, frames: List[StackFrame]) -> str:
        """Format a list of frames for display."""
        if not frames:
            return "No stack trace available"

        lines = ["Stack trace:"]
        for i, frame in enumerate(frames):
            lines.append(f"  [{i}] {self.format_frame(frame)}")

        return "\n".join(lines)
