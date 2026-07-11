import { useMemo, useState } from "react";
import type { Change, Project } from "../api";
import { cnDate } from "../api";

// 中央变更记录列(handoff §2,flex:1):项目大标题 + 工具行(筛选胶囊)+ 变更列表。
// 「✓ 标记完成」不写库:预填聊天输入框交 AI(design 决策,ds_web 保持只读)。

type Filter = "open" | "待确认" | "进行中" | "all";

const OPEN_SET = new Set(["待确认", "进行中"]);

type Props = {
  project: Project | null;
  changes: Change[] | null; // null = 加载中
  error: string | null;
  onMarkDone: (c: Change) => void;
};

function changeKey(c: Change, i: number): string {
  return c.cnum !== null ? `c${c.cnum}` : `i${i}`;
}

export default function ChangesColumn({ project, changes, error, onMarkDone }: Props) {
  const [filter, setFilter] = useState<Filter>("open");

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
        <div className="change-scroll">
          {shown.map((c, i) => (
            <div className={`change-row st-${c.status}`} key={changeKey(c, i)}>
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
              {OPEN_SET.has(c.status) && (
                <button className="mark-done" onClick={() => onMarkDone(c)}>
                  ✓ 标记完成
                </button>
              )}
              <span className={`st-pill st-${c.status}`}>
                <span className="d" />
                {c.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
