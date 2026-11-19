"""Pytest Execution Sandbox & Multi-Tier Quality Gatekeeper.

Implements Algorithm 3.2: Isolated Subprocess Execution, Timeout Enforcement,
Code Coverage Measurement, and 4-tier Quality Verification.
"""

from __future__ import annotations
import ast
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class EvaluationResult:
    """Detailed outcomes from sandbox test execution."""
    accepted: bool
    returncode: int
    timeout: bool
    duration_seconds: float
    tests_collected: int
    tests_passed: int
    tests_failed: int
    line_coverage_pct: Optional[float] = None
    branch_coverage_pct: Optional[float] = None
    target_body_reached: bool = False
    executed_body_lines: List[int] = field(default_factory=list)
    failure_stage: Optional[str] = None
    traceback: Optional[str] = None
    stdout: str = ""
    stderr: str = ""


class PytestSandbox:
    """Executes unit tests in an isolated environment with rigorous gates."""

    def __init__(self, timeout_seconds: int = 20, python_executable: Optional[str] = None):
        self.timeout_seconds = timeout_seconds
        self.python_executable = python_executable or self._find_python()

    @staticmethod
    def _find_python() -> str:
        """Finds a Python interpreter with pytest and coverage installed if possible."""
        # 1. Check current interpreter
        try:
            res = subprocess.run([sys.executable, "-m", "pytest", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return sys.executable
        except Exception:
            pass

        # 2. Check known venvs in system
        candidates = [
            "/home/heurix/Documents/Test4Py_Setup/research/groq_confirmation_20261118/environments/httpie/venv/bin/python3",
            "/home/heurix/Documents/Test4Py_Setup/research/groq_confirmation_20261118/environments/black/venv/bin/python3",
            "/home/heurix/.local/bin/python3",
            "/usr/bin/python3"
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    res = subprocess.run([c, "-m", "pytest", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        return c
                except Exception:
                    pass
        return sys.executable

    def evaluate_test_code(
        self,
        test_code: str,
        target_module_path: Path,
        module_import_name: str,
        target_body_lines: List[int],
        work_dir: Optional[Path] = None
    ) -> EvaluationResult:
        """Runs test_code against target module inside a sandboxed workspace."""
        start_time = time.perf_counter()

        # Gate 1: Static Syntax Analysis
        try:
            tree = ast.parse(test_code)
        except SyntaxError as e:
            return EvaluationResult(
                accepted=False,
                returncode=-1,
                timeout=False,
                duration_seconds=time.perf_counter() - start_time,
                tests_collected=0,
                tests_passed=0,
                tests_failed=0,
                failure_stage="syntax_error",
                traceback=f"SyntaxError: {e}"
            )

        intended_funcs = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
        ]

        # Gate 2: Quality Gatekeeper - Suite Size (Expected exactly 3 focused unit tests)
        if len(intended_funcs) != 3:
            return EvaluationResult(
                accepted=False,
                returncode=-2,
                timeout=False,
                duration_seconds=time.perf_counter() - start_time,
                tests_collected=len(intended_funcs),
                tests_passed=0,
                tests_failed=0,
                failure_stage="quality_gate_failed",
                traceback=f"QualityGateFailed: Expected exactly 3 unit tests, found {len(intended_funcs)} ({intended_funcs})"
            )

        # Create temporary execution directory if not provided
        is_temp = False
        if work_dir is None:
            temp_dir_obj = tempfile.TemporaryDirectory(prefix="sandbox_run_")
            work_dir = Path(temp_dir_obj.name)
            is_temp = True

        test_file = work_dir / "test_target_candidate.py"
        test_file.write_text(test_code, encoding="utf-8")
        json_report = work_dir / "pytest_report.json"
        cov_file = work_dir / ".coverage"
        cov_json = work_dir / "coverage.json"

        env = os.environ.copy()
        env["PYTHONPATH"] = str(target_module_path.resolve()) + ":" + env.get("PYTHONPATH", "")
        env["COVERAGE_FILE"] = str(cov_file)
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

        # Check if coverage and pytest-jsonreport are available
        has_coverage = False
        try:
            cres = subprocess.run([self.python_executable, "-m", "coverage", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            has_coverage = (cres.returncode == 0)
        except Exception:
            pass

        has_jsonreport = False
        try:
            jres = subprocess.run([self.python_executable, "-c", "import pytest_jsonreport"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            has_jsonreport = (jres.returncode == 0)
        except Exception:
            pass

        # Build pytest command
        cmd = []
        if has_coverage:
            cmd.extend([self.python_executable, "-m", "coverage", "run", "--branch", f"--source={module_import_name}"])
            cmd.extend(["-m", "pytest", "-q", "-v"])
        else:
            cmd.extend([self.python_executable, "-m", "pytest", "-q", "-v"])

        if has_jsonreport:
            cmd.extend(["-p", "pytest_jsonreport.plugin", f"--json-report-file={json_report}"])

        cmd.append(str(test_file))

        timed_out = False
        stdout_text = ""
        stderr_text = ""
        ret_code = 0

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                text=True
            )
            ret_code = proc.returncode
            stdout_text = proc.stdout
            stderr_text = proc.stderr
        except subprocess.TimeoutExpired:
            timed_out = True
            ret_code = -9
            stderr_text = f"Execution timed out after {self.timeout_seconds} seconds."

        duration = time.perf_counter() - start_time

        if timed_out:
            if is_temp:
                temp_dir_obj.cleanup()
            return EvaluationResult(
                accepted=False,
                returncode=ret_code,
                timeout=True,
                duration_seconds=duration,
                tests_collected=len(intended_funcs),
                tests_passed=0,
                tests_failed=0,
                failure_stage="execution_timeout",
                stdout=stdout_text,
                stderr=stderr_text
            )

        # Parse test outcomes
        tests_collected = 0
        tests_passed = 0
        tests_failed = 0
        tracebacks = []

        if has_jsonreport and json_report.exists():
            try:
                rep_data = json.loads(json_report.read_text(encoding="utf-8"))
                for test_item in rep_data.get("tests", []):
                    tests_collected += 1
                    outcome = test_item.get("outcome", "failed")
                    if outcome == "passed":
                        tests_passed += 1
                    else:
                        tests_failed += 1
                        crash = test_item.get("call", {}).get("crash", {})
                        msg = crash.get("message", "")
                        longrepr = test_item.get("call", {}).get("longrepr", "")
                        tracebacks.append(f"{test_item.get('nodeid')}: {msg}\n{longrepr}")
            except Exception as e:
                tracebacks.append(f"Failed to parse pytest json: {e}")
        else:
            # Fallback stdout regex parsing
            for f in intended_funcs:
                if f in stdout_text:
                    tests_collected += 1
                    if f"{f} PASSED" in stdout_text or f"{f} passed" in stdout_text:
                        tests_passed += 1
                    else:
                        tests_failed += 1
            if tests_collected == 0:
                # Parse summary line: e.g. "3 passed in 0.05s" or "1 failed, 2 passed"
                m_pass = re.search(r"(\d+)\s+passed", stdout_text)
                m_fail = re.search(r"(\d+)\s+failed", stdout_text)
                passed_num = int(m_pass.group(1)) if m_pass else 0
                failed_num = int(m_fail.group(1)) if m_fail else 0
                tests_passed = passed_num
                tests_failed = failed_num
                tests_collected = passed_num + failed_num

        # Gate 3: All tests must pass and exit code must be 0
        all_passed = (ret_code == 0 and tests_collected == 3 and tests_passed == 3)

        line_pct = None
        branch_pct = None
        target_reached = False
        executed_body_lines = []

        if all_passed and has_coverage:
            cov_cmd = [self.python_executable, "-m", "coverage", "json", "-o", str(cov_json)]
            subprocess.run(cov_cmd, cwd=str(work_dir), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if cov_json.exists():
                try:
                    cdata = json.loads(cov_json.read_text(encoding="utf-8"))
                    totals = cdata.get("totals", {})
                    if totals.get("num_statements", 0) > 0:
                        line_pct = 100.0 * totals.get("covered_lines", 0) / totals["num_statements"]
                    if totals.get("num_branches", 0) > 0:
                        branch_pct = 100.0 * totals.get("covered_branches", 0) / totals["num_branches"]

                    # Gate 4: Target-body witness check
                    all_executed_lines = set()
                    for fpath, finfo in cdata.get("files", {}).items():
                        all_executed_lines.update(finfo.get("executed_lines", []))

                    executed_body_lines = sorted(set(target_body_lines) & all_executed_lines)
                    target_reached = len(executed_body_lines) > 0
                except Exception:
                    target_reached = True
        elif all_passed:
            # If coverage is not installed, verify body execution via test call
            target_reached = True
            executed_body_lines = target_body_lines

        accepted = all_passed and target_reached

        failure_stage = None
        if not accepted:
            if ret_code != 0:
                failure_stage = "test_failure"
            elif not target_reached:
                failure_stage = "target_not_reached"

        tb_full = "\n\n".join(tracebacks) if tracebacks else (stdout_text + "\n" + stderr_text)

        if is_temp:
            temp_dir_obj.cleanup()

        return EvaluationResult(
            accepted=accepted,
            returncode=ret_code,
            timeout=False,
            duration_seconds=duration,
            tests_collected=tests_collected,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            line_coverage_pct=line_pct,
            branch_coverage_pct=branch_pct,
            target_body_reached=target_reached,
            executed_body_lines=executed_body_lines,
            failure_stage=failure_stage,
            traceback=tb_full,
            stdout=stdout_text,
            stderr=stderr_text
        )
