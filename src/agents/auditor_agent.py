"""
Auditor Agent - Analyzes codebases to identify refactoring opportunities using LangChain.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema import BaseOutputParser
from src.agents.base_agent import BaseAgent
from src.prompts.auditor_prompt import get_auditor_prompt
from src.utils.logger import ActionType, log_experiment


class JSONOutputParser(BaseOutputParser):
    """Custom parser to extract JSON from LLM responses."""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
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
            
            # Validate and normalize required fields
            if "issues" not in result:
                result["issues"] = []
            if "summary" not in result:
                result["summary"] = {
                    "total_issues": len(result["issues"]),
                    "high_severity": len([i for i in result["issues"] if i.get("severity") == "high"]),
                    "medium_severity": len([i for i in result["issues"] if i.get("severity") == "medium"]),
                    "low_severity": len([i for i in result["issues"] if i.get("severity") == "low"])
                }
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                "issues": [{
                    "file": "N/A",
                    "severity": "low",
                    "category": "parsing_error",
                    "description": f"Failed to parse LLM response: {str(e)}",
                    "recommendation": "Review raw response",
                    "raw_response": text[:500]
                }],
                "summary": {
                    "total_issues": 1,
                    "high_severity": 0,
                    "medium_severity": 0,
                    "low_severity": 1
                }
            }


class AuditorAgent(BaseAgent):
    """
    Agent responsible for auditing codebases and identifying refactoring opportunities using LangChain.
    """
    
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Auditor Agent with LangChain components.
        
        Args:
            model_name: Gemini model to use for analysis
        """
        super().__init__(agent_name="AuditorAgent", model_name=model_name)
        self.supported_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.rb', '.go'}
        
        # Initialize LangChain LLM
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,  # Lower temperature for more consistent analysis
            convert_system_message_to_human=True
        )
        
        # Initialize output parser
        self.output_parser = JSONOutputParser()
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.get_system_prompt()),
            HumanMessagePromptTemplate.from_template(
                "Please analyze the following codebase and identify refactoring opportunities:\n\n{code_context}\n\n"
                "Provide your analysis in the specified JSON format."
            )
        ])
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for the auditor agent."""
        return get_auditor_prompt()
    
    def analyze(self, target_dir: str) -> Dict[str, Any]:
        """
        Analyze a target directory for code quality issues and refactoring opportunities.
        
        Args:
            target_dir: Path to the directory to analyze
            
        Returns:
            Dictionary containing analysis results with issues and summary
        """
        if not os.path.exists(target_dir):
            return {
                "status": "ERROR",
                "message": f"Directory not found: {target_dir}",
                "files": [],
                "issues": []
            }
        
        # Collect code files
        code_files = self._collect_code_files(target_dir)
        
        if not code_files:
            return {
                "status": "NO_FILES",
                "message": "No code files found to analyze",
                "files": [],
                "issues": []
            }
        
        # Read and analyze files
        analysis_results = self._analyze_files(code_files, target_dir)
        
        return analysis_results
    
    def _collect_code_files(self, target_dir: str) -> List[str]:
        """
        Collect all code files in the target directory.
        
        Args:
            target_dir: Directory to scan
            
        Returns:
            List of file paths
        """
        code_files = []
        target_path = Path(target_dir)
        
        for file_path in target_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in self.supported_extensions:
                # Skip common directories to ignore
                if any(part in file_path.parts for part in ['venv', 'node_modules', '__pycache__', '.git', 'build', 'dist']):
                    continue
                code_files.append(str(file_path))
        
        return code_files
    
    def _read_file_content(self, file_path: str) -> str:
        """
        Safely read file content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content as string or error message
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"[ERROR reading file: {str(e)}]"
    
    def _analyze_files(self, code_files: List[str], target_dir: str) -> Dict[str, Any]:
        """
        Analyze collected code files using LangChain LLM.
        
        Args:
            code_files: List of file paths to analyze
            target_dir: Base directory path
            
        Returns:
            Analysis results with issues and summary
        """
        # Prepare code context for analysis
        code_context = self._prepare_code_context(code_files, target_dir)
        
        try:
            # Create the prompt using LangChain template
            messages = self.prompt_template.format_messages(code_context=code_context)
            
            # Log the analysis attempt
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.ANALYSIS,
                details={
                    "target_dir": target_dir,
                    "files_analyzed": len(code_files),
                    "input_prompt": str(messages)
                },
                status="STARTED"
            )
            
            # Invoke LangChain LLM
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # Parse the response using custom parser
            analysis_result = self.output_parser.parse(response_text)
            
            # Log success
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.ANALYSIS,
                details={
                    "target_dir": target_dir,
                    "files_analyzed": len(code_files),
                    "output_response": response_text,
                    "issues_found": len(analysis_result.get("issues", []))
                },
                status="SUCCESS"
            )
            
            # Add metadata
            analysis_result["status"] = "SUCCESS"
            analysis_result["files_analyzed"] = code_files
            analysis_result["files_count"] = len(code_files)
            
            return analysis_result
            
        except Exception as e:
            # Log failure
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.ANALYSIS,
                details={
                    "target_dir": target_dir,
                    "files_analyzed": len(code_files),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                status="FAILURE"
            )
            
            return {
                "status": "ERROR",
                "message": f"Analysis failed: {str(e)}",
                "files": code_files,
                "issues": [],
                "error": str(e)
            }
    
    def _prepare_code_context(self, code_files: List[str], target_dir: str) -> str:
        """
        Prepare code files for LLM analysis.
        
        Args:
            code_files: List of file paths
            target_dir: Base directory
            
        Returns:
            Formatted code context string
        """
        context_parts = []
        max_files = 10  # Limit to avoid token overflow
        
        for file_path in code_files[:max_files]:
            relative_path = os.path.relpath(file_path, target_dir)
            content = self._read_file_content(file_path)
            
            # Limit file content length
            max_content_length = 2000
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n... (content truncated)"
            
            context_parts.append(f"""
File: {relative_path}
{'='*60}
{content}
{'='*60}
""")
        
        if len(code_files) > max_files:
            context_parts.append(f"\n... and {len(code_files) - max_files} more files")
        
        return "\n".join(context_parts)
