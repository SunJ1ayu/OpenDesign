import { Fragment, useEffect, useState } from "react";
import type { Project } from "./api";
import { cnDate, editChange, setDueDate } from "./api";
import DuePicker from "./DuePicker";
import GroupToggle from "./GroupToggle";
import StatusPicker from "./StatusPicker";
import TodoRail from "./TodoRail";
import type { ChatSession } from "./chat/connection";
import { batchCaption, batchKey } from "./todoBatches";
import {
  batchEditRequests,
  buildEditRequest,
  dueStatus,
  groupByProject,
  idleProjectKeys,
  isTerminalStatus,
  latestRecordAge,
  orderItems,
  orderProjectCards,
  STALE_AFTER_DAYS,
  type ProjectCard,
  STATUS_HINT,
  type EditDraft,
  type OpenItem,
  type StaleItem,
} from "./todo";

// 4a 待办事项页(track p4 T3 + todo-edit T6 + todo-ux + todo-v3):单一项目卡视图
// + 两轨排序 + 超期标签 + 行内直接编辑
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
  const [reloadNonce, setReloadNonce] = useState(0);
  // 项目卡默认全部展开;用户点过后只在本会话记住。
  const [foldPrefs, setFoldPrefs] = useState<Record<string, boolean>>({});

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

  // 批量选择(track opendesign-todo-batch-space T3):键 = `${project}:${line}`
  // (与 row key 同源,唯一)。应用中禁止重复点。
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

  // keep-mounted 行为对齐(主 agent 收货,panel subglm 提):常驻化之前,离开待办页
  // = 组件卸载 = toast 与编辑态一并丢弃。常驻后它们会跨页存活,切回来可能看到一条
  // 早该过期的 toast,或一个还开着、内容却已被别处改过的编辑框。
  // 本单自定的规矩是「除『对话不丢』外行为必须不可区分」,所以离开时主动清掉这两样,
  // 把旧语义原样还回去。(对话不丢是右栏 ChatPage 的事,不受这里影响。)
  useEffect(() => {
    if (active) return;
    setToast(null);
    setEditing(null);
    setDraft({});
    setEditErr(null);
  }, [active]);

  function reload() {
    setReloadNonce((n) => n + 1);
    onEdited?.();
  }

  // ── 截止日弹出日历(track opendesign-due-picker)────────────────────────────
  // 用户 2026-07-28:「我没法手动设置待办事项的截止日期」。写口 set_due_date 本来
  // 就有,入口原先只在工作区变更栏 —— 而待办页才是他"开始做的时候看"的地方。
  // 开合键 = `${project}:C${cnum}`(与 editId 同源);anchor 存 DOM 节点供浮层贴位。
  const [duePick, setDuePick] = useState<{ key: string; anchor: HTMLElement } | null>(null);
  const [dueBusy, setDueBusy] = useState(false);
  const [dueErr, setDueErr] = useState<string | null>(null);

  function openDuePicker(it: OpenItem, el: HTMLElement) {
    const key = editId(it);
    if (key === null) return; // 残缺行没有 C 号,后端寻址不到,不给入口
    setDueErr(null);
    setDuePick((cur) => (cur && cur.key === key ? null : { key, anchor: el }));
  }

  async function saveDue(it: OpenItem, due: string | null) {
    if (it.cnum === null) return;
    setDueBusy(true);
    setDueErr(null);
    try {
      await setDueDate({ project: it.project, cnum: it.cnum, due });
      setDuePick(null);
      reload();
    } catch (e) {
      // 不关浮层:关掉等于把错误一起吞了,用户只会看到"点了没反应"
      setDueErr(`设置截止日失败(${(e as Error).message})。`);
    } finally {
      setDueBusy(false);
    }
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

  // ── 全选本卡(track opendesign-todo-one-view)────────────────────────────
  // ⚠️ 收货闸③抓到的能力回归:「全选本组」原来挂在空间小节/日期批次头上,
  // 那两个分组头本单被删,按钮跟着没了 —— 但**分组本身没消失,它变成了项目卡**。
  // 0.34.0 交付的"整组一次选中"不能因为换了容器就丢,所以挂回卡头。
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

  // 折叠开合(共享 GroupToggle 用):把这个键的当前展开态取反、记成**显式偏好**。
  function toggleOpen(key: string, currentlyOpen: boolean) {
    setFoldPrefs((prev) => ({ ...prev, [key]: !currentlyOpen }));
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
  const projectCards = orderProjectCards(groups, data.today);
  // 闲置项目 = 已建档项目 − 有卡的 − 已被「档案 N 天没更新」独立行报过的(不重复说同一件事)。
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
    ? orderProjectCards(groupByProject(filteredOpen), data.today)
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
    // 正在设截止日的那条高亮、其余压暗(用户拍板:"一眼看清在给谁设")。
    const dueOpen = duePick !== null;
    const dueTarget = dueOpen && eid !== null && duePick.key === eid;
    return (
      <div
        className={`todo-row${dueTarget ? " due-editing" : ""}${dueOpen && !dueTarget ? " due-dim" : ""}`}
        key={`${it.project}:${it.line}:${i}`}
      >
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
          {/* 截止日(track opendesign-due-picker):**入口就在日期该在的位置** ——
              已经有日期的,那个标签自己就是按钮;还没有的,悬停出一个日历图标。
              原先这里只读、设置入口只在工作区变更栏,而待办页才是用户开工前看的地方。
              着色仍走 dueStatus(与 ChangesColumn .due-tag 同口径)。 */}
          {it.cnum === null ? (
            it.due && (
              <span className={`due-tag due-${dueStatus(it.due, data.today)}`}>
                截止 {cnDate(it.due)}
              </span>
            )
          ) : (
            <button
              type="button"
              className={it.due ? `due-tag due-${dueStatus(it.due, data.today)}` : "due-add"}
              data-ui="due-trigger"
              title={it.due ? "改截止日" : "设截止日"}
              onClick={(e) => openDuePicker(it, e.currentTarget)}
            >
              {/* 空态**不用图标**:截图里 📅 在缺字形的环境下渲染成豆腐块(□),
                  而且图标要用户先学会它是什么意思。用字最稳,也跟有日期时的
                  「截止 7月30日」是同一个词。 */}
              {it.due ? `截止 ${cnDate(it.due)}` : "＋截止"}
            </button>
          )}
          {dueTarget && (
            <DuePicker
              anchor={duePick.anchor}
              value={it.due}
              today={data.today}
              otherDues={data.open
                .filter((o) => o.project === it.project && o.line !== it.line && o.due)
                .map((o) => o.due as string)}
              busy={dueBusy}
              error={dueErr}
              onPick={(d) => saveDue(it, d)}
              onClose={() => setDuePick(null)}
            />
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

  // 项目卡:单一看法。阶段降为卡头标签,条目直接按两轨排序渲染。
  const projectCard = (c: ProjectCard) => {
    const p = projects.find((x) => x.key === c.project);
    const cardKey = batchKey("@proj", c.project);
    // 项目卡默认全部展开(用户是来看待办的);点过就以偏好为准。
    // @proj 键不落盘 —— 保持原来的会话级行为,T4a 不改默认视图。
    const open = foldPrefs[cardKey] ?? true;
    const age = latestRecordAge(c.items, data.today);
    return (
      <section className="todo-card" key={c.project}>
        <header className="card-head">
          <GroupToggle open={open} onToggle={() => toggleOpen(cardKey, open)}>
            <span className="ico-col"><span className={dotClass(p)} /></span>
            <span className="nm">{p?.name ?? c.project}</span>
            {/* 阶段 + 本阶段天数绑成一个视觉单元(G4 截图发现:三个小灰字
                「28 天」「2 条未办结」「最近记录 43 天前」同字号同色排一行,
                串成一片,而「28 天」还没有标签)。card-stage 节点本身不动 ——
                todo_one_view.e2e.mjs:199 锁着它的文字。 */}
            {p?.stage && (
              <span className="card-stage-cell">
                <span className="card-stage" data-ui="card-stage">{p.stage}</span>
                {p?.stage_days !== null && p?.stage_days !== undefined && (
                  <span className="card-stage-days" data-ui="card-stage-days">
                    {p.stage_days} 天
                  </span>
                )}
              </span>
            )}
            <span className="n-open">{c.items.length} 条未办结</span>
            {age !== null && age >= STALE_AFTER_DAYS && (
              <span className="card-recency" data-ui="card-recency">
                最近记录 {age} 天前
              </span>
            )}
          </GroupToggle>
          <button
            className="group-select-btn"
            data-ui="todo-select-group"
            onClick={() => toggleGroup(c.items)}
          >
            {groupAllSelected(c.items) ? "取消本卡" : "全选本卡"}
          </button>
          <button className="link-act" onClick={() => onGoProject(c.project)}>
            去项目
          </button>
        </header>
        {/* 批次小标题(用户 08-01 拍板):0.60.0「助手记录时给这一批起名」原来只在
            被砍掉的「按时间」看法里显示,不接回来它就成了有人写没人看的字段。
            **刻意选最轻的形态**——不加折叠层,只在同一批的第一条上方加一行小字;
            没名字的批次不显示。同一批记录日期相同、软轨按记录日期排 ⇒ 天生挨着,
            所以这行标题不打乱两轨顺序、也不需要重新分组。 */}
        {open && orderItems(c.items, data.today).map((it, i, arr) => {
          const cap = batchCaption(it, i === 0 ? null : arr[i - 1]);
          return (
            <Fragment key={`${it.project}:${it.line}`}>
              {cap && (
                <div className="batch-cap" data-ui="batch-cap">{cap}</div>
              )}
              {row(it, i)}
            </Fragment>
          );
        })}
      </section>
    );
  };

  return (
    <div className="page todo-page">
      {/* 题头提到顶部占满整宽(真机反馈 2026-07-24):下面主区+右栏并排、顶边齐平,
          日历白卡与左边首张待办卡从同一 y 起。 */}
      <header className="todo-head">
        <h2 className="serif">待办事项</h2>
        <span className="sub">
          {data.open.length} 条未办结 · {groups.length} 个项目
        </span>
      </header>

      <div className="todo-body">
        <div className="todo-main">
          {dateFilter && (
            <div className="todo-date-filter" data-ui="todo-date-filter">
              <span>只看 {cnDate(dateFilter)} 到期的事项</span>
              <button onClick={() => setDateFilter(null)}>✕ 清除</button>
            </div>
          )}

          {data.open.length === 0 && (
            <div className="todo-empty muted">所有项目都没有未办结事项,喝口茶吧。</div>
          )}

          {data.open.length > 0 && (
            <div className="todo-cards by-project">
              {filteredProjectCards.map(projectCard)}
              {idleNames.length > 0 && (
                <div className="todo-card idle-card" data-ui="todo-idle-card">
                  {idleNames.join("、")} 没有未办结事项
                </div>
              )}
            </div>
          )}

          {staleNoCard.map((s) => (
            <div className="todo-rest muted" key={s.project}>
              ⛑ {projects.find((p) => p.key === s.project)?.name ?? s.project} —{" "}
              档案 {s.days} 天没更新(无未办结条目)
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
          onTurnEnd={onEdited}
          items={data.open}
          today={data.today}
          selectedDate={dateFilter}
          onSelectDate={toggleDateFilter}
          session={session}
        />
      </div>
    </div>
  );
}
