import { useEffect, useState } from "react";
import type { Project } from "./api";
import { cnDate, editChange } from "./api";
import GroupToggle from "./GroupToggle";
import StatusPicker from "./StatusPicker";
import TodoRail from "./TodoRail";
import type { ChatSession } from "./chat/connection";
import {
  batchEditRequests,
  buildEditRequest,
  dueStatus,
  groupByDate,
  groupByProject,
  idleProjectKeys,
  isTerminalStatus,
  orderProjectCards,
  sortByDateDesc,
  spaceSections,
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

// 页面级瞬时提示:终态变更后的撤销,或一句错误,或批量操作结果。
type Toast =
  | { kind: "undo"; project: string; cnum: number; label: string; prevStatus: string }
  | { kind: "error"; message: string }
  | { kind: "batch"; message: string };

type Props = {
  projects: Project[];
  onGoProject: (key: string) => void;
  onEdited?: () => void; // 成功编辑后回调(App bump dataEpoch:刷侧栏角标/项目列表)
  // track opendesign-todo-assistant T1/T2:keep-mounted 门(隐藏时不取数,
  // 但保留 DOM/UI 态)+ dataEpoch(与 CompanionColumn 同款依赖,保持约定一致)。
  active: boolean;
  dataEpoch: number;
  // T4:右栏项目助手要挂 ChatPage 真身,session 从 App 经这里透传进 TodoRail。
  session: ChatSession;
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

export default function TodoPage({
  projects,
  onGoProject,
  onEdited,
  active,
  dataEpoch,
  session,
}: Props) {
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

  // 批量选择(track opendesign-todo-batch-space T3):选中集与视图无关,键 = `${project}:${line}`
  // (与 row key 同源,唯一;切视图不清空,两视图各自都能选)。应用中禁止重复点。
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);

  // 右栏日历日期过滤(track opendesign-todo-rail T3):点日期是全局意图,两个视图都过滤。
  // 谓词 = it.due === dateFilter;再点同一日期取消。
  const [dateFilter, setDateFilter] = useState<string | null>(null);

  function toggleDateFilter(date: string) {
    setDateFilter((cur) => (cur === date ? null : date));
  }

  // track opendesign-todo-assistant T2:keep-mounted 后照抄 CompanionColumn 的
  // active 约定——`if (!active) return;` + deps 带 dataEpoch/active。三条性质:
  // 进入页面必取数(active 由 false→true 即改变依赖数组,effect 必重跑)、
  // 隐藏期间不取数(早退不发请求)、隐藏时不卸载(state 原样留着,不清空)。
  // 不做 CompanionColumn 那种 stamp 去重——design.md 明确要求"进入必refetch",
  // 与今天"卸载重建"的可观察行为一致,这里刻意更简单。
  useEffect(() => {
    if (!active) return;
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
  }, [reloadNonce, dataEpoch, active]);

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

  // 批量选择:键 = `${project}:${line}`,残缺行(cnum===null)不可寻址,不参与选择。
  function selKey(it: OpenItem): string {
    return `${it.project}:${it.line}`;
  }

  function toggleSelect(it: OpenItem) {
    if (it.cnum === null) return;
    const key = selKey(it);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function selectableKeys(items: OpenItem[]): string[] {
    return items.filter((it) => it.cnum !== null).map(selKey);
  }

  function groupAllSelected(items: OpenItem[]): boolean {
    const keys = selectableKeys(items);
    return keys.length > 0 && keys.every((k) => selected.has(k));
  }

  function toggleGroup(items: OpenItem[]) {
    const keys = selectableKeys(items);
    const allOn = keys.length > 0 && keys.every((k) => selected.has(k));
    setSelected((prev) => {
      const next = new Set(prev);
      for (const k of keys) {
        if (allOn) next.delete(k);
        else next.add(k);
      }
      return next;
    });
  }

  // 折叠开合(共享 GroupToggle 用):反转某 key 的"被点过"标记,复用既有
  // toggled Set(与 XOR 默认机制同源,时间批次 @time|<date> / 项目卡 @proj|<projectKey>)。
  function toggleOpen(key: string) {
    setToggled((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // 应用批量改状态:batchEditRequests 装配 → 逐条串行 await editChange;
  // 成功/失败计数;终态且 ≥2 条先 confirm(终态会把项从页面移除,批量不可逐条撤销)。
  async function applyBatch(newStatus: string) {
    if (applying || state.kind !== "ready") return;
    const byKey = new Map(state.data.open.map((it) => [selKey(it), it]));
    const items = [...selected]
      .map((k) => byKey.get(k))
      .filter((it): it is OpenItem => it !== undefined);
    const reqs = batchEditRequests(items, newStatus);
    if (reqs.length === 0) {
      setSelected(new Set());
      return;
    }
    if (isTerminalStatus(newStatus) && reqs.length >= 2) {
      const ok = window.confirm(
        `确认把选中的 ${reqs.length} 条改为「${newStatus}」?终态批量不可逐条撤销。`,
      );
      if (!ok) return;
    }
    setApplying(true);
    let okCount = 0;
    let failCount = 0;
    try {
      for (const req of reqs) {
        try {
          await editChange(req);
          okCount++;
        } catch {
          failCount++;
        }
      }
    } finally {
      // finally 保证任何意外抛出都不会把浮栏卡在 applying(cancel 禁用)态(panel subglm 提)
      setApplying(false);
    }
    setSelected(new Set());
    setToast({
      kind: "batch",
      message: `已改 ${okCount} 条${failCount > 0 ? ` · ${failCount} 条失败` : ""}`,
    });
    reload();
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
  const staleNoCard = data.stale.filter((s) => !carded.has(s.project));
  // 「按项目」卡序(track opendesign-todo-layout T5):超期天数降序在前、其余未办结数降序在后。
  const projectCards = orderProjectCards(groups, data.stale);
  // 闲置项目 = 已建档项目 − 有卡的 − 已被「⛑ N 天没动静」独立行报过的(不重复说同一件事)。
  const idleKeys = idleProjectKeys(
    projects.filter((p) => !p.unregistered).map((p) => p.key),
    [...carded],
    data.stale.map((s) => s.project),
  );
  const idleNames = idleKeys.map((k) => projects.find((p) => p.key === k)?.name ?? k);

  // 右栏日历日期过滤(T3):谓词 = it.due === dateFilter,两个视图都过滤——只收窄
  // 主列表本身的展示内容;项目完整性信息(闲置项目 / 「⛑ N 天没动静」独立行)与具体
  // 日期无关,过滤态下原样保留,不跟着变。
  const filteredOpen = dateFilter ? data.open.filter((it) => it.due === dateFilter) : data.open;
  const filteredProjectCards = dateFilter
    ? orderProjectCards(groupByProject(filteredOpen), data.stale)
    : projectCards;

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
        <input
          type="checkbox"
          className="todo-select"
          data-ui="todo-select"
          checked={it.cnum !== null && selected.has(selKey(it))}
          disabled={it.cnum === null}
          onChange={() => toggleSelect(it)}
        />
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
          {/* 截止日只读展示(track opendesign-todo-duedate):设置入口留在工作区变更列,
              待办页只显示,按 dueStatus 着色(与 ChangesColumn .due-tag 同口径)。 */}
          {it.due && (
            <span className={`due-tag due-${dueStatus(it.due, data.today)}`}>
              截止 {cnDate(it.due)}
            </span>
          )}
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
  // 批次头自带日期 → 行内不再重复显示日期。折叠控件 = 共享 GroupToggle(track
  // opendesign-todo-layout T3):「全选本组」留在控件外(嵌套 button 非法 + 语义上不是折叠动作)。
  const batches = (items: OpenItem[], scope: string, withProject = false) =>
    groupByDate(items).map((dg, gi) => {
      const key = `${scope}|${dg.date ?? "@none"}`;
      const open = (gi === 0) !== toggled.has(key);
      return (
        <div className="batch-sect" key={key}>
          <div className="batch-head">
            <GroupToggle open={open} onToggle={() => toggleOpen(key)}>
              <span className="d8">{dg.date ? cnDate(dg.date) : "未标注日期"}</span>
              <span className="n">{dg.items.length} 条</span>
            </GroupToggle>
            <button
              className="group-select-btn"
              data-ui="todo-select-group"
              onClick={() => toggleGroup(dg.items)}
            >
              {groupAllSelected(dg.items) ? "取消本组" : "全选本组"}
            </button>
          </div>
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
          <button
            className="group-select-btn"
            data-ui="todo-select-group"
            onClick={() => toggleGroup(sec.items)}
          >
            {groupAllSelected(sec.items) ? "取消本组" : "全选本组"}
          </button>
        </div>
        {sec.items.map((it, j) => row(it, i * 1000 + j))}
      </div>
    ));

  return (
    <div className="page todo-page">
      <div className="todo-main">
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

        {dateFilter && (
          <div className="todo-date-filter" data-ui="todo-date-filter">
            <span>只看 {cnDate(dateFilter)} 到期的事项</span>
            <button onClick={() => setDateFilter(null)}>✕ 清除</button>
          </div>
        )}

        {data.open.length === 0 && (
          <div className="todo-empty muted">所有项目都没有未办结事项,喝口茶吧。</div>
        )}

        {view === "project" && data.open.length > 0 && (
          <div className="todo-cards by-project">
            {filteredProjectCards.map((c) => {
              const p = projects.find((x) => x.key === c.project);
              const cardKey = `@proj|${c.project}`;
              const open = !toggled.has(cardKey); // 项目卡默认全部展开(用户是来看待办的)
              return (
                <section className="todo-card" key={c.project}>
                  <header className="card-head">
                    <GroupToggle open={open} onToggle={() => toggleOpen(cardKey)}>
                      <span className="ico-col"><span className={dotClass(p)} /></span>
                      <span className="nm">{p?.name ?? c.project}</span>
                      <span className="n-open">{c.items.length} 条未办结</span>
                      {c.stale !== null && (
                        <span className="stale-badge">⛑ {c.stale} 天没动静</span>
                      )}
                    </GroupToggle>
                    <button className="go-link" onClick={() => onGoProject(c.project)}>
                      去项目 →
                    </button>
                  </header>
                  {open && spaceBatches(c.items)}
                </section>
              );
            })}
            {idleNames.length > 0 && (
              <div className="todo-card idle-card" data-ui="todo-idle-card">
                {idleNames.join("、")} 没有未办结事项
              </div>
            )}
          </div>
        )}

        {view === "time" && data.open.length > 0 && (
          <div className="todo-cards by-time">
            <section className="todo-card flat">
              {batches(sortByDateDesc(filteredOpen), "@time", true)}
            </section>
          </div>
        )}

        {staleNoCard.map((s) => (
          <div className="todo-rest muted" key={s.project}>
            ⛑ {projects.find((p) => p.key === s.project)?.name ?? s.project} —{" "}
            {s.days} 天没动静(无未办结条目)
          </div>
        ))}

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

        {selected.size > 0 && (
          <div className="todo-batch-bar" data-ui="todo-batch-bar" role="toolbar">
            <span className="n">已选 {selected.size} 条</span>
            <StatusPicker status="" label="改为…" menuUp onPick={applyBatch} />
            <button
              className="batch-cancel"
              disabled={applying}
              onClick={() => setSelected(new Set())}
            >
              取消
            </button>
          </div>
        )}
      </div>

      <TodoRail
        items={data.open}
        today={data.today}
        selectedDate={dateFilter}
        onSelectDate={toggleDateFilter}
        session={session}
      />
    </div>
  );
}
