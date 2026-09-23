import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  fetchKeyStatus,
  restartNotice,
  saveKey,
  vendorStateText,
  type KeyStatus,
} from "./llmKey";

type Props = {
  initialStatus?: KeyStatus | null;
  onStatus?: (status: KeyStatus) => void;
};

function hasProvider(status: KeyStatus, id: string): boolean {
  return status.providers.some((p) => p.id === id);
}

function preferredProvider(status: KeyStatus | null): string {
  if (!status) return "";
  if (status.provider && hasProvider(status, status.provider)) return status.provider;
  return status.providers[0]?.id ?? "";
}

export default function LlmKeyCard({ initialStatus = null, onStatus }: Props) {
  const [status, setStatus] = useState<KeyStatus | null>(initialStatus);
  const [provider, setProvider] = useState(() => preferredProvider(initialStatus));
  const [loading, setLoading] = useState(initialStatus === null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!initialStatus) return;
    setStatus(initialStatus);
    setProvider((cur) => (hasProvider(initialStatus, cur) ? cur : preferredProvider(initialStatus)));
  }, [initialStatus]);

  useEffect(() => {
    let stale = false;
    if (!status) setLoading(true);
    fetchKeyStatus(fetch)
      .then((next) => {
        if (stale) return;
        setStatus(next);
        setProvider((cur) => (hasProvider(next, cur) ? cur : preferredProvider(next)));
        onStatus?.(next);
      })
      .catch(() => {
        if (!stale) setError("读不到大模型 key 状态,请稍后重试。");
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
    // 只在卡片挂载时刷新一次;initialStatus 变化由上面的 effect 接住。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onStatus]);

  // 有厂商「已保存、等后台重启」时隔一会儿再问一次,后台起好后这一行自己变成「在用」
  // (第 1 轮 G5:只在存完那一刻问一次的话,卡片会一直写着「等重启」)。有上限,不无限轮询。
  const waiting = status?.vendors.some((v) => v.pending) ?? false;
  useEffect(() => {
    if (!waiting) return;
    let tries = 0;
    let stale = false;
    const timer = window.setInterval(() => {
      tries += 1;
      // 上限约 10 分钟:业主机器上网关冷启动见过近 4 分钟(第 2 轮残余:原来 2 分钟会早停)
      if (tries > 200) {
        window.clearInterval(timer);
        return;
      }
      fetchKeyStatus(fetch)
        .then((next) => {
          if (stale) return;
          setStatus(next);
          onStatus?.(next);
        })
        .catch(() => { /* 这一次没问到,下一次再问 */ });
    }, 3000);
    return () => {
      stale = true;
      window.clearInterval(timer);
    };
  }, [waiting, onStatus]);

  const selected = status?.providers.find((p) => p.id === provider) ?? null;
  const selectedVendor = status?.vendors.find((v) => v.id === provider) ?? null;
  // 被环境变量遮蔽 ⇒ 这一格在这个界面里改不动(后端也会拒绝,见 ds_credential.save)。
  // 提前变只读,业主就不用填一次才知道 —— 形状来自 DSH 的 describe().writable。
  const shadowed = status?.writable === false;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!provider || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    const rawKey = inputRef.current?.value ?? "";
    const outcome = await saveKey(fetch, provider, rawKey);
    if (outcome.ok) {
      if (inputRef.current) inputRef.current.value = "";
      const next: KeyStatus = {
        configured: outcome.configured,
        provider: outcome.provider,
        hint: outcome.hint,
        // 刚写进 key.txt 才会走到这里(被 env 遮蔽时后端直接拒绝,进不了 ok 分支)
        source: outcome.configured ? "file" : null,
        writable: true,
        providers: status?.providers ?? [],
        vendors: status?.vendors ?? [],
      };
      setStatus(next);
      setProvider((cur) => (hasProvider(next, cur) ? cur : preferredProvider(next)));
      onStatus?.(next);
      setNotice(restartNotice(outcome.restart));
      // 每家一行的状态以后端为准(存的是哪一槽、要不要等重启,只有后端知道)
      fetchKeyStatus(fetch).then((fresh) => {
        setStatus(fresh);
        onStatus?.(fresh);
      }).catch(() => { /* 读不到就先用上面那份 */ });
    } else {
      setError(outcome.error);
    }
    setSaving(false);
  };

  return (
    <div
      className="llm-key-card"
      data-ui="llm-key-card"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="llm-key-head">
        <div>
          <h2>AI 模型 key</h2>
          <p>选择厂商,粘贴 API key,保存后配置会写入本机。</p>
        </div>
        {status?.configured && (
          <div className="llm-key-current">
            <span>当前</span>
            {/* 多家时报**正在用的那家**的末四位;老字段 hint 只讲最早那一家(主槽) */}
            <strong>{status.vendors.find((v) => v.active)?.hint ?? status.hint ?? "已配置"}</strong>
          </div>
        )}
      </div>

      {status && status.vendors.length > 1 && (
        // 每家一行的只读状态(track opendesign-per-vendor-keys):点一行 = 在下面的下拉里选中那家
        <ul className="llm-key-vendors" data-ui="llm-key-vendors">
          {status.vendors.map((v) => (
            <li key={v.id}>
              <button
                type="button"
                className={`llm-key-vendor${provider === v.id ? " selected" : ""}`}
                data-ui="llm-key-vendor"
                data-vendor={v.id}
                disabled={loading || saving || !hasProvider(status, v.id)}
                onClick={() => setProvider(v.id)}
              >
                <span className="name">{v.label}</span>
                <span className={`state${v.active ? " active" : v.pending ? " pending" : ""}`}>
                  {vendorStateText(v)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="llm-key-form" onSubmit={onSubmit}>
        <label>
          <span>厂商</span>
          <select
            data-ui="llm-key-provider"
            value={provider}
            disabled={loading || saving || !status?.providers.length}
            onChange={(e) => setProvider(e.target.value)}
          >
            {status?.providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label} · {p.model}
              </option>
            ))}
          </select>
        </label>

        {selected && (
          <p className="llm-key-provider-note">
            将使用 {selected.label} 的 {selected.model}
          </p>
        )}

        <label>
          <span>API key</span>
          <input
            ref={inputRef}
            data-ui="llm-key-input"
            type="password"
            autoComplete="off"
            placeholder={shadowed
              ? "这台机器的 key 由环境变量提供"
              : selectedVendor
                // 多家各存各的:只说「这一家」,别说「覆盖当前配置」(存 DeepSeek 不会动 MiMo 那把)
                ? (selectedVendor.configured ? "粘贴新 key,替换这一家现在的 key" : "粘贴这一家的 API key")
                : status?.configured ? "粘贴新 key 可覆盖当前配置" : "粘贴 API key"}
            disabled={loading || saving || shadowed}
          />
        </label>

        {selected?.keyUrl && !shadowed && (
          // 外链:Electron 外壳把站外地址交给系统浏览器(navPolicy),浏览器里开新标签
          <a className="llm-key-link" data-ui="llm-key-link" href={selected.keyUrl}
             target="_blank" rel="noreferrer">
            获取 {selected.label} 的 API Key ›
          </a>
        )}

        {shadowed && (
          <p className="llm-key-note" data-ui="llm-key-readonly">
            当前的 key 由环境变量提供,启动时它优先于本机的 key.txt ——
            在这里改不会生效。要改成在这里填,请先清掉那个环境变量再重开程序。
          </p>
        )}

        {error && <p className="llm-key-error">{error}</p>}
        {notice && (
          <p className="llm-key-notice" data-ui="llm-key-notice">
            {notice}
          </p>
        )}

        <button
          type="submit"
          className="btn-primary llm-key-save"
          data-ui="llm-key-save"
          disabled={loading || saving || !provider || shadowed}
        >
          {saving ? "保存中…" : "保存"}
        </button>
      </form>
    </div>
  );
}
