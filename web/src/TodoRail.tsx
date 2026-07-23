import { useState } from "react";
import { dueStatus, type OpenItem } from "./todo";
import { dueDates, followUpItems, monthGrid } from "./schedule";

// 待办页右栏(track opendesign-todo-rail T2):320px,两段——① 日程月历
// ② 需要今天跟进(③ 项目助手拆到下一单 opendesign-todo-assistant,右栏容器先建好)。
// 状态边界:当前显示月份自己持有(纯展示态);选中日期由 props 上提给 TodoPage
// (因为要过滤主列表——点日期是全局意图,不是这个组件局部的事)。

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

type Props = {
  items: OpenItem[]; // 全量未办结(不随主列表的 dateFilter 收窄——日历/跟进区是跨项目总览)
  today: string;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
};

function ymFromIso(iso: string): [number, number] {
  const [y, m] = iso.split("-").map(Number);
  return [y, m];
}

function daysBetween(due: string, today: string): number {
  const [dy, dm, dd] = due.split("-").map(Number);
  const [ty, tm, td] = today.split("-").map(Number);
  const d1 = Date.UTC(dy, dm - 1, dd);
  const d2 = Date.UTC(ty, tm - 1, td);
  return Math.round((d2 - d1) / 86400000);
}

export default function TodoRail({ items, today, selectedDate, onSelectDate }: Props) {
  const [[year, month], setYm] = useState<[number, number]>(() => ymFromIso(today));

  function shiftMonth(delta: number) {
    setYm(([y, m]) => {
      let ny = y;
      let nm = m + delta;
      if (nm > 12) {
        nm = 1;
        ny += 1;
      } else if (nm < 1) {
        nm = 12;
        ny -= 1;
      }
      return [ny, nm];
    });
  }

  const grid = monthGrid(year, month);
  const dueStatusByDate = new Map(dueDates(items).map((d) => [d, dueStatus(d, today)]));
  const follow = followUpItems(items, today);

  return (
    <aside className="todo-rail" data-ui="todo-rail">
      <section className="rail-cal">
        <header className="cal-head">
          <button
            type="button"
            className="cal-nav"
            data-ui="cal-prev"
            aria-label="上个月"
            onClick={() => shiftMonth(-1)}
          >
            ‹
          </button>
          <span className="cal-month" data-ui="cal-month">
            {year} 年 {month} 月
          </span>
          <button
            type="button"
            className="cal-nav"
            data-ui="cal-next"
            aria-label="下个月"
            onClick={() => shiftMonth(1)}
          >
            ›
          </button>
        </header>
        <div className="cal-weekdays">
          {WEEKDAYS.map((w) => (
            <span key={w}>{w}</span>
          ))}
        </div>
        <div className="cal-grid">
          {grid.map((c) => {
            const status = dueStatusByDate.get(c.date);
            const cls = [
              "cal-cell",
              c.inMonth ? "in-month" : "",
              c.date === today ? "today" : "",
              c.date === selectedDate ? "sel" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <button
                key={c.date}
                type="button"
                className={cls}
                data-ui="cal-cell"
                data-date={c.date}
                onClick={() => onSelectDate(c.date)}
              >
                <span className="cal-daynum">{Number(c.date.slice(8))}</span>
                {status && <span className={`cal-dot dot-${status}`} />}
              </button>
            );
          })}
        </div>
      </section>

      <section className="rail-follow">
        <h3 className="rail-title">需要今天跟进</h3>
        {follow.length === 0 ? (
          <div className="follow-empty" data-ui="follow-empty">
            今天没有到期事项,喝口茶吧。
          </div>
        ) : (
          <ol className="follow-list">
            {follow.map((it) => {
              const label =
                dueStatus(it.due, today) === "today"
                  ? "今天到期"
                  : `超期 ${daysBetween(it.due as string, today)} 天`;
              return (
                <li className="follow-card" data-ui="follow-card" key={`${it.project}:${it.line}`}>
                  <span className="cnum">{it.cnum !== null ? `C${it.cnum}` : "—"}</span>
                  <span className="txt">{it.text}</span>
                  <span className="meta">
                    {it.project}
                    {it.space ? ` · ${it.space}` : ""} · {label}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </aside>
  );
}
