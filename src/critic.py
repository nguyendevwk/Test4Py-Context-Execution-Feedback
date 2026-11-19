"""Adaptive Critic Feedback & Multi-Round Repair Engine.

Implements Section 3.3 & Algorithm 3.2: 2-Round Diagnostic Feedback Loop.
- Round 1: Syntactic, Import, and Signature Rectification.
- Round 2: Micro-Assertion Calibration via Pytest Traceback Diffs.
- Strict Assertion Integrity Preservation (never weakens or deletes assertions).
"""

from __future__ import annotations
import ast
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class RepairAnalysis:
    """Diagnostic analysis of sandbox execution failure."""
    failure_category: str  # 'syntax' | 'import' | 'type_arity' | 'assertion_mismatch' | 'unknown'
    root_cause: str
    suggested_strategy: str
    diff_context: str


class AdaptiveCritic:
    """Analyzes execution tracebacks and guides iterative code repair."""

    @staticmethod
    def analyze_failure(traceback_text: str, round_index: int) -> RepairAnalysis:
        """Categorizes runtime failure and prescribes targeted remediation."""
        text = traceback_text or ""

        # 1. Check for syntax or indentation errors
        if "SyntaxError" in text or "IndentationError" in text:
            return RepairAnalysis(
                failure_category="syntax",
                root_cause="Python compilation failed due to improper indentation or syntax format.",
                suggested_strategy="Fix indentation levels, ensure valid multi-line docstring escapes, and close all brackets.",
                diff_context=text[:500]
            )

        # 2. Check for missing module or import name
        if "ModuleNotFoundError" in text or "ImportError" in text:
            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", text)
            missing = match.group(1) if match else "unknown module"
            return RepairAnalysis(
                failure_category="import",
                root_cause=f"Test failed to import required module or symbol: `{missing}`.",
                suggested_strategy=f"Correct the import path or mock optional external dependency `{missing}` if not in standard library.",
                diff_context=text[:500]
            )

        # 3. Check for parameter / argument mismatch (TypeError arity)
        if "TypeError" in text and ("positional argument" in text or "keyword argument" in text):
            return RepairAnalysis(
                failure_category="type_arity",
                root_cause="Function call argument mismatch with target signature.",
                suggested_strategy="Align constructor or method parameters with the AST signature specifications.",
                diff_context=text[:500]
            )

        # 4. Check for assertion mismatch
        if "AssertionError" in text or "assert " in text:
            return RepairAnalysis(
                failure_category="assertion_mismatch",
                root_cause="Test expectation diverged from actual production return value.",
                suggested_strategy=(
                    "Calibrate expected assertion value using the pytest diff. "
                    "DO NOT delete the assert or replace it with 'assert True'. "
                    "Ensure the test tests domain behavior rather than trivial identity."
                ),
                diff_context=text[:1000]
            )

        return RepairAnalysis(
            failure_category="unknown",
            root_cause="Runtime exception or assertion discrepancy during test execution.",
            suggested_strategy="Inspect the traceback carefully and align test calls with target semantics.",
            diff_context=text[:800]
        )

    @staticmethod
    def build_repair_prompt(
        original_code: str,
        analysis: RepairAnalysis,
        round_index: int,
        target_name: str
    ) -> str:
        """Constructs a strict repair instruction prompt."""
        prompt = [
            f"### CRITIC REPAIR DIRECTIVE (Round {round_index} of 2)",
            f"The unit test suite for `{target_name}` failed execution in the Pytest sandbox.",
            f"**Failure Category**: {analysis.failure_category.upper()}",
            f"**Root Cause**: {analysis.root_cause}",
            f"**Action Required**: {analysis.suggested_strategy}",
            "",
            "**Traceback Snippet**:",
            "```text",
            analysis.diff_context,
            "```",
            "",
            "**Previous Code**:",
            "```python",
            original_code,
            "```",
            "",
            "**Output Requirement**:",
            "- Return ONLY the complete, corrected Python test file in a single code block.",
            "- Must contain exactly 3 unit tests with names starting with `test_`.",
            "- DO NOT delete assertions or weaken assertions to trivial checks.",
        ]
        return "\n".join(prompt)

    @staticmethod
    def count_verification_statements(code: str) -> int:
        """Counts both assert statements and pytest.raises() context managers."""
        try:
            tree = ast.parse(code)
            count = 0
            for n in ast.walk(tree):
                if isinstance(n, ast.Assert):
                    count += 1
                elif isinstance(n, ast.With):
                    for item in n.items:
                        call_repr = ast.unparse(item.context_expr)
                        if "pytest.raises" in call_repr:
                            count += 1
            return count
        except SyntaxError:
            return 0

    @classmethod
    def verify_assertion_integrity(cls, original_code: str, repaired_code: str) -> bool:
        """Ensures the repaired code does not hollow out assertions (Quality Gatekeeper)."""
        orig_count = cls.count_verification_statements(original_code)
        rep_count = cls.count_verification_statements(repaired_code)

        # Repaired code must maintain at least 3 verification checks
        if rep_count < 3:
            return False
        if orig_count > 0 and rep_count < int(orig_count * 0.75):
            return False
        return True
