import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { monthGrid } from "./schedule";
import { popoverPosition } from "./duePicker";
import { dueStatus } from "./todo";

// 截止日「就地弹出日历」(track opendesign-due-picker)。用户 2026-07-28 拍板:
// 「截止日还是出现一个日历比较好,这样可以随便点就行了」。
//
// 三个刻意的决定,都来自用户或来自踩过的坑:
//  ① **挂到 body 上**(createPortal)。待办行/变更行都在 overflow:auto 的滚动容器里,
//    浮层留在原地会被祖先裁掉 —— 这跟"设了 padding 却被别的规则盖掉"是同一类病:
//    你以为它在,它其实被切了一半。
//  ② **位置算在 duePicker.ts 的纯函数里**,本组件只负责量尺寸、贴样式。
//    边界情形(贴底边、贴右缘、窄视口)在 tests/test_due_picker.mjs 一次列全。
//  ③ **点一下日期就存、就关**,不设"确定"按钮 —— 用户原话"随便点就行了"。
//    反悔靠 Esc / 点外面(都不写入)与「清除」。
//
// 与右栏那个月历的关系:那个是**筛选**(点日期 = 只看那天到期的),这个是**修改**。
// 同一个东西两个意思是乱的开始,所以两者视觉上不同款(那边 .cal-*,这边 .due-*)。

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

/** "YYYY-MM-DD" → 年月;缺省用 today。日历初次打开落在**已有截止日那个月**,
 *  没设过才落在本月 —— 改期的人多半是在原日期附近挪。 */
function initialMonth(value: string | null, today: string): { year: number; month: number } {
  const src = value || today;
  return { year: Number(src.slice(0, 4)), month: Number(src.slice(5, 7)) };
}

type Props = {
  /** 触发按钮:浮层贴着它弹,关闭时焦点还给它。 */
  anchor: HTMLElement | null;
  /** 当前截止日(没有 = null)。 */
  value: string | null;
  /** 今天(后端口径,DS_TODAY 可冻结)—— 不自己 new Date(),免得跟别处两套"今天"。 */
  today: string;
  /** 同一项目**其它**条目的截止日:在格子上打点,免得把三件活约到同一天(用户要的)。 */
  otherDues?: string[];
  busy?: boolean;
  error?: string | null;
  /** 选中某天 → due;点「清除」→ null。调用方负责写后端并关闭。 */
  onPick: (due: string | null) => void;
  onClose: () => void;
};

export default function DuePicker({
  anchor, value, today, otherDues = [], busy = false, error = null, onPick, onClose,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [{ year, month }, setYm] = useState(() => initialMonth(value, today));
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  // 位置:量到自己的真实尺寸之后再算(高度随月份行数固定 6 行,但字号/缩放会变),
  // useLayoutEffect = 在浏览器绘制前落位,不会先闪一下再跳过去。
  useLayoutEffect(() => {
    if (!anchor || !ref.current) return;
    const a = anchor.getBoundingClientRect();
    const b = ref.current.getBoundingClientRect();
    const p = popoverPosition(
      { left: a.left, right: a.right, top: a.top, bottom: a.bottom },
      { width: b.width, height: b.height },
      { width: window.innerWidth, height: window.innerHeight },
    );
    setPos({ left: p.left, top: p.top });
  }, [anchor, year, month]);

  // Esc 关 + 点浮层外面关(都**不写入** —— 半路反悔不该留痕迹)。
  // 滚动/改窗口大小时直接关掉:锚点跑了还硬跟着算位置,不如干脆利落。
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t)) return;
      if (anchor?.contains(t)) return; // 再点一次触发键 = 由触发方自己切换,别在这抢
      onClose();
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("mousedown", onDown, true);
    window.addEventListener("resize", onClose);
    window.addEventListener("scroll", onClose, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("mousedown", onDown, true);
      window.removeEventListener("resize", onClose);
      window.removeEventListener("scroll", onClose, true);
    };
  }, [anchor, onClose]);

  const shift = (d: number) => {
    const m = month + d;
    if (m < 1) setYm({ year: year - 1, month: 12 });
    else if (m > 12) setYm({ year: year + 1, month: 1 });
    else setYm({ year, month: m });
  };

  const others = new Set(otherDues.filter((d) => d !== value));

  return createPortal(
    <div
      className="due-pop"
      data-ui="due-pop"
      ref={ref}
      role="dialog"
      aria-label="选择截止日"
      // pos 还没算出来时先藏着:否则第一帧会在 (0,0) 闪一下
      style={pos ? { left: pos.left, top: pos.top } : { left: -9999, top: -9999 }}
    >
      <header className="due-pop-head">
        <button type="button" className="due-nav" data-ui="due-prev"
                aria-label="上个月" onClick={() => shift(-1)}>‹</button>
        <span className="due-month" data-ui="due-month">{year} 年 {month} 月</span>
        <button type="button" className="due-nav" data-ui="due-next"
                aria-label="下个月" onClick={() => shift(1)}>›</button>
      </header>
      <div className="due-weekdays">
        {WEEKDAYS.map((w) => <span key={w}>{w}</span>)}
      </div>
      <div className="due-grid">
        {monthGrid(year, month).map((c) => {
          const cls = [
            "due-cell",
            c.inMonth ? "in-month" : "",
            c.date === today ? "today" : "",
            c.date === value ? "sel" : "",
          ].filter(Boolean).join(" ");
          const other = others.has(c.date);
          return (
            <button
              key={c.date}
              type="button"
              className={cls}
              data-ui="due-cell"
              data-date={c.date}
              disabled={busy}
              // 别人那天已经有事 —— 用户要的"免得把三件活约到同一天"
              title={other ? `${c.date} · 这天已经有别的事项到期` : c.date}
              onClick={() => onPick(c.date)}
            >
              <span className="due-daynum">{Number(c.date.slice(8))}</span>
              {other && <span className={`due-dot dot-${dueStatus(c.date, today) ?? "upcoming"}`} />}
            </button>
          );
        })}
      </div>
      <footer className="due-pop-foot">
        {value ? (
          <button type="button" className="due-clear" data-ui="due-clear"
                  disabled={busy} onClick={() => onPick(null)}>清除</button>
        ) : <span className="due-foot-hint">点一天就设上</span>}
      </footer>
      {error && <div className="error-note sm" data-ui="due-err">{error}</div>}
    </div>,
    document.body,
  );
}
