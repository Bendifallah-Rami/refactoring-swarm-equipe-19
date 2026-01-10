"""
Pytest Tool for Toolsmith
Execute unit tests and provide test results
"""
import subprocess
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from src.utils.logger import log_experiment, ActionType
from src.tools.file_tools import is_safe_path


def run_pytest(directory: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Run pytest on a directory and return results.
    
    Args:
        directory: Directory containing tests
        sandbox_dir: Sandbox root directory
        
    Returns:
        Dictionary with test results:
        {
            "directory": "path",
            "passed": 5,
            "failed": 2,
            "skipped": 0,
            "total": 7,
            "success_rate": 71.4,
            "tests": [...],
            "error_log": "..."
        }
        
    Raises:
        SecurityError: If path is outside sandbox
    """
    is_safe_path(directory, sandbox_dir)

    try:
        # Run pytest with JSON report
        result = subprocess.run(
            ['pytest', directory, '--tb=short', '-v', '--no-header'],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Parse output
        output = result.stdout + result.stderr

        # Extract test statistics
        passed = len(re.findall(r'PASSED', output))
        failed = len(re.findall(r'FAILED', output))
        skipped = len(re.findall(r'SKIPPED', output))
        total = passed + failed + skipped

        success_rate = (passed / total * 100) if total > 0 else 0

        # Parse individual test results
        tests = parse_pytest_output(output)

        test_result = {
            "directory": directory,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "success_rate": round(success_rate, 2),
            "exit_code": result.returncode,
            "tests": tests,
            "error_log": output if failed > 0 else ""
        }

        status = "SUCCESS" if result.returncode == 0 else "FAILURE"

        log_experiment(
            agent_name="Toolsmith",
            model_used="pytest",
            action=ActionType.ANALYSIS,
            details={
                "operation": "pytest_run",
                "directory": directory,
                "input_prompt": f"Run tests: {directory}",
                "output_response": json.dumps(test_result),
                "passed": passed,
                "failed": failed,
                "total": total
            },
            status=status
        )

        return test_result

    except subprocess.TimeoutExpired:
        log_experiment(
            agent_name="Toolsmith",
            model_used="pytest",
            action=ActionType.DEBUG,
            details={
                "operation": "pytest_run",
                "directory": directory,
                "input_prompt": f"Run tests: {directory}",
                "output_response": "Pytest execution timed out",
                "error": "timeout"
            },
            status="FAILURE"
        )
        return {
            "directory": directory,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "success_rate": 0,
            "error": "Test execution timeout",
            "tests": []
        }
    except Exception as e:
        log_experiment(
            agent_name="Toolsmith",
            model_used="pytest",
            action=ActionType.DEBUG,
            details={
                "operation": "pytest_run",
                "directory": directory,
                "input_prompt": f"Run tests: {directory}",
                "output_response": f"Error: {str(e)}",
                "error": str(e)
            },
            status="FAILURE"
        )
        return {
            "directory": directory,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "success_rate": 0,
            "error": str(e),
            "tests": []
        }


def run_single_test(test_file: str, test_name: Optional[str] = None, 
                   sandbox_dir: str = "./sandbox") -> Dict:
    """
    Run a single test or specific test function.
    
    Args:
        test_file: Path to test file
        test_name: Optional specific test function name
        sandbox_dir: Sandbox root directory
        
    Returns:
        Dictionary with test result
    """
    is_safe_path(test_file, sandbox_dir)

    try:
        cmd = ['pytest', test_file, '-v', '--tb=short']

        if test_name:
            cmd.append(f'-k {test_name}')

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout + result.stderr

        # Parse result
        passed = len(re.findall(r'PASSED', output))
        failed = len(re.findall(r'FAILED', output))

        test_result = {
            "test_file": test_file,
            "test_name": test_name,
            "passed": passed,
            "failed": failed,
            "success": passed > 0 and failed == 0,
            "output": output
        }

        log_experiment(
            agent_name="Toolsmith",
            model_used="pytest",
            action=ActionType.ANALYSIS,
            details={
                "operation": "single_test_run",
                "test_file": test_file,
                "test_name": test_name,
                "input_prompt": f"Run test: {test_file}::{test_name}" if test_name else f"Run tests: {test_file}",
                "output_response": json.dumps(test_result),
                "passed": passed,
                "failed": failed
            },
            status="SUCCESS" if failed == 0 else "FAILURE"
        )

        return test_result

    except Exception as e:
        log_experiment(
            agent_name="Toolsmith",
            model_used="pytest",
            action=ActionType.DEBUG,
            details={
                "operation": "single_test_run",
                "test_file": test_file,
                "test_name": test_name,
                "input_prompt": f"Run test: {test_file}",
                "output_response": f"Error: {str(e)}",
                "error": str(e)
            },
            status="FAILURE"
        )
        return {
            "test_file": test_file,
            "test_name": test_name,
            "passed": 0,
            "failed": 1,
            "success": False,
            "error": str(e)
        }


def parse_pytest_output(output: str) -> List[Dict]:
    """
    Parse pytest output to extract individual test results.
    
    Args:
        output: Raw pytest output
        
    Returns:
        List of test result dictionaries
    """
    tests = []

    # Pattern to match test results
    pattern = r'(test_\w+.*?)\s+(PASSED|FAILED|SKIPPED)'

    for match in re.finditer(pattern, output):
        test_name = match.group(1).strip()
        status = match.group(2)

        tests.append({
            "name": test_name,
            "status": status
        })

    return tests


def get_test_coverage(directory: str, sandbox_dir: str = "./sandbox") -> Dict:
    """
    Run pytest with coverage analysis.
    
    Args:
        directory: Directory containing tests
        sandbox_dir: Sandbox root directory
        
    Returns:
        Dictionary with test and coverage results
    """
    is_safe_path(directory, sandbox_dir)

    try:
        # Try to run with coverage if installed
        result = subprocess.run(
            ['pytest', directory, '--cov', '--cov-report=json'],
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr

        # Fallback: just run regular pytest
        test_result = run_pytest(directory, sandbox_dir)

        return {
            **test_result,
            "coverage_available": '.coverage.json' in output
        }

    except Exception as e:
        return run_pytest(directory, sandbox_dir)


def get_failing_tests(directory: str, sandbox_dir: str = "./sandbox") -> List[Dict]:
    """
    Get list of failing tests with error details.
    
    Args:
        directory: Directory containing tests
        sandbox_dir: Sandbox root directory
        
    Returns:
        List of failing test details
    """
    result = run_pytest(directory, sandbox_dir)

    # Extract failed tests
    failing = [t for t in result.get("tests", []) if t.get("status") == "FAILED"]

    return {
        "failed_count": result.get("failed", 0),
        "failing_tests": failing,
        "error_log": result.get("error_log", "")
    }