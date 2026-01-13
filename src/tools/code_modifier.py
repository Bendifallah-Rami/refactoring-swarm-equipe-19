"""
Code Modifier Tool for Toolsmith
Apply code fixes and validate syntax
"""
import ast
import json
from typing import Dict

from src.utils.logger import log_experiment, ActionType
from src.tools.sandbox_manager import is_path_in_sandbox
from src.tools.file_tools import read_file, write_file


def validate_python_syntax(code: str) -> None:
    """
    Validate Python code syntax.
    """
    ast.parse(code)


def apply_fix(file_path: str, fixed_code: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Apply a code fix to a file.
    """
    is_path_in_sandbox(file_path, sandbox_dir)

    validate_python_syntax(fixed_code)

    original_content = read_file(file_path, sandbox_dir)
    write_file(file_path, fixed_code, sandbox_dir)

    result = {
        "file_path": file_path,
        "original_size": len(original_content),
        "new_size": len(fixed_code),
        "size_change": len(fixed_code) - len(original_content)
    }

    log_experiment(
        agent_name="Toolsmith",
        model_used="code_modifier",
        action=ActionType.FIX,
        details={
            "input_prompt": f"Apply fix to {file_path}",
            "output_response": json.dumps(result)
        },
        status="SUCCESS"
    )

    return result


def add_docstring(file_path: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Analyze missing docstrings.
    """
    is_path_in_sandbox(file_path, sandbox_dir)

    content = read_file(file_path, sandbox_dir)
    tree = ast.parse(content)

    missing = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        and not ast.get_docstring(node)
    )

    result = {
        "file_path": file_path,
        "missing_docstrings": missing
    }

    log_experiment(
        agent_name="Toolsmith",
        model_used="code_modifier",
        action=ActionType.ANALYSIS,
        details={
            "input_prompt": f"Check docstrings in {file_path}",
            "output_response": json.dumps(result)
        },
        status="SUCCESS"
    )

    return result


def get_code_metrics(file_path: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Compute basic code metrics.
    """
    is_path_in_sandbox(file_path, sandbox_dir)

    content = read_file(file_path, sandbox_dir)
    tree = ast.parse(content)

    has_main = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        for node in ast.walk(tree)
    )

    metrics = {
        "file_path": file_path,
        "lines_of_code": len(content.split("\n")),
        "functions": sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree)),
        "classes": sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree)),
        "has_main": has_main
    }

    log_experiment(
        agent_name="Toolsmith",
        model_used="code_modifier",
        action=ActionType.ANALYSIS,
        details={
            "input_prompt": f"Compute metrics for {file_path}",
            "output_response": json.dumps(metrics)
        },
        status="SUCCESS"
    )

    return metrics


def compare_files(file_path1: str, file_path2: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Compare two Python files.
    """
    is_path_in_sandbox(file_path1, sandbox_dir)
    is_path_in_sandbox(file_path2, sandbox_dir)

    content1 = read_file(file_path1, sandbox_dir)
    content2 = read_file(file_path2, sandbox_dir)

    result = {
        "file1": file_path1,
        "file2": file_path2,
        "identical": content1 == content2
    }

    log_experiment(
        agent_name="Toolsmith",
        model_used="code_modifier",
        action=ActionType.ANALYSIS,
        details={
            "input_prompt": f"Compare {file_path1} and {file_path2}",
            "output_response": json.dumps(result)
        },
        status="SUCCESS"
    )

    return result