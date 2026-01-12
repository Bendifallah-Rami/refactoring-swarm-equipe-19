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
    abs_path = os.path.abspath(path)
    abs_sandbox = os.path.abspath(sandbox_dir)
    
    if not abs_path.startswith(abs_sandbox):
        raise SecurityError(
            f"❌ SECURITY VIOLATION: Path '{path}' is outside sandbox! "
            f"Only paths within '{abs_sandbox}' are allowed."
        )
    return True
