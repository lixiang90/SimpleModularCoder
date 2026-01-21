# SimpleModularCoder - Autonomous Modular Coding Agent

SimpleModularCoder is a lightweight yet powerful autonomous modular coding tool. It incorporates the "Divide and Conquer" philosophy of modern software engineering, coordinating different Agent roles (Architect, Builder, Coder) to automate the process from high-level design to concrete code implementation.

## 🌟 Key Features

*   **Multi-Mode Agents**: Supports four modes: Coder (General Purpose), Architect (Architectural Design), Pure Architect (Interface Design Only), and Builder (Single Module Construction).
*   **Ralph Mode (Iterative Repair)**: The Builder mode features a built-in "Auto Test-Repair Loop", automatically running test cases and self-correcting code based on error logs.
*   **Security Sandbox**:
    *   **Permission Isolation**: Builder mode strictly locks write permissions to the current module directory, explicitly prohibiting tampering with test cases or other modules.
    *   **Command Approval**: Sensitive Shell command execution requires Human-in-the-Loop approval.
*   **Incremental Updates**: Both Architect and Builder are capable of maintenance, supporting interface upgrades and bug fixes on existing code.

## 🚀 Quick Start

### 1. Install Dependencies

Ensure your Python version is >= 3.8 and install necessary dependencies (e.g., `openai`, `pytest`).

```bash
pip install openai pytest
```

### 2. Configure LLM

Configure your LLM provider information in `src/llm_config.json` (compatible with OpenAI interface, such as DeepSeek, OpenAI, Claude, etc.).

```json
{
  "api_key": "sk-...",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "temperature": 0.0
}
```

### 3. Launch Agent

The entry point is `run_basic.py`. You can switch modes using the `--mode` argument.

#### 🏗️ Mode 1: Pure Architect Mode

**Use Case**: Initial project phase. Design system modules, define interfaces, and write test specifications without implementation.

```bash
python run_basic.py --mode pure_architect --dir ./workspace
```

**Interaction Example**:
> User: "Design a Snake Game system"
>
> **Agent Outputs**:
> - `dependency_graph.json`: Module dependencies
> - `GameLoop/interface.py`: Game loop interface definitions
> - `GameLoop/test_spec.py`: Test cases for the interface
> - `GameLoop/PROMPT.md`: Implementation guide

#### 🔨 Mode 2: Builder Mode - Recommended 🔥

**Use Case**: Implement a single module defined by the Architect.

```bash
python run_basic.py --mode builder --dir ./workspace
```

**Interaction Example**:
> User: "Build module: ./workspace/GameLoop"
>
> **Agent Behavior**:
> 1.  **Lock Permissions**: Can ONLY write to `GameLoop` directory. Modifying `test_spec.py` is FORBIDDEN.
> 2.  **Implement Code**: Reads interfaces and tests, writes `implementation.py`.
> 3.  **Ralph Loop**:
>     *   Runs `pytest GameLoop/test_spec.py`
>     *   ❌ Fail -> Reset Memory -> Read Error Log -> Fix Code
>     *   ✅ Success -> Task Complete

#### 🏛️ Mode 3: Architect Mode (Full)

**Use Case**: Rapid prototyping. The Architect designs interfaces and also generates implementation code directly (not recommended for complex projects).

```bash
python run_basic.py --mode architect --dir ./workspace
```

#### 💻 Mode 4: Coder Mode (General) - Default

**Use Case**: Free-form conversation, executing arbitrary coding tasks.

```bash
python run_basic.py --mode coder --dir ./workspace
```

## 🛡️ Security Mechanisms

1.  **Command Execution**: When the Agent attempts to execute `pytest` or other Shell commands, a `[SECURITY WARNING]` will appear in the console, requiring `y` to confirm.
2.  **Filesystem Constraints**: In Builder mode, the system intercepts any attempt to write outside the target module directory to prevent Agent "cheating" (e.g., modifying test cases to pass tests).

## 📂 Project Structure

```text
SimpleModularCoder/
├── run_basic.py       # Entry point
├── README.md          # Documentation (Chinese)
├── README_EN.md       # Documentation (English)
└── src/
    ├── agent.py       # Core Agent logic
    ├── tools.py       # Toolset (File ops, Command exec, Security checks)
    ├── prompts.py     # System Prompts for each mode
    ├── session.py     # Session management
    ├── types.py       # Type definitions
    └── llm_config.json # LLM Configuration
```
