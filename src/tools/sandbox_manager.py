"""
Sandbox Manager - Security layer for file operations
Ensures all file operations are restricted to the sandbox directory.
"""

import os


class SecurityError(Exception):
    """Raised when a file operation violates sandbox restrictions"""
    pass


def is_path_in_sandbox(path: str, sandbox_dir: str = "./sandbox") -> bool:
    """
    Check if path is strictly inside sandbox.
    
    Args:
        path: Path to check
        sandbox_dir: Sandbox root directory
        
    Returns:
        True if path is inside sandbox, False otherwise
        
    Raises:
        SecurityError: If path is outside sandbox
    """
    # Resolve symlinks and normalize paths to prevent bypass attempts
    abs_path = os.path.normpath(os.path.abspath(os.path.realpath(path)))
    abs_sandbox = os.path.normpath(os.path.abspath(os.path.realpath(sandbox_dir)))
    
    # Add separator to prevent false positives (e.g., /sandbox vs /sandbox_evil)
    if not (abs_path.startswith(abs_sandbox + os.sep) or abs_path == abs_sandbox):
        raise SecurityError(
            f"❌ SECURITY VIOLATION: Path '{path}' is outside sandbox! "
            f"Only paths within '{abs_sandbox}' are allowed."
        )
    return True
