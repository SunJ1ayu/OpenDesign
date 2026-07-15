import { useEffect, useState } from "react";
import type { Project } from "./api";
import { cnDate, editChange } from "./api";
import {
  buildEditRequest,
  groupByProject,
  groupBySpace,
  isTerminalStatus,
  sortByDateDesc,
  staleDays,
  STATUS_HINT,
  STATUSES,
  type EditDraft,
  type OpenItem,
  type StaleItem,
} from "./todo";

// 4a 待办事项页(track p4 T3 + todo-edit T6 + todo-ux):项目卡 + 空间小节 + 超期标签
// + 按项目/按时间切换 + 行内直接编辑 + 状态 pill 一键改(快捷菜单)+ 终态撤销 toast。
// 数据 = /api/todos(ds_todo.collect 单一真相源;只含未办结=待确认/进行中)。
// 分组/排序/请求装配在 ./todo.ts(纯函数,oracle 直测),本文件只管摆 + 调 editChange 针孔。
// 编辑写口:POST /api/changes/edit → ds_tools.edit_change(保格式 + 向变更历史段留痕)。
// 乐观回显(本会话):改正文后「改过·看原文」、加备注后「备注:…」;持久留痕在工作台变更列
// (/changes 端点带 history)——待办页数据源不带 history/note,accepted deviation。

type Todos = {
  today: string;
  stale_days: number;
  open: OpenItem[];
  stale: StaleItem[];
};

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: Todos };

// 页面级瞬时提示:终态变更后的撤销,或一句错误。
type Toast =
  | { kind: "undo"; project: string; cnum: number; label: string; prevStatus: string }
  | { kind: "error"; message: string };

type Props = {
  projects: Project[];
  onGoProject: (key: string) => void;
  onEdited?: () => void; // 成功编辑后回调(App bump dataEpoch:刷侧栏角标/项目列表)
};

function dotClass(p: Project | undefined): string {
  if (!p) return "dot open";
  if (p.delivered) return "dot done";
  if (p.open_count > 0) return "dot open";
  return "dot idle";
}

// 后端 error code → 人话
function editErrMsg(code: string): string {
  switch (code) {
    case "change_not_found":
      return "这条待办找不到了(可能刚被改动),刷新重试。";
    case "invalid_status":
      return "状态不合法。";
    case "empty_text":
      return "正文不能为空。";
    default:
      return `保存失败(${code})。`;
  }
}

function editId(it: OpenItem): string | null {
  return it.cnum !== null ? `${it.project}:C${it.cnum}` : null;
}

export default function TodoPage({ projects, onGoProject, onEdited }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<"project" | "time">("project");
  const [reloadNonce, setReloadNonce] = useState(0);

  // 行内编辑态
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditDraft>({});
  const [saving, setSaving] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  // 状态快捷菜单:打开的行 editId(null=没开)
  const [menuFor, setMenuFor] = useState<string | null>(null);
  // 页面级瞬时提示(撤销 / 错误)
  const [toast, setToast] = useState<Toast | null>(null);
  // 本会话乐观留痕:editId → 旧正文(「改过·看原文」)/ editId → 备注(「备注:…」)
  const [edited, setEdited] = useState<Record<string, string>>({});
  const [noted, setNoted] = useState<Record<string, string>>({});

  useEffect(() => {
    let stale = false;
    fetch("/api/todos")
      .then(async (r) => {
        if (!r.ok) throw new Error(`服务返回 ${r.status}`);
        const data = (await r.json()) as Todos;
        if (!stale) setState({ kind: "ready", data });
      })
      .catch((e: Error) => {
        if (stale) return;
        // 重拉失败不抹掉已有数据;首拉失败才进 error 页
        setState((s) =>
          s.kind === "ready"
            ? s
            : {
                kind: "error",
                message: `读不到待办(${e.message})。确认 ds-web 服务在跑,刷新重试。`,
              },
        );
      });
    return () => {
      stale = true;
    };
  }, [reloadNonce]);

  // 撤销 toast 自动消失(错误提示也走同一超时);再次变更会覆盖旧 toast。
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  function reload() {
    setReloadNonce((n) => n + 1);
    onEdited?.();
  }

  function startEdit(it: OpenItem) {
    setMenuFor(null);
    setEditing(editId(it));
    setDraft({ status: it.status, text: it.text, note: "" });
    setEditErr(null);
  }

  function cancelEdit() {
    setEditing(null);
    setDraft({});
    setEditErr(null);
  }

  // A1:状态 pill 快捷菜单直接改(不进编辑态)。A2:改到终态 → 弹撤销 toast。
  async function quickSetStatus(it: OpenItem, next: string) {
    setMenuFor(null);
    const req = buildEditRequest(it, { status: next });
    if (!req) return; // no-op(==原状态)
    try {
      await editChange(req);
      setToast(
        isTerminalStatus(next) && it.cnum !== null
          ? { kind: "undo", project: it.project, cnum: it.cnum, label: next, prevStatus: it.status }
          : null,
      );
      reload();
    } catch (e) {
      setToast({ kind: "error", message: editErrMsg((e as Error).message) });
    }
  }

  // A2:撤销 = 把状态改回变更前的原状态。
  async function undoStatus(t: Extract<Toast, { kind: "undo" }>) {
    setToast(null);
    try {
      await editChange({ project: t.project, cnum: t.cnum, new_status: t.prevStatus });
      reload();
    } catch (e) {
      setToast({ kind: "error", message: editErrMsg((e as Error).message) });
    }
  }

  async function save(it: OpenItem) {
    const req = buildEditRequest(it, draft);
    if (!req) {
      cancelEdit();
      return; // 无有效改动:直接关
    }
    setSaving(true);
    setEditErr(null);
    try {
      await editChange(req);
      const eid = editId(it);
      if (eid && req.new_text !== undefined) {
        setEdited((m) => ({ ...m, [eid]: it.text })); // 记旧正文供看原文
      }
      if (eid && req.note !== undefined) {
        setNoted((m) => ({ ...m, [eid]: req.note! })); // A3:备注乐观回显
      }
      setEditing(null);
      setDraft({});
      // 改到终态 → 撤销 toast(与快捷菜单同款)
      setToast(
        req.new_status !== undefined && isTerminalStatus(req.new_status) && it.cnum !== null
          ? { kind: "undo", project: it.project, cnum: it.cnum, label: req.new_status, prevStatus: it.status }
          : null,
      );
      reload();
    } catch (e) {
      setEditErr(editErrMsg((e as Error).message));
    } finally {
      setSaving(false);
    }
  }

  if (state.kind === "loading")
    return <div className="page"><p className="muted">读取中…</p></div>;
  if (state.kind === "error")
    return <div className="page"><p className="error-note">{state.message}</p></div>;

  const { data } = state;
  const groups = groupByProject(data.open);
  const carded = new Set(groups.map((g) => g.project));
  const restCount = projects.filter((p) => !carded.has(p.key)).length;
  const staleNoCard = data.stale.filter((s) => !carded.has(s.project));

  const editor = (it: OpenItem) => (
    <div className="todo-row editing" key={`edit:${it.project}:${it.line}`}>
      <span className="cnum">{it.cnum !== null ? `C${it.cnum}` : "—"}</span>
      <div className="edit-fields">
        <input
          className="edit-text"
          value={draft.text ?? ""}
          autoFocus
          onChange={(e) => setDraft((d) => ({ ...d, text: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === "Enter") save(it);
            else if (e.key === "Escape") cancelEdit();
          }}
        />
        <div className="edit-controls">
          <select
            className="edit-status"
            value={draft.status ?? it.status}
            onChange={(e) => setDraft((d) => ({ ...d, status: e.target.value }))}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s} · {STATUS_HINT[s]}</option>
            ))}
          </select>
          <input
            className="edit-note"
            placeholder="加备注(可选)"
            value={draft.note ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, note: e.target.value }))}
          />
          <button className="btn-save" disabled={saving} onClick={() => save(it)}>
            {saving ? "保存中…" : "保存"}
          </button>
          <button className="btn-cancel" disabled={saving} onClick={cancelEdit}>
            取消
          </button>
        </div>
        {editErr && <div className="error-note sm">{editErr}</div>}
      </div>
    </div>
  );

  // 状态单元:pill 是按钮(cnum 可编辑时),点开快捷菜单直接改状态。
  const statusCell = (it: OpenItem) => {
    const eid = editId(it);
    if (!eid) {
      // 残缺行(cnum=null)不可改:退化为纯展示
      return (
        <span className={`st-pill st-${it.status}`} title={STATUS_HINT[it.status as keyof typeof STATUS_HINT]}>
          <span className="d" />
          {it.status}
        </span>
      );
    }
    const open = menuFor === eid;
    return (
      <span className="st-cell">
        <button
          className={`st-pill st-btn st-${it.status}${open ? " open" : ""}`}
          title={`${STATUS_HINT[it.status as keyof typeof STATUS_HINT] ?? ""} · 点击改状态`}
          onClick={() => setMenuFor(open ? null : eid)}
        >
          <span className="d" />
          {it.status}
          <span className="caret">⌄</span>
        </button>
        {open && (
          <>
            <div className="st-menu-backdrop" onClick={() => setMenuFor(null)} />
            <div className="st-menu" role="menu">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  className={
                    `st-menu-item${s === it.status ? " current" : ""}` +
                    (isTerminalStatus(s) ? " term" : "")
                  }
                  disabled={s === it.status}
                  onClick={() => quickSetStatus(it, s)}
                >
                  <span className={`chip st-${s}`}><span className="d" />{s}</span>
                  <span className="hint">{STATUS_HINT[s]}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </span>
    );
  };

  const row = (it: OpenItem, i: number, withProject = false) => {
    const eid = editId(it);
    if (eid && editing === eid) return editor(it);
    const oldText = eid ? edited[eid] : undefined;
    const note = eid ? noted[eid] : undefined;
    return (
      <div className="todo-row" key={`${it.project}:${it.line}:${i}`}>
        <span className="cnum">{it.cnum !== null ? `C${it.cnum}` : "—"}</span>
        <span className="txt">
          {it.text}
          {oldText !== undefined && (
            <span className="edited-tag" title={`原:${oldText}`}>
              改过 · 看原文
            </span>
          )}
          {note !== undefined && <span className="note-tag">备注:{note}</span>}
        </span>
        <span className="meta">
          {withProject && (
            <button className="proj-link" onClick={() => onGoProject(it.project)}>
              {it.project}
            </button>
          )}
          {cnDate(it.date)}
          {it.cnum !== null && (
            <button className="edit-btn" onClick={() => startEdit(it)}>
              编辑
            </button>
          )}
        </span>
        {statusCell(it)}
      </div>
    );
  };

  return (
    <div className="page todo-page">
      <header className="todo-head">
        <h2 className="serif">待办事项</h2>
        <span className="sub">
          {data.open.length} 条未办结 · {groups.length} 个项目
        </span>
        <span className="grow" />
        <div className="filter-pills">
          <button
            className={`pill${view === "project" ? " on" : ""}`}
            onClick={() => setView("project")}
          >
            按项目
          </button>
          <button
            className={`pill${view === "time" ? " on" : ""}`}
            onClick={() => setView("time")}
          >
            按时间
          </button>
        </div>
      </header>

      {data.open.length === 0 && (
        <div className="todo-empty muted">所有项目都没有未办结事项,喝口茶吧。</div>
      )}

      {view === "project" && data.open.length > 0 && (
        <div className="todo-cards">
          {groups.map((g) => {
            const p = projects.find((x) => x.key === g.project);
            const days = staleDays(data.stale, g.project);
            return (
              <section className="todo-card" key={g.project}>
                <header className="card-head">
                  <span className="ico-col"><span className={dotClass(p)} /></span>
                  <span className="nm">{p?.name ?? g.project}</span>
                  <span className="n-open">{g.items.length} 条未办结</span>
                  {days !== null && (
                    <span className="stale-badge">⛑ {days} 天没动静</span>
                  )}
                  <span className="grow" />
                  <button className="go-link" onClick={() => onGoProject(g.project)}>
                    去项目 →
                  </button>
                </header>
                {groupBySpace(g.items).map((sg) => (
                  <div className="space-sect" key={sg.space ?? "@none"}>
                    <div className="space-head">
                      <span>{sg.space ?? "未标注"}</span>
                      <span className="rule" />
                    </div>
                    {sg.items.map((it, i) => row(it, i))}
                  </div>
                ))}
              </section>
            );
          })}
        </div>
      )}

      {view === "time" && data.open.length > 0 && (
        <div className="todo-cards">
          <section className="todo-card flat">
            {sortByDateDesc(data.open).map((it, i) => row(it, i, true))}
          </section>
        </div>
      )}

      {staleNoCard.map((s) => (
        <div className="todo-rest muted" key={s.project}>
          ⛑ {projects.find((p) => p.key === s.project)?.name ?? s.project} —{" "}
          {s.days} 天没动静(无未办结条目)
        </div>
      ))}
      {data.open.length > 0 && restCount > 0 && (
        <div className="todo-rest muted">其余 {restCount} 个项目没有未办结事项</div>
      )}

      {toast && (
        <div className={`todo-toast ${toast.kind}`} role="status">
          {toast.kind === "undo" ? (
            <>
              <span>已标记「{toast.label}」</span>
              <button className="toast-undo" onClick={() => undoStatus(toast)}>撤销</button>
            </>
          ) : (
            <span>{toast.message}</span>
          )}
          <button className="toast-x" onClick={() => setToast(null)} aria-label="关闭">✕</button>
        </div>
      )}
    </div>
  );
}
