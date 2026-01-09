"""
Fixer Agent - Applies refactoring fixes to code based on identified issues using LangChain.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.schema import BaseOutputParser
from src.agents.base_agent import BaseAgent
from src.prompts.fixer_prompt import get_fixer_prompt
from src.utils.logger import ActionType, log_experiment


class FixOutputParser(BaseOutputParser):
    """Custom parser to extract fix JSON from LLM responses."""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse JSON fix from LLM response, handling markdown code blocks."""
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                json_str = text[json_start:json_end].strip()
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                json_str = text[json_start:json_end].strip()
            else:
                json_str = text.strip()
            
            result = json.loads(json_str)
            
            # Normalize to always return a list of fixes
            if "fixes" in result:
                fixes = result["fixes"]
            elif "file" in result:
                # Single fix object
                fixes = [result]
            else:
                fixes = []
            
            return {
                "fixes": fixes,
                "raw_response": text
            }
            
        except json.JSONDecodeError as e:
            return {
                "fixes": [],
                "error": f"Failed to parse LLM response: {str(e)}",
                "raw_response": text[:500]
            }


class FixerAgent(BaseAgent):
    """
    Agent responsible for applying refactoring fixes to code using LangChain.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize the Fixer Agent with LangChain components.
        
        Args:
            model_name: Gemini model to use for fixing
        """
        super().__init__(agent_name="FixerAgent", model_name=model_name)
        
        # Initialize LangChain LLM
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1,  # Very low temperature for consistent, precise fixes
            convert_system_message_to_human=True
        )
        
        # Initialize output parser
        self.output_parser = FixOutputParser()
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.get_system_prompt()),
            HumanMessagePromptTemplate.from_template(
                "Please fix the following issue:\n\n"
                "File: {file_path}\n"
                "Issue: {issue_description}\n"
                "Severity: {severity}\n"
                "Category: {category}\n"
                "Recommendation: {recommendation}\n\n"
                "Current Code (lines {line_start}-{line_end}):\n"
                "```\n{code_content}\n```\n\n"
                "Provide your fix in the specified JSON format."
            )
        ])
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for the fixer agent."""
        return get_fixer_prompt()
    
    def fix_issue(self, issue: Dict[str, Any], target_dir: str) -> Dict[str, Any]:
        """
        Apply a fix for a specific issue.
        
        Args:
            issue: Issue dictionary containing file, description, recommendation, etc.
            target_dir: Base directory path
            
        Returns:
            Dictionary containing fix result
        """
        file_path = issue.get("file", "")
        if not file_path:
            return {
                "status": "ERROR",
                "message": "No file path provided in issue"
            }
        
        # Make file path absolute if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(target_dir, file_path)
        
        if not os.path.exists(file_path):
            return {
                "status": "ERROR",
                "message": f"File not found: {file_path}"
            }
        
        # Read the file content
        try:
            code_content = self._read_file_section(
                file_path,
                issue.get("line_start"),
                issue.get("line_end")
            )
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Failed to read file: {str(e)}"
            }
        
        # Generate fix using LLM
        fix_result = self._generate_fix(issue, file_path, code_content)
        
        return fix_result
    
    def fix_issues(self, issues: List[Dict[str, Any]], target_dir: str) -> Dict[str, Any]:
        """
        Apply fixes for multiple issues.
        
        Args:
            issues: List of issue dictionaries
            target_dir: Base directory path
            
        Returns:
            Dictionary containing results for all fixes
        """
        results = []
        successful_fixes = 0
        failed_fixes = 0
        
        for issue in issues:
            fix_result = self.fix_issue(issue, target_dir)
            results.append({
                "issue": issue,
                "fix_result": fix_result
            })
            
            if fix_result.get("status") == "SUCCESS":
                successful_fixes += 1
            else:
                failed_fixes += 1
        
        return {
            "status": "COMPLETED",
            "total_issues": len(issues),
            "successful_fixes": successful_fixes,
            "failed_fixes": failed_fixes,
            "results": results
        }
    
    def apply_fix(self, fix: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply a fix to the actual file.
        
        Args:
            fix: Fix dictionary containing file, original_code, fixed_code
            dry_run: If True, don't actually modify the file
            
        Returns:
            Result of applying the fix
        """
        file_path = fix.get("file")
        original_code = fix.get("original_code")
        fixed_code = fix.get("fixed_code")
        
        if not all([file_path, original_code is not None, fixed_code is not None]):
            return {
                "status": "ERROR",
                "message": "Missing required fields: file, original_code, or fixed_code"
            }
        
        if not os.path.exists(file_path):
            return {
                "status": "ERROR",
                "message": f"File not found: {file_path}"
            }
        
        try:
            # Read the current file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verify the original code exists in the file
            if original_code not in content:
                return {
                    "status": "ERROR",
                    "message": "Original code not found in file - code may have changed"
                }
            
            if dry_run:
                return {
                    "status": "DRY_RUN",
                    "message": "Fix validated but not applied (dry run mode)",
                    "file": file_path,
                    "fix": fix
                }
            
            # Apply the fix
            new_content = content.replace(original_code, fixed_code, 1)
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Log the fix
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file": file_path,
                    "explanation": fix.get("explanation", ""),
                    "confidence": fix.get("confidence", "unknown")
                },
                status="SUCCESS"
            )
            
            return {
                "status": "SUCCESS",
                "message": "Fix applied successfully",
                "file": file_path
            }
            
        except Exception as e:
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file": file_path,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                status="FAILURE"
            )
            
            return {
                "status": "ERROR",
                "message": f"Failed to apply fix: {str(e)}"
            }
    
    def _read_file_section(self, file_path: str, line_start: Optional[int], line_end: Optional[int]) -> str:
        """
        Read a specific section of a file.
        
        Args:
            file_path: Path to the file
            line_start: Starting line number (1-indexed)
            line_end: Ending line number (1-indexed)
            
        Returns:
            File content or section
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if line_start is None or line_end is None:
            # Return entire file if no line range specified
            return ''.join(lines)
        
        # Adjust for 0-indexing
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)
        
        return ''.join(lines[start_idx:end_idx])
    
    def _generate_fix(self, issue: Dict[str, Any], file_path: str, code_content: str) -> Dict[str, Any]:
        """
        Generate a fix for the issue using LangChain LLM.
        
        Args:
            issue: Issue dictionary
            file_path: Path to the file
            code_content: Content of the code section
            
        Returns:
            Fix result dictionary
        """
        try:
            # Create the prompt using LangChain template
            messages = self.prompt_template.format_messages(
                file_path=file_path,
                issue_description=issue.get("description", ""),
                severity=issue.get("severity", "unknown"),
                category=issue.get("category", "unknown"),
                recommendation=issue.get("recommendation", ""),
                line_start=issue.get("line_start", "N/A"),
                line_end=issue.get("line_end", "N/A"),
                code_content=code_content
            )
            
            # Log the fix attempt
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file": file_path,
                    "issue": issue.get("description", ""),
                    "input_prompt": str(messages)
                },
                status="STARTED"
            )
            
            # Invoke LangChain LLM
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # Parse the response using custom parser
            fix_result = self.output_parser.parse(response_text)
            
            if not fix_result.get("fixes"):
                log_experiment(
                    agent_name=self.agent_name,
                    model_used=self.model_name,
                    action=ActionType.FIX,
                    details={
                        "file": file_path,
                        "error": "No fixes generated",
                        "response": response_text[:500]
                    },
                    status="FAILURE"
                )
                
                return {
                    "status": "ERROR",
                    "message": "No fixes generated by LLM",
                    "raw_response": response_text
                }
            
            # Log success
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file": file_path,
                    "fixes_generated": len(fix_result["fixes"]),
                    "output_response": response_text
                },
                status="SUCCESS"
            )
            
            return {
                "status": "SUCCESS",
                "fixes": fix_result["fixes"],
                "raw_response": response_text
            }
            
        except Exception as e:
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file": file_path,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                status="FAILURE"
            )
            
            return {
                "status": "ERROR",
                "message": f"Fix generation failed: {str(e)}",
                "error": str(e)
            }
