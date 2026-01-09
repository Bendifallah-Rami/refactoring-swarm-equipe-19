"""File Tools for Toolsmith.

Minimal API expected by the TP:
- `read_file`, `write_file`, `list_python_files`
- strict sandbox path restriction
- logging via `log_experiment`
"""

import os
from pathlib import Path
from typing import List

from src.utils.logger import ActionType, log_experiment


class SecurityError(Exception):
    """Raised when a file operation violates sandbox restrictions"""
    pass


def is_safe_path(file_path: str, sandbox_dir: str = "./sandbox") -> bool:
    """
    Verify that a file path is within the sandbox directory.
    
    Args:
        file_path: Path to check
        sandbox_dir: Sandbox root directory
        
    Returns:
        True if path is safe
        
    Raises:
        SecurityError: If path is outside sandbox
    """
    try:
        abs_path = os.path.abspath(file_path)
        abs_sandbox = os.path.abspath(sandbox_dir)
        
        if not abs_path.startswith(abs_sandbox):
            raise SecurityError(
                f"❌ SECURITY VIOLATION: Path '{file_path}' is outside sandbox! "
                f"Only paths within '{abs_sandbox}' are allowed."
            )
        return True
    except Exception as e:
        if isinstance(e, SecurityError):
            raise
        raise SecurityError(f"Path validation error: {str(e)}")


def read_file(file_path: str, sandbox_dir: str = "./sandbox") -> str:
    """
    Read a Python file safely from sandbox.
    
    Args:
        file_path: Path to file
        sandbox_dir: Sandbox root directory
        
    Returns:
        File content as string
        
    Raises:
        SecurityError: If path is outside sandbox
        FileNotFoundError: If file doesn't exist
    """
    is_safe_path(file_path, sandbox_dir)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    log_experiment(
        agent_name="Toolsmith",
        model_used="file_tools",
        action=ActionType.ANALYSIS,
        details={
            "operation": "read_file",
            "file_path": file_path,
            "input_prompt": f"Read file: {file_path}",
            "output_response": f"Successfully read {len(content)} characters",
            "file_size": len(content)
        },
        status="SUCCESS"
    )
    
    return content


def write_file(file_path: str, content: str, sandbox_dir: str = "./sandbox") -> bool:
    """
    Write content to a Python file safely in sandbox.
    
    Args:
        file_path: Path to file
        content: Content to write
        sandbox_dir: Sandbox root directory
        
    Returns:
        True if successful
        
    Raises:
        SecurityError: If path is outside sandbox
    """
    is_safe_path(file_path, sandbox_dir)
    
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        log_experiment(
            agent_name="Toolsmith",
            model_used="file_tools",
            action=ActionType.FIX,
            details={
                "operation": "write_file",
                "file_path": file_path,
                "input_prompt": f"Write file: {file_path}",
                "output_response": f"Successfully wrote {len(content)} characters",
                "bytes_written": len(content)
            },
            status="SUCCESS"
        )
        
        return True
    except Exception as e:
        log_experiment(
            agent_name="Toolsmith",
            model_used="file_tools",
            action=ActionType.DEBUG,
            details={
                "operation": "write_file",
                "file_path": file_path,
                "input_prompt": f"Write file: {file_path}",
                "output_response": f"Error: {str(e)}",
                "error": str(e)
            },
            status="FAILURE"
        )
        raise


def list_python_files(directory: str, sandbox_dir: str = "./sandbox") -> List[str]:
    """
    List all Python files in a directory within sandbox.
    
    Args:
        directory: Directory to list
        sandbox_dir: Sandbox root directory
    Returns:
        List of file paths
        
    Raises:
        SecurityError: If path is outside sandbox
    """
    is_safe_path(directory, sandbox_dir)
    
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Not a directory: {directory}")
    
    files = [str(p) for p in Path(directory).rglob("*.py")]
    
    log_experiment(
        agent_name="Toolsmith",
        model_used="file_tools",
        action=ActionType.ANALYSIS,
        details={
            "operation": "list_python_files",
            "directory": directory,
            "input_prompt": f"List files in: {directory}",
            "output_response": f"Found {len(files)} Python files",
            "file_count": len(files)
        },
        status="SUCCESS"
    )
    
    return files



