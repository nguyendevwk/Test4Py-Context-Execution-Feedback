"""Test Generation Orchestrator & Multi-Component Pipeline.

Coordinates AST Scope Extraction, Setup Probing, Prompt Synthesis,
Sandbox Execution, and Adaptive Critic Feedback Loops.
"""

from __future__ import annotations
import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.ast_context import ASTContextExtractor, TargetScopeInfo
from src.setup_probing import SetupProber, SetupProbeResult
from src.sandbox import PytestSandbox, EvaluationResult
from src.critic import AdaptiveCritic, RepairAnalysis


SPECIFICATION_PROMPT_TEMPLATE = """You are a senior software verification engineer generating professional Pytest suites.

### TARGET SPECIFICATION:
- Module: `{module_name}`
- Target: `{target_name}` ({target_type})
- Signature: `{signature}`

### AST CODE CONTEXT:
```python
{source_code}
```

{auxiliary_context}

{setup_hints}

### GENERATION CONSTRAINTS (STRICT):
1. Output exactly ONE Python code block containing a complete, standalone pytest file.
2. The suite must contain EXACTLY 3 test functions:
   - `test_target_normal()`: Verifies typical domain usage and expected return values.
   - `test_target_boundary()`: Verifies edge cases (e.g. empty, zero, None, extremes).
   - `test_target_exception()`: Verifies exception handling and error branches.
3. Call the REAL production implementation `{target_name}` directly. Never mock the target itself.
4. Always import `pytest` and required dependencies at the top.
5. Provide rigorous assertions that check values and state mutations, not just `assert True`.
"""


class TestGenerator:
    """End-to-end synthesizer combining AST context and execution feedback."""

    def __init__(
        self,
        extractor: Optional[ASTContextExtractor] = None,
        sandbox: Optional[PytestSandbox] = None,
        max_repair_rounds: int = 2
    ):
        self.extractor = extractor or ASTContextExtractor()
        self.sandbox = sandbox or PytestSandbox()
        self.max_repair_rounds = max_repair_rounds

    def build_prompt(
        self,
        module_name: str,
        target_name: str,
        scope: TargetScopeInfo,
        probe: Optional[SetupProbeResult] = None
    ) -> str:
        """Constructs the prompt containing AST context and setup hints."""
        aux_text = ""
        if scope.auxiliary_functions:
            aux_lines = ["### Auxiliary Context (Enclosing & Sibling Functions):"]
            for aux in scope.auxiliary_functions:
                aux_lines.append(f"```python\n# Helper: {aux['name']}\n{aux['source']}\n```")
            aux_text = "\n".join(aux_lines)

        setup_text = ""
        if probe:
            setup_text = SetupProber.format_prompt_hint(probe)

        return SPECIFICATION_PROMPT_TEMPLATE.format(
            module_name=module_name,
            target_name=target_name,
            target_type=scope.target_type,
            signature=scope.signature,
            source_code=scope.source_code,
            auxiliary_context=aux_text,
            setup_hints=setup_text
        )

    @staticmethod
    def extract_code_block(text: str) -> str:
        """Extracts python code from markdown code fences."""
        pattern = r"```(?:python)?\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fallback: if no code fence, return cleaned text
        return text.strip()
