import { useEffect, useState } from "react";
import type { Project } from "./api";
import { cnDate, editChange, setDueDate } from "./api";
import DuePicker from "./DuePicker";
import GroupToggle from "./GroupToggle";
import StatusPicker from "./StatusPicker";
import TodoRail from "./TodoRail";
import type { ChatSession } from "./chat/connection";
import { loadBoolPrefs, type BoolPrefs } from "./boolPrefs";
import { groupProjectsByStage } from "./workspace/projectGroups";
import {
  batchKey,
  groupByBatch,
  groupHeading,
  isBatchOpen,
  TODO_BATCH_STORAGE_KEY,
} from "./todoBatches";
import {
  batchEditRequests,
  buildEditRequest,
  dueStatus,
  groupByProject,
  idleProjectKeys,
  isTerminalStatus,
  orderProjectCards,
  sortByDateDesc,
  type ProjectCard,
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
  // 阶段词表(后端 ds_tools.PROJECT_STAGES 经 /api/projects 下发):「按阶段」看法的堆序。
  stages: string[];
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
  stages,
  onGoProject,
  onEdited,
  active,
  dataEpoch,
  session,
}: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<"project" | "time" | "stage">("project");
  const [reloadNonce, setReloadNonce] = useState(0);
  // 折叠偏好(T4a):只记**用户显式点过**的键 → true/false,没点过的走各自默认规则。
  // 原来是 XOR 一个 useState Set —— 刷新即忘,tasks.md 点名的旧债,这里还上。
  // 落盘只落时间批次(@time|<date>);项目卡(@proj|<key>)沿用"默认全展开、不落盘",
  // 本单不动它(改默认视图的行为不在 T4a 的判据里)。
  const [foldPrefs, setFoldPrefs] = useState<BoolPrefs>(() => {
    try {
      return loadBoolPrefs(localStorage.getItem(TODO_BATCH_STORAGE_KEY));
    } catch {
      return {}; // 隐私模式/禁用 storage:偏好丢了也不许白屏
    }
  });

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
  // 当前态由调用方算(各有各的默认规则),所以要传进来 —— 不在这里猜默认。
  // 只把时间批次与阶段堆写进 localStorage:项目卡的开合仍是会话级(见 foldPrefs 注释)。
  function toggleOpen(key: string, currentlyOpen: boolean) {
    setFoldPrefs((prev) => {
      const next = { ...prev, [key]: !currentlyOpen };
      try {
        const persisted: BoolPrefs = {};
        for (const [k, v] of Object.entries(next)) {
          if (k.startsWith("@time|") || k.startsWith("@stage|")) persisted[k] = v;
        }
        localStorage.setItem(TODO_BATCH_STORAGE_KEY, JSON.stringify(persisted));
      } catch {
        /* 存不进去就只在本会话生效,不影响界面 */
      }
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

  // 「按阶段」看法(C):卡不变,只是外面多一层阶段堆。分堆/堆序/未建档垫底全部复用
  // 左栏那份纯逻辑(阶段词表仍是后端 /api/projects 下发的 stages,前端不硬编码副本)。
  // 没在 /api/projects 里的项目(未建档文件夹里冒出来的卡)照 stage:"" 处理 → 未建档堆,
  // **一个项目都不丢**。
  const cardByKey = new Map(filteredProjectCards.map((c) => [c.project, c]));
  const cardProjects: Project[] = filteredProjectCards.map(
    (c) =>
      projects.find((p) => p.key === c.project) ?? {
        key: c.project,
        name: c.project,
        stage: "",
        open_count: c.items.length,
        delivered: false,
        last_update: "",
        unregistered: true,
      },
  );
  const stageSections = groupProjectsByStage(cardProjects, stages);

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

  // 日期批次(todo-v3;T4a 改标题与折叠规则):仅「按时间」视图用。
  // 批次头 = 日期 + **一句人话**(batchTitle 兜底「首条内容 等 N 条」,T4b 换成助手起的名)。
  // 默认开合走 isBatchOpen(≤2 条开 / ≥3 条收 / 有过期强制开),用户点过就以偏好为准并落盘。
  // 折叠控件 = 共享 GroupToggle(track opendesign-todo-layout T3):「全选本组」留在控件外
  // (嵌套 button 非法 + 语义上不是折叠动作)。
  const batches = (items: OpenItem[], scope: string, withProject = false) =>
    groupByBatch(items).map((dg) => {
      // 两个键分开:React 的 key 认"这是哪一组"(用会变的区间 id 也无妨),
      // 折叠偏好认 foldId(带项目、锚在区间起点,延长区间不换键)。
      // **写偏好和读偏好必须用同一个键** —— 用错就是点了没反应的死键。
      const foldKey = batchKey(scope, dg.date, dg.foldId);
      const open = isBatchOpen(dg, foldPrefs, data.today, scope);
      return (
        <div
          className="batch-sect"
          key={`${dg.date ?? "@none"}|${dg.id ?? "@loose"}`}
          data-date={dg.date ?? "@none"}
          {...(dg.id ? { "data-batch": dg.id } : {})}
        >
          <div className="batch-head">
            <GroupToggle open={open} onToggle={() => toggleOpen(foldKey, open)}>
              <span className="d8">{dg.date ? cnDate(dg.date) : "未标注日期"}</span>
              <span className="batch-title">{groupHeading(dg)}</span>
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
          {/* 真机反馈 2026-07-24 #6:没空间就不写名字(原来顶着「未分空间」四个字)。
              分节与「全选本组」保留——去掉的是字,不是功能。 */}
          {sec.space && <span className="nm">{sec.space}</span>}
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

  // 项目卡(「按项目」与「按阶段」共用同一份 —— 后者只是把它装进阶段堆里,
  // 不另起第二种卡片语言)。
  const projectCard = (c: ProjectCard) => {
    const p = projects.find((x) => x.key === c.project);
    const cardKey = batchKey("@proj", c.project);
    // 项目卡默认全部展开(用户是来看待办的);点过就以偏好为准。
    // @proj 键不落盘 —— 保持原来的会话级行为,T4a 不改默认视图。
    const open = foldPrefs[cardKey] ?? true;
    return (
      <section className="todo-card" key={c.project}>
        <header className="card-head">
          <GroupToggle open={open} onToggle={() => toggleOpen(cardKey, open)}>
            <span className="ico-col"><span className={dotClass(p)} /></span>
            <span className="nm">{p?.name ?? c.project}</span>
            <span className="n-open">{c.items.length} 条未办结</span>
            {c.stale !== null && <span className="stale-badge">⛑ {c.stale} 天没动静</span>}
          </GroupToggle>
          <button className="link-act" onClick={() => onGoProject(c.project)}>
            去项目
          </button>
        </header>
        {open && spaceBatches(c.items)}
      </section>
    );
  };

  return (
    <div className="page todo-page">
      {/* 题头提到顶部占满整宽(真机反馈 2026-07-24):下面主区+右栏并排、顶边齐平,
          日历白卡与左边首张待办卡从同一 y 起。
          ⚠️ 题头虽整宽,切换器**必须紧跟副标题左对齐**(真机反馈 2026-07-31):
          这里曾有个 `.grow` 弹簧把 .seg 顶到题头最右端,题头一改整宽,它就被甩到整个
          视口的右上角 = 右栏 TodoRail 的正上方,离用户在看的卡片最远。别再加回来 ——
          要它靠右,得先解决"靠谁的右"(主区的右缘,不是视口的)。
          判据 tests/e2e/todo_view_switcher.e2e.mjs 的 A/B 段盯这件事,C/D 段盯上面那条
          齐平修复不许因此回归。 */}
      <header className="todo-head">
        <h2 className="serif">待办事项</h2>
        <span className="sub">
          {data.open.length} 条未办结 · {groups.length} 个项目
        </span>
        {/* 分组=选视图,全应用统一用 .seg 分段开关(与变更记录、参考/项目图 tab 同款) */}
        <div className="seg">
          <button
            className={`opt${view === "project" ? " on" : ""}`}
            onClick={() => setView("project")}
          >
            按项目
          </button>
          <button
            className={`opt${view === "time" ? " on" : ""}`}
            onClick={() => setView("time")}
          >
            按时间
          </button>
          <button
            className={`opt${view === "stage" ? " on" : ""}`}
            onClick={() => setView("stage")}
          >
            按阶段
          </button>
        </div>
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

          {view === "project" && data.open.length > 0 && (
            <div className="todo-cards by-project">
              {filteredProjectCards.map(projectCard)}
              {idleNames.length > 0 && (
                <div className="todo-card idle-card" data-ui="todo-idle-card">
                  {idleNames.join("、")} 没有未办结事项
                </div>
              )}
            </div>
          )}

          {/* 「按阶段」(C,07-30 真机反馈):不是第三种卡片语言,只是把同一批项目卡
              装进阶段堆里 —— 分堆逻辑复用左栏那份 groupProjectsByStage(零新字段)。 */}
          {view === "stage" && data.open.length > 0 && (
            <div className="todo-cards by-stage">
              {stageSections.map((g) => {
                const sectKey = batchKey("@stage", g.stage);
                // 默认全展开,与项目卡同一条理由(用户是来看待办的)。
                // **刻意不抄左栏 isStageGroupOpen 的「整堆已交付则默认收起」**:
                // 这里的卡只在有未办结条目时才出现,已交付项目还挂着待办恰恰最该被看见。
                const open = foldPrefs[sectKey] ?? true;
                const n = g.projects.reduce(
                  (sum, p) => sum + (cardByKey.get(p.key)?.items.length ?? 0),
                  0,
                );
                return (
                  <section className="stage-sect" data-stage={g.stage} key={g.stage}>
                    <div className="stage-sect-head">
                      <GroupToggle open={open} onToggle={() => toggleOpen(sectKey, open)}>
                        <span className="nm">{g.stage}</span>
                        <span className="n-open">
                          {g.projects.length} 个项目 · {n} 条未办结
                        </span>
                      </GroupToggle>
                    </div>
                    {open &&
                      g.projects.map((p) => {
                        const c = cardByKey.get(p.key);
                        return c ? projectCard(c) : null;
                      })}
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
