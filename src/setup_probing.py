"""Dynamic Setup Probing and Execution Scaffolding.

Analyzes callable parameter constraints, required fixtures, constructor signatures,
and initialization contracts without oracle contamination.
"""

from __future__ import annotations
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SetupProbeResult:
    """Scaffolding information derived from parameter inspection."""
    callable_name: str
    required_args: List[str] = field(default_factory=list)
    optional_args: Dict[str, Any] = field(default_factory=dict)
    varargs: Optional[str] = None
    varkw: Optional[str] = None
    type_annotations: Dict[str, str] = field(default_factory=dict)
    instantiation_scaffold: str = ""
    oracle_integrity_verified: bool = True


class SetupProber:
    """Probes callable signatures and constructs setup templates."""

    @staticmethod
    def probe_callable(target_callable: Callable) -> SetupProbeResult:
        """Inspects live callable signature to build robust instantiation hints."""
        try:
            sig = inspect.signature(target_callable)
        except (ValueError, TypeError):
            return SetupProbeResult(callable_name=getattr(target_callable, '__name__', str(target_callable)))

        req_args = []
        opt_args = {}
        annotations = {}

        for name, param in sig.parameters.items():
            if name in ('self', 'cls'):
                continue
            if param.annotation != inspect.Parameter.empty:
                annotations[name] = str(param.annotation)
            if param.default == inspect.Parameter.empty:
                if param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    req_args.append(name)
            else:
                opt_args[name] = repr(param.default)

        # Build scaffolding snippet
        args_repr = []
        for a in req_args:
            # Provide sensible dummy values for common types
            ann = annotations.get(a, '').lower()
            if 'str' in ann:
                args_repr.append(f"{a}='test_{a}'")
            elif 'int' in ann:
                args_repr.append(f"{a}=1")
            elif 'float' in ann:
                args_repr.append(f"{a}=1.0")
            elif 'bool' in ann:
                args_repr.append(f"{a}=True")
            elif 'list' in ann:
                args_repr.append(f"{a}=[]")
            elif 'dict' in ann:
                args_repr.append(f"{a}={{}}")
            else:
                args_repr.append(f"{a}=None")

        scaffold = f"# Setup template for {getattr(target_callable, '__name__', 'target')}:\n"
        if inspect.isclass(target_callable):
            scaffold += f"instance = {target_callable.__name__}({', '.join(args_repr)})\n"
        else:
            scaffold += f"# Call signature: {target_callable.__name__}({', '.join(args_repr)})\n"

        return SetupProbeResult(
            callable_name=getattr(target_callable, '__name__', 'target'),
            required_args=req_args,
            optional_args=opt_args,
            type_annotations=annotations,
            instantiation_scaffold=scaffold,
            oracle_integrity_verified=True
        )

    @staticmethod
    def format_prompt_hint(probe: SetupProbeResult) -> str:
        """Formats setup hints into a clear instruction for the LLM."""
        lines = [
            "### Setup Probing Scaffolding:",
            f"- Callable: `{probe.callable_name}`",
            f"- Required parameters: {probe.required_args or 'None'}",
            f"- Optional / Defaults: {list(probe.optional_args.keys()) or 'None'}",
        ]
        if probe.type_annotations:
            lines.append(f"- Annotations: {probe.type_annotations}")
        lines.append("- Note: Construct realistic domain inputs. Do not assume unverified return values as constants.")
        return "\n".join(lines)
