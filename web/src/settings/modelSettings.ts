// 设置页 · 模型设置(照 ZCode,track opendesign-zcode-model-settings)的纯逻辑:读接口、每家状态怎么说、
// 左栏怎么分组、上下文长度怎么显示、设置页路由,以及所有写操作的发送与回包清洗。
// 界面在 ModelSettings.tsx / SettingsPage.tsx;语义全在后端 ds_credential(D1~D4)。
// 判据:tests/test_model_settings_ui.mjs(ms1~ms9)、tests/test_llm_key.mjs(a1~d3,接替旧 llmKey.ts)、
//       tests/test_llm_key_surface.mjs(本目录不许碰浏览器存储、不许打日志)。
//
// 🔴 key 在前端只过一次手:输入框 → 那一次 POST 的 body。回包里万一回显了(上游漏了),
//    这里也不当传声筒 —— postSettings 把含 key 的字符串抹掉再交给界面(c2)。

export const PROVIDERS_PATH = "/api/llm/providers";
export const PROVIDER_KEY_PATH = "/api/llm/providers/key";
export const PROVIDER_ENABLED_PATH = "/api/llm/providers/enabled";
export const PROVIDER_MODELS_PATH = "/api/llm/providers/models";
export const CUSTOM_PROVIDER_PATH = "/api/llm/providers/custom";
export const TEST_MODEL_PATH = "/api/llm/test";

export type ProviderModel = { id: string; label: string; builtin: boolean; contextWindow: number | null };
export type ProviderRow = {
  id: string;
  label: string;
  kind: "builtin" | "custom";
  apiBase: string;
  /** 「获取 API Key」链到哪;只收 https,不合格 ⇒ null(不画空链接)。 */
  keyUrl: string | null;
  /** 存了这家的 key */ configured: boolean;
  /** 末四位提示;永不是原文 */ hint: string | null;
  /** 后台(网关)手里有这把 key */ live: boolean;
  /** 正在用 */ active: boolean;
  /** 存了、等后台重启才能用 */ pending: boolean;
  enabled: boolean;
  /** 被环境变量供着 ⇒ false(界面只读并说明,H1)。 */
  writable: boolean;
  models: ProviderModel[];
};
export type ProvidersView = {
  providers: ProviderRow[];
  current: { provider: string; model: string } | null;
  /** 有外壳 = 每家各存各的、能加自定义供应商;没外壳(老装法)= 只能用一家。 */
  multi: boolean;
  /** 这台机器有没有 key(旧 key 卡片同一口径);老后端没这个字段 ⇒ null,退回看每家那一行。 */
  configured: boolean | null;
};
export type ProviderStatus = "ready" | "unavailable" | "disabled";
export type SettingsSection = "general" | "models";
export type SaveResult =
  | { ok: true; view: ProvidersView; restart: string | null }
  | { ok: false; error: string };

type ResponseLike = { status: number; json(): Promise<unknown> };
type FetchLike = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string },
) => Promise<ResponseLike>;

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

// 只认 https:// 开头的绝对地址 —— 后端表被改坏时,页面上不许出现 javascript:/http:/相对路径的链接(ms2)
const HTTPS_URL = /^https:\/\/[^\s/]+(\/\S*)?$/;

function asModel(v: unknown): ProviderModel | null {
  const r = asRecord(v);
  if (typeof r.id !== "string" || !r.id) return null;
  const cw = r.contextWindow;
  return {
    id: r.id,
    label: typeof r.label === "string" && r.label ? r.label : r.id,
    builtin: r.builtin === true,
    contextWindow: typeof cw === "number" && Number.isInteger(cw) && cw > 0 ? cw : null,
  };
}

function asRow(v: unknown): ProviderRow | null {
  const r = asRecord(v);
  if (typeof r.id !== "string" || !r.id || typeof r.label !== "string") return null;
  return {
    id: r.id,
    label: r.label,
    kind: r.kind === "custom" ? "custom" : "builtin",
    apiBase: typeof r.apiBase === "string" ? r.apiBase : "",
    keyUrl: typeof r.keyUrl === "string" && HTTPS_URL.test(r.keyUrl) ? r.keyUrl : null,
    configured: r.configured === true,
    hint: typeof r.hint === "string" && r.hint ? r.hint : null,
    live: r.live === true,
    active: r.active === true,
    pending: r.pending === true,
    // 缺省往"能用"那边倒:上游少给一个字段,不该把一家锁死(锁死不可自救;写不进去后端还会拦)
    enabled: r.enabled !== false,
    writable: r.writable !== false,
    models: Array.isArray(r.models) ? r.models.map(asModel).filter((m): m is ProviderModel => m !== null) : [],
  };
}

/** 形状不对 ⇒ null;坏的那几行丢掉,不让整页崩(ms1)。 */
export function readProvidersResponse(status: number, body: unknown): ProvidersView | null {
  if (status !== 200) return null;
  const r = asRecord(body);
  if (!Array.isArray(r.providers)) return null;
  const cur = asRecord(r.current);
  return {
    providers: r.providers.map(asRow).filter((p): p is ProviderRow => p !== null),
    current: typeof cur.provider === "string" && typeof cur.model === "string"
      ? { provider: cur.provider, model: cur.model } : null,
    multi: r.multi === true,
    configured: typeof r.configured === "boolean" ? r.configured : null,
  };
}

/** 左栏状态点(照 ZCode ProviderStatusIndicator):未启用 > 就绪 > 未就绪(ms3)。 */
export function providerStatus(p: ProviderRow): ProviderStatus {
  if (!p.enabled) return "disabled";
  return p.configured && p.live ? "ready" : "unavailable";
}

/** 圆点的读屏文字(ZCode zh-CN 原词)。 */
export const STATUS_LABEL: Record<ProviderStatus, string> = { ready: "就绪", unavailable: "未就绪", disabled: "未启用" };

/** 详情顶上那一句:在用 / 就绪 / 已保存等重启 / 没填 / 未启用 —— 五种说法不许混(ms4)。
 *  等重启那一句必须说清要等后台重启 —— 不说,业主会以为存了没用。 */
export function providerStateText(p: ProviderRow): string {
  const hint = p.hint ? ` ${p.hint}` : "";
  if (!p.enabled) return `${STATUS_LABEL.disabled}${p.configured ? ` · 已存${hint}` : ""}(不会出现在换模型菜单里)`;
  if (p.configured && p.live && p.active) return `在用 · 已存${hint}`;
  if (p.configured && p.live) return `就绪 · 已存${hint}`;
  // 不说「正在」:重启可能根本不会发生(没外壳应答、起网关那步失败)—— 那时「正在重启」是永久假话(第 1 轮评审 #4)
  if (p.configured) return `已保存${hint},后台重启后就能在聊天里选;一直没好就退出 OpenDesign 再打开`;
  return "还没填 API Key";
}

export type NavGroup = { id: "builtin" | "custom"; title: string; items: ProviderRow[] };

/** 左栏两组(照后端顺序);自定义那一组没有也要在,「添加供应商」挂在它下面(ms5)。 */
export function navGroups(view: ProvidersView): NavGroup[] {
  return [
    { id: "builtin", title: "内置供应商", items: view.providers.filter((p) => p.kind === "builtin") },
    { id: "custom", title: "自定义供应商", items: view.providers.filter((p) => p.kind === "custom") },
  ];
}

/** 上下文长度小标签(ms6):照 ZCode formatModelContextWindowLabel —— 技术规格,固定 en-US compact,
 *  262144 ⇒ 262.1K、128000 ⇒ 128K;没有 ⇒ 空串(不显示那个小标签,不像 ZCode 画「0」)。 */
export function contextLabel(tokens: number | null | undefined): string {
  if (typeof tokens !== "number" || !Number.isFinite(tokens) || tokens <= 0) return "";
  return new Intl.NumberFormat("en-US", {
    notation: tokens >= 1_000 ? "compact" : "standard", maximumFractionDigits: 1, minimumFractionDigits: 0,
  }).format(tokens);
}

/** 设置页路由(ms7):#/settings[/general|/models][?provider=<id>];不是设置页 ⇒ null。 */
export function settingsRoute(hash: string): { section: SettingsSection; provider: string | null } | null {
  const m = /^#\/settings(?:\/([a-z]+))?\/?(?:\?(.*))?$/.exec(hash);
  if (!m) return null;
  const provider = new URLSearchParams(m[2] ?? "").get("provider");
  return { section: m[1] === "models" ? "models" : "general", provider: provider || null };
}

export function settingsHash(section: SettingsSection, provider?: string | null): string {
  return `#/settings/${section}${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`;
}

/** 一家 key 都没有 ⇒ 首启直接进模型设置(接替旧卡片的自动弹出)。口径与旧卡片同一个:后端说有 key 就算有(ms9)。 */
export function anyConfigured(view: ProvidersView): boolean {
  return view.configured === true || view.providers.some((p) => p.configured);
}

async function readJson(res: ResponseLike): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

/** 抹掉回包里任何含 key(或它前 12 个字符)的字符串 —— 上游漏了,前端也不当传声筒(c2)。 */
function withoutSecret<T>(v: T, secret: string): T {
  if (!secret) return v;
  const head = secret.length >= 12 ? secret.slice(0, 12) : secret;
  const walk = (x: unknown): unknown => {
    if (typeof x === "string") return x.includes(head) ? x.split(secret).join("•••").split(head).join("•••") : x;
    if (Array.isArray(x)) return x.map(walk);
    if (x && typeof x === "object") {
      return Object.fromEntries(Object.entries(x as Record<string, unknown>).map(([k, y]) => [k, walk(y)]));
    }
    return x;
  };
  return walk(v) as T;
}

/** GET 列表;连不上 / 回包不对 ⇒ null(界面说"读不到",不崩)。 */
export async function fetchProviders(fetchFn: FetchLike): Promise<ProvidersView | null> {
  try {
    const res = await fetchFn(PROVIDERS_PATH);
    return readProvidersResponse(res.status, await readJson(res));
  } catch {
    return null;
  }
}

/** 所有写操作的同一条路:POST JSON;200 ⇒ 新列表(+ restart);否则把后端的人话原样端出来(a5)。
 *  `secret` = 这次 body 里带的 key(存 key / 带 key 添加供应商),回包与报错里一律抹掉。 */
export async function postSettings(
  fetchFn: FetchLike,
  path: string,
  body: Record<string, unknown>,
  secret = "",
): Promise<SaveResult> {
  let res: ResponseLike;
  try {
    res = await fetchFn(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, error: "保存失败:OpenDesign 后台连不上,请稍后再试" };
  }
  const data = withoutSecret(asRecord(await readJson(res)), secret);
  if (res.status !== 200) {
    const msg = typeof data.error === "string" && data.error ? data.error : `服务返回 HTTP ${res.status}`;
    return { ok: false, error: msg };
  }
  const view = readProvidersResponse(200, data);
  if (!view) return { ok: false, error: "后台回的内容看不懂,请点「刷新」再看一次" };
  return { ok: true, view, restart: typeof data.restart === "string" ? data.restart : null };
}

/** 存一家的 key:key 只在 body 里(a3),回包不含 key(c1/c2)。 */
export function saveProviderKey(fetchFn: FetchLike, provider: string, key: string): Promise<SaveResult> {
  return postSettings(fetchFn, PROVIDER_KEY_PATH, { provider, key }, key);
}

/** 模型列表每行的「测试」:后端直连这家发一句最短的话(会花一点点额度)。 */
export async function testModel(fetchFn: FetchLike, provider: string, model: string): Promise<{ ok: boolean; message: string }> {
  try {
    const res = await fetchFn(TEST_MODEL_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, model }),
    });
    const d = asRecord(await readJson(res));
    if (res.status === 200) return { ok: d.ok === true, message: typeof d.message === "string" ? d.message : "" };
    return { ok: false, message: typeof d.error === "string" ? d.error : `服务返回 HTTP ${res.status}` };
  } catch {
    return { ok: false, message: "OpenDesign 后台连不上,请稍后再试" };
  }
}

export function restartNotice(restart: unknown, savedIsCurrent = false, savedDisabled = false): string {
  if (restart === "live" && savedDisabled) {
    // 未启用的那家不在换模型菜单里(D3),不能叫他去右下角换(第 1 轮评审 DeepSeek #1);正在用的那家不许禁用,所以这里一定不是当前那家
    return "已保存。这家现在未启用:在上面打开「启用」后,才会出现在聊天框右下角的换模型里。";
  }
  if (restart === "live") {
    // 网关在跑、现读 key 文件(ds_web.key_saved_verdict;track opendesign-key-restart):不重启、连接不断。
    // 存 key 不换当前模型 ⇒ 只有改的就是正在用的那家,才能说「下一句就用」;存了另一家要告诉他去哪儿换(QA 设计 d5)。
    return savedIsCurrent
      ? "已保存,下一句对话起就用新的 key。"
      : "已保存,马上可用:在聊天框右下角就能换到这家的模型。";
  }
  if (restart === "requested") {
    // 🔴 措辞只能说到"已请求"。`requested` 的定义是**帧送到了外壳、它认了这个动词**
    //    (ds_web._restart_verdict),不是"起好了" —— 外壳随后失败会自己弹告警。
    //    只在聊天服务没在跑时才会走到这里(全新装机第一次存 key),所以不说「重启」;
    //    也不沿用业主 09-24 让删掉的那条启动横幅的原话(test_quiet_start_icons q1 全仓禁用)。
    return "已保存,正在准备聊天服务,稍等片刻即可开始对话;若稍后仍连不上,请退出 OpenDesign 再打开。";
  }
  return "已保存。当前环境不能自动应用新配置,请手动重启 OpenDesign 后再继续使用。";
}
