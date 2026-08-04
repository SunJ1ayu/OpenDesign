// 重连策略单独放在纯逻辑层，是为了让 React 接线层只负责执行连接与计时，
// 不把一次性 token、口令失效和退避规则混进浏览器生命周期。这里不接触 DOM、
// WebSocket 或定时器，只根据刚发生的事件返回下一步动作。来源:opendesign-chat-reconnect T6。

export const BACKOFF_MS = [500, 1000, 2000, 4000, 8000, 15000] as const;
export const JITTER = 0.15;

export type ReconnectMode = "connected" | "waiting" | "stopped";

export interface ReconnectState {
  failures: number;
  mode: ReconnectMode;
}

export type ReconnectAction =
  | { kind: "none" }
  | { kind: "schedule"; delayMs: number }
  | { kind: "login" };

export interface ReconnectResult {
  state: ReconnectState;
  action: ReconnectAction;
}

export const initialReconnect: ReconnectState = Object.freeze({
  failures: 0,
  mode: "connected",
});

const NONE: ReconnectAction = Object.freeze({ kind: "none" });

/** 只认错误名，避免不同 realm 或打包副本让 instanceof 失效。 */
export function isPasswordFailure(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "PasswordRejected"
  );
}

function scheduleRetry(
  state: ReconnectState,
  rand: () => number,
): ReconnectResult {
  const index = Math.min(state.failures, BACKOFF_MS.length - 1);
  const baseDelay = BACKOFF_MS[index];
  const factor = 1 - JITTER + 2 * JITTER * rand();

  return {
    state: { failures: state.failures + 1, mode: "waiting" },
    action: { kind: "schedule", delayMs: Math.round(baseDelay * factor) },
  };
}

/** 根据连接事件计算下一状态与动作；动作由接线层执行，本函数不产生外部副作用。 */
export function reduceReconnect(
  state: ReconnectState,
  event: unknown,
  rand: () => number = Math.random,
): ReconnectResult {
  if (typeof event !== "object" || event === null || !("type" in event)) {
    return { state, action: NONE };
  }

  const type = event.type;
  if (type === "connected") {
    return { state: initialReconnect, action: NONE };
  }

  if (state.mode === "stopped") {
    return { state, action: NONE };
  }

  if (type === "online" || type === "visible") {
    if (state.mode === "connected") return { state, action: NONE };
    return {
      state: { failures: 0, mode: "waiting" },
      action: { kind: "schedule", delayMs: 0 },
    };
  }

  if (type === "failed") {
    const error = "error" in event ? event.error : undefined;
    if (isPasswordFailure(error)) {
      return {
        state: { failures: state.failures, mode: "stopped" },
        action: { kind: "login" },
      };
    }
    return scheduleRetry(state, rand);
  }

  if (type === "closed") return scheduleRetry(state, rand);

  return { state, action: NONE };
}
