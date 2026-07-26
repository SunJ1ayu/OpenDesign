// 聊天流式渲染的纯逻辑层(T5,design.md D-C3)。
// 协议事实以 docs/nanobot-ws-protocol.md §2(T0 实抓)为准:
//   - 出站信封一律带 webui:true + turn_id(一等路径,消息实时进 transcript);
//   - 出站事件序列 = delta(按 stream_id 归组拼接)→ stream_end 定稿
//     → turn_end 收尾解锁输入;
//   - reasoning_* / goal_status / session_updated / tool_hint / progress
//     以及将来才有的事件一律忽略不崩(协议会长)。
// 全部纯函数,不碰 DOM/ws,node --test 直接可测;节流是 UI 层的事,不在这里。

export interface ChatMessage {
  id: string; // assistant = stream_id;user = 本地生成 id
  role: "user" | "assistant";
  content: string;
  streaming: boolean;
  /** 本条随手发出去的图(track opendesign-chat-image)。只有本地上屏的用户消息才有:
   * 历史回放里图是签名链接、形态不同,本期不还原(non-goal)。 */
  media?: OutboundMedia[];
}

export interface TranscriptState {
  messages: ChatMessage[];
  busy: boolean; // 发出消息 → turn_end 期间锁输入
}

export const emptyTranscript: TranscriptState = Object.freeze({
  messages: [],
  busy: false,
});

/** 一张随消息发出的图(协议 §2 `media`;svg 被上游显式排除,见 chat/media.ts)。 */
export interface OutboundMedia {
  data_url: string;
  name: string;
}

/** 出站信封(协议 §2 入站)。
 * `media` 可选:**没图时信封里不出现这个键**(老形状逐字节不变,免得给上游多一个
 * 待解析字段;空数组同样不出现——空 media 没有任何意义)。 */
export function messageEnvelope(
  chatId: string,
  content: string,
  turnId: string,
  media?: OutboundMedia[],
) {
  const env: {
    type: "message";
    chat_id: string;
    content: string;
    webui: true;
    turn_id: string;
    media?: OutboundMedia[];
  } = {
    type: "message" as const,
    chat_id: chatId,
    content,
    webui: true as const,
    turn_id: turnId,
  };
  if (media && media.length > 0) env.media = media;
  return env;
}

/** 出站 attach 信封(p6 续聊:挂回历史会话的 chat_id,协议 §2 入站)。 */
export function attachEnvelope(chatId: string) {
  return { type: "attach" as const, chat_id: chatId };
}

/**
 * webui-thread 回放 → TranscriptState(p6,design.md D2)。
 * 只收 role∈{user,assistant} 且 content 为 string 的行;跳过 kind:"trace" 与
 * 空白 assistant;id 沿用服务端的,缺/非法则 replay-<i>;回放完不锁输入。
 * 畸形 payload → null(安全降级,调用方回退空 transcript)。
 */
export function hydrateFromThread(payload: unknown): TranscriptState | null {
  if (typeof payload !== "object" || payload === null) return null;
  const raw = (payload as Record<string, unknown>).messages;
  if (!Array.isArray(raw)) return null;
  const messages: ChatMessage[] = [];
  for (let i = 0; i < raw.length; i++) {
    const m = raw[i];
    if (typeof m !== "object" || m === null) continue;
    const r = m as Record<string, unknown>;
    if (r.kind === "trace") continue;
    const role = r.role;
    if (role !== "user" && role !== "assistant") continue;
    if (typeof r.content !== "string") continue;
    if (role === "assistant" && !r.content.trim()) continue;
    const id = typeof r.id === "string" && r.id ? r.id : `replay-${i}`;
    messages.push({ id, role, content: r.content, streaming: false });
  }
  return { messages, busy: false };
}

/** 用户消息本地上屏 + 锁输入(回显不靠 ws,协议不回放自己的消息)。 */
export function appendLocalUser(
  state: TranscriptState,
  content: string,
  id: string,
  media?: OutboundMedia[],
): TranscriptState {
  const msg: ChatMessage = { id, role: "user", content, streaming: false };
  if (media && media.length > 0) msg.media = media;
  return { messages: [...state.messages, msg], busy: true };
}

/** 入站事件 → 新 state。认不出/畸形的一律原样返回(安全降级)。 */
export function applyEvent(state: TranscriptState, ev: unknown): TranscriptState {
  if (typeof ev !== "object" || ev === null) return state;
  const e = ev as Record<string, unknown>;
  switch (e.event) {
    case "delta": {
      if (typeof e.stream_id !== "string" || typeof e.text !== "string") return state;
      // role 守卫:stream_id 万一撞上本地用户消息 id(服务端 bug),不往用户气泡里拼
      const i = state.messages.findIndex(
        (m) => m.role === "assistant" && m.id === e.stream_id,
      );
      if (i === -1) {
        return {
          ...state,
          messages: [
            ...state.messages,
            { id: e.stream_id, role: "assistant", content: e.text, streaming: true },
          ],
        };
      }
      const messages = state.messages.slice();
      messages[i] = { ...messages[i], content: messages[i].content + e.text };
      return { ...state, messages };
    }
    case "stream_end": {
      if (typeof e.stream_id !== "string") return state;
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === e.stream_id ? { ...m, streaming: false } : m,
        ),
      };
    }
    case "error":
      // 协议快照未覆盖失败路径:一轮出错若只发 error 不发 turn_end,
      // busy 会死锁到刷新。error 一律解锁(attach 场景的 error 到 T7 才有)。
      return state.busy ? { ...state, busy: false } : state;
    case "turn_end":
      // 收尾:解锁输入,兜底定稿所有仍在流的消息(stream_end 丢了也不卡界面)
      return {
        busy: false,
        messages: state.messages.map((m) =>
          m.streaming ? { ...m, streaming: false } : m,
        ),
      };
    default:
      return state;
  }
}

/**
 * Enter 是否发送(F8):中文输入法候选确认时 isComposing=true
 * (老 IME 用 keyCode 229 兜底),不能把半截拼音发出去;Shift+Enter 换行。
 */
export function shouldSendOnEnter(ev: {
  key: string;
  shiftKey?: boolean;
  isComposing?: boolean;
  keyCode?: number;
}): boolean {
  return (
    ev.key === "Enter" && !ev.shiftKey && !ev.isComposing && ev.keyCode !== 229
  );
}
