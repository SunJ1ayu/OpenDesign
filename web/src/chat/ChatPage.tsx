import { useEffect, useMemo, useRef, useState } from "react";
import { ChatSession, PasswordRejected, type BootstrapInfo } from "./connection";

// T4 聊天页 = 登录/连接流。消息收发(流式渲染)是 T5,这里先把连接立起来:
// 口令一次 → localStorage → 每次开 ws 前新签一次性 token(StrictMode 双连各自签,
// 由 connection.ts 保证)→ ready 即已连接;口令被拒弹回登录,其余错误走横幅,
// 横幅里永远给"打开原版界面"保底链接(design D-C4)。

const STOCK_WEBUI = "http://127.0.0.1:8765/";

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
  const pwRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!session.hasPassword()) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let info: BootstrapInfo | null = null;
    setView({ kind: "connecting" });

    session
      .openSocket()
      .then((r) => {
        if (cancelled) {
          (r.socket as WebSocket).close();
          return;
        }
        ws = r.socket as WebSocket;
        info = r.info;
        ws.onmessage = (ev) => {
          if (cancelled) return;
          try {
            const m = JSON.parse(ev.data);
            if (m.event === "ready" && typeof m.chat_id === "string") {
              setView({ kind: "connected", chatId: m.chat_id, model: info?.model_name });
            }
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
      ws?.close();
    };
  }, [session, attempt]);

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
      <div className="chat-empty">
        <p>连接就绪。消息收发在下一轮交付（T5）。</p>
        <p>
          现在发消息请用 <StockLink />
        </p>
      </div>
      <div className="chat-inputbar">给 OpenDesign 发消息…（T5 开通）</div>
    </div>
  );
}
