// 设置页 · 模型设置,照 ZCode `packages/ui/src/settings/model-provider-section/`(track opendesign-zcode-model-settings):
// 顶上说明 + 刷新 / 添加供应商;卡片左栏 224px(内置供应商 / 自定义供应商,各家带三态圆点),右边这家的详情:
// 名称 + 启用、Base URL(内置只读)、API Key + 获取 API Key、模型列表(上下文窗口 + 测试 / 编辑 / 删除)+ 添加模型。
// 逻辑与回包清洗在 modelSettings.ts;语义在后端(D1~D4)。钩子表:track design.md「界面钩子」。
//
// 🔴 key 输入框一律**不受控**(ref 取值、存完清空):受控输入框会被 React 同步成 value 属性,
//    打字那一刻 key 就进了页面 HTML(e2e C1 扫的就是这一面)。
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  contextLabel,
  CUSTOM_PROVIDER_PATH,
  fetchProviders,
  navGroups,
  postSettings,
  PROVIDER_ENABLED_PATH,
  PROVIDER_MODELS_PATH,
  providerStateText,
  providerStatus,
  restartNotice,
  saveProviderKey,
  STATUS_LABEL,
  testModel,
  type ProviderRow,
  type ProvidersView,
  type SaveResult,
} from "./modelSettings";

type Props = {
  /** 路由里点名的那一家(#/settings/models?provider=…);null ⇒ 当前在用那家,再没有就第一家。 */
  provider: string | null;
  onSelectProvider: (id: string) => void;
};

type Notice = { ok: boolean; text: string } | null;
type Dialog = { mode: "add" } | { mode: "edit"; model: string; contextWindow: number | null } | null;

const API_FORMAT = "Chat Completions (/v1/chat/completions)";
const POLL_MS = 1500;

function pickSelected(view: ProvidersView | null, wanted: string | null): string | null {
  if (!view || view.providers.length === 0) return null;
  if (wanted && view.providers.some((p) => p.id === wanted)) return wanted;
  const cur = view.current?.provider;
  if (cur && view.providers.some((p) => p.id === cur)) return cur;
  return view.providers[0].id;
}

function StatusDot({ p }: { p: ProviderRow }) {
  const st = providerStatus(p);
  return <span className={`ms-dot ${st}`} data-provider-status={st} role="img" aria-label={STATUS_LABEL[st]} title={STATUS_LABEL[st]} />;
}

function Modal({ ui, title, desc, onClose, children }: {
  ui: string; title: string; desc?: string; onClose: () => void; children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);
  return (
    <div className="ms-modal-mask" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="ms-modal" data-ui={ui} role="dialog" aria-modal="true" aria-label={title}>
        <h3>{title}</h3>
        {desc && <p className="ms-modal-desc">{desc}</p>}
        {children}
      </div>
    </div>
  );
}

export default function ModelSettings({ provider, onSelectProvider }: Props) {
  const [view, setView] = useState<ProvidersView | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  // 刚存了 key、正在等后台重启的是哪一家:起好之后提示要改口(不然绿条还说「正在重启」,和状态句打架)
  const [awaiting, setAwaiting] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [dialogErr, setDialogErr] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [nameDraft, setNameDraft] = useState("");
  const [baseDraft, setBaseDraft] = useState("");
  const keyRef = useRef<HTMLInputElement>(null);
  const pfKeyRef = useRef<HTMLInputElement>(null);
  const modelIdRef = useRef<HTMLInputElement>(null);
  const modelCtxRef = useRef<HTMLInputElement>(null);
  const pfNameRef = useRef<HTMLInputElement>(null);
  const pfBaseRef = useRef<HTMLInputElement>(null);
  const pfModelsRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    const v = await fetchProviders(fetch);
    if (v) {
      setView(v);
      setLoadFailed(false);
    } else {
      setLoadFailed(true);
    }
    return v;
  }, []);
  useEffect(() => { void load(); }, [load]);

  const selectedId = pickSelected(view, provider);
  const sel = view?.providers.find((p) => p.id === selectedId) ?? null;

  // 换了一家:提示、测试结果、草稿都归零(别让上一家的话挂在这一家头上)
  useEffect(() => {
    setNotice(null);
    setTestResult(null);
    setShowKey(false);
    setNameDraft(sel?.label ?? "");
    setBaseDraft(sel?.apiBase ?? "");
    // 只在换家时重置;sel 的其余字段随轮询变化不该冲掉草稿
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    if (!awaiting || !view) return;
    const row = view.providers.find((p) => p.id === awaiting);
    if (!row || row.pending) return;
    if (row.id === selectedId && row.live) {
      // 🔴 只说确定知道的:这家进了配置 = 外壳已开始重启网关(prepare_gateway 只在起 / 重启网关时跑),
      //    **不等于**新网关已经起好 —— 外壳先写配置、再换进程,换失败它会自己弹窗。
      //    不许说「已重启 / 已生效」(第 2 轮评审 #8,「不许撒谎的重启」)。
      setNotice({ ok: true, text: "后台已开始换上这把 key:稍等几秒就能在聊天里选这家的模型;若弹窗说没能自己重启,请退出 OpenDesign 再打开。" });
    }
    setAwaiting(null);
  }, [awaiting, view, selectedId]);

  // 有哪家「已保存、等后台重启」⇒ 隔一会儿再问一次,起好之后页面自己跟上(旧卡片 G5 / e2e B7)
  const waiting = !!view?.providers.some((p) => p.pending);
  useEffect(() => {
    if (!waiting) return;
    const t = window.setTimeout(() => { void load(); }, POLL_MS);
    return () => window.clearTimeout(t);
  }, [waiting, view, load]);

  const apply = (r: SaveResult, okText: string, savedId?: string): boolean => {
    if (r.ok) {
      setView(r.view);
      setNotice({ ok: true, text: r.restart ? restartNotice(r.restart, !!savedId && r.view.current?.provider === savedId) : okText });
      return true;
    }
    setNotice({ ok: false, text: r.error });
    return false;
  };

  const run = async (fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  const saveKey = (p: ProviderRow) => run(async () => {
    const raw = keyRef.current?.value ?? "";
    const r = await saveProviderKey(fetch, p.id, raw);
    if (apply(r, "已保存", p.id)) {
      // 只有这一行确实「等重启」才等它改口;主槽那家没有可观察的等待(有 key 即算后台拿到)⇒ 保留「正在重启」那句老实话
      if (r.ok && r.restart === "requested" && r.view.providers.some((x) => x.id === p.id && x.pending)) setAwaiting(p.id);
      if (keyRef.current) keyRef.current.value = "";
      setShowKey(false);
    }
  });

  const toggleEnabled = (p: ProviderRow) => run(async () => {
    apply(await postSettings(fetch, PROVIDER_ENABLED_PATH, { provider: p.id, enabled: !p.enabled }),
      p.enabled ? `${p.label} 已设为未启用` : `已启用 ${p.label}`);
  });

  const removeModel = (p: ProviderRow, model: string) => run(async () => {
    apply(await postSettings(fetch, PROVIDER_MODELS_PATH, { op: "remove", provider: p.id, model }), `已删除 ${model}`);
  });

  const runTest = async (p: ProviderRow, model: string) => {
    setTesting(model);
    setTestResult({ ok: true, text: `正在测试 ${p.label} / ${model}…` });
    const r = await testModel(fetch, p.id, model);
    setTesting(null);
    setTestResult({ ok: r.ok, text: r.ok ? `${p.label} / ${r.message || `${model} 连接成功`}`
      : `${p.label} / ${model} 连接失败:${r.message || "测试失败"}` });
  };

  const saveModelDialog = (p: ProviderRow) => run(async () => {
    if (!dialog) return;
    const id = dialog.mode === "add" ? (modelIdRef.current?.value ?? "").trim() : dialog.model;
    const ctxRaw = (modelCtxRef.current?.value ?? "").trim();
    if (!id) { setDialogErr("模型 ID 不能为空"); return; }
    if (ctxRaw && !/^\d+$/.test(ctxRaw)) { setDialogErr("上下文窗口必须是正整数"); return; }
    if (dialog.mode === "edit" && !ctxRaw) { setDialogErr("上下文窗口必须是正整数"); return; }
    const ctx = ctxRaw ? Number(ctxRaw) : undefined;
    const body = dialog.mode === "add"
      ? { op: "add", provider: p.id, model: id, ...(ctx !== undefined ? { contextWindow: ctx } : {}) }
      : { op: "context", provider: p.id, model: id, contextWindow: ctx };
    const r = await postSettings(fetch, PROVIDER_MODELS_PATH, body);
    if (r.ok) {
      apply(r, dialog.mode === "add" ? `已添加 ${id}` : `已保存 ${id}`);
      setDialog(null);
    } else {
      setDialogErr(r.error);
    }
  });

  const saveCustom = (p: ProviderRow) => run(async () => {
    apply(await postSettings(fetch, CUSTOM_PROVIDER_PATH,
      { op: "update", provider: p.id, label: nameDraft.trim(), apiBase: baseDraft.trim() }), `${nameDraft.trim()} 保存成功`);
  });

  const deleteCustom = (p: ProviderRow) => run(async () => {
    if (!window.confirm(`删除供应商“${p.label}”?\n\n删除后将移除这个自定义供应商和它的 API Key。`)) return;
    const r = await postSettings(fetch, CUSTOM_PROVIDER_PATH, { op: "remove", provider: p.id });
    if (apply(r, `已删除 ${p.label}`) && r.ok) {
      const next = pickSelected(r.view, null);
      if (next) onSelectProvider(next);
    }
  });

  const addProvider = () => run(async () => {
    const key = pfKeyRef.current?.value ?? "";
    const models = (pfModelsRef.current?.value ?? "").split("\n").map((m) => m.trim()).filter(Boolean);
    const before = new Set((view?.providers ?? []).map((p) => p.id));
    const r = await postSettings(fetch, CUSTOM_PROVIDER_PATH, {
      op: "add", label: (pfNameRef.current?.value ?? "").trim(), apiBase: (pfBaseRef.current?.value ?? "").trim(),
      models, ...(key.trim() ? { key } : {}),
    }, key);
    if (!r.ok) { setFormErr(r.error); return; }
    if (pfKeyRef.current) pfKeyRef.current.value = "";
    setFormOpen(false);
    setView(r.view);
    const added = r.view.providers.find((p) => !before.has(p.id));
    if (added) onSelectProvider(added.id);
    if (added && r.restart === "requested" && added.pending) setAwaiting(added.id);
    // 换家会清提示 ⇒ 等选中生效后再说「正在重启」
    window.setTimeout(() => setNotice({ ok: true, text: r.restart ? restartNotice(r.restart) : "已添加" }), 0);
  });

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const groups = view ? navGroups(view) : [];
  const current = view?.current ?? null;

  return (
    <section className="ms" data-ui="model-settings">
      <header className="ms-head">
        <div>
          <h2>模型设置</h2>
          <p className="ms-desc">管理模型供应商与 API Key,配置后可在聊天时选择使用。</p>
        </div>
        <div className="ms-head-actions">
          <button className="ms-btn" data-ui="ms-refresh" onClick={() => void refresh()} disabled={refreshing}>
            {refreshing ? "正在刷新…" : "刷新"}
          </button>
          {view?.multi && (
            <button className="ms-btn primary" data-ui="ms-add-provider"
              onClick={() => { setFormErr(""); setNotice(null); setFormOpen(true); }}>
              添加供应商
            </button>
          )}
        </div>
      </header>
      {view && !view.multi && (
        <p className="ms-single-note" data-ui="ms-single-note">
          这台机器是老装法,只能用一家:存哪家的 key 就用哪家(换一家会替换掉原来那把)。
        </p>
      )}
      {loadFailed && !view && (
        <p className="ms-error">读不到模型设置(OpenDesign 后台没有响应),点「刷新」再试一次。</p>
      )}
      {view && (
        <div className="ms-card">
          <aside className="ms-nav" data-ui="ms-nav">
            {groups.map((g) => (
              <div className="ms-group" data-ui="ms-group" data-group={g.id} key={g.id}>
                <h3>{g.title}</h3>
                {g.items.map((p) => (
                  <button
                    key={p.id}
                    className={`ms-nav-item${p.id === selectedId ? " current" : ""}`}
                    data-ui="ms-nav-item"
                    data-provider={p.id}
                    aria-current={p.id === selectedId ? "page" : undefined}
                    onClick={() => onSelectProvider(p.id)}
                  >
                    <span className="nm" title={p.label}>{p.label}</span>
                    <StatusDot p={p} />
                  </button>
                ))}
                {g.id === "custom" && g.items.length === 0 && (
                  <p className="ms-empty">暂无自定义模型供应商</p>
                )}
              </div>
            ))}
          </aside>
          {sel && (
            <div className="ms-detail" data-ui="ms-detail" data-provider={sel.id} key={sel.id}>
              <div className="ms-detail-head">
                {sel.kind === "custom" ? (
                  <input className="ms-input ms-name-input" data-ui="ms-name" aria-label="名称" value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)} maxLength={40} />
                ) : (
                  <h3 className="ms-name" data-ui="ms-name">{sel.label}</h3>
                )}
                {sel.kind === "custom" && (
                  <button className="ms-link-btn danger" data-ui="ms-delete-provider" disabled={busy}
                    onClick={() => void deleteCustom(sel)}>删除供应商</button>
                )}
                <label className="ms-switch-wrap">
                  <span className="ms-muted">{sel.enabled ? "已启用" : "未启用"}</span>
                  <button
                    className={`ms-switch${sel.enabled ? " on" : ""}`}
                    role="switch"
                    aria-checked={sel.enabled}
                    aria-label={sel.enabled ? "禁用供应商" : "启用供应商"}
                    data-ui="ms-enable"
                    disabled={busy}
                    onClick={() => void toggleEnabled(sel)}
                  >
                    <span className="knob" />
                  </button>
                </label>
              </div>
              <p className="ms-state" data-ui="ms-state">{providerStateText(sel)}</p>
              {notice && (
                <p className={`ms-notice${notice.ok ? "" : " err"}`} data-ui="ms-notice" role="status">{notice.text}</p>
              )}

              <div className="ms-field">
                <label className="ms-label">Base URL{sel.kind === "builtin" ? "(只读)" : ""}</label>
                {sel.kind === "builtin" ? (
                  <input className="ms-input mono" data-ui="ms-base" value={sel.apiBase} readOnly aria-label="Base URL(只读)" />
                ) : (
                  <input className="ms-input mono" data-ui="ms-base" value={baseDraft} aria-label="Base URL"
                    placeholder="https://api.example.com/v1" onChange={(e) => setBaseDraft(e.target.value)} />
                )}
              </div>
              {sel.kind === "custom" && (
                <>
                  <div className="ms-field">
                    <label className="ms-label">API 格式</label>
                    <div className="ms-readonly" data-ui="ms-format">{API_FORMAT}</div>
                  </div>
                  <div className="ms-row-actions">
                    <button className="ms-btn" data-ui="ms-provider-save"
                      disabled={busy || (nameDraft.trim() === sel.label && baseDraft.trim() === sel.apiBase)}
                      onClick={() => void saveCustom(sel)}>保存名称和地址</button>
                  </div>
                </>
              )}

              <div className="ms-field">
                <div className="ms-label-row">
                  <label className="ms-label" htmlFor={`ms-key-${sel.id}`}>API Key</label>
                  {sel.keyUrl && (
                    <a className="ms-link" data-ui="ms-key-link" href={sel.keyUrl} target="_blank" rel="noreferrer">
                      获取 API Key ↗
                    </a>
                  )}
                </div>
                <div className="ms-key-row">
                  <input
                    id={`ms-key-${sel.id}`}
                    key={sel.id}
                    ref={keyRef}
                    className="ms-input mono"
                    data-ui="ms-key"
                    type={showKey ? "text" : "password"}
                    autoComplete="off"
                    spellCheck={false}
                    disabled={!sel.writable || busy}
                    placeholder={sel.configured && sel.hint ? `已保存 ${sel.hint},粘贴新的 key 即可替换` : "输入 API Key"}
                    onKeyDown={(e) => { if (e.key === "Enter") void saveKey(sel); }}
                  />
                  <button className="ms-icon-btn" data-ui="ms-key-eye" type="button" disabled={!sel.writable}
                    aria-label={showKey ? "隐藏正在输入的 key" : "显示正在输入的 key"} title="只管正在输入的这一把;已保存的只显示首尾几位"
                    onClick={() => setShowKey((v) => !v)}>
                    {showKey ? "隐藏" : "显示"}
                  </button>
                  <button className="ms-btn primary" data-ui="ms-key-save" disabled={!sel.writable || busy}
                    onClick={() => void saveKey(sel)}>保存</button>
                </div>
                {!sel.writable && (
                  <p className="ms-hint warn" data-ui="ms-key-shadowed">
                    这把 key 由环境变量提供(启动脚本读环境变量优先),在这里改不会生效。要在界面里改,请先清掉那个环境变量。
                  </p>
                )}
                {sel.writable && !sel.configured && <p className="ms-hint">设置 API Key 后即可在聊天里选这家的模型。</p>}
              </div>

              <div className="ms-field">
                <div className="ms-label-row">
                  <span className="ms-label">模型列表</span>
                  <button className="ms-btn small" data-ui="ms-add-model" onClick={() => { setDialogErr(""); setDialog({ mode: "add" }); }}>
                    + 添加模型
                  </button>
                </div>
                <div className="ms-models" data-ui="ms-models">
                  {sel.models.length === 0 && <p className="ms-empty">当前没有配置模型,添加模型后可在聊天中使用。</p>}
                  {sel.models.map((m) => {
                    const ctx = contextLabel(m.contextWindow);
                    // 一把 key 都没存的那家不标「在用」(配置里记着的当前模型此刻根本发不出去)
                    const inUse = sel.configured && current?.provider === sel.id && current.model === m.id;
                    return (
                      <div className="ms-model" data-ui="ms-model" data-model={m.id} key={m.id}>
                        <span className="nm mono" title={m.label}>{m.label}</span>
                        {inUse && <span className="ms-badge in-use" data-ui="ms-in-use">在用</span>}
                        {ctx && <span className="ms-badge" data-ui="ms-ctx" title={`上下文窗口:${ctx}`}>{ctx}</span>}
                        <span className="grow" />
                        <button className="ms-link-btn" data-ui="ms-test" disabled={testing !== null}
                          title="会向这家发一句很短的请求(花一点点额度)" onClick={() => void runTest(sel, m.id)}>
                          {testing === m.id ? "测试中…" : "测试"}
                        </button>
                        <button className="ms-link-btn" data-ui="ms-edit"
                          onClick={() => { setDialogErr(""); setDialog({ mode: "edit", model: m.id, contextWindow: m.contextWindow }); }}>
                          编辑
                        </button>
                        {!m.builtin ? (
                          <button className="ms-link-btn danger" data-ui="ms-delete" disabled={busy}
                            onClick={() => void removeModel(sel, m.id)}>删除</button>
                        ) : (
                          // 内置模型删不了:留个同宽的空位,「测试 / 编辑」和自加模型行对齐(K5)
                          <span className="ms-link-btn ms-slot" aria-hidden="true">删除</span>
                        )}
                      </div>
                    );
                  })}
                </div>
                {testResult && (
                  <p className={`ms-test-result${testResult.ok ? "" : " err"}`} data-ui="ms-test-result" role="status">
                    {testResult.text}
                  </p>
                )}
              </div>

              {dialog && (
                <Modal ui="ms-model-dialog" title={dialog.mode === "add" ? "添加模型" : "编辑模型配置"}
                  desc={dialog.mode === "add" ? `给 ${sel.label} 加一个模型,加完就能在聊天里选。` : "编辑这个模型的上下文窗口。"}
                  onClose={() => setDialog(null)}>
                  <label className="ms-label">模型 ID</label>
                  <input className="ms-input mono" data-ui="ms-model-id" ref={modelIdRef} autoFocus={dialog.mode === "add"}
                    defaultValue={dialog.mode === "edit" ? dialog.model : ""} readOnly={dialog.mode === "edit"}
                    placeholder="例如 mimo-v2.6-pro" />
                  <label className="ms-label">上下文窗口</label>
                  <input className="ms-input mono" data-ui="ms-model-ctx" ref={modelCtxRef} inputMode="numeric"
                    defaultValue={dialog.mode === "edit" && dialog.contextWindow ? String(dialog.contextWindow) : ""}
                    placeholder="可不填,例如 262144" />
                  {dialogErr && <p className="ms-error" data-ui="ms-dialog-error">{dialogErr}</p>}
                  <div className="ms-modal-actions">
                    <button className="ms-btn" onClick={() => setDialog(null)}>取消</button>
                    <button className="ms-btn primary" data-ui="ms-dialog-save" disabled={busy}
                      onClick={() => void saveModelDialog(sel)}>保存</button>
                  </div>
                </Modal>
              )}
            </div>
          )}
        </div>
      )}

      {formOpen && (
        <Modal ui="ms-provider-form" title="添加模型供应商" desc="配置一个完全自定义的 API 端点和初始模型。" onClose={() => setFormOpen(false)}>
          <label className="ms-label">名称</label>
          <input className="ms-input" data-ui="ms-pf-name" ref={pfNameRef} maxLength={40} placeholder="如:我的中转" autoFocus />
          <label className="ms-label">Base URL</label>
          <input className="ms-input mono" data-ui="ms-pf-base" ref={pfBaseRef} placeholder="https://api.example.com/v1" />
          <label className="ms-label">API Key</label>
          <input className="ms-input mono" data-ui="ms-pf-key" ref={pfKeyRef} type="password" autoComplete="off"
            spellCheck={false} placeholder="输入 API Key" />
          <label className="ms-label">API 格式</label>
          <div className="ms-readonly" data-ui="ms-pf-format">{API_FORMAT}</div>
          <label className="ms-label">模型</label>
          <textarea className="ms-input mono" data-ui="ms-pf-models" ref={pfModelsRef} rows={4} placeholder="每行一个模型名称" />
          {formErr && <p className="ms-error" data-ui="ms-pf-error">{formErr}</p>}
          <div className="ms-modal-actions">
            <button className="ms-btn" onClick={() => setFormOpen(false)}>取消</button>
            <button className="ms-btn primary" data-ui="ms-pf-save" disabled={busy} onClick={() => void addProvider()}>添加供应商</button>
          </div>
        </Modal>
      )}
    </section>
  );
}
