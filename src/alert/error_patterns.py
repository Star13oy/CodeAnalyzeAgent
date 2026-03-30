"""
Error Pattern Matching

Identifies common error patterns and provides suggested fixes.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for better organization."""
    NULL_POINTER = "null_pointer"
    TYPE_ERROR = "type_error"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    OUT_OF_MEMORY = "out_of_memory"
    DIVISION_BY_ZERO = "division_by_zero"
    INDEX_ERROR = "index_error"
    KEY_ERROR = "key_error"
    IMPORT_ERROR = "import_error"
    SYNTAX_ERROR = "syntax_error"
    DATABASE = "database"
    NETWORK = "network"
    CONCURRENCY = "concurrency"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


@dataclass
class ErrorPattern:
    """A recognized error pattern with fix suggestions."""
    id: str
    category: ErrorCategory
    patterns: List[str]
    description: str
    common_causes: List[str]
    solutions: List[str]
    code_example: Optional[str] = None
    severity: str = "medium"  # low, medium, high, critical


class ErrorMatcher:
    """
    Matches error messages against known patterns.

    Provides intelligent suggestions for common errors.
    """

    # Common error patterns database
    PATTERNS: List[ErrorPattern] = [
        # Null Pointer / NoneType errors
        ErrorPattern(
            id="null_pointer_python",
            category=ErrorCategory.NULL_POINTER,
            patterns=[
                r"'NoneType' object has no attribute",
                r"AttributeError: 'NoneType'",
                r"NullPointerException",
                r"Cannot read property .* of undefined",
            ],
            description="Null/None value access",
            common_causes=[
                "Variable not initialized before use",
                "Function returned None without checking",
                "Missing null/None check",
            ],
            solutions=[
                "Add null/None check before accessing",
                "Initialize variables with default values",
                "Use optional chaining (obj?.prop in JS)",
            ],
            severity="high",
        ),

        # File Not Found
        ErrorPattern(
            id="file_not_found",
            category=ErrorCategory.FILE_NOT_FOUND,
            patterns=[
                r"FileNotFoundError: \[Errno 2\]",
                r"No such file or directory",
                r"ENOENT",
                r"open\([^)]*\) failed",
            ],
            description="File or directory not found",
            common_causes=[
                "Incorrect file path",
                "File doesn't exist",
                "Wrong working directory",
                "Missing file extension",
            ],
            solutions=[
                "Verify file path is correct",
                "Check if file exists with os.path.exists()",
                "Use absolute path instead of relative",
                "Add error handling for missing files",
            ],
            code_example="if os.path.exists(file_path):\n    with open(file_path) as f:\n        ...",
            severity="medium",
        ),

        # Permission Denied
        ErrorPattern(
            id="permission_denied",
            category=ErrorCategory.PERMISSION_DENIED,
            patterns=[
                r"Permission denied",
                r"AccessDenied",
                r"\[Errno 13\] Permission denied",
                r"403 Forbidden",
            ],
            description="Permission denied",
            common_causes=[
                "Insufficient file permissions",
                "Trying to write to read-only file",
                "Running without admin privileges",
            ],
            solutions=[
                "Check file permissions with chmod/chown",
                "Run with appropriate privileges",
                "Check if file is open elsewhere",
            ],
            severity="high",
        ),

        # Index Out of Range
        ErrorPattern(
            id="index_out_of_range",
            category=ErrorCategory.INDEX_ERROR,
            patterns=[
                r"IndexError: .*\s*out of range",
                r"ArrayIndexOutOfBoundsException",
                r"undefined is not an object",
                r"Cannot read property .* of undefined",
            ],
            description="Index out of range",
            common_causes=[
                "Accessing array/list beyond its length",
                "Using wrong index (off-by-one)",
                "Missing check before accessing",
            ],
            solutions=[
                "Check array/list length before accessing",
                "Use bounds check: if 0 <= i < len(arr)",
                "Add try-catch around access",
            ],
            code_example="if 0 <= index < len(array):\n    value = array[index]",
            severity="high",
        ),

        # Key Error
        ErrorPattern(
            id="key_error",
            category=ErrorCategory.KEY_ERROR,
            patterns=[
                r"KeyError: .*",
                r"The .* key was not found",
                r"'[^']' key not found",
            ],
            description="Dictionary key not found",
            common_causes=[
                "Accessing non-existent dictionary key",
                "Typo in key name",
                "Key not present in dictionary",
            ],
            solutions=[
                "Use dict.get(key, default) instead of dict[key]",
                "Check if key exists with 'in' operator",
                "Use dict.setdefault() to provide default",
            ],
            code_example="value = my_dict.get(key, default_value)",
            severity="medium",
        ),

        # Type Error
        ErrorPattern(
            id="type_error",
            category=ErrorCategory.TYPE_ERROR,
            patterns=[
                r"TypeError: .*",
                r"invalid type",
                r"expected .* but got .*",
            ],
            description="Type mismatch",
            common_causes=[
                "Passing wrong type to function",
                "Incompatible types in operation",
                "Wrong format conversion",
            ],
            solutions=[
                "Check function signature for expected types",
                "Use type() to verify variable type",
                "Add type conversion: int(), str(), etc.",
            ],
            severity="medium",
        ),

        # Import Error
        ErrorPattern(
            id="import_error",
            category=ErrorCategory.IMPORT_ERROR,
            patterns=[
                r"ModuleNotFoundError: No module named",
                r"ImportError: cannot import name",
                r"require\(.*\) is not defined",
            ],
            description="Module import failed",
            common_causes=[
                "Module not installed",
                "Wrong import path",
                "Circular import",
                "Virtual environment not activated",
            ],
            solutions=[
                "Install missing package: pip install <package>",
                "Check PYTHONPATH includes module directory",
                "Fix circular import by moving imports",
                "Activate virtual environment: source venv/bin/activate",
            ],
            severity="medium",
        ),

        # Database Errors
        ErrorPattern(
            id="database_connection",
            category=ErrorCategory.DATABASE,
            patterns=[
                r"OperationalError: unable to connect",
                r"Connection refused",
                r"Authentication failed",
                r"Table .* doesn't exist",
            ],
            description="Database error",
            common_causes=[
                "Database server not running",
                "Wrong connection parameters",
                "Missing database migration",
                "Insufficient privileges",
            ],
            solutions=[
                "Verify database server is running",
                "Check connection string/host/port",
                "Run migrations to create tables",
                "Verify user has required permissions",
            ],
            severity="high",
        ),

        # Timeout
        ErrorPattern(
            id="timeout",
            category=ErrorCategory.TIMEOUT,
            patterns=[
                r"TimeoutError",
                r"Read timeout",
                r"Connection timed out",
                r"504 Gateway Timeout",
            ],
            description="Operation timeout",
            common_causes=[
                "Operation took too long",
                "Server not responding",
                "Network latency",
                "Resource deadlock",
            ],
            solutions=[
                "Increase timeout duration",
                "Check server health/status",
                "Optimize slow queries",
                "Add retry logic with exponential backoff",
            ],
            severity="medium",
        ),

        # Out of Memory
        ErrorPattern(
            id="out_of_memory",
            category=ErrorCategory.OUT_OF_MEMORY,
            patterns=[
                r"MemoryError",
                r"OutOfMemoryError",
                r"std::bad_alloc",
                r"JavaScript heap out of memory",
            ],
            description="Out of memory",
            common_causes=[
                "Memory leak",
                "Loading too much data at once",
                "Infinite recursion",
                "Memory limit exceeded",
            ],
            solutions=[
                "Process data in chunks instead of all at once",
                "Fix memory leaks (close connections, release resources)",
                "Increase memory limit",
                "Use streaming for large datasets",
            ],
            severity="critical",
        ),

        # Syntax Error
        ErrorPattern(
            id="syntax_error",
            category=ErrorCategory.SYNTAX_ERROR,
            patterns=[
                r"SyntaxError: .*",
                r"Unexpected token",
                r"ParseError: .*",
                r"Unexpected end of input",
            ],
            description="Syntax error",
            common_causes=[
                "Typo in code",
                "Missing colon/bracket/quote",
                "Wrong indentation (Python)",
                "Using keyword as variable name",
            ],
            solutions=[
                "Check line above error for syntax issues",
                "Verify all brackets/quotes are closed",
                "Check indentation (Python: use 4 spaces)",
                "Run linter to catch syntax errors early",
            ],
            severity="high",
        ),

        # Configuration Error
        ErrorPattern(
            id="config_error",
            category=ErrorCategory.CONFIGURATION,
            patterns=[
                r"ConfigurationError",
                r"ConfigParser\.NoSectionError",
                r"Missing required configuration",
                r"Environment variable not found",
            ],
            description="Configuration error",
            common_causes=[
                "Missing config file",
                "Wrong config format",
                "Missing environment variables",
                "Invalid config value",
            ],
            solutions=[
                "Create config file with required sections",
                "Set required environment variables",
                "Validate config values before use",
                "Use default values for optional settings",
            ],
            severity="medium",
        ),
    ]

    def __init__(self):
        """Initialize the error matcher."""
        self._compiled_patterns = []
        for pattern in self.PATTERNS:
            for regex in pattern.patterns:
                try:
                    self._compiled_patterns.append({
                        'pattern': re.compile(regex, re.IGNORECASE),
                        'error_info': pattern
                    })
                except re.error as e:
                    logger.warning(f"Failed to compile pattern '{regex}': {e}")

    def match(self, error_message: str) -> List[ErrorPattern]:
        """
        Match error message against known patterns.

        Args:
            error_message: The error message to analyze

        Returns:
            List of matching ErrorPattern objects
        """
        matches = []

        for compiled in self._compiled_patterns:
            if compiled['pattern'].search(error_message):
                matches.append(compiled['error_info'])

        return matches

    def get_suggestions(self, error_message: str) -> Dict[str, Any]:
        """
        Get fix suggestions for an error.

        Args:
            error_message: The error message to analyze

        Returns:
            Dictionary with analysis results
        """
        matches = self.match(error_message)

        if not matches:
            return {
                "matched": False,
                "category": ErrorCategory.UNKNOWN.value,
                "message": "No specific pattern matched",
            }

        # Use the first (highest severity) match
        pattern = matches[0]

        return {
            "matched": True,
            "category": pattern.category.value,
            "pattern_id": pattern.id,
            "description": pattern.description,
            "severity": pattern.severity,
            "common_causes": pattern.common_causes,
            "solutions": pattern.solutions,
            "code_example": pattern.code_example,
        }

    def get_quick_fix(self, error_message: str) -> Optional[str]:
        """
        Get a one-line quick fix suggestion.

        Args:
            error_message: The error message

        Returns:
            Quick fix string or None
        """
        suggestions = self.get_suggestions(error_message)

        if suggestions.get('matched') and suggestions.get('solutions'):
            return suggestions['solutions'][0]

        return None
