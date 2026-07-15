import { useState } from "react";
import { isTerminalStatus, STATUS_HINT, STATUSES } from "./todo";

// 可点状态 pill + 快捷菜单(todo-ux2):待办页与项目工作区变更列共用。
// pill 是按钮,点开菜单选一个状态 → onPick(next)。当前态项 disabled;
// 终态(已完成/已关闭).term 次级显眼度(降手滑)。菜单开合 + 点外收起自管(fixed backdrop)。
// 无写副作用:纯 UI,写口径(editChange)由调用方持有——待办页走撤销 toast,
// 变更列直接改(全部筛选下不消失,可随时再点回滚)。

type Props = {
  status: string;
  onPick: (next: string) => void;
};

export default function StatusPicker({ status, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const hint = STATUS_HINT[status as keyof typeof STATUS_HINT] ?? "";
  return (
    <span className="st-cell">
      <button
        className={`st-pill st-btn st-${status}${open ? " open" : ""}`}
        title={`${hint} · 点击改状态`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="d" />
        {status}
        <span className="caret">⌄</span>
      </button>
      {open && (
        <>
          <div className="st-menu-backdrop" onClick={() => setOpen(false)} />
          <div className="st-menu" role="menu">
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
