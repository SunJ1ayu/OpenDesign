import { useEffect, useMemo, useRef, useState } from "react";
import type { Change, Project } from "../api";
import { cnDate, editChange } from "../api";
import StatusPicker from "../StatusPicker";

// 中央变更记录列(handoff §2,flex:1):项目大标题 + 工具行(筛选胶囊)+ 变更列表。
// 每行状态 pill 可点直接改(todo-ux2):在「全部」筛选下已完成/已关闭也在,故这里是**随时回滚**
// 的家(点 pill 改回待确认/任意状态);写口径复用 /api/changes/edit 针孔。
// highlight(p4 T4):搜索回车直达 → 筛选切「全部」+ 滚动定位 + 闪烁一下。

type Filter = "open" | "待确认" | "进行中" | "all";

const OPEN_SET = new Set(["待确认", "进行中"]);

type Props = {
  project: Project | null;
  changes: Change[] | null; // null = 加载中
  error: string | null;
  onEdited?: () => void; // 改状态成功后回调(App bump dataEpoch → 变更列/待办角标重拉)
  highlight?: { cnum: number | null; nonce: number };
};

function changeKey(c: Change, i: number): string {
  return c.cnum !== null ? `c${c.cnum}` : `i${i}`;
}

export default function ChangesColumn({
  project, changes, error, onEdited, highlight,
}: Props) {
  const [filter, setFilter] = useState<Filter>("open");
  const [hl, setHl] = useState<number | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  const counts = useMemo(() => {
    const list = changes ?? [];
    const pending = list.filter((c) => c.status === "待确认").length;
    const doing = list.filter((c) => c.status === "进行中").length;
    return { pending, doing, open: pending + doing, all: list.length };
  }, [changes]);

  const shown = useMemo(() => {
    const list = changes ?? [];
    if (filter === "all") return list;
    if (filter === "open") return list.filter((c) => OPEN_SET.has(c.status));
    return list.filter((c) => c.status === filter);
  }, [changes, filter]);

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

  // p7:工作区自动发现的未建档文件夹——没有档案可读,给建档引导
  if (project.unregistered) {
    return (
      <section className="center">
        <div className="center-head">
          <div className="proj-title">{project.name}</div>
        </div>
        <div className="center-empty">
          <div className="big">工作区项目,还未建档</div>
          <div>
            右侧文件和图墙已经可用;在对话里说「新建项目:{project.name}」,
            就能开始记录这个项目的变更。
          </div>
        </div>
      </section>
    );
  }

  const pills: { key: Filter; label: string; n?: number }[] = [
    { key: "open", label: "未办结", n: counts.open },
    { key: "待确认", label: "待确认", n: counts.pending },
    { key: "进行中", label: "进行中", n: counts.doing },
    { key: "all", label: "全部" },
  ];

  return (
    <section className="center">
      <div className="center-head">
        <div className="proj-title">{project.name}</div>
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
                <div className="txt">{c.text}</div>
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
