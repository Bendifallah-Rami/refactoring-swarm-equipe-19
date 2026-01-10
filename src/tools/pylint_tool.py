"""
Pylint Tool for Toolsmith
Static code analysis and quality scoring
"""
import subprocess
import json
import re
from typing import Dict, List, Optional
from src.utils.logger import log_experiment, ActionType
from src.tools.file_tools import is_safe_path, list_files


def run_pylint_analysis(file_path: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Run pylint analysis on a Python file.
    
    Args:
        file_path: Path to Python file
        sandbox_dir: Sandbox root directory
        
    Returns:
        Dictionary with analysis results:
        {
            "file": "path/to/file.py",
            "score": 8.5,
            "issues": [...],
            "warnings": [...],
            "errors": [...],
            "statement_count": int
        }
        
    Raises:
        SecurityError: If path is outside sandbox
    """
    is_safe_path(file_path, sandbox_dir)

    try:
        # Run pylint with JSON output for issues
        result_json = subprocess.run(
            ['pylint', '--output-format=json', file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse JSON output
        try:
            issues = json.loads(result_json.stdout)
        except json.JSONDecodeError:
            issues = []

        # Run pylint again with text output to get score
        result_text = subprocess.run(
            ['pylint', file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Extract score from text output
        score = extract_pylint_score(result_text.stdout + result_text.stderr)

        # Categorize issues
        errors = [i for i in issues if i.get('type') == 'error']
        warnings = [i for i in issues if i.get('type') == 'warning']

        analysis_result = {
            "file": file_path,
            "score": score,
            "total_issues": len(issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": issues[:20],  # Limit to first 20 issues
            "issues_detail": [
                {
                    "line": i.get('line'),
                    "column": i.get('column'),
                    "type": i.get('type'),
                    "symbol": i.get('symbol'),
                    "message": i.get('message')
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
    Extract pylint score from output.
    
    Pylint calcule le score comme suit:
    - Score de base = 10.0
    - Chaque erreur/warning/convention retire des points
    - Formule: 10.0 - (10.0 * nombre_issues / nombre_statements)
    - Le score est arrondi à 2 décimales
    
    Exemples:
    - 0 issues → 10.00/10
    - Beaucoup d'issues → peut descendre à 0.00/10 (voire négatif mais limité à 0)
    
    Args:
        output: Pylint output text
        
    Returns:
        Score between 0 and 10
    """
    # Look for pattern like "rated at 8.50/10" or "rated at 0.00/10"
    match = re.search(r'rated at ([-\d.]+)/10', output)
    if match:
        try:
            score = float(match.group(1))
            # Pylint peut donner des scores négatifs, on les limite à 0
            return max(0.0, score)
        except ValueError:
            pass

    # Default score if not found (should rarely happen)
    return 0.0


def get_directory_quality_score(directory: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Analyze all Python files in a directory and get overall quality score.
    
    Args:
        directory: Directory to analyze
        sandbox_dir: Sandbox root directory
        
    Returns:
        Dictionary with directory analysis:
        {
            "directory": "path",
            "average_score": 7.5,
            "file_count": 3,
            "total_issues": 15,
            "files": [...]
        }
    """
    is_safe_path(directory, sandbox_dir)

    files = list_files(directory, sandbox_dir)

    if not files:
        return {
            "directory": directory,
            "average_score": 10.0,
            "file_count": 0,
            "total_issues": 0,
            "files": []
        }

    file_analyses = []
    total_score = 0
    total_issues = 0

    for file_path in files:
        analysis = run_pylint_analysis(file_path, sandbox_dir)
        file_analyses.append({
            "file": file_path,
            "score": analysis.get("score", 0),
            "issues": analysis.get("total_issues", 0)
        })
        total_score += analysis.get("score", 0)
        total_issues += analysis.get("total_issues", 0)

    average_score = total_score / len(files) if files else 0

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
    
    Args:
        file_path: Path to Python file
        sandbox_dir: Sandbox root directory
        
    Returns:
        Dictionary with organized issues
    """
    analysis = run_pylint_analysis(file_path, sandbox_dir)

    issues_by_type = {}
    for issue in analysis.get("issues", []):
        issue_type = issue.get('type', 'unknown')
        if issue_type not in issues_by_type:
            issues_by_type[issue_type] = []
        issues_by_type[issue_type].append(issue)

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