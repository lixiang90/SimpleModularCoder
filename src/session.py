from typing import List
from .types import Message, Role

class Session:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.history: List[Message] = []
        # 初始化时加入 System Prompt
        self.history.append(Message(role="system", content=system_prompt))

    def add_user_message(self, content: str):
        self.history.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str, tool_calls=None):
        self.history.append(Message(role="assistant", content=content, tool_calls=tool_calls))

    def add_tool_output(self, tool_call_id: str, tool_name: str, output: str):
        self.history.append(Message(
            role="tool",
            content=output,
            tool_call_id=tool_call_id,
            name=tool_name
        ))

    def get_context(self) -> List[dict]:
        """
        获取用于发送给 LLM 的完整上下文列表
        """
        return [msg.to_dict() for msg in self.history]

    def render_history(self):
        """
        辅助函数：打印当前会话历史
        """
        print("\n=== Session History ===")
        for msg in self.history:
            print(f"[{msg.role.upper()}]: {msg.content}")
            if msg.tool_calls:
                print(f"  -> Tool Calls: {msg.tool_calls}")
            if msg.role == "tool":
                print(f"  -> For Call ID: {msg.tool_call_id}")
        print("=======================\n")
