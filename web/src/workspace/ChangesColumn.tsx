import { useEffect, useMemo, useRef, useState } from "react";
import type { Change, Project } from "../api";
import { addChange, cnDate, createProject, editChange } from "../api";
import StatusPicker from "../StatusPicker";
import type { Filter } from "./changes";
import { changeCounts, filterChanges, PROGRESS_ORDER } from "./changes";

// 中央变更记录列(handoff §2,flex:1):项目大标题 + 进度一览 + 工具行(筛选胶囊)+ 变更列表。
// 每行状态 pill 可点直接改(todo-ux2):在「全部」/「已办结」筛选下已完成/已关闭也在,故这里是
// **随时回滚**的家(点 pill 改回待确认/任意状态);写口径复用 /api/changes/edit 针孔。
// 计数/筛选分类抽到 ./changes(纯逻辑,oracle 直测);本文件只管渲染与交互。
// highlight(p4 T4):搜索回车直达 → 筛选切「全部」+ 滚动定位 + 闪烁一下。

type Props = {
  project: Project | null;
  changes: Change[] | null; // null = 加载中
  error: string | null;
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
function createProjectErrMsg(code: string): string {
  if (code === "empty_name") return "项目名和业主名都要填。";
  if (code === "bad_stage") return "阶段不在词表里。";
  if (code === "project_exists") return "这个项目已经建过档了,刷新看看。";
  return `建档失败(${code})。`;
}

export default function ChangesColumn({
  project, changes, error, onEdited, onCreated, highlight,
}: Props) {
  const [filter, setFilter] = useState<Filter>("open");
  const [hl, setHl] = useState<number | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 「+ 记一条」快捷输入(track opendesign-clickable-actions T3)
  const [addText, setAddText] = useState("");
  const [addSpace, setAddSpace] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const [addErr, setAddErr] = useState<string | null>(null);
  // 变更行正文就地编辑(track opendesign-frontend-p1 §①)
  const [editingCnum, setEditingCnum] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  // 切项目清空快捷输入:防"给 A 打字→切到 B→提交记进 B"的串项目(与建档表单同款重置)
  useEffect(() => {
    setAddText("");
    setAddSpace("");
    setAddErr(null);
    setEditingCnum(null);
    setEditDraft("");
    setEditErr(null);
  }, [project?.key]);

  async function submitAdd() {
    const content = addText.trim();
    if (!project || !content || addBusy) return;
    setAddBusy(true);
    setAddErr(null);
    try {
      await addChange({ project: project.key, content, space: addSpace.trim() || undefined });
      setAddText("");
      setAddSpace("");
      onEdited?.();
    } catch (e) {
      setAddErr(addChangeErrMsg((e as Error).message));
    } finally {
      setAddBusy(false);
    }
  }

  // 「一键建档」小表单(未建档空态,track opendesign-clickable-actions T4)
  const [cpName, setCpName] = useState(project?.unregistered ? project.name : "");
  const [cpClient, setCpClient] = useState("");
  const [cpBusy, setCpBusy] = useState(false);
  const [cpErr, setCpErr] = useState<string | null>(null);
  // 切到另一个未建档文件夹:表单重新预填该项目名(而非留着上一个的残留输入)
  useEffect(() => {
    if (project?.unregistered) {
      setCpName(project.name);
      setCpClient("");
      setCpErr(null);
    }
  }, [project?.unregistered, project?.key, project?.name]);

  async function submitCreate() {
    const proj = cpName.trim();
    const client = cpClient.trim();
    if (!proj || !client || cpBusy) return;
    setCpBusy(true);
    setCpErr(null);
    try {
      await createProject({ project: proj, client });
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
          <div className="proj-title">{project.name}</div>
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
              disabled={cpBusy}
            />
            <input
              className="edit-text"
              placeholder="业主名(必填)"
              value={cpClient}
              onChange={(e) => setCpClient(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitCreate();
              }}
              disabled={cpBusy}
            />
            <button
              className="btn-save"
              disabled={cpBusy || !cpName.trim() || !cpClient.trim()}
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

  const pills: { key: Filter; label: string; n?: number }[] = [
    { key: "open", label: "未办结", n: counts.open },
    { key: "待确认", label: "待确认", n: counts.待确认 },
    { key: "进行中", label: "进行中", n: counts.进行中 },
    { key: "done", label: "已办结", n: counts.done },
    { key: "all", label: "全部" },
  ];

  return (
    <section className="center">
      <div className="center-head">
        <div className="proj-title">{project.name}</div>
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
        <div className="center-toolbar">
          <span className="t">变更记录</span>
          <span className="n">{counts.all} 条</span>
          <span className="grow" />
          <div className="filter-pills">
            {pills.map((p) => (
              <button
                key={p.key}
                className={`pill${filter === p.key ? " on" : ""}`}
                onClick={() => setFilter(p.key)}
              >
                {p.label}
                {p.n !== undefined && p.n > 0 ? ` ${p.n}` : ""}
              </button>
            ))}
          </div>
        </div>
        <div className="quick-add-change">
          <input
            className="edit-text"
            placeholder="+ 记一条变更…"
            value={addText}
            onChange={(e) => setAddText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitAdd();
            }}
            disabled={addBusy}
          />
          <input
            className="edit-note qac-space"
            placeholder="空间(可选)"
            value={addSpace}
            onChange={(e) => setAddSpace(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitAdd();
            }}
            disabled={addBusy}
          />
          <button
            className="btn-save"
            disabled={addBusy || !addText.trim()}
            onClick={submitAdd}
          >
            {addBusy ? "记录中…" : "记一条"}
          </button>
        </div>
        {addErr && <div className="error-note sm">{addErr}</div>}
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
            </>
          ) : (
            <div className="muted">这个筛选下没有条目</div>
          )}
        </div>
      ) : (
        <div className="change-scroll" ref={scrollRef}>
          {shown.map((c, i) => (
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
                  <div className="txt">
                    {c.text}
                    {c.cnum !== null && (
                      <button
                        className="edit-trigger"
                        onClick={() => startEditText(c)}
                        title="编辑正文"
                      >
                        编辑
                      </button>
                    )}
                  </div>
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
                </div>
              </div>
              {c.cnum !== null ? (
                <StatusPicker status={c.status} onPick={(s) => pickStatus(c, s)} />
              ) : (
                <span className={`st-pill st-${c.status}`}>
                  <span className="d" />
                  {c.status}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {actionErr && <div className="change-action-err error-note sm">{actionErr}</div>}
    </section>
  );
}
