// 后台起没起好(外壳 → 界面;track opendesign-instant-ui)。界面不再挂横幅(opendesign-quiet-start-icons),通道留着。
export type BackendState = { phase: "starting" | "ready" };

export type DesktopUpdateState = {
  phase: "idle" | "checking" | "latest" | "downloading" | "downloaded" | "error";
  version?: string;
  percent?: number;
  error?: string;
};

export interface OdBackend {
  state(): Promise<BackendState>;
  onState(callback: (state: BackendState) => void): () => void;
}

export interface OdShell {
  minimize(): Promise<unknown>;
  toggleMaximize(): Promise<{ maximized: boolean } | null>;
  close(): Promise<unknown>;
  windowState(): Promise<{ maximized: boolean } | null>;
  onWindowState(callback: (state: { maximized: boolean }) => void): () => void;
  reportStartup(event: string, detail?: string): unknown;
  /** 后台起没起好(track opendesign-instant-ui);旧 preload 没有,用 backendApi() 取 */
  backend?: OdBackend;
  update: {
    check(): Promise<unknown>;
    install(): Promise<unknown>;
    state(): Promise<DesktopUpdateState>;
    onState(callback: (state: DesktopUpdateState) => void): () => void;
  };
}

const method = (value: unknown): value is (...args: never[]) => unknown => typeof value === "function";

export function shellApi(win: unknown = globalThis): OdShell | null {
  if (!win || typeof win !== "object") return null;
  const api = (win as { odShell?: Partial<OdShell> }).odShell;
  if (!api || !method(api.minimize) || !method(api.toggleMaximize) || !method(api.close)
      || !method(api.windowState) || !method(api.onWindowState) || !method(api.reportStartup)) return null;
  const update = api.update;
  if (!update || !method(update.check) || !method(update.install)
      || !method(update.state) || !method(update.onState)) return null;
  return api as OdShell;
}

/** 后台状态桥(新 preload 才有)。旧 preload 没有它时返回 null —— 外壳照样认得出(fb2)。 */
export function backendApi(win: unknown = globalThis): OdBackend | null {
  if (!shellApi(win)) return null;
  const backend = (win as { odShell?: { backend?: Partial<OdBackend> } }).odShell?.backend;
  if (!backend || !method(backend.state) || !method(backend.onState)) return null;
  return backend as OdBackend;
}
