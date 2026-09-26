// 网关的英文系统句 → 一行中文系统小字(track opendesign-composer-zcode;上一单欠账 R1)。
// 这几句都是无 kind 的 message,以前会原样英文上屏,回放里也各是一条助手行:
//   “Stopped N task(s).” / “No active task to stop.”   —— /stop 的回话(nanobot command/builtin.py:128-133)
//   “Background task completed.”                       —— 子任务没有正文时的空回报(nanobot agent/loop.py:1228)
// 实时(applyEvent)与回放(hydrateFromThread)都过这一个函数 ⇒ 切走再回来是同一句。只认整句,正文里提到不算。

const STOPPED = /^Stopped \d+ task\(s\)\.$/;

export function describeSystemNote(content: string): string | null {
  if (typeof content !== "string") return null;
  const t = content.trim();
  // 停在记账 / 挪文件中间时,那一步是独立进程里的工具,照常做完(design.md「完全实现仍可能失败」②,QA Gemini)
  if (STOPPED.test(t)) return "已停止(已经开始的那一步可能已做完)";
  if (t === "No active task to stop.") return "这次回复已经说完了,没有要停的";
  if (t === "Background task completed.") return "后台任务做完了";
  return null;
}
