# SimpleModularCoder - 模块化自主编程 Agent

SimpleModularCoder 是一个轻量级但功能强大的模块化自主编程工具。它引入了现代软件工程中的“分而治之”思想，通过不同的 Agent 角色（架构师、构建器、程序员）协同工作，实现从高层设计到具体代码实现的自动化流程。

## 🌟 核心特性

*   **多模式 Agent**: 支持 Coder（全能）、Architect（架构设计）、Pure Architect（纯接口设计）、Builder（单模块构建）四种模式。
*   **Ralph 模式 (Iterative Repair)**: 构建器模式下内置“自动测试-修复循环”，自动运行测试用例并根据错误信息自我修正代码。
*   **安全沙箱**:
    *   **权限隔离**: Builder 模式强制锁定只能修改当前模块目录，严禁篡改测试用例和其他模块。
    *   **命令审批**: 敏感的 Shell 命令执行需要 Human-in-the-Loop 人工审批。
*   **增量更新**: 架构师和构建器均具备维护能力，支持在现有代码基础上进行接口升级和 Bug 修复。

## 🚀 快速开始

### 1. 安装依赖

确保你的 Python 环境版本 >= 3.8，并安装必要的依赖（如 `openai`, `pytest`）。

```bash
pip install openai pytest
```

### 2. 配置 LLM

在 `src/llm_config.json` 中配置你的 LLM 服务商信息（兼容 OpenAI 接口，如 DeepSeek, OpenAI, Claude 等）。

```json
{
  "api_key": "sk-...",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "temperature": 0.0
}
```

### 3. 启动 Agent

工具入口为 `run_basic.py`，支持通过 `--mode` 参数切换不同模式。

#### 🏗️ 模式一：纯架构师模式 (Pure Architect)

**适用场景**: 项目初期，需要设计系统模块、定义接口和编写测试规范，但不涉及具体实现。

```bash
python run_basic.py --mode pure_architect --dir ./workspace
```

**交互示例**:
> User: "设计一个贪吃蛇游戏系统"
>
> **Agent 产物**:
> - `dependency_graph.json`: 模块依赖关系
> - `GameLoop/interface.py`: 游戏循环接口定义
> - `GameLoop/test_spec.py`: 针对接口的测试用例
> - `GameLoop/PROMPT.md`: 实现指南

#### 🔨 模式二：构建器模式 (Builder) - 推荐 🔥

**适用场景**: 实现由架构师定义的单个模块。

```bash
python run_basic.py --mode builder --dir ./workspace
```

**交互示例**:
> User: "构建模块: ./workspace/GameLoop"
>
> **Agent 行为**:
> 1.  **锁定权限**: 只能写入 `GameLoop` 目录，禁止修改 `test_spec.py`。
> 2.  **实现代码**: 读取接口和测试，编写 `implementation.py`。
> 3.  **Ralph 循环**:
>     *   运行 `pytest GameLoop/test_spec.py`
>     *   ❌ 失败 -> 重置记忆 -> 读取错误日志 -> 修复代码
>     *   ✅ 成功 -> 任务结束

#### 🏛️ 模式三：全能架构师模式 (Architect)

**适用场景**: 快速原型开发，架构师不仅设计接口，还直接生成实现代码（不推荐用于复杂项目）。

```bash
python run_basic.py --mode architect --dir ./workspace
```

#### 💻 模式四：通用程序员模式 (Coder) - 默认

**适用场景**: 自由对话，执行任意编码任务。

```bash
python run_basic.py --mode coder --dir ./workspace
```

## 🛡️ 安全机制

1.  **命令执行**: Agent 尝试执行 `pytest` 或其他 Shell 命令时，控制台会弹出 `[SECURITY WARNING]`，需输入 `y` 确认。
2.  **文件系统约束**: Builder 模式下，系统会拦截任何试图写入非目标模块目录的操作，防止 Agent "作弊"（如修改测试用例以通过测试）。

## 📂 项目结构

```text
SimpleModularCoder/
├── run_basic.py       # 启动入口
├── README.md          # 说明文档
└── src/
    ├── agent.py       # Agent 核心逻辑
    ├── tools.py       # 工具集 (含文件操作、命令执行、安全检查)
    ├── prompts.py     # 各模式的 System Prompts
    ├── session.py     # 会话管理
    ├── types.py       # 类型定义
    └── llm_config.json # LLM 配置
```
