# 探针:网关空闲压缩(compact_idle_session 里的 retain_recent_legal_suffix(8))会不会把长对话早期的项目工具调用从对话文件里删掉
from nanobot.session.manager import Session
msgs = [{"role": "user", "content": "给翡翠湾记一笔"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
          "function": {"name": "mcp_design-studio_append_change_tool", "arguments": "{\"project\": \"翡翠湾-1801\"}"}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "mcp_design-studio_append_change_tool", "content": "{\"ok\": true}"},
        {"role": "assistant", "content": "记好了"}]
for i in range(8):
    msgs += [{"role": "user", "content": f"闲聊 {i}"}, {"role": "assistant", "content": "嗯"}]
s = Session(key="websocket:probe", messages=msgs)
dropped, _ = s.retain_recent_legal_suffix(8, extend_to_user=True)
kept_tools = [m for m in s.messages if m.get("tool_calls")]
print(f"总 {len(msgs)} 条;压缩后留 {len(s.messages)} 条;删掉 {len(dropped)} 条;留下的里还有项目工具调用: {bool(kept_tools)}")
