import { useEffect, useState } from "react";

// /api/todos 的形状 = ds_todo.collect() 输出(单一真相源,字段勿在前端另造)
type OpenItem = {
  project: string;
  line: number;
  raw: string;
  status: string;
  cnum: number | null;
  date: string | null;
  text: string;
};
type StaleItem = { project: string; days: number; last: string };
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

function groupByProject(items: OpenItem[]): [string, OpenItem[]][] {
  const order: string[] = [];
  const map = new Map<string, OpenItem[]>();
  for (const it of items) {
    if (!map.has(it.project)) {
      map.set(it.project, []);
      order.push(it.project);
    }
    map.get(it.project)!.push(it);
  }
  return order.map((p) => [p, map.get(p)!]);
}

export default function TodoPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

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

  if (state.kind === "loading") return <p className="muted">读取中…</p>;
  if (state.kind === "error") return <p className="error-note">{state.message}</p>;

  const { data } = state;
  const groups = groupByProject(data.open);

  return (
    <div className="todo-page">
      <header className="page-head">
        <h2>待办</h2>
        <span className="muted">
          {data.today} · 未关闭 {data.open.length} 条 · 超期 {data.stale.length} 个项目
        </span>
      </header>

      <section>
        <h3>未关闭事项（待确认 / 进行中）</h3>
        {groups.length === 0 && (
          <p className="muted">没有未关闭的变更。在聊天里记下新变更,这里会出现。</p>
        )}
        {groups.map(([project, items]) => (
          <div className="project-card" key={project}>
            <div className="project-name">{project}</div>
            <ul className="change-list">
              {items.map((it) => (
                <li key={`${it.project}:${it.line}`}>
                  {/* C 编号照 CAD 图纸修订标签画:方框角标,设计师的母语 */}
                  <span className="rev-tag">{it.cnum !== null ? `C${it.cnum}` : "C?"}</span>
                  <span
                    className={`status status-${it.status === "待确认" ? "pending" : "doing"}`}
                  >
                    {it.status}
                  </span>
                  <span className="change-text">{it.text || it.raw}</span>
                  {it.date && <span className="change-date">{it.date}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section>
        <h3>超过 {data.stale_days} 天未更新的项目</h3>
        {data.stale.length === 0 && <p className="muted">没有超期项目。</p>}
        {data.stale.length > 0 && (
          <ul className="stale-list">
            {data.stale.map((s) => (
              <li key={s.project}>
                <span className="stale-days">{s.days} 天</span>
                <span className="project-name-inline">{s.project}</span>
                <span className="muted">最后更新 {s.last}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
