import { useEffect, useMemo, useRef, useState } from "react";
import type { Change, Project } from "../api";
import { addChange, cnDate, createProject, editChange, setDueDate, setStage } from "../api";
import DuePicker from "../DuePicker";
import StatusPicker from "../StatusPicker";
import { dueStatus, isTerminalStatus } from "../todo";
import type { Filter } from "./changes";
import { changeCounts, filterChanges, groupByDate, groupBySpace, PROGRESS_ORDER } from "./changes";
import { formatHistoryEntry, historyEntries, historySummary } from "./history";

// 中央变更记录列(handoff §2,flex:1):项目大标题 + 进度一览 + 工具行(筛选胶囊)+ 变更列表。
// 每行状态 pill 可点直接改(todo-ux2):在「全部」/「已办结」筛选下已完成/已关闭也在,故这里是
// **随时回滚**的家(点 pill 改回待确认/任意状态);写口径复用 /api/changes/edit 针孔。
// 计数/筛选分类抽到 ./changes(纯逻辑,oracle 直测);本文件只管渲染与交互。
// highlight(p4 T4):搜索回车直达 → 筛选切「全部」+ 滚动定位 + 闪烁一下。

type Props = {
  project: Project | null;
  changes: Change[] | null; // null = 加载中
  error: string | null;
  // 阶段词表(track opendesign-stage-history §7):单一真相源经 App(/api/projects
  // 顶层 stages)下发,stage-chip 下拉直接列它,不硬编码副本。
  stages: string[];
  onEdited?: () => void; // 改状态成功后回调(App bump dataEpoch → 变更列/待办角标重拉)
  // 建档成功回调(track opendesign-clickable-actions T4):新项目 key,App 据此
  // bump dataEpoch(重拉项目列表)并选中它,人从未建档空态直接落进新项目工作区。
  onCreated?: (key: string) => void;
  highlight?: { cnum: number | null; nonce: number };
};

function changeKey(c: Change, i: number): string {
  return c.cnum !== null ? `c${c.cnum}` : `i${i}`;
}

// 「记一条」错误码 → 中文提示(posture 同 pickStatus 的 change_not_found 分支)
function addChangeErrMsg(code: string): string {
  if (code === "project_not_found") return "这个项目找不到了(可能刚被移走),刷新重试。";
  if (code === "no_change_section") return "这个项目档案没有变更记录段,记不进去。";
  return `记录失败(${code})。`;
}

// 「一键建档」错误码 → 中文提示
// 切阶段的错误码 → 人话(同 createProjectErrMsg 先例;不把裸错误码怼给用户,
// subdeepseek 提的)
function stageErrMsg(code: string): string {
  if (code === "bad_stage") return "这个阶段不在词表里,刷新页面重试。";
  if (code === "project_not_found") return "项目档案找不到了,刷新页面看看。";
  if (code === "bad_name" || code === "path_escape") return "项目名不合法,改不了阶段。";
  return `切阶段失败(${code})。`;
}

function createProjectErrMsg(code: string): string {
  if (code === "empty_name") return "项目名要填。";
  if (code === "bad_stage") return "阶段不在词表里。";
  if (code === "project_exists") return "这个项目已经建过档了,刷新看看。";
  return `建档失败(${code})。`;
}

export default function ChangesColumn({
  project, changes, error, stages, onEdited, onCreated, highlight,
}: Props) {
  const [filter, setFilter] = useState<Filter>("open");
  // 分组切换(track opendesign-todo-batch-space T4):默认按时间;先 filterChanges 再分组渲染,
  // 分节不折叠(v1 从简)。groupByDate/groupBySpace 见 ./changes(镜像 todo.ts,独立实现)。
  const [groupMode, setGroupMode] = useState<"time" | "space">("time");
  const [hl, setHl] = useState<number | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // 切阶段下拉(#7):开合态 + 保存中 + 行内错误。不做乐观改写——阶段是档案头部
  // 字段,以后端回值为准(design.md §7 取舍);保存中禁用菜单再点。
  const [stageMenuOpen, setStageMenuOpen] = useState(false);
  const [stageSaving, setStageSaving] = useState(false);
  const [stageErr, setStageErr] = useState<string | null>(null);
  // 变更行「改过 N 次」展开态(#9):cnum 集合,纯 UI 状态不进 history.ts。
  const [histOpen, setHistOpen] = useState<Set<number>>(new Set());

  // 快记单行输入卡(修改单 B,track opendesign-frontend-p2-polish):圆角卡 =
  // ✎ + 单行 input + 空间 chip(popover:本项目已有空间建议 + 自由输入 + 不指定)
  // + 主色「记一条」。回车提交;**不做 AI 猜空间**——不选 = 无前缀(拍板见 design.md)。
  const [addText, setAddText] = useState("");
  const [addSpace, setAddSpace] = useState(""); // "" = 不指定,提交后恒重置(每条独立选)
  const [addBusy, setAddBusy] = useState(false);
  const [addErr, setAddErr] = useState<string | null>(null);
  const [spacePopOpen, setSpacePopOpen] = useState(false);
  const [spaceFreeInput, setSpaceFreeInput] = useState("");
  const [addToast, setAddToast] = useState<string | null>(null);
  const quickInputRef = useRef<HTMLInputElement>(null);
  // 变更行正文就地编辑(track opendesign-frontend-p1 §①)
  const [editingCnum, setEditingCnum] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  // 截止日设/清(track opendesign-todo-duedate → due-picker):📅 切一个 cnum 的
  // **弹出日历**开合。原先是原生 <input type=date>:要用户翻月历点格子,而用户嘴里
  // 说的是"周六""周天前"。2026-07-28 换成与待办页**同一个** DuePicker ——
  // 用户的要求是"同一个东西一个交互",不做两套(判据 duedate_picker.e2e.mjs G 段
  // 钉住原生输入框真的没了)。anchor 存触发按钮,浮层贴着它弹。
  // 不做乐观改写——成功后 onEdited 整列重拉(与切阶段/正文编辑同套服务端为真相源原则)。
  const [dueEditingCnum, setDueEditingCnum] = useState<number | null>(null);
  const [dueAnchor, setDueAnchor] = useState<HTMLElement | null>(null);
  const [dueSaving, setDueSaving] = useState(false);
  const [dueErr, setDueErr] = useState<string | null>(null);
  // 行内截止日着色的基准"今天":用客户端**本地**日期(纯展示分类,非账本写入)。
  // 不用 toISOString()——那是 UTC,UTC+8 午夜后 8 小时会比本地早一天,把"今天到期"误标超期。
  const today = useMemo(() => {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  }, []);
  // 切项目清空快捷输入:防"给 A 打字→切到 B→提交记进 B"的串项目(与建档表单同款重置)
  useEffect(() => {
    setAddText("");
    setAddSpace("");
    setAddErr(null);
    setSpacePopOpen(false);
    setSpaceFreeInput("");
    setEditingCnum(null);
    setEditDraft("");
    setEditErr(null);
    setDueEditingCnum(null);
    setDueAnchor(null);
    setDueErr(null);
    setStageMenuOpen(false);
    setStageErr(null);
    setHistOpen(new Set());
    setGroupMode("time");
  }, [project?.key]);

  // esc 关阶段下拉(全局原则 A3,同既有 …/状态菜单规矩)
  useEffect(() => {
    if (!stageMenuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setStageMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stageMenuOpen]);

  // 本项目已出现过的空间(首现序),popover 建议行用。
  const existingSpaces = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const c of changes ?? []) {
      if (c.space && !seen.has(c.space)) {
        seen.add(c.space);
        out.push(c.space);
      }
    }
    return out;
  }, [changes]);

  // esc 关空间 popover(全局原则 A3)
  useEffect(() => {
    if (!spacePopOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSpacePopOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [spacePopOpen]);

  // toast 2s 自动淡出
  useEffect(() => {
    if (!addToast) return;
    const t = setTimeout(() => setAddToast(null), 2000);
    return () => clearTimeout(t);
  }, [addToast]);

  async function submitAdd() {
    const content = addText.trim();
    if (!project || !content || addBusy) return;
    setAddBusy(true);
    setAddErr(null);
    try {
      const r = await addChange({ project: project.key, content, space: addSpace || undefined });
      setAddText("");
      setAddSpace(""); // 每条独立选空间,提交后恒重置(不沿用上一条)
      setAddToast(`已记入 ${r.change_id}`);
      const num = Number(r.change_id.replace(/^C/, ""));
      if (!Number.isNaN(num)) setHl(num); // 复用 hl-flash 机制(见下方 change-row className)
      onEdited?.();
    } catch (e) {
      setAddErr(addChangeErrMsg((e as Error).message));
    } finally {
      setAddBusy(false);
    }
  }

  function pickSpace(s: string) {
    setAddSpace(s);
    setSpacePopOpen(false);
    setSpaceFreeInput("");
  }

  // 「一键建档」小表单(未建档空态,track opendesign-clickable-actions T4)
  // 真机反馈 2026-07-24 #3:业主名框整个去掉 —— 建档只填项目名,业主之后用
  // update_client 补(核心 create_project 空业主时不写 [[链接]]、不建 stub)。
  const [cpName, setCpName] = useState(project?.unregistered ? project.name : "");
  const [cpBusy, setCpBusy] = useState(false);
  const [cpErr, setCpErr] = useState<string | null>(null);
  // 切到另一个未建档文件夹:表单重新预填该项目名(而非留着上一个的残留输入)
  useEffect(() => {
    if (project?.unregistered) {
      setCpName(project.name);
      setCpErr(null);
    }
  }, [project?.unregistered, project?.key, project?.name]);

  async function submitCreate() {
    const proj = cpName.trim();
    if (!proj || cpBusy) return;
    setCpBusy(true);
    setCpErr(null);
    try {
      await createProject({ project: proj });
      onCreated?.(proj);
    } catch (e) {
      setCpErr(createProjectErrMsg((e as Error).message));
    } finally {
      setCpBusy(false);
    }
  }

  // 行内改状态(可随时把已完成/已关闭点回待确认等)。全部筛选下条目不消失,无需撤销 toast。
  async function pickStatus(c: Change, next: string) {
    if (!project || c.cnum === null || next === c.status) return;
    setActionErr(null);
    try {
      await editChange({ project: project.key, cnum: c.cnum, new_status: next });
      onEdited?.();
    } catch (e) {
      const code = (e as Error).message;
      setActionErr(
        code === "change_not_found"
          ? "这条变更找不到了(可能刚被改动),刷新重试。"
          : `改状态失败(${code})。`,
      );
    }
  }

  // 切阶段(#7):选中即调针孔;不做乐观改写,成功后靠 onEdited 重拉(App 重拉
  // /api/projects,新阶段随 selected project 回来)。失败保留菜单开着,行内报错。
  async function pickStage(next: string) {
    if (!project || next === project.stage || stageSaving) {
      setStageMenuOpen(false);
      return;
    }
    setStageSaving(true);
    setStageErr(null);
    try {
      await setStage(project.key, next);
      setStageMenuOpen(false);
      onEdited?.();
    } catch (e) {
      setStageErr(stageErrMsg((e as Error).message));
    } finally {
      setStageSaving(false);
    }
  }

  // 设/清截止日:null = 清除。成功后关浮层 + onEdited 重拉(due 随行回来)。
  async function saveDue(c: Change, value: string | null) {
    if (!project || c.cnum === null || dueSaving) return;
    setDueSaving(true);
    setDueErr(null);
    try {
      await setDueDate({ project: project.key, cnum: c.cnum, due: value || null });
      setDueAnchor(null);
      setDueEditingCnum(null);
      onEdited?.();
    } catch (e) {
      setDueErr(`设置截止日失败(${(e as Error).message})。`);
    } finally {
      setDueSaving(false);
    }
  }

  function toggleHistory(cnum: number) {
    setHistOpen((prev) => {
      const next = new Set(prev);
      if (next.has(cnum)) next.delete(cnum);
      else next.add(cnum);
      return next;
    });
  }

  // 行内正文就地编辑(track opendesign-frontend-p1 §①):Enter 保存 / Esc 取消,
  // 服务端为真相源不做乐观 tag——onEdited 整列重拉。空文本/未改动直接取消不发请求。
  function startEditText(c: Change) {
    if (c.cnum === null) return;
    setEditingCnum(c.cnum);
    setEditDraft(c.text);
    setEditErr(null);
  }
  function cancelEditText() {
    setEditingCnum(null);
    setEditDraft("");
    setEditErr(null);
  }
  async function saveEditText(c: Change) {
    if (!project || c.cnum === null || editSaving) return;
    const text = editDraft.trim();
    if (!text || text === c.text) {
      cancelEditText();
      return;
    }
    setEditSaving(true);
    setEditErr(null);
    try {
      await editChange({ project: project.key, cnum: c.cnum, new_text: text });
      cancelEditText();
      onEdited?.();
    } catch (e) {
      setEditErr(`保存失败(${(e as Error).message})。`);
    } finally {
      setEditSaving(false);
    }
  }

  // 搜索直达:换到「全部」(目标可能不在当前筛选下)并记下要闪的编号
  useEffect(() => {
    if (!highlight || highlight.nonce === 0 || highlight.cnum === null) return;
    setFilter("all");
    setHl(highlight.cnum);
  }, [highlight?.nonce]);

  // 数据到位后滚过去;1.6s 后收掉闪烁态
  useEffect(() => {
    if (hl === null || changes === null) return;
    const el = scrollRef.current?.querySelector(`[data-ck="c${hl}"]`);
    el?.scrollIntoView({ block: "center" });
    const t = setTimeout(() => setHl(null), 1600);
    return () => clearTimeout(t);
  }, [hl, changes]);

  const counts = useMemo(() => changeCounts(changes), [changes]);
  const shown = useMemo(() => filterChanges(changes, filter), [changes, filter]);
  // changeKey 的残缺行(cnum===null)分支靠数组下标去重;分组渲染后下标按组重置会撞号,
  // 故用引用做全局下标查找(groupByDate/groupBySpace 只搬引用不拷贝,identity 保持)。
  const globalIndex = useMemo(() => {
    const m = new Map<Change, number>();
    shown.forEach((c, i) => m.set(c, i));
    return m;
  }, [shown]);

  if (!project) {
    return (
      <section className="center">
        <div className="center-empty">
          <div className="big">还没有项目</div>
          <div>在右侧对话里说「新建项目:小区名-户号」,项目会出现在左侧列表。</div>
        </div>
      </section>
    );
  }

  // p7:工作区自动发现的未建档文件夹——没有档案可读,给建档小表单直接建
  if (project.unregistered) {
    return (
      <section className="center">
        <div className="center-head">
          <div className="head-row">
            <div className="proj-title">{project.name}</div>
            <span className="stage-chip unreg" data-ui="stage-chip">未建档</span>
          </div>
        </div>
        <div className="center-empty">
          <div className="big">工作区项目,还未建档</div>
          <div>右侧文件和图墙已经可用;建个档就能开始记录这个项目的变更。</div>
          <div className="create-proj-form">
            <input
              className="edit-text"
              placeholder="项目名"
              value={cpName}
              onChange={(e) => setCpName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitCreate();
              }}
              disabled={cpBusy}
            />
            <button
              className="btn-primary"
              disabled={cpBusy || !cpName.trim()}
              onClick={submitCreate}
            >
              {cpBusy ? "建档中…" : "建档"}
            </button>
          </div>
          {cpErr && <div className="error-note sm">{cpErr}</div>}
        </div>
      </section>
    );
  }

  // 单条变更行(修改单 E + #9 备注/历史):按时间/按空间分组(T4)后仍复用同一渲染,
  // 结构与 .change-row 不动;全局下标(globalIndex)供 changeKey 残缺行去重,
  // 避免分组后每组下标各自从 0 起数导致 key/data-ck 撞号。
  const renderRow = (c: Change) => {
    const i = globalIndex.get(c) ?? 0;
    return (
      <div
        className={`change-row st-${c.status}${c.cnum !== null && c.cnum === hl ? " hl-flash" : ""}`}
        data-ck={changeKey(c, i)}
        key={changeKey(c, i)}
      >
        <span className="cnum">{c.cnum !== null ? `C${c.cnum}` : "C?"}</span>
        <div className="body">
          {c.cnum !== null && editingCnum === c.cnum ? (
            <div className="edit-fields">
              <input
                className="edit-text"
                value={editDraft}
                autoFocus
                onChange={(e) => setEditDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveEditText(c);
                  else if (e.key === "Escape") cancelEditText();
                }}
                disabled={editSaving}
              />
              <div className="edit-controls">
                <button
                  className="btn-save"
                  disabled={editSaving}
                  onClick={() => saveEditText(c)}
                >
                  {editSaving ? "保存中…" : "保存"}
                </button>
                <button
                  className="btn-cancel"
                  disabled={editSaving}
                  onClick={cancelEditText}
                >
                  取消
                </button>
              </div>
              {editErr && <div className="error-note sm">{editErr}</div>}
            </div>
          ) : (
            <div className="txt">{c.text}</div>
          )}
          <div className="meta">
            {c.space && <span>{c.space}</span>}
            {c.space && (c.date || c.source) && <span>·</span>}
            {(c.date || c.source) && (
              <span>
                {cnDate(c.date)}
                {c.date && c.source ? " " : ""}
                {c.source ?? ""}
              </span>
            )}
            {/* 截止日(track opendesign-todo-duedate):有 due 才带该 tag,按 dueStatus 着色 */}
            {c.due && (
              <span className={`due-tag due-${dueStatus(c.due, today)}`}>
                截止 {cnDate(c.due)}
              </span>
            )}
            {/* #9 备注(与待办页同口径,note-tag)+「改过 N 次」展开(design.md §9) */}
            {c.note !== undefined && <span className="note-tag">备注:{c.note}</span>}
            {c.cnum !== null && historySummary(c) && (
              <button
                type="button"
                className="history-toggle"
                data-ui="history-toggle"
                onClick={() => toggleHistory(c.cnum as number)}
              >
                {historySummary(c)}
              </button>
            )}
          </div>
          {c.cnum !== null && histOpen.has(c.cnum) && (
            <div className="history-list">
              {historyEntries(c).map((h, hi) => (
                <div className="history-entry" data-ui="history-entry" key={hi}>
                  {formatHistoryEntry(h)}
                </div>
              ))}
            </div>
          )}
          {c.cnum !== null && dueEditingCnum === c.cnum && dueAnchor && (
            <DuePicker
              anchor={dueAnchor}
              value={c.due ?? null}
              today={today}
              // 同项目其它条目的截止日 → 格子上打点(用户:免得把三件活约到同一天)。
              // 这里 changes 是**全量**(含已办结),打点也照打:那天有事就是有事。
              otherDues={(changes ?? [])
                .filter((o) => o.cnum !== c.cnum && o.due)
                .map((o) => o.due as string)}
              busy={dueSaving}
              error={dueErr}
              onPick={(d) => saveDue(c, d)}
              onClose={() => { setDueEditingCnum(null); setDueAnchor(null); }}
            />
          )}
        </div>
        {/* 修改单 E:hover 图标按钮组 ✎(编辑,保留 .edit-trigger 兼容)+ ✓(标记完成,
            仅未办结行出);编辑态下隐藏,让 edit-fields 的保存/取消占位 */}
        {c.cnum !== null && editingCnum !== c.cnum && (
          <div className="row-actions">
            <button
              className="icon-act edit-trigger"
              data-ui="change-edit"
              onClick={() => startEditText(c)}
              title="编辑正文"
            >
              ✎
            </button>
            <button
              className="icon-act due-btn"
              data-ui="change-due"
              onClick={(e) => {
                const el = e.currentTarget;
                setDueEditingCnum((cur) => (cur === c.cnum ? null : c.cnum));
                setDueAnchor((cur) => (dueEditingCnum === c.cnum && cur ? null : el));
              }}
              title="设置截止日"
            >
              📅
            </button>
            {!isTerminalStatus(c.status) && (
              <button
                className="icon-act done-btn"
                data-ui="change-done"
                onClick={() => pickStatus(c, "已完成")}
                title="标记完成"
              >
                ✓
              </button>
            )}
          </div>
        )}
        {c.cnum !== null ? (
          <StatusPicker status={c.status} onPick={(s) => pickStatus(c, s)} />
        ) : (
          <span className={`st-pill st-${c.status}`}>
            <span className="d" />
            {c.status}
          </span>
        )}
      </div>
    );
  };

  // status:该胶囊是否精确对应一个状态(决定选中色);未办结/全部是复合筛选 → 无。
  const pills: { key: Filter; label: string; n?: number; status?: string }[] = [
    { key: "open", label: "未办结", n: counts.open },
    { key: "待确认", label: "待确认", n: counts.待确认, status: "待确认" },
    { key: "进行中", label: "进行中", n: counts.进行中, status: "进行中" },
    { key: "done", label: "已办结", n: counts.done, status: "已办结" },
    { key: "all", label: "全部" },
  ];

  return (
    <section className="center">
      <div className="center-head">
        <div className="head-row">
          <div className="proj-title">{project.name}</div>
          {/* 未建档项目在上面的分支已提前 return,这里恒是已建档项目 → chip 恒渲染:
              档案头部缺 `- 阶段:` 行时显「未设阶段」,点开同一下拉即可补上(核心
              set_stage 支持缺行补插——收货闸③抓到「唯一需要补插的场景恰好被 UI 藏了」)。 */}
          <span className="stage-cell">
              {/* innerText 精确等于阶段名(e2e 断言,見 stage_history.e2e.mjs):
                  不塞 caret/图标进按钮文本,可点性靠样式(cursor/hover)传达。 */}
              <button
                type="button"
                className={`stage-chip stage-btn${project.delivered ? " done" : ""}`}
                data-ui="stage-chip"
                disabled={stageSaving}
                onClick={() => setStageMenuOpen((o) => !o)}
                title="点击切换阶段"
              >
                {project.stage || "未设阶段"}
              </button>
              {stageMenuOpen && (
                <>
                  <div className="stage-menu-backdrop" onClick={() => setStageMenuOpen(false)} />
                  <div className="stage-menu" data-ui="stage-menu" role="menu">
                    {stages.map((s) => (
                      <button
                        key={s}
                        className={`stage-menu-item${s === project.stage ? " current" : ""}`}
                        data-ui="stage-option"
                        disabled={s === project.stage || stageSaving}
                        onClick={() => pickStage(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </>
              )}
          </span>
        </div>
        {stageErr && <div className="error-note sm">{stageErr}</div>}
        {counts.all > 0 && (
          <div className="proj-progress" title="项目进度一览(各状态条数)">
            {PROGRESS_ORDER.filter((s) => counts[s] > 0).map((s) => (
              <span className={`prog-item st-${s}`} key={s}>
                <span className="d" />
                {counts[s]} {s}
              </span>
            ))}
          </div>
        )}
        {/* 药丸=选内容(筛选),分段开关=选视图(分组);分组统一用 .seg 且置于右端 */}
        <div className="center-toolbar">
          <span className="t">变更记录</span>
          <span className="n">{counts.all} 条</span>
          <div className="filter-pills">
            {/* 真机反馈 2026-07-24 #5:选中态原本一律全黑。只给**单一状态**的胶囊上语义色
                (与行内 st-pill 同族 token);「未办结」「全部」是复合筛选,保持中性墨
                —— 颜色只在能唯一指代一个状态时才承载信息。 */}
            {pills.map((p) => (
              <button
                key={p.key}
                className={`pill${filter === p.key ? " on" : ""}`}
                data-status={p.status ?? undefined}
                onClick={() => setFilter(p.key)}
              >
                {p.label}
                {p.n !== undefined && p.n > 0 ? ` ${p.n}` : ""}
              </button>
            ))}
          </div>
          <span className="grow" />
          <div className="seg" data-ui="change-group-toggle">
            <button
              className={`opt${groupMode === "time" ? " on" : ""}`}
              onClick={() => setGroupMode("time")}
            >
              按时间
            </button>
            <button
              className={`opt${groupMode === "space" ? " on" : ""}`}
              onClick={() => setGroupMode("space")}
            >
              按空间
            </button>
          </div>
        </div>
        {/* 快记单行输入卡(修改单 B):✎ + 单行 input + 空间 chip(popover)+ 主色「记一条」 */}
        <div className="quicknote-card" data-ui="quicknote-card">
          <span className="qn-icon">✎</span>
          <input
            ref={quickInputRef}
            className="qn-input"
            data-ui="quicknote-input"
            placeholder="记一条变更,如:玄关柜改到 2.4 米,柜顶留检修口…"
            value={addText}
            onChange={(e) => setAddText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitAdd();
            }}
            disabled={addBusy}
          />
          <div className="qn-space-wrap">
            <button
              type="button"
              className="qn-space-chip"
              data-ui="quicknote-space"
              onClick={() => setSpacePopOpen((v) => !v)}
              title="给这条变更标个空间(可不选)"
            >
              {addSpace || "空间"} <span className="caret">⌄</span>
            </button>
            {spacePopOpen && (
              <>
                <div className="qn-pop-backdrop" onClick={() => setSpacePopOpen(false)} />
                <div className="qn-space-pop" data-ui="quicknote-space-pop">
                  {existingSpaces.length > 0 && (
                    <div className="qn-space-sugg">
                      {existingSpaces.map((s) => (
                        <button key={s} className="qn-space-opt" onClick={() => pickSpace(s)}>
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                  <input
                    className="qn-space-input"
                    data-ui="quicknote-space-input"
                    placeholder="自定义空间…"
                    value={spaceFreeInput}
                    onChange={(e) => setSpaceFreeInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const v = spaceFreeInput.trim();
                        if (v) pickSpace(v);
                      }
                    }}
                  />
                  <button className="qn-space-clear" onClick={() => pickSpace("")}>
                    不指定
                  </button>
                </div>
              </>
            )}
          </div>
          <button
            type="button"
            className="btn-primary qn-submit"
            disabled={addBusy || !addText.trim()}
            onClick={submitAdd}
          >
            {addBusy ? "记录中…" : "记一条"}
          </button>
        </div>
        {addErr && <div className="error-note sm">{addErr}</div>}
        {addToast && (
          <div className="quicknote-toast" data-ui="quicknote-toast">
            {addToast}
          </div>
        )}
      </div>

      {error ? (
        <div className="center-empty">
          <div className="error-note">{error}</div>
        </div>
      ) : changes === null ? (
        <div className="center-empty">
          <div className="muted">读取中…</div>
        </div>
      ) : shown.length === 0 ? (
        <div className="center-empty">
          {counts.all === 0 ? (
            <>
              <div className="big">还没有变更记录</div>
              <div>在右侧对话里说「记一下:玄关柜改到 2.4 米」,会自动记进来。</div>
              <button
                className="btn-secondary"
                data-ui="empty-add-first"
                onClick={() => quickInputRef.current?.focus()}
              >
                记第一条变更
              </button>
            </>
          ) : (
            <div className="muted">这个筛选下没有条目</div>
          )}
        </div>
      ) : (
        <div className="change-scroll" ref={scrollRef}>
          {groupMode === "time"
            ? groupByDate(shown).map((g) => (
                <div className="change-group" key={g.date ?? "@none"}>
                  <div className="change-group-head" data-ui="change-group-head">
                    <span className="nm">{g.date ? cnDate(g.date) : "未标注日期"}</span>
                    <span className="rule" />
                  </div>
                  {g.items.map((c) => renderRow(c))}
                </div>
              ))
            : groupBySpace(shown).map((g) => (
                <div className="change-group" key={g.space ?? "@none"}>
                  <div className="change-group-head" data-ui="change-group-head">
                    {/* #6:没空间就不写名字(同待办页,单一语言) */}
                    {g.space && <span className="nm">{g.space}</span>}
                    <span className="rule" />
                  </div>
                  {g.items.map((c) => renderRow(c))}
                </div>
              ))}
        </div>
      )}
      {actionErr && <div className="change-action-err error-note sm">{actionErr}</div>}
    </section>
  );
}
