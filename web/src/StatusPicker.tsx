import { useEffect, useState } from "react";
import { isTerminalStatus, STATUS_HINT, STATUSES } from "./todo";

// 可点状态 pill + 快捷菜单(todo-ux2):待办页与项目工作区变更列共用。
// pill 是按钮,点开菜单选一个状态 → onPick(next)。当前态项 disabled;
// 终态(已完成/已关闭).term 次级显眼度(降手滑)。菜单开合 + 点外收起自管(fixed backdrop)。
// 无写副作用:纯 UI,写口径(editChange)由调用方持有——待办页走撤销 toast,
// 变更列直接改(全部筛选下不消失,可随时再点回滚)。
//
// track opendesign-todo-batch-space T3:批量操作栏复用本组件,无"当前状态"概念
// (选中项状态各异)→ 传 label 覆盖按钮文案(如「改为…」);status 传空串时
// STATUSES 均不 disabled。menuUp 供菜单贴底容器(浮动操作栏)向上展开,避免出屏。

type Props = {
  status: string;
  onPick: (next: string) => void;
  label?: string;
  menuUp?: boolean;
};

export default function StatusPicker({ status, onPick, label, menuUp }: Props) {
  const [open, setOpen] = useState(false);
  const hint = STATUS_HINT[status as keyof typeof STATUS_HINT] ?? "";

  // 全局原则(修改单 A3):esc 关一切弹层——状态菜单也不例外。
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <span className="st-cell">
      <button
        className={`st-pill st-btn st-${status}${open ? " open" : ""}`}
        title={label ? label : `${hint} · 点击修改状态`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="d" />
        {label ?? status}
        <span className="caret">⌄</span>
      </button>
      {open && (
        <>
          <div className="st-menu-backdrop" onClick={() => setOpen(false)} />
          <div className={`st-menu${menuUp ? " up" : ""}`} role="menu">
            {STATUSES.map((s) => (
              <button
                key={s}
                className={
                  `st-menu-item${s === status ? " current" : ""}` +
                  (isTerminalStatus(s) ? " term" : "")
                }
                disabled={s === status}
                onClick={() => {
                  setOpen(false);
                  onPick(s);
                }}
              >
                <span className={`chip st-${s}`}><span className="d" />{s}</span>
                <span className="hint">{STATUS_HINT[s]}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </span>
  );
}
