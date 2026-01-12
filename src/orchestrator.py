"""
Orchestrator - Coordinates the multi-agent refactoring workflow using LangChain.

Day 6 Task 1: Execution graph - connects Auditor → Fixer → Judge workflow
Day 6 Task 2: Self-healing loop - iterates until approved or max iterations reached
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from src.agent_registry import get_registry
from src.utils.logger import log_experiment, ActionType

# Maximum iterations for self-healing loop
MAX_ITERATIONS = 10


class WorkflowState:
    """
    Maintains state as it flows through the agent workflow.
    Passes data between Auditor → Fixer → Judge with iteration tracking.
    """
    
    def __init__(self, file_path: str):
        """Initialize workflow state for a file."""
        self.file_path = file_path
        self.original_code: Optional[str] = None
        self.audit_result: Optional[Dict] = None
        self.fix_result: Optional[Dict] = None
        self.judgment: Optional[Dict] = None
        self.iteration: int = 0  # Track current iteration
        self.completed: bool = False  # Track if processing is complete
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for logging."""
        return {
            "file_path": self.file_path,
            "has_audit": self.audit_result is not None,
            "has_fixes": self.fix_result is not None,
            "has_judgment": self.judgment is not None,
            "iteration": self.iteration,
            "completed": self.completed
        }


class RefactoringOrchestrator:
    """
    Orchestrator that executes the workflow graph: Auditor → Fixer → Judge
    Uses LangChain agents connected in sequence with self-healing loop.
    Iterates up to MAX_ITERATIONS until Judge approves or gives up.
    """
    
    def __init__(self, target_dir: str):
        """
        Initialize orchestrator with target directory.
        
        Args:
            target_dir: Path to directory containing code to refactor
        """
        self.target_dir = Path(target_dir)
        self.registry = get_registry()
        self.results: Dict[str, WorkflowState] = {}
        
        # Initialize agents
        if not self.registry.is_initialized():
            self.registry.initialize()
        
        print(f"🔧 Orchestrator initialized for: {target_dir}")
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the workflow graph on all Python files.
        
        Returns:
            Summary of processing results
        """
        print(f"\n{'='*60}")
        print(f"🚀 STARTING REFACTORING SWARM")
        print(f"{'='*60}\n")
        
        # Find Python files
        python_files = list(self.target_dir.glob("*.py"))
        
        if not python_files:
            print(f"⚠️  No Python files found in {self.target_dir}")
            return {"files_processed": 0, "success": False}
        
        print(f"📁 Found {len(python_files)} Python file(s) to process\n")
        
        # Process each file through workflow graph
        for file_path in python_files:
            print(f"\n{'─'*60}")
            print(f"📄 Processing: {file_path.name}")
            print(f"{'─'*60}\n")
            
            self._execute_workflow(str(file_path))
        
        # Generate summary
        summary = self._generate_summary()
        
        print(f"\n{'='*60}")
        print(f"✅ WORKFLOW COMPLETE")
        print(f"{'='*60}\n")
        print(f"Files processed: {summary['files_processed']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        
        return summary
    
    def _execute_workflow(self, file_path: str) -> WorkflowState:
        """
        Execute workflow graph with self-healing loop: Auditor → Fixer → Judge
        Repeats until Judge approves or MAX_ITERATIONS reached.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            Workflow state with results
        """
        state = WorkflowState(file_path)
        
        # Read original code
        with open(file_path, 'r', encoding='utf-8') as f:
            state.original_code = f.read()
        
        # Get agents from registry
        auditor = self.registry.get_auditor()
        fixer = self.registry.get_fixer()
        judge = self.registry.get_judge()
        
        print(f"🔄 Starting self-healing loop (max {MAX_ITERATIONS} iterations)...")
        
        # Self-healing loop
        while state.iteration < MAX_ITERATIONS and not state.completed:
            state.iteration += 1
            print(f"\n  🔁 Iteration {state.iteration}/{MAX_ITERATIONS}")
            
            # Node 1: Auditor analyzes code
            print("    1️⃣ Auditor analyzing...")
            state.audit_result = self._run_auditor(auditor, file_path)
            
            if not state.audit_result or not state.audit_result.get("issues"):
                print("    ✅ No issues found!")
                state.completed = True
                break
            
            issues_count = len(state.audit_result.get("issues", []))
            print(f"    🔍 Found {issues_count} issue(s)")
            
            # Node 2: Fixer generates fixes
            print("    2️⃣ Fixer generating fixes...")
            state.fix_result = self._run_fixer(fixer, file_path, state.audit_result)
            
            if not state.fix_result or not state.fix_result.get("fixes"):
                print("    ⚠️  Fixer couldn't generate fixes - stopping")
                break
            
            fixes_count = len(state.fix_result.get("fixes", []))
            print(f"    🔧 Generated {fixes_count} fix(es)")
            
            # Node 3: Judge validates fixes
            print("    3️⃣ Judge evaluating...")
            state.judgment = self._run_judge(judge, file_path, state.audit_result, state.fix_result)
            
            verdict = state.judgment.get("verdict", "UNKNOWN")
            score = state.judgment.get("overall_score", 0)
            print(f"    📊 Verdict: {verdict} (Score: {score}/100)")
            
            # Check if approved - exit loop
            if verdict == "APPROVED":
                print(f"    ✅ APPROVED - Stopping at iteration {state.iteration}")
                state.completed = True
                break
            elif verdict == "REJECTED":
                print(f"    ❌ REJECTED - Stopping at iteration {state.iteration}")
                break
            else:  # NEEDS_REVISION
                if state.iteration < MAX_ITERATIONS:
                    print(f"    🔄 NEEDS_REVISION - Continuing to iteration {state.iteration + 1}")
                else:
                    print(f"    ⏱️  Max iterations reached - Stopping")
        
        # Save result
        self.results[file_path] = state
        
        # Log workflow execution
        log_experiment(
            agent_name="Orchestrator",
            model_used="N/A",
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": f"Self-healing workflow on: {file_path}",
                "output_response": f"Completed in {state.iteration} iteration(s), completed={state.completed}"
            }
        )
        
        return state
    
    def _run_auditor(self, auditor, file_path: str) -> Dict[str, Any]:
        """Execute Auditor agent."""
        try:
            # Auditor.analyze() expects a directory, so we pass the parent directory
            import os
            target_dir = os.path.dirname(file_path)
            result = auditor.analyze(target_dir)
            return result
        except Exception as e:
            print(f"    ❌ Auditor error: {str(e)}")
            return {"issues": [], "error": str(e)}
    
    def _run_fixer(self, fixer, file_path: str, audit_result: Dict) -> Dict[str, Any]:
        """Execute Fixer agent."""
        try:
            import os
            target_dir = os.path.dirname(file_path)
            issues = audit_result.get("issues", [])
            result = fixer.fix_issues(issues, target_dir)
            return result
        except Exception as e:
            print(f"    ❌ Fixer error: {str(e)}")
            return {"fixes": [], "error": str(e)}
    
    def _run_judge(self, judge, file_path: str, audit_result: Dict, fix_result: Dict) -> Dict[str, Any]:
        """Execute Judge agent."""
        try:
            import os
            target_dir = os.path.dirname(file_path)
            fixes = fix_result.get("fixes", [])
            issues = audit_result.get("issues", [])
            result = judge.evaluate_fixes(fixes, issues, target_dir)
            return result
        except Exception as e:
            print(f"    ❌ Judge error: {str(e)}")
            return {"verdict": "ERROR", "overall_score": 0, "error": str(e)}
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary of all processing results."""
        total = len(self.results)
        successful = sum(1 for state in self.results.values() 
                        if state.judgment and state.judgment.get("verdict") == "APPROVED")
        failed = total - successful
        
        return {
            "files_processed": total,
            "successful": successful,
            "failed": failed,
            "results": {
                path: state.to_dict() 
                for path, state in self.results.items()
            }
        }
    
    def get_results(self) -> Dict[str, WorkflowState]:
        """Get detailed results for all processed files."""
        return self.results
