import { useState } from "react";
import { dueStatus, type OpenItem } from "./todo";
import { dueDates, followUpItems, monthGrid } from "./schedule";
import ChatPage from "./chat/ChatPage";
import type { ChatSession } from "./chat/connection";
import { inputPlaceholder } from "./chat/inputHint";

// 待办页右栏(track opendesign-todo-rail T2 + opendesign-todo-assistant T3/T4/T5):
// 320px,三段——① 日程月历 ② 需要今天跟进 ③ 项目助手(跨项目入口)。
// 状态边界:当前显示月份自己持有(纯展示态);选中日期由 props 上提给 TodoPage
// (因为要过滤主列表——点日期是全局意图,不是这个组件局部的事)。
//
// ③ 项目助手两态(design.md):收起态=一句能力说明+单行输入+「发送」;展开态=
// ChatPage 真身占满右栏,①②让位(route-hidden,不卸载)。ChatPage 常驻挂载、
// 收起态也只是 CSS 隐藏——卸载就等于丢对话。variant="home":column 变体的登录
// 卡藏在 bannerOpen 内部 state 后面(ChatPage.tsx 私有,外部够不着),home 变体
// 登录态直接渲染 connect-card,才能满足「未连接提交 → 立即展开露出连接卡」。
// 不吞字(design.md 补的约束,设计稿没写):已连接 → dispatch 程序化发送 + 清空
// 右栏输入框;未连接 → 只展开,右栏输入框里的字原样留着(ChatPage login 态没有
// 输入框,prefill 会把字落进看不见的地方,读源码后否掉,理由见 design.md)。
// 连接态由 ChatPage 既有的 onConnected 回调在本组件内记一个本地 flag。

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

type Props = {
  items: OpenItem[]; // 全量未办结(不随主列表的 dateFilter 收窄——日历/跟进区是跨项目总览)
  today: string;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
  // 项目助手(T4):与 home/工作区共享同一 ChatSession——第三个 ChatPage 实例,
  // 结构上同构,不是新架构(design.md)。
  session: ChatSession;
  // 主 agent 收货补线:一轮对话结束后要能刷新待办数据。少了它,用户在右栏说
  // 「记一下 XX」,变更已写进档案,而**同一屏**的待办列表纹丝不动,要切走再切回才更新
  // ——正是 track hardening M5「聊完免 F5」治过的毛病。另两个 ChatPage 实例都接了这条线,
  // 右栏不接就是半成品。接到 TodoPage 既有的 onEdited(→ App bump dataEpoch → 本页重拉)。
  onTurnEnd?: () => void;
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

export default function TodoRail({
  items, today, selectedDate, onSelectDate, session, onTurnEnd,
}: Props) {
  const [[year, month], setYm] = useState<[number, number]>(() => ymFromIso(today));
  // 项目助手(T3/T4/T5):expanded=两态切换;connected=ChatPage onConnected 记的
  // 本地 flag;askText=右栏自己的输入(不吞字用);dispatch=程序化发送(nonce 去重,
  // 复用 CompanionColumn「接入工作区」的既有通道)。
  const [expanded, setExpanded] = useState(false);
  const [connected, setConnected] = useState(false);
  const [askText, setAskText] = useState("");
  const [dispatch, setDispatch] = useState<{ text: string; nonce: number }>({
    text: "",
    nonce: 0,
  });

  // 提交(不吞字):已连接 → 程序化发送 + 清空;未连接 → 展开露出连接卡,
  // **且 ask 区继续可见、字留在框里**。
  //
  // 主 agent 收货修正:原实现让 ask 区在展开时一律 route-hidden,于是未连接提交后
  // 用户面对一张连接卡、自己刚打的字从画面上消失(实测截图),这正是"不吞字"这条
  // 要求本来要防的体验;而"字还在 DOM 里、收起一次能看到"不算数——用户不知道要收起。
  // 判据同样虚(inputValue() 读隐藏元素照样绿),已一并收紧为必须 visible。
  // 现在的规则只有一条:**ask 区只在"聊天自己有输入框可用"(即已连接)时才让位**。
  function handleAsk() {
    const text = askText.trim();
    if (!text) return;
    setExpanded(true);
    if (connected) {
      setDispatch((p) => ({ text, nonce: p.nonce + 1 }));
      setAskText("");
    }
  }

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
      <section className={`rail-cal${expanded ? " route-hidden" : ""}`}>
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

      <section className={`rail-follow${expanded ? " route-hidden" : ""}`}>
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

      <section
        className={`rail-assistant${expanded ? " expanded" : ""}`}
        data-ui="rail-assistant"
      >
        <div className={`rail-ask-block${expanded && connected ? " route-hidden" : ""}`}>
          <p className="rail-ask-hint">
            问项目助手一句,记得带上项目名——比如「翡翠湾-1801,C7 业主上次怎么说的」,
            「记一下」也是靠项目名归档。
          </p>
          <div className="rail-ask-row">
            <input
              type="text"
              className="rail-ask-input"
              data-ui="rail-ask"
              placeholder={inputPlaceholder("问待办")}
              value={askText}
              onChange={(e) => setAskText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleAsk();
              }}
            />
            <button type="button" className="rail-send" data-ui="rail-send" onClick={handleAsk}>
              发送
            </button>
          </div>
          {/* 已展开时不再显示(panel subglm 提):那时点它是 no-op,而且和聊天头里的
              「收起」并排出现,语义打架。 */}
          {!expanded && (
            <button
              type="button"
              className="rail-expand-link"
              data-ui="rail-expand"
              onClick={() => setExpanded(true)}
            >
              展开对话 →
            </button>
          )}
        </div>

        {/* ChatPage 常驻挂载、收起态 CSS 隐藏(卸载=丢对话,与 p3 keep-mounted 同规矩)。
            跨项目入口,刻意不传 firstSendPrefix(那是工作区列传项目前缀用的,design.md)。 */}
        <div className={`rail-chat${expanded ? "" : " route-hidden"}`} data-ui="rail-chat">
          <div className="rail-chat-head">
            <span className="t">项目助手</span>
            <span className="grow" />
            <button
              type="button"
              className="icon-btn"
              data-ui="rail-collapse"
              title="收起"
              onClick={() => setExpanded(false)}
            >
              收起
            </button>
          </div>
          <div className="rail-chat-body">
            <ChatPage
              variant="home"
              session={session}
              dispatch={dispatch}
              onConnected={() => setConnected(true)}
              onTurnEnd={onTurnEnd}
            />
          </div>
        </div>
      </section>
    </aside>
  );
}
