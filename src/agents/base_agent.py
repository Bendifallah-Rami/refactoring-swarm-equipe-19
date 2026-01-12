import os
from abc import ABC, abstractmethod
from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.logger import log_experiment, ActionType

class BaseAgent(ABC):
    """Abstract base class for all agents in the Refactoring Swarm."""
    
    def __init__(self, agent_name: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the base agent.
        
        Args:
            agent_name: Name identifier for this agent
            model_name: Gemini model to use
        """
        self.agent_name = agent_name
        self.model_name = model_name
        
        # Configure LangChain LLM
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.model = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,
            convert_system_message_to_human=True
        )
    
    def call_llm(self, prompt: str, action_type: ActionType, extra_details: dict = None) -> str:
        """
        Call the LLM and log the interaction.
        
        Args:
            prompt: The prompt to send to the LLM
            action_type: Type of action being performed
            extra_details: Additional details to log
        
        Returns:
            LLM response text
        """
        try:
            # Call LLM through LangChain
            response = self.model.invoke(prompt)
            response_text = response.content
            
            # Prepare log details
            details = {
                "input_prompt": prompt,
                "output_response": response_text,
            }
            if extra_details:
                details.update(extra_details)
            
            # Log the interaction
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=action_type,
                details=details,
                status="SUCCESS"
            )
            
            return response_text
            
        except Exception as e:
            # Log failure
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=action_type,
                details={
                    "input_prompt": prompt,
                    "output_response": f"ERROR: {str(e)}",
                    "error_type": type(e).__name__
                },
                status="FAILURE"
            )
            raise
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent. Must be implemented by subclasses."""
        pass