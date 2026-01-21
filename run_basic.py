import argparse
import os
import sys
import subprocess
import re
import json
from opencode_basic.agent import Agent
from opencode_basic.prompts import DEFAULT_SYSTEM_PROMPT, ARCHITECT_SYSTEM_PROMPT, PURE_ARCHITECT_SYSTEM_PROMPT, BUILDER_SYSTEM_PROMPT

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

def get_project_context(module_path):
    """
    Traverses up from module_path to find dependency_graph.json.
    Returns (project_root, graph_data) or (None, None).
    """
    current = module_path
    # Security brake: don't go up forever, maybe stop at drive root or 5 levels
    for _ in range(5):
        parent = os.path.dirname(current)
        if parent == current:
            break
        
        graph_path = os.path.join(parent, "dependency_graph.json")
        if os.path.exists(graph_path):
            try:
                with open(graph_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return parent, data
            except Exception as e:
                print(f"Error loading dependency graph: {e}")
                return None, None
        
        current = parent
    return None, None

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
                    
                    # 1. Analyze Dependencies
                    project_root, dep_graph = get_project_context(module_path)
                    module_name = os.path.basename(module_path)
                    
                    dependency_context = ""
                    allowed_read_paths = []
                    
                    if dep_graph and module_name in dep_graph:
                        dependencies = dep_graph[module_name]
                        if dependencies:
                            print(f"Found dependencies for {module_name}: {dependencies}")
                            dependency_context += "\n\n### DEPENDENCY INJECTION\n"
                            dependency_context += "You depend on the following modules. You MUST read their `interface.py` to understand the API:\n"
                            
                            for dep in dependencies:
                                # Assume standard structure: project_root/DepName
                                dep_path = os.path.join(project_root, dep)
                                if os.path.exists(dep_path):
                                    allowed_read_paths.append(dep_path)
                                    dependency_context += f"- **{dep}**: Path `{dep_path}`\n"
                                else:
                                    dependency_context += f"- **{dep}**: (Path not found at {dep_path})\n"
                        else:
                            print(f"Module {module_name} has no dependencies.")
                    
                    # Apply constraints to the current agent immediately
                    # We allow writing ONLY to module_path, but reading is generally open via tool, 
                    # yet we explicitly mention allowed_dirs for clarity/safety if we enforced read.
                    # Currently tool_set.allowed_dirs only restricts WRITES.
                    agent.tool_set.set_constraints(
                        allowed_dirs=[module_path],
                        readonly_files=["test_spec.py", "PROMPT.md", "interface.py"]
                    )
                    
                    print("Entering Ralph Mode (Iterative Build & Test)...")
                    
                    max_attempts = 5
                    # Inject dependency info into the prompt
                    current_prompt = user_input + dependency_context
                    
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
                            # Re-inject dependency context for the retry as well, just in case
                            if dependency_context:
                                current_prompt += dependency_context
                else:
                    # Fallback if no path detected
                    print(f"\n[WARNING] Ralph Mode (Auto-Test) NOT activated.")
                    print(f"Reason: Could not find a valid module path containing 'test_spec.py' in your input.")
                    print(f"Base Directory: {base_dir}")
                    print(f"User Input: '{user_input}'")
                    print("Please ensure:")
                    print("1. You provide the correct relative path to the module (e.g., 'snake_game/GameLoop').")
                    print("2. The 'test_spec.py' file exists in that directory.")
                    print("3. Your working directory (--dir) matches where the project is located.\n")
                    
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
