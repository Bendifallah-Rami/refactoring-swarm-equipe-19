"""
Judge Agent - Evaluates and validates refactoring work performed by other agents using LangChain.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.schema import BaseOutputParser
from src.agents.base_agent import BaseAgent
from src.prompts.judge_prompt import get_judge_prompt
from src.utils.logger import ActionType, log_experiment


class JudgmentOutputParser(BaseOutputParser):
    """Custom parser to extract judgment JSON from LLM responses."""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse JSON judgment from LLM response, handling markdown code blocks."""
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
            if "verdict" not in result:
                result["verdict"] = "NEEDS_REVISION"
            
            if "overall_score" not in result:
                result["overall_score"] = 0
            
            if "assessment" not in result:
                result["assessment"] = {}
            
            if "issues_found" not in result:
                result["issues_found"] = []
            
            if "strengths" not in result:
                result["strengths"] = []
            
            if "summary" not in result:
                result["summary"] = "No summary provided"
            
            if "requires_revision" not in result:
                result["requires_revision"] = result["verdict"] in ["REJECTED", "NEEDS_REVISION"]
            
            if "blocking_issues" not in result:
                result["blocking_issues"] = [
                    issue["description"] 
                    for issue in result["issues_found"] 
                    if issue.get("severity") == "critical"
                ]
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                "verdict": "NEEDS_REVISION",
                "overall_score": 0,
                "assessment": {},
                "issues_found": [{
                    "severity": "critical",
                    "category": "parsing_error",
                    "description": f"Failed to parse LLM judgment response: {str(e)}",
                    "location": "general",
                    "recommendation": "Review raw response"
                }],
                "strengths": [],
                "summary": "Failed to parse judgment",
                "requires_revision": True,
                "blocking_issues": ["Failed to parse judgment response"],
                "raw_response": text[:500]
            }


class JudgeAgent(BaseAgent):
    """
    Agent responsible for evaluating and validating refactoring work using LangChain.
    """
    
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Judge Agent with LangChain components.
        
        Args:
            model_name: Gemini model to use for judgment
        """
        super().__init__(agent_name="JudgeAgent", model_name=model_name)
        
        # Initialize LangChain LLM
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.3,  # Moderate temperature for balanced judgment
            convert_system_message_to_human=True
        )
        
        # Initialize output parser
        self.output_parser = JudgmentOutputParser()
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.get_system_prompt()),
            HumanMessagePromptTemplate.from_template(
                "Please evaluate the following refactoring:\n\n"
                "Original Issue:\n{issue_description}\n\n"
                "File: {file_path}\n"
                "Lines: {line_start}-{line_end}\n\n"
                "Original Code:\n"
                "```\n{original_code}\n```\n\n"
                "Refactored Code:\n"
                "```\n{refactored_code}\n```\n\n"
                "Explanation: {explanation}\n\n"
                "{additional_context}"
                "Provide your judgment in the specified JSON format."
            )
        ])
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for the judge agent."""
        return get_judge_prompt()
    
    def evaluate_fix(self, fix: Dict[str, Any], issue: Optional[Dict[str, Any]] = None, 
                    test_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate a single refactoring fix.
        
        Args:
            fix: Fix dictionary containing file, original_code, fixed_code, explanation
            issue: Optional original issue that prompted the fix
            test_results: Optional test results to include in evaluation
            
        Returns:
            Dictionary containing judgment result
        """
        file_path = fix.get("file", "")
        original_code = fix.get("original_code", "")
        fixed_code = fix.get("fixed_code", "")
        explanation = fix.get("explanation", "No explanation provided")
        
        if not all([file_path, original_code, fixed_code]):
            return {
                "status": "ERROR",
                "verdict": "REJECTED",
                "message": "Incomplete fix data - missing required fields"
            }
        
        # Prepare issue description
        issue_description = "No original issue provided"
        line_start = fix.get("line_start", "N/A")
        line_end = fix.get("line_end", "N/A")
        
        if issue:
            issue_description = (
                f"Severity: {issue.get('severity', 'unknown')}\n"
                f"Category: {issue.get('category', 'unknown')}\n"
                f"Description: {issue.get('description', 'N/A')}\n"
                f"Recommendation: {issue.get('recommendation', 'N/A')}"
            )
            line_start = issue.get("line_start", line_start)
            line_end = issue.get("line_end", line_end)
        
        # Prepare additional context
        additional_context = ""
        if test_results:
            test_status = test_results.get("status", "unknown")
            test_summary = test_results.get("summary", "")
            additional_context = f"\nTest Results: {test_status}\n{test_summary}\n\n"
        
        # Generate judgment using LLM
        judgment_result = self._generate_judgment(
            issue_description=issue_description,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            original_code=original_code,
            refactored_code=fixed_code,
            explanation=explanation,
            additional_context=additional_context
        )
        
        return judgment_result
    
    def evaluate_fixes(self, fixes: List[Dict[str, Any]], issues: Optional[List[Dict[str, Any]]] = None,
                      test_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate multiple refactoring fixes.
        
        Args:
            fixes: List of fix dictionaries
            issues: Optional list of original issues corresponding to fixes
            test_results: Optional test results to include in evaluation
            
        Returns:
            Dictionary containing aggregated judgment results
        """
        judgments = []
        approved_count = 0
        rejected_count = 0
        needs_revision_count = 0
        
        for idx, fix in enumerate(fixes):
            # Get corresponding issue if available
            issue = issues[idx] if issues and idx < len(issues) else None
            
            # Evaluate the fix
            judgment = self.evaluate_fix(fix, issue, test_results)
            judgments.append({
                "fix": fix,
                "issue": issue,
                "judgment": judgment
            })
            
            # Count verdicts
            verdict = judgment.get("verdict", "NEEDS_REVISION")
            if verdict in ["APPROVED", "APPROVED_WITH_NOTES"]:
                approved_count += 1
            elif verdict == "REJECTED":
                rejected_count += 1
            else:
                needs_revision_count += 1
        
        # Calculate overall assessment
        total_fixes = len(fixes)
        overall_verdict = self._determine_overall_verdict(
            approved_count, rejected_count, needs_revision_count, total_fixes
        )
        
        return {
            "status": "COMPLETED",
            "overall_verdict": overall_verdict,
            "total_fixes": total_fixes,
            "approved": approved_count,
            "rejected": rejected_count,
            "needs_revision": needs_revision_count,
            "judgments": judgments,
            "summary": self._create_summary(judgments)
        }
    
    def _generate_judgment(self, issue_description: str, file_path: str, 
                          line_start: Any, line_end: Any,
                          original_code: str, refactored_code: str,
                          explanation: str, additional_context: str) -> Dict[str, Any]:
        """
        Generate judgment using LLM via LangChain.
        
        Args:
            issue_description: Description of the original issue
            file_path: Path to the file
            line_start: Starting line number
            line_end: Ending line number
            original_code: Original code before refactoring
            refactored_code: Refactored code after changes
            explanation: Explanation of the changes made
            additional_context: Additional context like test results
            
        Returns:
            Judgment result dictionary
        """
        try:
            # Format the prompt using the template
            messages = self.prompt_template.format_messages(
                issue_description=issue_description,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                original_code=original_code,
                refactored_code=refactored_code,
                explanation=explanation,
                additional_context=additional_context
            )
            
            # Call LLM through LangChain
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # Parse the response
            judgment = self.output_parser.parse(response_text)
            judgment["status"] = "SUCCESS"
            judgment["file"] = file_path
            
            # Log the judgment
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.JUDGE,
                details={
                    "file": file_path,
                    "verdict": judgment["verdict"],
                    "overall_score": judgment["overall_score"],
                    "issues_found": len(judgment.get("issues_found", [])),
                    "blocking_issues": len(judgment.get("blocking_issues", [])),
                    "input_prompt": str(messages),
                    "output_response": response_text
                },
                status="SUCCESS"
            )
            
            return judgment
            
        except Exception as e:
            error_judgment = {
                "status": "ERROR",
                "verdict": "NEEDS_REVISION",
                "overall_score": 0,
                "message": f"Failed to generate judgment: {str(e)}",
                "file": file_path,
                "issues_found": [{
                    "severity": "critical",
                    "category": "evaluation_error",
                    "description": f"Judge agent error: {str(e)}",
                    "location": "general",
                    "recommendation": "Review the error and retry"
                }],
                "requires_revision": True,
                "blocking_issues": [f"Judge agent error: {str(e)}"]
            }
            
            # Log failure
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.JUDGE,
                details={
                    "file": file_path,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                status="FAILURE"
            )
            
            return error_judgment
    
    def _determine_overall_verdict(self, approved: int, rejected: int, 
                                   needs_revision: int, total: int) -> str:
        """
        Determine overall verdict based on individual judgments.
        
        Args:
            approved: Number of approved fixes
            rejected: Number of rejected fixes
            needs_revision: Number of fixes needing revision
            total: Total number of fixes
            
        Returns:
            Overall verdict string
        """
        if total == 0:
            return "NO_FIXES"
        
        if rejected > 0:
            return "REJECTED"
        
        if needs_revision > 0:
            return "NEEDS_REVISION"
        
        if approved == total:
            return "APPROVED"
        
        return "APPROVED_WITH_NOTES"
    
    def _create_summary(self, judgments: List[Dict[str, Any]]) -> str:
        """
        Create a summary of all judgments.
        
        Args:
            judgments: List of judgment results
            
        Returns:
            Summary string
        """
        if not judgments:
            return "No fixes were evaluated."
        
        total = len(judgments)
        avg_score = sum(j["judgment"].get("overall_score", 0) for j in judgments) / total
        
        critical_issues = []
        all_strengths = []
        
        for j in judgments:
            judgment = j["judgment"]
            blocking = judgment.get("blocking_issues", [])
            if blocking:
                critical_issues.extend(blocking)
            
            strengths = judgment.get("strengths", [])
            all_strengths.extend(strengths)
        
        summary = f"Evaluated {total} fix(es) with an average score of {avg_score:.1f}/100.\n"
        
        if critical_issues:
            summary += f"\nCritical issues found: {len(critical_issues)}\n"
            for issue in critical_issues[:3]:  # Show top 3
                summary += f"  - {issue}\n"
        
        if all_strengths:
            summary += f"\nStrengths identified: {len(set(all_strengths))}\n"
            for strength in list(set(all_strengths))[:3]:  # Show top 3 unique
                summary += f"  - {strength}\n"
        
        return summary.strip()
    
    def compare_versions(self, file_path: str, version_a: str, version_b: str,
                        context: Optional[str] = None) -> Dict[str, Any]:
        """
        Compare two versions of code and provide judgment on which is better.
        
        Args:
            file_path: Path to the file being compared
            version_a: First version of the code
            version_b: Second version of the code
            context: Optional context about the comparison
            
        Returns:
            Comparison judgment result
        """
        comparison_prompt = (
            f"Compare the following two versions of code from {file_path}:\n\n"
            f"Version A:\n```\n{version_a}\n```\n\n"
            f"Version B:\n```\n{version_b}\n```\n\n"
            f"{context if context else ''}\n\n"
            "Evaluate both versions and determine which is better in terms of "
            "code quality, maintainability, performance, and best practices. "
            "Provide your judgment in the specified JSON format, treating Version B as "
            "the 'refactored' version for the response structure."
        )
        
        try:
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": comparison_prompt}
            ]
            
            response = self.llm.invoke(comparison_prompt)
            response_text = response.content
            
            judgment = self.output_parser.parse(response_text)
            judgment["status"] = "SUCCESS"
            judgment["file"] = file_path
            judgment["comparison"] = True
            
            return judgment
            
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Failed to compare versions: {str(e)}",
                "file": file_path
            }
