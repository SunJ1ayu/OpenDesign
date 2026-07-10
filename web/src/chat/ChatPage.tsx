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

// T5(半):消息收发 + 流式渲染。协议按 docs/nanobot-ws-protocol.md §2:
// 发 = 信封带 webui:true+turn_id,本地上屏并锁发送;收 = delta 按 stream_id
// 归组拼接 → stream_end 定稿 → turn_end 解锁。事件先进缓冲,80ms 节流批量
// 过 reducer(delta 每帧一 setState 会把渲染打爆)。断线自愈/会话列表是 T6/T7。

const STOCK_WEBUI = "http://127.0.0.1:8765/";
const FLUSH_MS = 80;

type View =
  | { kind: "login" }
  | { kind: "connecting" }
  | { kind: "connected"; chatId: string; model?: string }
  | { kind: "error"; msg: string };

function StockLink() {
  return (
    <a href={STOCK_WEBUI} target="_blank" rel="noreferrer">
      打开原版界面（127.0.0.1:8765）
    </a>
  );
}

export default function ChatPage() {
  const session = useMemo(() => new ChatSession(), []);
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

  // 新内容到就贴底(半 T5 简单版:一律贴底,不做"看历史时不打扰")
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

  if (view.kind === "login") {
    return (
      <div className="chat-shell">
        <div className="chat-empty">
          <form
            className="chat-login"
            onSubmit={(e) => {
              e.preventDefault();
              login();
            }}
          >
            <h2>连接聊天服务</h2>
            <p className="muted">
              输入 nanobot WebUI 的访问口令。只需一次,保存在本机浏览器。
            </p>
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
      </div>
    );
  }

  if (view.kind === "connecting") {
    return (
      <div className="chat-shell">
        <div className="chat-empty">
          <p>正在连接聊天服务…</p>
        </div>
        <div className="chat-inputbar">给 OpenDesign 发消息…（连接中）</div>
      </div>
    );
  }

  if (view.kind === "error") {
    return (
      <div className="chat-shell">
        <div className="chat-banner">
          <span>{view.msg}。请确认 nanobot gateway 已启动。</span>
          <span className="chat-banner-actions">
            <button className="chat-btn" onClick={() => setAttempt((n) => n + 1)}>
              重试
            </button>
            <button className="chat-btn" onClick={logout}>
              退出登录
            </button>
          </span>
        </div>
        <div className="chat-empty">
          <p>
            连接恢复前可以先用 <StockLink />
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-shell">
      <div className="chat-status">
        <span className="chat-status-dot" aria-hidden="true" />
        <span>
          已连接{view.model ? ` · ${view.model}` : ""} · 会话 {view.chatId.slice(0, 8)}
        </span>
        <button className="chat-btn subtle" onClick={logout}>
          退出登录
        </button>
      </div>
      {transcript.messages.length === 0 ? (
        <div className="chat-empty">
          <p>连接就绪,说点什么吧——比如「记一下:张三家玄关柜改到 2.4 米」。</p>
        </div>
      ) : (
        <div className="chat-messages" ref={scrollRef}>
          {transcript.messages.map((m) => (
            <div key={m.id} className={`chat-msg ${m.role}`}>
              <div className={`chat-msg-body${m.streaming ? " streaming" : ""}`}>
                {m.role === "assistant" ? renderMarkdown(m.content) : m.content}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="chat-inputbar live">
        <textarea
          rows={2}
          value={draft}
          placeholder={transcript.busy ? "回复中…" : "给 OpenDesign 发消息,Enter 发送,Shift+Enter 换行"}
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
        <button
          className="chat-btn primary"
          disabled={transcript.busy || !draft.trim()}
          onClick={send}
        >
          发送
        </button>
      </div>
    </div>
  );
}
