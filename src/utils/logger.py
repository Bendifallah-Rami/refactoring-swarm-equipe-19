# -*- coding: utf-8 -*-
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

import json
from datetime import datetime
from enum import Enum
from typing import Any
import uuid

# ... rest of your code


import json
import os
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

# Chemin du fichier de logs
LOG_FILE = os.path.join("logs", "experiment_data.json")

class ActionType(str, Enum):
    """
    Énumération des types d'actions possibles pour standardiser l'analyse.
    """
    ANALYSIS = "ANALYSIS"      # Audit, lecture, recherche de bugs
    GENERATION = "GENERATION"  # Création de nouveau code/tests/docs
    DEBUG = "DEBUG"            # Analyse d'erreurs d'exécution
    FIX = "FIX"                # Application de correctifs


def _ensure_log_file():
    """S'assure que le fichier de log existe avec la structure correcte."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"experiments": []}, f, indent=2)


def log_experiment(
    agent_name: str, 
    model_used: str, 
    action: ActionType, 
    details: dict[str, Any], 
    status: str = "SUCCESS"
) -> str:
    """
    Enregistre une interaction d'agent pour l'analyse scientifique.

    Args:
        agent_name (str): Nom de l'agent (ex: "Auditor_Agent", "Fixer_Agent").
        model_used (str): Modèle LLM utilisé (ex: "gemini-2.0-flash").
        action (ActionType): Le type d'action effectué (utiliser l'Enum ActionType).
        details (dict): Dictionnaire contenant les détails. 
                       DOIT contenir 'input_prompt' et 'output_response'.
        status (str): "SUCCESS" ou "FAILURE" (défaut: "SUCCESS").

    Returns:
        str: L'ID unique de l'expérience loggée

    Raises:
        ValueError: Si les champs obligatoires sont manquants dans 'details'.

    Example:
        >>> log_experiment(
        ...     agent_name="Auditor_Agent",
        ...     model_used="gemini-2.0-flash",
        ...     action=ActionType.ANALYSIS,
        ...     details={
        ...         "input_prompt": "Analyse ce code...",
        ...         "output_response": "J'ai trouvé 3 bugs..."
        ...     }
        ... )
        'uuid-1234-5678-...'
    """
    
    # --- 1. VALIDATION DU TYPE D'ACTION ---
    valid_actions = [a.value for a in ActionType]
    if isinstance(action, ActionType):
        action_str = action.value
    elif action in valid_actions:
        action_str = action
    else:
        raise ValueError(
            f"❌ Action invalide : '{action}'. "
            f"Utilisez ActionType.ANALYSIS, ActionType.FIX, etc."
        )

    # --- 2. VALIDATION STRICTE DES DONNÉES ---
    # Pour le TP, input_prompt et output_response sont OBLIGATOIRES
    if 'input_prompt' not in details:
        raise ValueError(
            f"❌ Erreur de Logging (Agent: {agent_name}) : "
            f"Le champ 'input_prompt' est manquant dans 'details'. "
            f"Il est OBLIGATOIRE pour valider le TP."
        )
    
    if 'output_response' not in details:
        raise ValueError(
            f"❌ Erreur de Logging (Agent: {agent_name}) : "
            f"Le champ 'output_response' est manquant dans 'details'. "
            f"Il est OBLIGATOIRE pour valider le TP."
        )

    # --- 3. PRÉPARATION DE L'ENTRÉE ---
    _ensure_log_file()
    
    experiment_id = str(uuid.uuid4())
    entry = {
        "id": experiment_id,
        "timestamp": datetime.now().isoformat(),
        "agent_name": agent_name,     # Nom de champ conforme
        "model_used": model_used,     # Nom de champ conforme
        "action": action_str,
        "details": details,           # Doit être un dict avec input_prompt et output_response
        "status": status
    }

    # --- 4. LECTURE & ÉCRITURE ROBUSTE ---
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Si l'ancien format (array) existe, on convertit
        if isinstance(data, list):
            print("⚠️ Conversion de l'ancien format vers le nouveau format...")
            data = {"experiments": data}
            
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"⚠️ Le fichier de logs était vide ou corrompu. Création d'un nouveau.")
        data = {"experiments": []}

    # Ajouter la nouvelle expérience
    data["experiments"].append(entry)
    
    # Écriture
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return experiment_id


def get_experiment_stats() -> dict:
    """
    Obtenir des statistiques sur les expériences loggées.
    
    Returns:
        dict: Statistiques (total, par agent, par action, par statut).
    """
    _ensure_log_file()
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    experiments = data.get("experiments", [])
    
    if not experiments:
        return {
            "total_experiments": 0,
            "by_agent": {},
            "by_action": {},
            "by_status": {}
        }
    
    stats = {
        "total_experiments": len(experiments),
        "by_agent": {},
        "by_action": {},
        "by_status": {"SUCCESS": 0, "FAILURE": 0}
    }
    
    for exp in experiments:
        # Compter par agent
        agent = exp.get("agent_name", "unknown")
        stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
        
        # Compter par action
        action = exp.get("action", "unknown")
        stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
        
        # Compter par statut
        status = exp.get("status", "FAILURE")
        if status in stats["by_status"]:
            stats["by_status"][status] += 1
    
    return stats


def validate_log_entry(entry: dict) -> bool:
    """
    Validate that a log entry has all required fields.
    
    Args:
        entry: Log entry dictionary
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "id", "timestamp", "agent_name", 
        "model_used", "action", "details", "status"
    ]
    
    # Check top-level fields
    for field in required_fields:
        if field not in entry:
            return False
    
    # Check details has required fields
    if "input_prompt" not in entry["details"]:
        return False
    if "output_response" not in entry["details"]:
        return False
    
    return True

def get_experiment_stats() -> dict:
    """
    Get statistics about logged experiments.
    
    Returns:
        Dictionary with stats (total_experiments, by_agent, by_action, etc.)
    """
    _ensure_log_file()
    
    with open(LOG_FILE, 'r') as f:
        data = json.load(f)
    
    experiments = data.get("experiments", [])
    
    stats = {
        "total_experiments": len(experiments),
        "by_agent": {},
        "by_action": {},
        "by_status": {"SUCCESS": 0, "FAILURE": 0}
    }
    
    for exp in experiments:
        # Count by agent
        agent = exp.get("agent_name", "unknown")
        stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
        
        # Count by action
        action = exp.get("action", "unknown")
        stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
        
        # Count by status
        status = exp.get("status", "FAILURE")
        if status in stats["by_status"]:
            stats["by_status"][status] += 1
    
    return stats

def log_iteration(
    iteration_number: int,
    phase: str,
    result: dict,
    status: str = "SUCCESS"
) -> str:
    """
    Log a complete iteration of the refactoring loop.
    
    Args:
        iteration_number: Current iteration (1-10)
        phase: "audit", "fix", or "judge"
        result: Result dictionary from that phase
        status: "SUCCESS" or "FAILURE"
    
    Returns:
        Unique log ID
    
    Example:
        >>> log_iteration(
        ...     iteration_number=1,
        ...     phase="audit",
        ...     result={"issues_found": 5},
        ...     status="SUCCESS"
        ... )
        'uuid-1234-...'
    """
    return log_experiment(
        agent_name=f"Orchestrator_Iteration_{iteration_number}",
        model_used="system",
        action=ActionType.DEBUG,
        details={
            "input_prompt": f"Starting {phase} phase",
            "output_response": json.dumps(result, indent=2),
            "iteration": iteration_number,
            "phase": phase
        },
        status=status
    )

if __name__ == "__main__":
    # Test rapide
    print("🧪 Test du logger...")
    
    test_id = log_experiment(
        agent_name="Test_Agent",
        model_used="test-model",
        action=ActionType.ANALYSIS,
        details={
            "input_prompt": "Test prompt",
            "output_response": "Test response"
        }
    )
    
    print(f"✅ Logged: {test_id}")
    print(f"✅ Vérifiez: logs/experiment_data.json")