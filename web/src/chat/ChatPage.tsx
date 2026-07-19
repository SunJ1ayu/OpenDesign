import { useEffect, useMemo, useRef, useState } from "react";
import { ChatSession, PasswordRejected, type BootstrapInfo } from "./connection";
import {
  emptyTranscript,
  appendLocalUser,
  applyEvent,
  attachEnvelope,
  hydrateFromThread,
  messageEnvelope,
  shouldSendOnEnter,
  type TranscriptState,
} from "./transcript";
import { renderMarkdown } from "./markdown";

// P2 T3:视觉照 handoff §4 重排(用户消息低对比右对齐 / AI 无气泡直排 /
// 赤陶流式光标 / Claude 式组合输入卡 / 「记一下」chip 预填)。
// 逻辑层零改动:connection.ts / transcript.ts / markdown.ts 原样复用(硬约束,
// 各自 oracle 守着);连接流程、80ms 节流、信封与事件归组与 P1 完全一致。

const STOCK_WEBUI = "http://127.0.0.1:8765/";
const FLUSH_MS = 80;

// 3a 空态三建议 chip(handoff §5,逐字):预填不自动发,发送权在人。
const HOME_CHIPS = ["新建一个项目", "这周有哪些变更没确认?", "找一张客厅参考图"] as const;

type View =
  | { kind: "login" }
  | { kind: "connecting" }
  | { kind: "connected"; chatId: string; model?: string }
  | { kind: "error"; msg: string };

type Props = {
  /** App 级共享的会话(侧栏历史对话与聊天复用同一 token 缓存);缺省自建。 */
  session?: ChatSession;
  /** 预填输入框(「✓ 标记完成」「新建项目」等联动);nonce 变化即覆盖 draft。 */
  prefill?: { text: string; nonce: number };
  /**
   * 程序化发送(connect-ux:「接入工作区」等完整动作)。nonce 变化 → 能发就
   * 直接发(已连接且不 busy);不能发 → 降级为预填+聚焦(动作不丢,与 prefill
   * 同终态)。与 prefill 的区别:prefill=把话递到嘴边,dispatch=替用户说出去。
   */
  dispatch?: { text: string; nonce: number };
  /** 连接就绪回调(App 借此刷新侧栏历史对话;首次登录后无需刷新页面)。 */
  onConnected?: () => void;
  /** 每轮回复收尾(turn_end)回调(p6:App 借此自动刷新侧栏历史对话,免 F5)。 */
  onTurnEnd?: () => void;
  /**
   * 续聊目标(p6,design.md D1):设了 = 连接后 attach 挂回该历史会话并回放
   * thread;null/缺省 = 新对话(服务端默认新 chat_id,现行为)。nonce 变化
   * 触发重连(同一会话点两次也要重挂)。
   * project-thread:chatId 为空串 = **强制新会话**(nonce 驱动重连但不 attach,
   * 切到无映射的项目时用;null→null 切换不重连,空串补上这个缺口)。
   */
  resume?: { sessionKey: string; chatId: string; nonce: number } | null;
  /** 连上后回调真实 chat_id(ready 新会话/attached 均;项目→会话映射记账用)。 */
  onChatId?: (chatId: string) => void;
  /** attach 历史会话失败回调(映射指向已删会话时,App 借此清映射+重开自愈)。 */
  onAttachFailed?: () => void;
  /**
   * 本会话第一条消息的前缀(项目列:「【当前项目:X】」)。仅当 transcript 为空时
   * 拼上——attach 回放有内容=不是第一句,不拼;回放晚到竞态=多拼一次,无害。
   */
  firstSendPrefix?: string;
  /**
   * 展示变体(P3 T1,design.md「抽薄不 fork」):column = 2a 右列(默认),
   * home = 3a 新对话页。变体只影响 className 与空态 JSX 与输入卡外层样式;
   * 连接 effect、send、节流缓冲、Enter 判定的代码路径逐字不变(硬约束)。
   */
  variant?: "column" | "home";
};

function StockLink() {
  return (
    <a href={STOCK_WEBUI} target="_blank" rel="noreferrer">
      打开原版界面（127.0.0.1:8765）
    </a>
  );
}

export default function ChatPage({
  session: sessionProp,
  prefill,
  dispatch,
  onConnected,
  onTurnEnd,
  resume = null,
  onChatId,
  onAttachFailed,
  firstSendPrefix,
  variant = "column",
}: Props) {
  const fallback = useMemo(() => new ChatSession(), []);
  const session = sessionProp ?? fallback;
  const [view, setView] = useState<View>(() =>
    session.hasPassword() ? { kind: "connecting" } : { kind: "login" },
  );
  const [loginError, setLoginError] = useState("");
  const [attempt, setAttempt] = useState(0); // 递增触发重连 effect
  // 修改单 C(视图层,不动连接逻辑):工作区聊天列未连接时不放裸表单,顶部琥珀横幅
  // 点开 = 同一张连接卡的 modal;esc/点遮罩关(全局原则 A3)。仅 variant="column" 用。
  const [bannerOpen, setBannerOpen] = useState(false);
  useEffect(() => {
    if (!bannerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setBannerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bannerOpen]);
  const [transcript, setTranscript] = useState<TranscriptState>(emptyTranscript);
  // modal 不在提交时关(口令错时行内报错要留在眼前——修改单 C):连接成功 login 分支
  // 整体卸载,modal 自然消失;这里只负责把状态收干净,防登出后 modal 幽灵自开。
  useEffect(() => {
    if (view.kind === "connected") setBannerOpen(false);
  }, [view.kind]);
  const [draft, setDraft] = useState("");
  const pwRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null); // 当前活连接,send 用
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 预填联动:nonce 变化 → 覆盖 draft 并聚焦(不自动发送,发送权在人)
  useEffect(() => {
    if (!prefill || prefill.nonce === 0) return;
    setDraft(prefill.text);
    inputRef.current?.focus();
  }, [prefill]);

  useEffect(() => {
    if (!session.hasPassword()) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let info: BootstrapInfo | null = null;
    // 节流缓冲:本连接私有,断开即弃
    let pending: unknown[] = [];
    let timer: ReturnType<typeof setTimeout> | null = null;
    const flush = () => {
      timer = null;
      if (cancelled || pending.length === 0) return;
      const batch = pending;
      pending = [];
      setTranscript((s) => batch.reduce(applyEvent, s));
    };
    setView({ kind: "connecting" });
    setTranscript(emptyTranscript);
    // p6 续聊:本轮 effect 的恢复目标(闭包捕获;null/空 chatId = 新对话走 ready 即连上
    // ——空串是 project-thread 的「强制新会话」信号,只借 nonce 触发重连,不 attach)
    const target = resume && resume.chatId ? resume : null;
    let attached = false;
    if (target) {
      // thread 回放与建连并行;回放消息一律「前插」——无论先后到,都不覆盖
      // attach 后用户已发的新消息。失败静默降级(attach 仍成立,从空开始)。
      // key 走裸串:ds_web 代理的 _KEY_RE 白名单是 [A-Za-z0-9_:.-](含冒号、
      // 不含 %),encodeURIComponent 会把 websocket: 编成 %3A 被代理拒(e2e 实抓)
      session
        .apiFetch(`/api/chat/sessions/${target.sessionKey}/thread`)
        .then(async (r) => (r.status === 200 ? r.json() : null))
        .then((p) => {
          const replay = p === null ? null : hydrateFromThread(p);
          if (cancelled || !replay || replay.messages.length === 0) return;
          setTranscript((s) => ({ ...s, messages: [...replay.messages, ...s.messages] }));
        })
        .catch(() => {});
    }

    session
      .openSocket()
      .then((r) => {
        if (cancelled) {
          (r.socket as WebSocket).close();
          return;
        }
        ws = r.socket as WebSocket;
        info = r.info;
        wsRef.current = ws;
        ws.onmessage = (ev) => {
          if (cancelled) return;
          try {
            const m = JSON.parse(ev.data);
            if (m.event === "ready" && typeof m.chat_id === "string") {
              if (target) {
                // 服务端默认给的新 chat_id 弃用,改挂历史会话;attached 前不置连上
                ws?.send(JSON.stringify(attachEnvelope(target.chatId)));
                return;
              }
              setView({ kind: "connected", chatId: m.chat_id, model: info?.model_name });
              onChatId?.(m.chat_id);
              onConnected?.();
              return;
            }
            if (target && !attached) {
              if (m.event === "attached" && m.chat_id === target.chatId) {
                attached = true;
                setView({ kind: "connected", chatId: target.chatId, model: info?.model_name });
                onChatId?.(target.chatId);
                onConnected?.();
                return;
              }
              if (m.event === "error") {
                setView({ kind: "error", msg: "无法打开该历史对话" });
                onAttachFailed?.(); // 项目列自愈:清映射+强制新会话重连(App 层)
                return;
              }
            }
            if (m.event === "turn_end") onTurnEnd?.();
            pending.push(m);
            if (timer === null) timer = setTimeout(flush, FLUSH_MS);
          } catch {
            /* 非 JSON 帧忽略(协议会长,未知的不崩) */
          }
        };
        ws.onclose = () => {
          if (!cancelled) setView({ kind: "error", msg: "连接已断开" });
        };
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof PasswordRejected) {
          session.clearPassword();
          setLoginError("口令未通过验证,请重新输入");
          setView({ kind: "login" });
        } else {
          setView({ kind: "error", msg: e instanceof Error ? e.message : String(e) });
        }
      });

    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
      if (wsRef.current === ws) wsRef.current = null;
      ws?.close();
    };
    // resume 整体由 nonce 代表(点同一会话两次也要重挂);onConnected/onTurnEnd
    // 是稳定回调,不入依赖(与既有 onConnected 同约定)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, attempt, resume?.nonce ?? 0]);

  // 新内容到就贴底(简单版:一律贴底,不做"看历史时不打扰")
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [transcript]);

  const login = () => {
    const pw = pwRef.current?.value.trim();
    if (!pw) return;
    setLoginError("");
    session.setPassword(pw);
    setAttempt((n) => n + 1);
  };

  const logout = () => {
    session.clearPassword();
    setLoginError("");
    setView({ kind: "login" });
    // 触发 effect 清理关掉在挂的 ws;无口令时新一轮 effect 直接早退,视图留在登录
    setAttempt((n) => n + 1);
  };

  // 发送单一真相源:按钮/Enter/dispatch 三入口共用,envelope 逻辑只此一份。
  // 项目列首句拼「【当前项目:X】」前缀(transcript 为空=本会话第一句;前缀随消息
  // 上屏,对用户可见=诚实)。
  const sendText = (content: string): boolean => {
    const ws = wsRef.current;
    if (!content || transcript.busy || view.kind !== "connected" || !ws) return false;
    const outbound =
      firstSendPrefix && transcript.messages.length === 0
        ? `${firstSendPrefix}${content}`
        : content;
    ws.send(JSON.stringify(messageEnvelope(view.chatId, outbound, crypto.randomUUID())));
    setTranscript((s) => appendLocalUser(s, outbound, `local-${crypto.randomUUID()}`));
    return true;
  };

  const send = () => {
    if (sendText(draft.trim())) setDraft("");
  };

  // 程序化发送:nonce 去重(ref,不进依赖数组=每渲染都核对但只消费一次);
  // 发不出去(未连接/busy)→ 降级为预填+聚焦,动作不丢
  const dispatchedRef = useRef(0);
  useEffect(() => {
    if (!dispatch || dispatch.nonce === 0 || dispatch.nonce === dispatchedRef.current) return;
    dispatchedRef.current = dispatch.nonce;
    if (!sendText(dispatch.text)) {
      setDraft(dispatch.text);
      inputRef.current?.focus();
    }
  });

  // Claude 式组合输入卡(handoff §4:白底/14px 圆角/聚焦赤陶描边/工具行)
  const inputCard = (
    <div className="chat-inputwrap">
      <div className="chat-card">
        <textarea
          ref={inputRef}
          rows={2}
          value={draft}
          placeholder={
            view.kind !== "connected"
              ? "连接后可用…"
              : transcript.busy
                ? "回复中…"
                : variant === "home"
                  ? "聊设计、找东西,或直接说「记一下…」"
                  : "回复,或直接说「记一下…」"
          }
          disabled={view.kind !== "connected"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (
              shouldSendOnEnter({
                key: e.key,
                shiftKey: e.shiftKey,
                isComposing: e.nativeEvent.isComposing,
                keyCode: e.keyCode,
              })
            ) {
              e.preventDefault();
              send(); // busy 时 send 自己拦(锁发送不锁打字,回复中可先打下一条)
            }
          }}
        />
        <div className="tools">
          <button className="tool-sq" title="添加图片或文件(即将支持)">+</button>
          <button
            className="tool-chip"
            title="快捷开头:记一下"
            onClick={() => {
              setDraft((d) => (d.startsWith("记一下") ? d : `记一下:${d}`));
              inputRef.current?.focus();
            }}
          >
            ✎ 记一下
          </button>
          <span className="grow" />
          <button
            className="send-btn"
            title="发送(Enter)"
            disabled={view.kind !== "connected" || transcript.busy || !draft.trim()}
            onClick={send}
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );

  if (view.kind === "login") {
    // 「连接聊天服务」的正确形态(修改单 C):永远是一张卡,不是裸表单;
    // 只出现在聊天区域内,不占页面 C 位。两处复用同一张卡:
    // - home(3a):居中呈现(见 .home-pane-login 外层)。
    // - column(2a 工作区聊天列):不放表单,顶部琥珀横幅点开 modal 才现卡。
    const connectCard = (
      <div className="connect-card" data-ui="connect-card">
        <h2>连接聊天服务</h2>
        <p className="cc-desc">
          输入 nanobot WebUI 的访问口令,只需一次,保存在本机。变更记录、图墙、文件不受影响,
          现在就能用。
        </p>
        <form
          className="chat-login"
          onSubmit={(e) => {
            e.preventDefault();
            login();
          }}
        >
          <input
            ref={pwRef}
            type="password"
            placeholder="访问口令"
            autoFocus
            autoComplete="current-password"
          />
          {loginError && <p className="chat-login-error">{loginError}</p>}
          <button type="submit" className="btn-primary cc-submit">
            连接
          </button>
        </form>
        <p className="cc-hint">口令在 nanobot WebUI 设置页获取</p>
      </div>
    );

    if (variant === "home") {
      return (
        <div className="home-pane-login">
          {connectCard}
        </div>
      );
    }

    return (
      <>
        <button
          className="connect-banner"
          data-ui="connect-banner"
          onClick={() => setBannerOpen(true)}
        >
          <span className="dot" />
          未连接聊天服务
          <span className="banner-link">连接</span>
        </button>
        <div className="chat-fill-blank" />
        {bannerOpen && (
          <div className="connect-modal-mask" onClick={() => setBannerOpen(false)}>
            <div
              className="connect-modal"
              data-ui="connect-modal"
              onClick={(e) => e.stopPropagation()}
            >
              {connectCard}
            </div>
          </div>
        )}
        {inputCard}
      </>
    );
  }

  if (view.kind === "connecting") {
    return (
      <>
        <div className="chat-fill">
          <p>正在连接聊天服务…</p>
        </div>
        {inputCard}
      </>
    );
  }

  if (view.kind === "error") {
    return (
      <>
        <div className="chat-note">
          <span>{view.msg}。请确认 nanobot gateway 已启动。</span>
          <span className="acts">
            <button className="chat-btn" onClick={() => setAttempt((n) => n + 1)}>
              重试
            </button>
            <button className="chat-btn" onClick={logout}>
              退出登录
            </button>
          </span>
        </div>
        <div className="chat-fill">
          <p>
            连接恢复前可以先用 <StockLink />
          </p>
        </div>
        {inputCard}
      </>
    );
  }

  return (
    <>
      <div className="chat-meta">
        已连接{view.model ? ` · ${view.model}` : ""}
        <button
          className="icon-btn"
          style={{ float: "right", fontSize: 11 }}
          onClick={logout}
          title="退出登录"
        >
          退出登录
        </button>
      </div>
      {transcript.messages.length === 0 ? (
        variant === "home" ? (
          /* 3a 空态(handoff §5):问候语 + 620px 大输入卡 + 三建议 chip,
             除此之外不放任何内容;首条消息后走下面的普通聊天流分支 */
          <div className="home-hero">
            <div className="home-greet">今天想聊点什么?</div>
            {inputCard}
            <div className="home-chips">
              {HOME_CHIPS.map((c) => (
                <button
                  key={c}
                  className="home-chip"
                  onClick={() => {
                    setDraft(c);
                    inputRef.current?.focus();
                  }}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-fill">
            <p>连接就绪,说点什么吧——比如「记一下:张三家玄关柜改到 2.4 米」。</p>
          </div>
        )
      ) : (
        <div className="chat-msgs" ref={scrollRef}>
          {transcript.messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="msg-user">
                {m.content}
              </div>
            ) : (
              <div key={m.id} className={`msg-ai${m.streaming ? " streaming" : ""}`}>
                {renderMarkdown(m.content)}
              </div>
            ),
          )}
          {/* 思考中(connect-ux):发出→首个 delta 之间的信号真空。纯派生:
              busy 且末条还是用户消息 = 助手在想;流式一开始末条变 assistant,
              指示自然消失。无新状态、无定时器。 */}
          {transcript.busy &&
            transcript.messages[transcript.messages.length - 1]?.role === "user" && (
              <div className="msg-ai thinking" aria-label="助手思考中">
                <span className="tdot" />
                <span className="tdot" />
                <span className="tdot" />
              </div>
            )}
        </div>
      )}
      {/* 3a 空态时输入卡已在 hero 里;其余(含开聊后)一律常规吸底卡 */}
      {(variant !== "home" || transcript.messages.length > 0) && inputCard}
    </>
  );
}
