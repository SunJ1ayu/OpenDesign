// 聊天流式渲染的纯逻辑层(T5,design.md D-C3)。
// 协议事实以 docs/nanobot-ws-protocol.md §2(T0 实抓)为准:
//   - 出站信封一律带 webui:true + turn_id(一等路径,消息实时进 transcript);
//   - 出站事件序列 = delta(按 stream_id 归组拼接)→ stream_end 定稿
//     → turn_end 收尾解锁输入;
//   - reasoning_* / goal_status / session_updated / tool_hint / progress
//     以及将来才有的事件一律忽略不崩(协议会长)。
//   - **没有 kind 的 message** = 一条没走流式的完整助手消息(模型出错的整句原文、助手用 message
//     工具主动发的话、定时推送、斜杠命令回复):上屏(track opendesign-chat-error-visible)。
// 全部纯函数,不碰 DOM/ws,node --test 直接可测;节流是 UI 层的事,不在这里。

import { describeModelError } from "./modelError.ts";
import { describeSystemNote } from "./systemNote.ts";

export interface ChatMessage {
  id: string; // assistant = stream_id;user = 本地生成 id
  role: "user" | "assistant";
  content: string;
  streaming: boolean;
  /** 出站信封里的 `turn_id`。gateway 会把它原样写进历史回放的 `turnId` 字段
   *  (2026-08-05 对活 gateway 实抓确认过),重连对账必须用这个真身份,否则同一句话
   *  说两遍时只能靠文本猜,会把用户断线时发出的第二遍吃掉。 */
  turnId?: string;
  /** 本条带的图(track opendesign-chat-image / -p2)。本地发出的 src=data URL,
   * 历史回放的 src=网关签名地址(见 BubbleMedia)。 */
  media?: BubbleMedia[];
  /** 这条是「模型 / 助手出错」的说明(track opendesign-chat-error-visible):content 已是给人看的中文,
   *  raw = 网关原文(key 形状的串已打码),以小字附着备查。实时与回放都由 describeModelError 产生。 */
  modelError?: { raw: string; rawLabel: string };
  /** 网关的英文系统句(停止回话、子任务空回报)换成的一行中文**系统小字**,不是助手回复
   *  (track opendesign-composer-zcode;上一单欠账 R1)。content 已是中文。 */
  systemNote?: true;
}

/** 一条非流式的完整助手消息:整条就是网关出错壳 ⇒ 换成人话 + 原文;否则原样。
 *  实时(applyEvent)与回放(hydrateFromThread)共用 ⇒ 切走再回来是同一句。 */
function assistantBubble(id: string, text: string): ChatMessage {
  const note = describeSystemNote(text);
  if (note) return { id, role: "assistant", content: note, streaming: false, systemNote: true };
  const err = describeModelError(text);
  return err
    ? { id, role: "assistant", content: err.text, streaming: false,
        modelError: { raw: err.raw, rawLabel: err.rawLabel } }
    : { id, role: "assistant", content: text, streaming: false };
}

export interface TranscriptState {
  messages: ChatMessage[];
  busy: boolean; // 发出消息 → turn_end 期间锁输入
  /** 「正在思考…」。由 goal_status:running 与 reasoning_delta 驱动 —— 等待期间
   *  真正在流的就是这两个,而它们从 T5 起一直被忽略,所以从按下发送到出第一个字
   *  的那几十秒界面是死的(2026-08-04 实抓:那一轮光 reasoning_delta 就 24 帧)。
   *  第一个答案 delta 到达即关掉。 */
  thinking: boolean;
  /** 工具活动回执(人话),**不是气泡**。协议给的是事后回执不是进度:
   *  `tool_events[].phase` 实测只有 `"end"` ⇒ 不做进度条,不编数据。
   *  turn_end 清空。 */
  activity: string[];
  /** 业主点了 ■ 停止、网关还没回话:值 = 发出去的那条 `/stop` 的 turn_id(track opendesign-composer-zcode)。
   *  网关停下后只发 goal_status:idle + 一句回话,**不发 turn_end**(探针 evidence/20260925-probe-stop.txt)⇒
   *  只有这个标记在时,idle 才算这一轮结束;没点过停止的 idle 不解锁(4c C2:正常回复只认 turn_end)。 */
  stopPending?: string;
}

export const emptyTranscript: TranscriptState = Object.freeze({
  messages: [],
  busy: false,
  thinking: false,
  activity: [],
});

/** 工具原名 → 给机主看的一句人话。
 *  映射不到的一律给通用文案:`mcp_design-studio_list_todos_tool` 这种字符串
 *  对一个室内设计师是纯噪音,**不许直接甩到界面上**(判据钉死)。 */
const TOOL_LABELS: Record<string, string> = {
  list_todos: "查了待办清单",
  read_project: "翻了项目档案",
  append_change: "记了一条变更",
  set_change_status: "更新了事项状态",
  set_due_date: "记了截止日",
  resolve_date: "算了日期",
  list_inbox: "看了收件箱",
  stage_intake: "整理了收件箱",
  set_stage: "更新了项目阶段",
  create_project: "建了项目档案",
};

/** 从 `mcp_design-studio_list_todos_tool` 这类原名里剥出中间的工具名。 */
function bareToolName(name: string): string {
  return name.replace(/^mcp_[^_]+(?:-[^_]+)*_/, "").replace(/_tool$/, "");
}

export function activityLabel(name: unknown): string {
  if (typeof name !== "string" || !name.trim()) return "查了一下资料";
  return TOOL_LABELS[bareToolName(name)] ?? "查了一下资料";
}

/** 一张随消息发出的图(协议 §2 `media`;svg 被上游显式排除,见 chat/media.ts)。 */
export interface OutboundMedia {
  data_url: string;
  name: string;
}

/** 气泡上要显示的图。`src` 两种来源:
 *  - 本地刚发出的 = data URL(所以「存进收件箱」拿得到字节);
 *  - 历史回放的 = 网关签名地址(只能看,拿不到字节 → 那条气泡不给存图按钮)。
 *  判据 h01 锁死回放项恰好是 {src,name} 两个键,别往里加东西。 */
export interface BubbleMedia {
  src: string;
  name: string;
}

/** 网关地址(与 connection.ts / STOCK_WEBUI 的 8765 同一处硬编码;换端口两处一起改)。 */
const GATEWAY_ORIGIN = "http://127.0.0.1:8765";

/**
 * 回放里的附件 → 可渲染的图。**只认 `kind==="image"` 且 url 以 `/api/media/` 开头**
 * 的签名地址(签名自带鉴权);任意外链一律拒 —— 回放数据虽来自本机网关,也不该让
 * 任意 URL 进 `<img src>`(判据 h02)。畸形一律跳过,不崩。
 */
function replayMedia(raw: unknown): BubbleMedia[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  const out: BubbleMedia[] = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const m = item as Record<string, unknown>;
    if (m.kind !== "image") continue;
    const url = m.url;
    // 前缀白名单 + 拒 `..`/`//`:浏览器会在发请求前把 `/api/media/../../x` 规范化成
    // `/x`,前缀闸就被绕过了(仍指向本机网关,面很小,但没理由留着)。
    if (typeof url !== "string" || !url.startsWith("/api/media/")) continue;
    if (url.includes("..") || url.includes("//")) continue;
    const name = typeof m.name === "string" && m.name ? m.name : "图片";
    out.push({ src: GATEWAY_ORIGIN + url, name });
  }
  return out.length > 0 ? out : undefined;
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
    // 回放里模型出错那一轮就是一条 assistant 行、内容是英文原文(探针核实)⇒ 与实时同一句人话
    const msg: ChatMessage = role === "assistant"
      ? assistantBubble(id, r.content)
      : { id, role, content: r.content, streaming: false };
    if (typeof r.turnId === "string" && r.turnId !== "") msg.turnId = r.turnId;
    // -p2:回放里带着图(网关的签名 URL)。以前这里把它丢了,于是"切走再回来,
    // 发过的图就没了" —— 图从来没丢,是这一行没接(用户实测报的那条)。
    const media = replayMedia(r.media);
    if (media) msg.media = media;
    messages.push(msg);
  }
  return { messages, busy: false, thinking: false, activity: [] };
}

/** 用户消息本地上屏 + 锁输入(回显不靠 ws,协议不回放自己的消息)。 */
export function appendLocalUser(
  state: TranscriptState,
  content: string,
  id: string,
  media?: OutboundMedia[],
  turnId?: string,
): TranscriptState {
  const msg: ChatMessage = { id, role: "user", content, streaming: false };
  if (turnId) msg.turnId = turnId;
  // 出站信封那份是 {data_url,name}(协议要求),气泡这份统一成 {src,name}:
  // src 就是同一个 data URL,所以「存进收件箱」照样拿得到字节,不必存两份。
  if (media && media.length > 0) {
    msg.media = media.map((m) => ({ src: m.data_url, name: m.name }));
  }
  // 新发一轮:上一轮的活动回执清掉(它属于上一轮),等待态交给事件去开;上一轮的停止标记也不许带进来(评审 R2)
  return withoutStop({ ...state, messages: [...state.messages, msg], busy: true, activity: [] });
}

/**
 * 重连后把服务端历史与本地残留对账。服务端历史排在前面,只把服务端还没记上的
 * 本地 user 补到尾部;assistant 一律丢弃,因为断线时本地只可能留下半截回复,
 * 完整答案必须以服务端回放为准。
 *
 * 认人的规矩:**本地那条有 turnId 就只看 turnId**(gateway 把我们发的 turn_id
 * 原样写进每一条 user 行,2026-08-05 抽样实测 7 个会话 7/7);只有本地那条根本
 * 没有 turnId 时——比如它本身就是从服务端回放前插进来的——才退回老的"文本+角色"启发式。
 *
 * ⚠️ 曾经在"有 turnId"这一支上还兜了一层文本比对,08-05 四审后删掉:它会把
 * **用户今天又说了一遍的那句上周的话**当成上周那条吃掉 —— 正是本单要消灭的病
 * 换了个入口回来。万一"服务端记下了却没写 turnId"真的发生,后果是多一个气泡,
 * 那远好于少一句话。
 */
export function reconcileThread(
  local: ChatMessage[],
  replay: ChatMessage[],
): ChatMessage[] {
  const replayUserTurnIds = new Set<string>();
  const replayUserTexts = new Set<string>();
  for (const m of replay) {
    if (m.role !== "user") continue;
    replayUserTexts.add(`${m.role}\u0000${m.content}`);
    if (m.turnId) replayUserTurnIds.add(m.turnId);
  }

  const localOnly = local.filter((m) => {
    if (m.role !== "user") return false;
    if (m.turnId) return !replayUserTurnIds.has(m.turnId);
    return !replayUserTexts.has(`${m.role}\u0000${m.content}`);
  });
  return [...replay, ...localOnly];
}

/** 这一轮收尾:解锁输入,兜底定稿所有仍在流的消息(stream_end 丢了也不卡界面),
 *  并清掉本轮的等待态、活动回执与停止标记(下一轮不该顶着上一轮的尾巴)。turn_end 与「停下了」共用。 */
function finishTurn(state: TranscriptState): TranscriptState {
  return {
    busy: false,
    thinking: false,
    activity: [],
    messages: state.messages.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
  };
}

/** 去掉停止标记(不留 `stopPending: undefined` 这个键,老判据按整形比较状态)。 */
function withoutStop(state: TranscriptState): TranscriptState {
  if (state.stopPending === undefined) return state;
  const { stopPending: _drop, ...rest } = state;
  return rest;
}

/** 放掉这一轮(断线重连后拉不到历史时用):解锁、收思考与活动行,**连停止标记一起清**(评审 R2:
 *  点了 ■ 回话没到就断线,标记留着 ⇒ 下一轮 ■ 一直灰)。不定稿流式正文 —— 与原来这条路的行为一致。 */
export function releaseTurn(state: TranscriptState): TranscriptState {
  return withoutStop({ ...state, busy: false, thinking: false, activity: [] });
}

/** 点了 ■:记下这条 `/stop` 的 turn_id,等网关回话。不在回复中 ⇒ 什么都不变(按钮本来就不该在)。
 *  不本地先解锁:连接刚断时 /stop 没送到,先解锁会让业主以为停了(design.md Alternatives)。 */
export function requestStop(state: TranscriptState, turnId: string): TranscriptState {
  return state.busy ? { ...state, stopPending: turnId } : state;
}

/** 没有 kind 的 message → 追加一条完整的助手气泡(出错壳换成人话)。
 *  id 由 turn_id + turn_seq 派生:同一帧收两次只算一条;缺了(定时推送等)就按序号,不互相吞。
 *  busy 不动(仍由 turn_end / error 解锁);「正在思考」收掉 —— 回复已经到了。 */
function appendNote(state: TranscriptState, e: Record<string, unknown>): TranscriptState {
  if (typeof e.text !== "string" || !e.text.trim()) return state;
  const id = typeof e.turn_id === "string" && e.turn_id && typeof e.turn_seq === "number"
    ? `note-${e.turn_id}-${e.turn_seq}`
    : `note-${state.messages.length}`;
  const bubble = assistantBubble(id, e.text);
  // 停止回话先于 idle 到(时序换了)也要收尾 —— 但只认**这次** /stop 的回话:网关原样带回我们发的 turn_id(探针)。
  // 等回话那一瞬来一句后台子任务回报(也是系统小字)不许提前解锁(评审 R3)
  const stopped = !!(state.stopPending && bubble.systemNote && e.turn_id === state.stopPending);
  if (state.messages.some((m) => m.id === id)) return stopped ? finishTurn(state) : state;
  const next = { ...state, thinking: false, messages: [...state.messages, bubble] };
  return stopped ? finishTurn(next) : next;
}

/** 入站事件 → 新 state。认不出/畸形的一律原样返回(安全降级)。 */
export function applyEvent(state: TranscriptState, ev: unknown): TranscriptState {
  if (typeof ev !== "object" || ev === null) return state;
  const e = ev as Record<string, unknown>;
  switch (e.event) {
    case "goal_status":
      // 本栏点过 ■ 之后的 idle = 网关已经停下(它不发 turn_end)⇒ 这一轮结束;别的 idle 不动(4c C2)
      if (e.status === "idle") return state.stopPending ? finishTurn(state) : state;
      // 等待态开
      return e.status === "running" && !state.thinking
        ? { ...state, thinking: true }
        : state;
    case "reasoning_delta":
      // 只取"它还活着"这一个信号,**正文一个字都不进 messages[]** ——
      // 那是没定稿的草稿,展示它等于把草稿当结论给用户看(判据钉死)
      return state.thinking ? state : { ...state, thinking: true };
    case "message": {
      // 没有 kind:网关约定这类消息**从不与流式正文重复**(带 `_streamed` 的最终回复 manager 不走 send(),
      // 见 nanobot channels/manager.py `_send_once`、agent/loop.py `_assemble_outbound`)。
      // 以前一律丢 ⇒ 模型出错时业主发完一句「没反应」(QA 录像第 9 步)。
      if (e.kind === undefined || e.kind === null) return appendNote(state, e);
      if (e.kind !== "progress" && e.kind !== "tool_hint") return state;
      const raw = Array.isArray(e.tool_events) ? e.tool_events : [];
      const lines: string[] = [];
      for (const t of raw) {
        if (typeof t !== "object" || t === null) continue;
        lines.push(activityLabel((t as Record<string, unknown>).name));
      }
      if (lines.length === 0) return state;
      return { ...state, activity: [...state.activity, ...lines] };
    }
    case "delta": {
      if (typeof e.stream_id !== "string" || typeof e.text !== "string") return state;
      // 第一个答案字一出来就收掉「正在思考」(别和正文一起挂着)
      state = state.thinking ? { ...state, thinking: false } : state;
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
      // 停止标记一起清(评审 R2:点了 ■ 回话没到就出错收尾,标记留着 ⇒ 下一轮 ■ 一直灰)
      return state.busy || state.stopPending ? withoutStop({ ...state, busy: false }) : state;
    case "turn_end":
      return finishTurn(state);
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
