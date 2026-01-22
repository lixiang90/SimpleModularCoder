import os
import json
from typing import Dict, Any, List, Optional

# --- Tool Definitions (JSON Schema for LLM) ---
# These remain static as they describe the interface
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to read (relative to workspace)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Overwrites existing files or creates new ones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to write (relative to workspace)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append content to a file. Useful for large files to avoid token limits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to append to (relative to workspace)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to append to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a specific string in a file with a new string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to edit (relative to workspace)"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to be replaced (must be unique in the file)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The new string to replace with"
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and directories in the specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list (default is root of workspace)",
                        "default": "."
                    }
                }
            }
        }
    }
]

class ToolSet:
    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.allowed_dirs = None # List[str] of allowed directories (absolute paths)
        self.readonly_files = [] # List[str] of filenames that are read-only (e.g. test_spec.py)

        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir)
            except Exception as e:
                raise ValueError(f"Could not create base directory {self.base_dir}: {e}")

    def set_constraints(self, allowed_dirs: Optional[List[str]] = None, readonly_files: Optional[List[str]] = None):
        """Sets permission constraints for file operations."""
        if allowed_dirs:
            self.allowed_dirs = [os.path.abspath(d) for d in allowed_dirs]
        else:
            self.allowed_dirs = None
            
        self.readonly_files = readonly_files if readonly_files else []
        
        print(f"[ToolSet] Constraints set: Allowed Dirs={self.allowed_dirs}, ReadOnly={self.readonly_files}")

    def _check_write_permission(self, abs_path: str) -> Optional[str]:
        """Checks if writing to the path is allowed based on constraints."""
        # 1. Check readonly files
        filename = os.path.basename(abs_path)
        if filename in self.readonly_files:
             return f"Access Denied: {filename} is read-only."

        # 2. Check allowed dirs
        if self.allowed_dirs:
            is_allowed = False
            for d in self.allowed_dirs:
                # Check if path is inside directory d
                # os.path.commonpath is safer than startswith for paths
                try:
                    if os.path.commonpath([abs_path, d]) == d:
                        is_allowed = True
                        break
                except ValueError:
                    # Can happen on Windows if drives are different
                    continue
            
            if not is_allowed:
                return f"Access Denied: Write operation restricted to {self.allowed_dirs}"
        
        return None

    def _resolve_path(self, user_path: str) -> str:
        """
        Securely resolves a user-provided path against the base directory.
        Prevents directory traversal attacks (Sandbox).
        """
        # Join path with base_dir
        # If user_path is absolute, os.path.join discards previous parts (on some OS) or joins them.
        # But we want to treat user_path as relative to base_dir always.
        # So we strip leading slashes/drive letters to force it relative.
        
        # A simple way is to use abspath and startswith check
        full_path = os.path.join(self.base_dir, user_path)
        abs_path = os.path.abspath(full_path)
        
        # Check if the resolved path starts with the base_dir
        if not abs_path.startswith(self.base_dir):
            raise ValueError(f"Access denied: Path '{user_path}' resolves to '{abs_path}', which is outside the workspace '{self.base_dir}'")
            
        return abs_path

    def read_file(self, path: str) -> str:
        """Reads the content of a file."""
        try:
            safe_path = self._resolve_path(path)
            if not os.path.exists(safe_path):
                return f"Error: File not found: {path}"
            if not os.path.isfile(safe_path):
                return f"Error: Path is not a file: {path}"
                
            with open(safe_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {path}: {str(e)}"

    def write_file(self, path: str, content: str) -> str:
        """Writes content to a file (overwrites or creates)."""
        try:
            safe_path = self._resolve_path(path)
            
            # Check constraints
            error = self._check_write_permission(safe_path)
            if error:
                return f"Error: {error}"

            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file {path}: {str(e)}"

    def append_file(self, path: str, content: str) -> str:
        """Appends content to a file."""
        try:
            safe_path = self._resolve_path(path)
            
            # Check constraints
            error = self._check_write_permission(safe_path)
            if error:
                return f"Error: {error}"

            if not os.path.exists(safe_path):
                 return f"Error: File not found: {path}. Use write_file to create new files."

            with open(safe_path, 'a', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully appended to {path}"
        except Exception as e:
            return f"Error appending to file {path}: {str(e)}"


    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        """Replaces old_string with new_string in the file."""
        try:
            safe_path = self._resolve_path(path)
            
            # Check constraints
            error = self._check_write_permission(safe_path)
            if error:
                return f"Error: {error}"

            if not os.path.exists(safe_path):
                 return f"Error: File not found: {path}"

            with open(safe_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_string not in content:
                return f"Error: old_string not found in {path}"
            
            # Check for multiple occurrences
            if content.count(old_string) > 1:
                return f"Error: Multiple occurrences of old_string found in {path}. Please provide more unique context."
                
            new_content = content.replace(old_string, new_string)
            
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file {path}: {str(e)}"

    def list_files(self, path: str = ".") -> str:
        """Lists files in a directory."""
        try:
            safe_path = self._resolve_path(path)
            if not os.path.exists(safe_path):
                return f"Error: Directory not found: {path}"
            
            items = os.listdir(safe_path)
            # Add indicators for directories
            result = []
            for item in items:
                item_path = os.path.join(safe_path, item)
                if os.path.isdir(item_path):
                    result.append(f"{item}/")
                else:
                    result.append(item)
            return "\n".join(result) if result else "(empty directory)"
        except Exception as e:
            return f"Error listing directory {path}: {str(e)}"

    def run_command(self, command: str) -> str:
        """Executes a shell command after user approval."""
        print(f"\n[SECURITY WARNING] Agent wants to execute: {command}")
        approval = input("Allow execution? (y/n): ").strip().lower()
        
        if approval != 'y':
            return "Error: User denied command execution."
            
        try:
            # Security: run in base_dir
            # Note: subprocess.run with shell=True is dangerous, but that's what we want for now.
            # We rely on user approval for security.
            result = subprocess.run(
                command, 
                shell=True, 
                cwd=self.base_dir, 
                capture_output=True, 
                text=True
            )
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
            
            output = f"Exit Code: {return_code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            return output
        except Exception as e:
            return f"Error executing command: {str(e)}"
