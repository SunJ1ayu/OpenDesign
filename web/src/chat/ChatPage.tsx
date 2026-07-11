import { useEffect, useMemo, useRef, useState } from "react";
import { ChatSession, PasswordRejected, type BootstrapInfo } from "./connection";
import {
  emptyTranscript,
  appendLocalUser,
  applyEvent,
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
};

function StockLink() {
  return (
    <a href={STOCK_WEBUI} target="_blank" rel="noreferrer">
      打开原版界面（127.0.0.1:8765）
    </a>
  );
}

export default function ChatPage({ session: sessionProp, prefill }: Props) {
  const fallback = useMemo(() => new ChatSession(), []);
  const session = sessionProp ?? fallback;
  const [view, setView] = useState<View>(() =>
    session.hasPassword() ? { kind: "connecting" } : { kind: "login" },
  );
  const [loginError, setLoginError] = useState("");
  const [attempt, setAttempt] = useState(0); // 递增触发重连 effect
  const [transcript, setTranscript] = useState<TranscriptState>(emptyTranscript);
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
    setTranscript(emptyTranscript); // 每条连接都是新 chat_id,历史回补是 T6/T7

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
              setView({ kind: "connected", chatId: m.chat_id, model: info?.model_name });
              return;
            }
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
  }, [session, attempt]);

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

  const send = () => {
    const content = draft.trim();
    const ws = wsRef.current;
    if (!content || transcript.busy || view.kind !== "connected" || !ws) return;
    ws.send(JSON.stringify(messageEnvelope(view.chatId, content, crypto.randomUUID())));
    setTranscript((s) => appendLocalUser(s, content, `local-${crypto.randomUUID()}`));
    setDraft("");
  };

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
            ↑
          </button>
        </div>
      </div>
    </div>
  );

  if (view.kind === "login") {
    return (
      <>
        <div className="chat-fill">
          <form
            className="chat-login"
            onSubmit={(e) => {
              e.preventDefault();
              login();
            }}
          >
            <h2>连接聊天服务</h2>
            <p className="muted">输入 nanobot WebUI 的访问口令。只需一次,保存在本机浏览器。</p>
            <input
              ref={pwRef}
              type="password"
              placeholder="访问口令"
              autoFocus
              autoComplete="current-password"
            />
            {loginError && <p className="chat-login-error">{loginError}</p>}
            <button type="submit" className="chat-btn primary">
              连接
            </button>
          </form>
        </div>
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
        <div className="chat-fill">
          <p>连接就绪,说点什么吧——比如「记一下:张三家玄关柜改到 2.4 米」。</p>
        </div>
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
        </div>
      )}
      {inputCard}
    </>
  );
}
