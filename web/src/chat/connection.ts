// 聊天登录/连接流的纯逻辑层(T4,design.md D-C2)。
// 协议事实以 docs/nanobot-ws-protocol.md(T0 实抓)为准:
//   - GET /api/chat/bootstrap(ds_web 代理 → /webui/bootstrap)是 token 唯一来源,
//     Bearer <口令>;一张 token 同时可用于 ws 握手 + HTTP API。
//   - ws 握手 token 一次性消费 → 每次开 ws 前必须新签(多标签/StrictMode 各自签)。
//   - HTTP 401 = api token 过期 → 透明重签一次;重 bootstrap 也 401 = 口令失效。
//   - ws 地址用 ws_path + 已知端口自拼,ws_url 只作参考(它按 Host 头拼,不可信)。
// 全部外设(fetch/WebSocket/storage/uuid)依赖注入,浏览器外可测。

export const PASSWORD_KEY = "ds-chat-password";

export interface BootstrapInfo {
  token: string;
  ws_path: string;
  ws_url?: string;
  expires_in?: number;
  model_name?: string;
}

// 只依赖用得到的最小面,方便测试替身
export interface ResponseLike {
  status: number;
  json(): Promise<unknown>;
}
type FetchLike = (url: string, init?: {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}) => Promise<ResponseLike>;
type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export interface ChatSessionDeps {
  fetchFn?: FetchLike;
  storage?: StorageLike;
  wsFactory?: (url: string) => unknown;
  randomId?: () => string;
  nanobotPort?: number;
}

/** 口令被拒/失效:UI 捕获后弹回登录。其余错误 = 服务问题,走错误横幅。 */
export class PasswordRejected extends Error {
  constructor(message = "口令未通过验证") {
    super(message);
    this.name = "PasswordRejected";
  }
}

export class ChatSession {
  private fetchFn: FetchLike;
  private storage: StorageLike;
  private wsFactory: (url: string) => unknown;
  private randomId: () => string;
  private nanobotPort: number;
  private apiToken: string | null = null;

  constructor(deps: ChatSessionDeps = {}) {
    this.fetchFn = deps.fetchFn ?? ((url, init) => fetch(url, init));
    this.storage = deps.storage ?? window.localStorage;
    this.wsFactory = deps.wsFactory ?? ((url) => new WebSocket(url));
    this.randomId = deps.randomId ?? (() => crypto.randomUUID());
    this.nanobotPort = deps.nanobotPort ?? 8765;
  }

  hasPassword(): boolean {
    return !!this.storage.getItem(PASSWORD_KEY);
  }

  setPassword(pw: string): void {
    this.storage.setItem(PASSWORD_KEY, pw);
    this.apiToken = null; // 换口令后旧 token 不再可信
  }

  clearPassword(): void {
    this.storage.removeItem(PASSWORD_KEY);
    this.apiToken = null;
  }

  /** 签一张新 token(ws 握手 + HTTP API 双用),并缓存作 api token。
   *  有手输口令时继续用 Bearer 兜底;没有口令时不带 Authorization,交给 ds_web 代签。 */
  async bootstrap(): Promise<BootstrapInfo> {
    const pw = this.storage.getItem(PASSWORD_KEY);
    const init: { headers?: Record<string, string> } = {};
    if (pw) {
      // fetch 的 header 值只收 Latin-1;中文等字符会抛 TypeError,被误读成
      // "服务故障"。提前转成登录错误,给用户可行动的提示。
      // eslint-disable-next-line no-control-regex
      if (/[^\x20-\xFF]/.test(pw)) {
        throw new PasswordRejected("口令含中文或特殊字符,浏览器无法发送——请在 nanobot 配置里换成字母数字口令");
      }
      init.headers = { Authorization: `Bearer ${pw}` };
    }
    const res = await this.fetchFn("/api/chat/bootstrap", init);
    if (res.status === 401) throw new PasswordRejected();
    if (res.status !== 200) {
      throw new Error(`bootstrap 失败:HTTP ${res.status}(gateway 未启动?)`);
    }
    const info = (await res.json()) as BootstrapInfo;
    this.apiToken = info.token;
    return info;
  }

  /**
   * 带鉴权调 ds_web 聊天代理。401 → 透明重签一次再试;
   * 重签 401 或新 token 仍 401 → PasswordRejected(有界,不循环)。
   */
  async apiFetch(
    path: string,
    init?: { method?: string; headers?: Record<string, string>; body?: string },
  ): Promise<ResponseLike> {
    if (!this.apiToken) await this.bootstrap();
    const call = () =>
      this.fetchFn(path, {
        ...init,
        // Authorization 后展开:调用方传入的 headers 不得覆盖鉴权
        headers: { ...init?.headers, Authorization: `Bearer ${this.apiToken}` },
      });
    let res = await call();
    if (res.status === 401) {
      await this.bootstrap(); // 口令错在这里直接抛 PasswordRejected
      res = await call();
      if (res.status === 401) throw new PasswordRejected();
    }
    return res;
  }

  /**
   * 开一条 ws:每次都新签(握手 token 一次性消费,复用必 401)。
   * 地址 = ws_path + 已知端口自拼;ws_url 按上游 Host 头生成,不作依据。
   */
  async openSocket(): Promise<{ socket: unknown; info: BootstrapInfo }> {
    const info = await this.bootstrap();
    const path = info.ws_path?.startsWith("/") ? info.ws_path : "/";
    const q = new URLSearchParams({
      client_id: this.randomId(),
      token: info.token,
    });
    const url = `ws://127.0.0.1:${this.nanobotPort}${path}?${q}`;
    return { socket: this.wsFactory(url), info };
  }
}
