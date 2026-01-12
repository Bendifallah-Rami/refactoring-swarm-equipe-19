"""
Agent Registry - Central place to instantiate and manage all agents in the Refactoring Swarm.

This module provides a registry pattern for managing the three core agents:
- Auditor Agent: Analyzes code for issues
- Fixer Agent: Generates refactoring solutions
- Judge Agent: Validates fixes and makes decisions

Day 5 Task: Create agent registry and loader
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv

from src.agents.auditor_agent import AuditorAgent
from src.agents.fixer_agent import FixerAgent
from src.agents.judge_agent import JudgeAgent
from src.utils.logger import log_experiment, ActionType

load_dotenv()


class AgentRegistry:
    """
    Central registry for managing all agents in the refactoring swarm.
    
    This class follows the singleton pattern to ensure only one instance
    of each agent exists throughout the application lifecycle.
    """
    
    def __init__(self):
        """Initialize the agent registry."""
        self._agents: Dict[str, any] = {}
        self._initialized = False
        
    def initialize(self) -> None:
        """
        Load and instantiate all agents.
        
        This method should be called once at application startup.
        It creates instances of all three agents and stores them in the registry.
        """
        if self._initialized:
            print("⚠️  Agent registry already initialized")
            return
            
        print("🔧 Initializing Agent Registry...")
        
        try:
            # Check for API key
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment variables")
            
            # Initialize Auditor Agent
            print("  📋 Loading Auditor Agent...")
            self._agents['auditor'] = AuditorAgent()
            
            # Initialize Fixer Agent
            print("  🔧 Loading Fixer Agent...")
            self._agents['fixer'] = FixerAgent()
            
            # Initialize Judge Agent
            print("  ⚖️  Loading Judge Agent...")
            self._agents['judge'] = JudgeAgent()
            
            self._initialized = True
            
            print(f"✅ Agent Registry initialized with {len(self._agents)} agents")
            
            # Log registry initialization
            log_experiment(
                agent_name="AgentRegistry",
                model_used="N/A",
                action=ActionType.ANALYSIS,
                details={
                    "input_prompt": "Agent registry initialization",
                    "output_response": f"Successfully loaded {len(self._agents)} agents: {list(self._agents.keys())}",
                }
            )
            
        except Exception as e:
            print(f"❌ Error initializing agent registry: {str(e)}")
            
            log_experiment(
                agent_name="AgentRegistry",
                model_used="N/A",
                action=ActionType.DEBUG,
                details={
                    "input_prompt": "Agent registry initialization",
                    "output_response": f"Failed to initialize: {str(e)}",
                }
            )
            raise
    
    def get_agent(self, agent_name: str) -> Optional[any]:
        """
        Retrieve an agent by name.
        
        Args:
            agent_name: Name of the agent ('auditor', 'fixer', 'judge')
            
        Returns:
            Agent instance if found, None otherwise
            
        Raises:
            RuntimeError: If registry not initialized
        """
        if not self._initialized:
            raise RuntimeError("Agent registry not initialized. Call initialize() first.")
        
        agent = self._agents.get(agent_name.lower())
        
        if agent is None:
            print(f"⚠️  Agent '{agent_name}' not found in registry")
            print(f"   Available agents: {list(self._agents.keys())}")
        
        return agent
    
    def get_auditor(self) -> AuditorAgent:
        """Get the Auditor Agent instance."""
        return self.get_agent('auditor')
    
    def get_fixer(self) -> FixerAgent:
        """Get the Fixer Agent instance."""
        return self.get_agent('fixer')
    
    def get_judge(self) -> JudgeAgent:
        """Get the Judge Agent instance."""
        return self.get_agent('judge')
    
    def list_agents(self) -> list:
        """
        Get list of all registered agent names.
        
        Returns:
            List of agent names
        """
        return list(self._agents.keys())
    
    def is_initialized(self) -> bool:
        """Check if the registry has been initialized."""
        return self._initialized
    
    def shutdown(self) -> None:
        """
        Shutdown all agents and clean up resources.
        
        This method should be called before application exit.
        """
        if not self._initialized:
            return
        
        print("🛑 Shutting down Agent Registry...")
        
        # Clear agent references
        self._agents.clear()
        self._initialized = False
        
        print("✅ Agent Registry shutdown complete")
        
        log_experiment(
            agent_name="AgentRegistry",
            model_used="N/A",
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": "Agent registry shutdown",
                "output_response": "All agents released and registry cleared",
            }
        )


# Global registry instance (singleton pattern)
_registry_instance: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    Get the global agent registry instance.
    
    This function implements the singleton pattern to ensure
    only one registry exists throughout the application.
    
    Returns:
        AgentRegistry instance
    """
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    
    return _registry_instance


# Convenience functions for quick agent access
def get_auditor_agent() -> AuditorAgent:
    """Get the Auditor Agent from the global registry."""
    return get_registry().get_auditor()


def get_fixer_agent() -> FixerAgent:
    """Get the Fixer Agent from the global registry."""
    return get_registry().get_fixer()


def get_judge_agent() -> JudgeAgent:
    """Get the Judge Agent from the global registry."""
    return get_registry().get_judge()
