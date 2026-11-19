"""AST Context Extraction & Symbol Scope Resolver.

Implements Algorithm 3.1: Auxiliary Context Closure Extraction from Python AST.
Extracts enclosing class definitions, sibling helper methods, imported symbols,
and signatures while adhering strictly to token / character context limits.
"""

from __future__ import annotations
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TargetScopeInfo:
    """Represents the parsed AST scope around a target callable."""
    target_name: str
    target_type: str  # 'function' | 'method' | 'class'
    source_code: str
    signature: str
    body_lines: List[int]
    docstring: Optional[str] = None
    enclosing_class: Optional[str] = None
    auxiliary_functions: List[Dict[str, str]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    symbol_table: Dict[str, str] = field(default_factory=dict)


class ASTContextExtractor:
    """Extracts bounded AST context and lexical symbol tables for target modules."""

    def __init__(self, max_body_chars: int = 6000, max_aux_chars: int = 4000, max_total_chars: int = 8000):
        self.max_body_chars = max_body_chars
        self.max_aux_chars = max_aux_chars
        self.max_total_chars = max_total_chars

    def extract_from_source(self, source_code: str, target_name: str) -> TargetScopeInfo:
        """Parses Python source code and extracts scoped context for target_name."""
        tree = ast.parse(source_code)
        
        # 1. Collect top-level imports
        imports = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(ast.unparse(node))
                
        # 2. Search for the target node (FunctionDef, AsyncFunctionDef, or ClassDef)
        target_node = None
        enclosing_class_name = None
        parent_map = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        candidates = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == target_name:
                    candidates.append(node)
                    
        if not candidates:
            # Fallback search by suffix or attribute
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if target_name.endswith(f".{node.name}") or node.name.endswith(target_name):
                        candidates.append(node)
                        break

        if not candidates:
            raise ValueError(f"Target '{target_name}' not found in source AST.")

        target_node = candidates[0]
        
        # Check enclosing class
        curr = parent_map.get(target_node)
        while curr:
            if isinstance(curr, ast.ClassDef):
                enclosing_class_name = curr.name
                break
            curr = parent_map.get(curr)

        # 3. Compute body lines
        start_line = getattr(target_node, 'lineno', 1)
        end_line = getattr(target_node, 'end_lineno', start_line)
        body_lines = list(range(start_line, end_line + 1))

        # 4. Extract signature
        if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = "(" + ast.unparse(target_node.args) + ")"
            if target_node.returns:
                sig += f" -> {ast.unparse(target_node.returns)}"
            target_type = "method" if enclosing_class_name else "function"
        else:
            sig = f"class {target_node.name}"
            target_type = "class"

        # 5. Extract docstring
        docstring = ast.get_docstring(target_node)

        # 6. Extract auxiliary functions / helper symbols
        auxiliary = []
        current_aux_chars = 0
        for node in tree.body:
            if node is not target_node and isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name.startswith("_") or node.name in ast.unparse(target_node):
                    node_src = ast.unparse(node)
                    if current_aux_chars + len(node_src) <= self.max_aux_chars:
                        auxiliary.append({
                            "name": node.name,
                            "type": "class" if isinstance(node, ast.ClassDef) else "function",
                            "source": node_src
                        })
                        current_aux_chars += len(node_src)

        # 7. Build local symbol table
        symbol_table = {}
        for imp in imports:
            symbol_table[imp] = "import"
        if enclosing_class_name:
            symbol_table[enclosing_class_name] = "enclosing_class"
        for aux in auxiliary:
            symbol_table[aux["name"]] = aux["type"]

        target_source = ast.unparse(target_node)
        if len(target_source) > self.max_body_chars:
            target_source = target_source[:self.max_body_chars] + "\n    # ... [truncated to fit context budget]"

        return TargetScopeInfo(
            target_name=target_name,
            target_type=target_type,
            source_code=target_source,
            signature=sig,
            body_lines=body_lines,
            docstring=docstring,
            enclosing_class=enclosing_class_name,
            auxiliary_functions=auxiliary,
            imports=imports,
            symbol_table=symbol_table
        )

    def extract_from_file(self, file_path: Path, target_name: str) -> TargetScopeInfo:
        """Reads file from disk and extracts scoped context."""
        code = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return self.extract_from_source(code, target_name)
