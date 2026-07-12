import { useEffect, useState } from "react";
import type { Project } from "./api";
import { cnDate } from "./api";
import {
  groupByProject,
  groupBySpace,
  sortByDateDesc,
  staleDays,
  type OpenItem,
  type StaleItem,
} from "./todo";

// 4a 待办事项页(track p4 T3,handoff §6):项目卡 + 空间小节 + 超期标签
// + 按项目/按时间切换。数据 = /api/todos(ds_todo.collect 单一真相源);
// 分组/排序在 ./todo.ts(纯函数,oracle 直测),本文件只管摆。
// 超期但无未办结条目的项目没有卡可标 → 底部一行轻提示(不丢旧版的提醒功能,
// 也不违"超期不单列区域"的定稿意图);行 hover 快捷操作本轮不做(2a 已有)。

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

type Props = {
  projects: Project[];
  onGoProject: (key: string) => void;
};

function dotClass(p: Project | undefined): string {
  if (!p) return "dot open";
  if (p.delivered) return "dot done";
  if (p.open_count > 0) return "dot open";
  return "dot idle";
}

export default function TodoPage({ projects, onGoProject }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<"project" | "time">("project");

  useEffect(() => {
    fetch("/api/todos")
      .then(async (r) => {
        if (!r.ok) throw new Error(`服务返回 ${r.status}`);
        setState({ kind: "ready", data: (await r.json()) as Todos });
      })
      .catch((e: Error) =>
        setState({
          kind: "error",
          message: `读不到待办（${e.message}）。确认 ds-web 服务在跑,刷新重试。`,
        }),
      );
  }, []);

  if (state.kind === "loading")
    return <div className="page"><p className="muted">读取中…</p></div>;
  if (state.kind === "error")
    return <div className="page"><p className="error-note">{state.message}</p></div>;

  const { data } = state;
  const groups = groupByProject(data.open);
  const carded = new Set(groups.map((g) => g.project));
  const restCount = projects.filter((p) => !carded.has(p.key)).length;
  const staleNoCard = data.stale.filter((s) => !carded.has(s.project));

  const row = (it: OpenItem, i: number, withProject = false) => (
    <div className="todo-row" key={`${it.project}:${it.line}:${i}`}>
      <span className="cnum">{it.cnum !== null ? `C${it.cnum}` : "—"}</span>
      <span className="txt">{it.text}</span>
      <span className="meta">
        {withProject && (
          <button className="proj-link" onClick={() => onGoProject(it.project)}>
            {it.project}
          </button>
        )}
        {cnDate(it.date)}
      </span>
      <span className={`st-pill st-${it.status}`}>
        <span className="d" />
        {it.status}
      </span>
    </div>
  );

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
    </div>
  );
}
