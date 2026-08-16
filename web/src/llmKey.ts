export const CREDENTIAL_PATH = "/api/llm/credential";

export type Provider = { id: string; label: string; model: string };
export type KeyStatus = {
  configured: boolean; provider: string | null; hint: string | null; providers: Provider[];
  /** 这把 key 现在由哪一层供着:"env"=进程环境变量、"file"=key.txt、null=没配。 */
  source: "env" | "file" | null;
  /** 在这个界面里改得动吗。env 供值时为 false —— 启动脚本 env 优先,写 key.txt 不生效。 */
  writable: boolean;
};
export type SaveOutcome =
  | { ok: true; configured: boolean; provider: string | null; hint: string | null; restart: string }
  | { ok: false; error: string };

type ResponseLike = {
  status: number;
  json(): Promise<unknown>;
};
type FetchLike = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string },
) => Promise<ResponseLike>;

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? v as Record<string, unknown> : {};
}

function asProvider(v: unknown): Provider | null {
  const r = asRecord(v);
  return typeof r.id === "string" && typeof r.label === "string" && typeof r.model === "string"
    ? { id: r.id, label: r.label, model: r.model }
    : null;
}

function asStatus(v: unknown): KeyStatus {
  const r = asRecord(v);
  const providers = Array.isArray(r.providers)
    ? r.providers.map(asProvider).filter((p): p is Provider => p !== null)
    : [];
  return {
    configured: r.configured === true,
    provider: typeof r.provider === "string" ? r.provider : null,
    hint: typeof r.hint === "string" ? r.hint : null,
    source: r.source === "env" || r.source === "file" ? r.source : null,
    // 🔴 缺省成 true(可写)而不是 false:上游万一没给这个字段,宁可让业主填得动
    //    也不要把一个正常的界面锁死。锁死是不可自救的,填了不生效后端还会拦
    //    (E 组 save 那道)。**两个方向的坏,选可恢复的那个。**
    writable: r.writable !== false,
    providers,
  };
}

async function readJson(res: ResponseLike): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

function withoutSecret(text: string, key: string): string {
  if (!key) return text;
  const head = key.length >= 12 ? key.slice(0, 12) : "";
  const noKey = text.split(key).join("[已隐藏]");
  return head ? noKey.split(head).join("[已隐藏]") : noKey;
}

function safeHint(v: unknown, key: string): string | null {
  if (typeof v !== "string") return null;
  return withoutSecret(v, key) === v ? v : null;
}

export async function fetchKeyStatus(fetchFn: FetchLike): Promise<KeyStatus> {
  const res = await fetchFn(CREDENTIAL_PATH);
  if (res.status !== 200) throw new Error(`读取大模型 key 状态失败:HTTP ${res.status}`);
  return asStatus(await readJson(res));
}

export async function saveKey(
  fetchFn: FetchLike,
  provider: string,
  key: string,
): Promise<SaveOutcome> {
  try {
    const res = await fetchFn(CREDENTIAL_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, key }),
    });
    const body = asRecord(await readJson(res));
    if (res.status === 200) {
      return {
        ok: true,
        configured: body.configured === true,
        provider: typeof body.provider === "string" ? body.provider : null,
        hint: safeHint(body.hint, key),
        restart: typeof body.restart === "string" ? body.restart : "",
      };
    }
    if (res.status === 400 && typeof body.error === "string" && body.error) {
      return { ok: false, error: withoutSecret(body.error, key) };
    }
    return { ok: false, error: `保存失败:服务返回 HTTP ${res.status}` };
  } catch {
    return { ok: false, error: "保存失败:服务不可用,请稍后再试" };
  }
}

export function restartNotice(restart: unknown): string {
  if (restart === "requested") {
    // 🔴 措辞只能说到"已请求"。`requested` 的定义是**帧送到了外壳、它认了这个动词**
    //    (ds_web._restart_verdict),不是"重启成功了" —— 外壳随后失败会自己弹告警,
    //    而界面若已经说了"已经自动应用",两句话就互相打脸(2026-08-16 四审 kimi
    //    Finding 4 / deepseek 同款措辞注记)。
    return "已保存,正在自动重启后台服务,稍等片刻即可继续使用;若稍后仍连不上,请手动重启 OpenDesign。";
  }
  return "已保存。当前环境不能自动应用新配置,请手动重启 OpenDesign 后再继续使用。";
}
