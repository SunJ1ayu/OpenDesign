import { useEffect, useState } from "react";
import type { Project } from "./api";
import { cnDate, editChange } from "./api";
import StatusPicker from "./StatusPicker";
import {
  buildEditRequest,
  groupByDate,
  groupByProject,
  isTerminalStatus,
  sortByDateDesc,
  spaceSections,
  staleDays,
  STATUS_HINT,
  type EditDraft,
  type OpenItem,
  type StaleItem,
} from "./todo";

// 4a 待办事项页(track p4 T3 + todo-edit T6 + todo-ux + todo-v3):项目卡 + 日期批次
// 折叠(最新一批默认展开)+ 超期标签 + 按项目/按时间切换 + 行内直接编辑
// + 状态 pill 一键改(快捷菜单)+ 终态撤销 toast。空间为行内标签。
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
  // 日期批次折叠(todo-v3):记"被点过反转"的批次 key,展开态 = 默认(最新一批开) XOR 反转。
  // 会话级不持久化;数据重拉后同 key 沿用用户的开合选择。
  const [toggled, setToggled] = useState<Set<string>>(new Set());

  // 行内编辑态
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditDraft>({});
  const [saving, setSaving] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
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
    const eid = editId(it);
    setEditing(eid);
    // 备注预填既有值(todo-ux2:在原文上改,不是重打);来源=本会话乐观留痕。
    setDraft({ text: it.text, note: (eid && noted[eid]) || "" });
    setEditErr(null);
  }

  function cancelEdit() {
    setEditing(null);
    setDraft({});
    setEditErr(null);
  }

  // A1:状态 pill 快捷菜单直接改(不进编辑态)。A2:改到终态 → 弹撤销 toast。
  async function quickSetStatus(it: OpenItem, next: string) {
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
    const eid = editId(it);
    const req = buildEditRequest(it, draft, (eid && noted[eid]) || "");
    if (!req) {
      cancelEdit();
      return; // 无有效改动:直接关
    }
    setSaving(true);
    setEditErr(null);
    try {
      await editChange(req);
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

  // 状态单元:可编辑行用共享 StatusPicker(点开菜单直接改);残缺行退化纯展示。
  const statusCell = (it: OpenItem) => {
    if (editId(it) === null) {
      return (
        <span className={`st-pill st-${it.status}`} title={STATUS_HINT[it.status as keyof typeof STATUS_HINT]}>
          <span className="d" />
          {it.status}
        </span>
      );
    }
    return <StatusPicker status={it.status} onPick={(s) => quickSetStatus(it, s)} />;
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
          {it.space && <span className="space-chip">{it.space}</span>}
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

  // 日期批次(todo-v3):仅「按时间」视图用。批次头可点折叠;最新一批(gi=0)默认展开。
  // 批次头自带日期 → 行内不再重复显示日期。
  const batches = (items: OpenItem[], scope: string, withProject = false) =>
    groupByDate(items).map((dg, gi) => {
      const key = `${scope}|${dg.date ?? "@none"}`;
      const open = (gi === 0) !== toggled.has(key);
      return (
        <div className="batch-sect" key={key}>
          <button
            className="batch-head"
            aria-expanded={open}
            onClick={() =>
              setToggled((prev) => {
                const next = new Set(prev);
                if (next.has(key)) next.delete(key);
                else next.add(key);
                return next;
              })
            }
          >
            <span className="chev">{open ? "▾" : "▸"}</span>
            <span className="d8">{dg.date ? cnDate(dg.date) : "未标注日期"}</span>
            <span className="n">{dg.items.length} 条</span>
            <span className="rule" />
          </button>
          {open && dg.items.map((it, i) => row(it, i, withProject))}
        </div>
      );
    });

  // 空间小节(修改单 G1,track opendesign-frontend-p2-polish):「按项目」视图用,
  // 不折叠、不按日期分批——纯展示分节,小节眉 = 空间名(null →「未分空间」)。
  const spaceBatches = (items: OpenItem[]) =>
    spaceSections(items).map((sec, i) => (
      <div className="space-sect" key={sec.space ?? "@none"}>
        <div className="space-sect-head" data-ui="todo-space-sect">
          <span className="nm">{sec.space ?? "未分空间"}</span>
          <span className="rule" />
        </div>
        {sec.items.map((it, j) => row(it, i * 1000 + j))}
      </div>
    ));

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
                {spaceBatches(g.items)}
              </section>
            );
          })}
        </div>
      )}

      {view === "time" && data.open.length > 0 && (
        <div className="todo-cards">
          <section className="todo-card flat">
            {batches(sortByDateDesc(data.open), "@time", true)}
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
