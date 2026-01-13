"""
Pylint Tool for Toolsmith
Static code analysis and quality scoring
"""
import subprocess
import json
import re
from typing import Dict

from src.utils.logger import log_experiment, ActionType
from src.tools.file_tools import list_files
from src.tools.sandbox_manager import is_path_in_sandbox


def run_pylint_analysis(file_path: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Run pylint analysis on a Python file.
    """
    is_path_in_sandbox(file_path, sandbox_dir)

    try:
        # Run pylint with JSON output
        result_json = subprocess.run(
            ["pylint", "--output-format=json", file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        try:
            issues = json.loads(result_json.stdout)
        except json.JSONDecodeError:
            issues = []

        # Run pylint again to extract score
        result_text = subprocess.run(
            ["pylint", file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        score = extract_pylint_score(result_text.stdout + result_text.stderr)

        errors = [i for i in issues if i.get("type") == "error"]
        warnings = [i for i in issues if i.get("type") == "warning"]

        analysis_result = {
            "file": file_path,
            "score": score,
            "total_issues": len(issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": issues[:20],
            "issues_detail": [
                {
                    "line": i.get("line"),
                    "column": i.get("column"),
                    "type": i.get("type"),
                    "symbol": i.get("symbol"),
                    "message": i.get("message")
                }
                for i in issues[:10]
            ]
        }

        log_experiment(
            agent_name="Toolsmith",
            model_used="pylint",
            action=ActionType.ANALYSIS,
            details={
                "operation": "pylint_analysis",
                "file_path": file_path,
                "input_prompt": f"Analyze code quality: {file_path}",
                "output_response": json.dumps(analysis_result),
                "score": score,
                "total_issues": len(issues)
            },
            status="SUCCESS"
        )

        return analysis_result

    except subprocess.TimeoutExpired:
        log_experiment(
            agent_name="Toolsmith",
            model_used="pylint",
            action=ActionType.DEBUG,
            details={
                "operation": "pylint_analysis",
                "file_path": file_path,
                "input_prompt": f"Analyze code quality: {file_path}",
                "output_response": "Pylint analysis timed out",
                "error": "timeout"
            },
            status="FAILURE"
        )
        return {
            "file": file_path,
            "score": 0,
            "error": "Analysis timeout",
            "issues": []
        }

    except Exception as e:
        log_experiment(
            agent_name="Toolsmith",
            model_used="pylint",
            action=ActionType.DEBUG,
            details={
                "operation": "pylint_analysis",
                "file_path": file_path,
                "input_prompt": f"Analyze code quality: {file_path}",
                "output_response": f"Error: {str(e)}",
                "error": str(e)
            },
            status="FAILURE"
        )
        return {
            "file": file_path,
            "score": 0,
            "error": str(e),
            "issues": []
        }


def extract_pylint_score(output: str) -> float:
    """
    Extract pylint score from output text.
    """
    match = re.search(r"rated at ([-\d.]+)/10", output)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            pass
    return 0.0


def get_directory_quality_score(directory: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Analyze all Python files in a directory.
    """
    is_path_in_sandbox(directory, sandbox_dir)

    files = list_files(directory, sandbox_dir)

    if not files:
        return {
            "directory": directory,
            "average_score": 10.0,
            "file_count": 0,
            "total_issues": 0,
            "files": []
        }

    total_score = 0
    total_issues = 0
    file_analyses = []

    for file_path in files:
        analysis = run_pylint_analysis(file_path, sandbox_dir)

        file_analyses.append({
            "file": file_path,
            "score": analysis.get("score", 0),
            "issues": analysis.get("total_issues", 0)
        })

        total_score += analysis.get("score", 0)
        total_issues += analysis.get("total_issues", 0)

    average_score = total_score / len(files)

    result = {
        "directory": directory,
        "average_score": round(average_score, 2),
        "file_count": len(files),
        "total_issues": total_issues,
        "files": file_analyses
    }

    log_experiment(
        agent_name="Toolsmith",
        model_used="pylint",
        action=ActionType.ANALYSIS,
        details={
            "operation": "directory_quality_analysis",
            "directory": directory,
            "input_prompt": f"Analyze directory quality: {directory}",
            "output_response": json.dumps(result),
            "average_score": average_score,
            "file_count": len(files)
        },
        status="SUCCESS"
    )

    return result


def get_code_issues_summary(file_path: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Get a summary of code issues organized by type.
    """
    analysis = run_pylint_analysis(file_path, sandbox_dir)

    issues_by_type = {}
    for issue in analysis.get("issues", []):
        issue_type = issue.get("type", "unknown")
        issues_by_type.setdefault(issue_type, []).append(issue)

    return {
        "file": file_path,
        "score": analysis.get("score", 0),
        "issues_by_type": issues_by_type,
        "summary": {
            "total": analysis.get("total_issues", 0),
            "errors": analysis.get("errors", 0),
            "warnings": analysis.get("warnings", 0)
        }
    }
