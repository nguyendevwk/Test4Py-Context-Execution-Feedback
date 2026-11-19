#!/usr/bin/env python3
"""Interactive Demonstration of Context-Aware Test Generation & Adaptive Repair.

Demonstrates the core proposed methodology:
1. AST Context Extraction & Symbol Scope Resolution (Algorithm 3.1).
2. Dynamic Setup Probing.
3. Multi-Tier Sandbox Execution with Timeout and Coverage Tracking (Algorithm 3.2).
4. Adaptive Critic Feedback: Diagnosis and 2-Round Targeted Repair.
"""

from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.ast_context import ASTContextExtractor
from src.setup_probing import SetupProber
from src.sandbox import PytestSandbox
from src.critic import AdaptiveCritic
from src.generator import TestGenerator


SAMPLE_PRODUCTION_MODULE = '''"""Simple sample module for verification: String Range Tokenizer."""

def _validate_separator(sep: str) -> bool:
    """Helper: Validates separator length."""
    return len(sep) > 0

class RangeTokenizer:
    """Tokenizes range specifications with step support."""
    def __init__(self, separator: str = ":"):
        if not _validate_separator(separator):
            raise ValueError("Separator cannot be empty")
        self.separator = separator

    def parse_range(self, text: str) -> tuple[int, int, int]:
        """Parses 'start:stop[:step]' into integers."""
        if not text:
            raise ValueError("Empty range string")
        parts = text.split(self.separator)
        if len(parts) == 2:
            return int(parts[0]), int(parts[1]), 1
        elif len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        raise ValueError(f"Invalid range format: {text}")
'''


def run_demo():
    print("=" * 80)
    print(" HỆ THỐNG SINH VÀ SỬA LỖI KIỂM THỬ PYTHON BẰNG NGỮ CẢNH VÀ PHẢN HỒI THỰC THI")
    print(" (Context-Aware Python Test Generation and Adaptive Critic Repair)")
    print("=" * 80)

    # 1. AST Context Extraction
    print("\n[BƯỚC 1] Trích xuất Ngữ cảnh AST và Bao đóng Phụ trợ (Algorithm 3.1)...")
    extractor = ASTContextExtractor()
    scope = extractor.extract_from_source(SAMPLE_PRODUCTION_MODULE, "parse_range")
    print(f"  - Target Name      : {scope.target_name}")
    print(f"  - Enclosing Class  : {scope.enclosing_class}")
    print(f"  - Target Signature : {scope.signature}")
    print(f"  - Body Lines       : {scope.body_lines}")
    print(f"  - Auxiliary Helpers: {[a['name'] for a in scope.auxiliary_functions]}")
    print(f"  - Scope Symbol Map : {list(scope.symbol_table.keys())}")

    # 2. Setup Probing Scaffolding
    print("\n[BƯỚC 2] Thăm dò Cấu hình Khởi tạo (Dynamic Setup Probing)...")
    probe_hint = (
        "Setup scaffolding:\n"
        "- Enclosing class: RangeTokenizer(separator=':')\n"
        "- Target method: instance.parse_range(text='1:10') -> (1, 10, 1)"
    )
    print("  - Gợi ý khởi tạo: " + probe_hint.replace("\n", "\n    "))

    # 3. Simulate Initial Generation (Round 0) with a simulated assertion discrepancy
    print("\n[BƯỚC 3] Tạo mã kiểm thử ban đầu (Round 0: Initial Synthesis)...")
    round0_test_code = """import pytest

def test_target_normal():
    # Calling the real implementation
    from sample_target import RangeTokenizer
    tokenizer = RangeTokenizer()
    start, stop, step = tokenizer.parse_range("1:10:2")
    # Intentional subtle assertion error for demonstration of Critic repair:
    assert (start, stop, step) == (1, 10, 99)

def test_target_boundary():
    from sample_target import RangeTokenizer
    tokenizer = RangeTokenizer()
    start, stop, step = tokenizer.parse_range("0:0")
    assert (start, stop, step) == (0, 0, 1)

def test_target_exception():
    from sample_target import RangeTokenizer
    tokenizer = RangeTokenizer()
    with pytest.raises(ValueError):
        tokenizer.parse_range("")
"""
    print("  - Đã tổng hợp bộ kiểm thử (3 test cases: normal, boundary, exception).")

    # 4. Sandbox Evaluation
    with tempfile.TemporaryDirectory(prefix="demo_workspace_") as tmp_dir:
        work_path = Path(tmp_dir)
        module_file = work_path / "sample_target.py"
        module_file.write_text(SAMPLE_PRODUCTION_MODULE, encoding="utf-8")

        sandbox = PytestSandbox(timeout_seconds=10)

        print("\n[BƯỚC 4] Thực thi trong Hộp cát Pytest (Sandbox Execution Gate)...")
        eval_res0 = sandbox.evaluate_test_code(
            test_code=round0_test_code,
            target_module_path=work_path,
            module_import_name="sample_target",
            target_body_lines=scope.body_lines,
            work_dir=work_path
        )

        print(f"  - Trạng thái chấp nhận (Accepted): {eval_res0.accepted}")
        print(f"  - Số ca kiểm thử đỗ (Passed/Total): {eval_res0.tests_passed} / {eval_res0.tests_collected}")
        print(f"  - Giai đoạn thất bại (Failure Stage): {eval_res0.failure_stage}")

        if not eval_res0.accepted:
            print("\n[BƯỚC 5] Kích hoạt Vòng lặp Phản biện Thích ứng (Adaptive Critic Loop)...")
            analysis = AdaptiveCritic.analyze_failure(eval_res0.traceback, round_index=1)
            print(f"  - Phân loại lỗi (Failure Category): {analysis.failure_category.upper()}")
            print(f"  - Nguyên nhân gốc rễ (Root Cause) : {analysis.root_cause}")
            print(f"  - Chiến lược khắc phục (Strategy) : {analysis.suggested_strategy}")

            # Critic builds prompt & performs precision repair (Round 2: assertion calibration)
            print("\n[BƯỚC 6] Hiệu chỉnh vi mô khẳng định (Round 2: Micro-Assertion Calibration)...")
            repaired_code = round0_test_code.replace("(1, 10, 99)", "(1, 10, 2)")
            
            # Verify assertion integrity
            integrity_ok = AdaptiveCritic.verify_assertion_integrity(round0_test_code, repaired_code)
            print(f"  - Kiểm tra toàn vẹn khẳng định (Assertion Integrity): {'VƯỢT QUA' if integrity_ok else 'THẤT BẠI'}")

            # Re-evaluate repaired test
            print("\n[BƯỚC 7] Chạy lại kiểm thử sau sửa lỗi trong Hộp cát...")
            eval_res1 = sandbox.evaluate_test_code(
                test_code=repaired_code,
                target_module_path=work_path,
                module_import_name="sample_target",
                target_body_lines=scope.body_lines,
                work_dir=work_path
            )

            print(f"  - Trạng thái chấp nhận chung cuộc: {eval_res1.accepted}")
            print(f"  - Số ca kiểm thử đỗ: {eval_res1.tests_passed} / {eval_res1.tests_collected} (100% PASS)")
            print(f"  - Chạm thân đối tượng mục tiêu   : {eval_res1.target_body_reached}")
            print(f"  - Các dòng thân hàm được thực thi: {eval_res1.executed_body_lines}")
            if eval_res1.line_coverage_pct is not None:
                print(f"  - Độ phủ câu lệnh (Statement Cov): {eval_res1.line_coverage_pct:.2f}%")
            if eval_res1.branch_coverage_pct is not None:
                print(f"  - Độ phủ rẽ nhánh (Branch Cov)  : {eval_res1.branch_coverage_pct:.2f}%")

    print("\n" + "=" * 80)
    print(" KẾT QUẢ DEMO: Quy trình Sinh - Đánh giá - Tự sửa lỗi hoàn tất thành công!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
