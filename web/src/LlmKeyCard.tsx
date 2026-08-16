import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  fetchKeyStatus,
  restartNotice,
  saveKey,
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

  const selected = status?.providers.find((p) => p.id === provider) ?? null;

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
        providers: status?.providers ?? [],
      };
      setStatus(next);
      setProvider((cur) => (hasProvider(next, cur) ? cur : preferredProvider(next)));
      onStatus?.(next);
      setNotice(restartNotice(outcome.restart));
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
            <strong>{status.hint ?? "已配置"}</strong>
          </div>
        )}
      </div>

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
            placeholder={status?.configured ? "粘贴新 key 可覆盖当前配置" : "粘贴 API key"}
            disabled={loading || saving}
          />
        </label>

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
          disabled={loading || saving || !provider}
        >
          {saving ? "保存中…" : "保存"}
        </button>
      </form>
    </div>
  );
}
