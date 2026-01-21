import argparse
import os
import sys
import subprocess
import re
from src.agent import Agent
from src.prompts import DEFAULT_SYSTEM_PROMPT, ARCHITECT_SYSTEM_PROMPT, PURE_ARCHITECT_SYSTEM_PROMPT, BUILDER_SYSTEM_PROMPT

def run_tests(test_path):
    """Runs pytest on the specified file and returns (success, output)."""
    try:
        # Use sys.executable to ensure we use the same python environment
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def extract_module_path(user_input, base_dir):
    """
    Tries to extract a valid module path (containing test_spec.py) from user input.
    """
    # Simple regex to find potential paths
    # Matches strings that look like paths (contain / or \)
    potential_paths = re.findall(r'[\w\-\./\\]+', user_input)
    
    for path in potential_paths:
        # Resolve to absolute path
        abs_path = os.path.abspath(os.path.join(base_dir, path))
        test_file = os.path.join(abs_path, "test_spec.py")
        if os.path.exists(test_file):
            return abs_path
    return None

def main():
    parser = argparse.ArgumentParser(description="OpenCode Basic - Autonomous Coding Agent")
    parser.add_argument(
        "--dir", 
        type=str, 
        default="./workspace", 
        help="Base directory for the agent's file operations (default: ./workspace)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="coder",
        choices=["coder", "architect", "pure_architect", "builder"],
        help="Agent operation mode: 'coder', 'architect', 'pure_architect', or 'builder'"
    )
    
    args = parser.parse_args()
    
    base_dir = args.dir
    print(f"Starting OpenCode Basic in workspace: {os.path.abspath(base_dir)}")
    print(f"Mode: {args.mode}")

    system_prompt = DEFAULT_SYSTEM_PROMPT
    if args.mode == "architect":
        system_prompt = ARCHITECT_SYSTEM_PROMPT
    elif args.mode == "pure_architect":
        system_prompt = PURE_ARCHITECT_SYSTEM_PROMPT
    elif args.mode == "builder":
        system_prompt = BUILDER_SYSTEM_PROMPT
    
    # Initial Agent
    try:
        agent = Agent(
            base_dir=base_dir, 
            system_prompt=system_prompt
        )
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return

    print("OpenCode Basic Initialized. Type 'exit' to quit.")
    
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            if not user_input.strip():
                continue

            # Ralph Mode Logic for Builder
            if args.mode == "builder":
                module_path = extract_module_path(user_input, base_dir)
                if module_path:
                    print(f"Detected module path: {module_path}")
                    
                    # Apply constraints to the current agent immediately
                    agent.tool_set.set_constraints(
                        allowed_dirs=[module_path],
                        readonly_files=["test_spec.py", "PROMPT.md", "interface.py"]
                    )
                    
                    print("Entering Ralph Mode (Iterative Build & Test)...")
                    
                    max_attempts = 5
                    current_prompt = user_input
                    
                    for attempt in range(max_attempts):
                        print(f"\n--- Attempt {attempt + 1}/{max_attempts} ---")
                        
                        # Run Agent
                        agent.run(current_prompt)
                        
                        # Run Tests
                        test_spec = os.path.join(module_path, "test_spec.py")
                        print(f"Running tests: {test_spec}")
                        success, output = run_tests(test_spec)
                        
                        if success:
                            print("\n✅ Tests Passed! Module build successful.")
                            break
                        else:
                            print("\n❌ Tests Failed.")
                            # Check if max attempts reached
                            if attempt == max_attempts - 1:
                                print("Max attempts reached. Build failed.")
                                break
                            
                            # Prepare for next attempt:
                            # 1. Reset Agent (Prune Context)
                            print("Resetting agent context for next attempt...")
                            agent = Agent(base_dir=base_dir, system_prompt=system_prompt)
                            
                            # 2. Update Prompt with Error Info
                            # We strip previous context, just giving the error.
                            # The agent will re-read files as per its protocol.
                            current_prompt = (
                                f"The previous implementation for module '{module_path}' failed tests.\n"
                                f"Here is the error output:\n{output}\n\n"
                                "Please analyze `implementation.py` and `test_spec.py`, then FIX the code to pass the tests.\n"
                                "DO NOT modify `test_spec.py`."
                            )
                else:
                    # Fallback if no path detected
                    agent.run(user_input)
            else:
                # Standard mode
                agent.run(user_input)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
