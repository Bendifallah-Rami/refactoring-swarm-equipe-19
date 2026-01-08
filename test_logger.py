"""
Test du systeme de logging - Day 1
"""

from src.utils.logger import log_experiment, ActionType, get_experiment_stats

print("=" * 70)
print("TEST DU LOGGER - DAY 1")
print("=" * 70)

# Test 1: Logging basique
print("\n[1] Test logging basique...")
try:
    log_id = log_experiment(
        agent_name="Auditor_Agent",
        model_used="gemini-2.0-flash",
        action=ActionType.ANALYSIS,
        details={
            "input_prompt": "Analyse ce code Python",
            "output_response": "J'ai trouve 3 problemes",
            "file_analyzed": "example.py"
        },
        status="SUCCESS"
    )
    print(f"    OK - SUCCESS: ID = {log_id}")
except Exception as e:
    print(f"    ERREUR - FAILED: {e}")

# Test 2: Tous les types d'actions
print("\n[2] Test de tous les ActionTypes...")
for action in ActionType:
    try:
        log_experiment(
            agent_name="Test_Agent",
            model_used="gemini-2.0-flash",
            action=action,
            details={
                "input_prompt": f"Test de {action.value}",
                "output_response": f"Reponse pour {action.value}"
            }
        )
        print(f"    OK - {action.value}")
    except Exception as e:
        print(f"    ERREUR - {action.value}: {e}")

# Test 3: Validation (devrait echouer)
print("\n[3] Test validation (doit echouer)...")
try:
    log_experiment(
        agent_name="Test_Agent",
        model_used="gemini-2.0-flash",
        action=ActionType.FIX,
        details={
            "input_prompt": "Prompt sans reponse"
            # Manque 'output_response'
        }
    )
    print("    ERREUR - FAILED: Devrait avoir leve une ValueError!")
except ValueError as e:
    print(f"    OK - CORRECT: Validation fonctionne")

# Test 4: Statistiques
print("\n[4] Statistiques...")
stats = get_experiment_stats()
print(f"    Total: {stats['total_experiments']} experiences")
print(f"    Par agent: {stats['by_agent']}")
print(f"    Par action: {stats['by_action']}")
print(f"    Par statut: {stats['by_status']}")

# Test 5: Verification du fichier
print("\n[5] Verification du fichier JSON...")
import json
try:
    with open("logs/experiment_data.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if "experiments" in data:
        print(f"    OK - Structure correcte: {len(data['experiments'])} experiences")
        
        # Verifier les champs obligatoires
        last_exp = data["experiments"][-1]
        required = ["id", "timestamp", "agent_name", "model_used", "action", "details", "status"]
        missing = [field for field in required if field not in last_exp]
        
        if not missing:
            print(f"    OK - Tous les champs obligatoires presents")
            
            # Verifier details
            if "input_prompt" in last_exp["details"] and "output_response" in last_exp["details"]:
                print(f"    OK - input_prompt et output_response presents")
            else:
                print(f"    ERREUR - Champs manquants dans details")
        else:
            print(f"    ERREUR - Champs manquants: {missing}")
    else:
        print(f"    ERREUR - Structure incorrecte (pas de cle 'experiments')")
        
except Exception as e:
    print(f"    ERREUR: {e}")

print("\n" + "=" * 70)
print("TESTS TERMINES - Verifiez logs/experiment_data.json")
print("=" * 70)