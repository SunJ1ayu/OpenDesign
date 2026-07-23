import type { ReactNode } from "react";

// 共享折叠控件(track opendesign-todo-layout T2):待办页「按时间」日期批次头与
// 「按项目」项目卡头共用同一个组件 + 一套 class(.grp-toggle),不留两份折叠样式。
// 可见性修复(反馈 #1):.rule(细横线)长在按钮内部且 flex:1,于是可点区域横跨整行,
// 而不是只有 chev 那 9px——"整行 hover 背景"与"hover 到的就是能点的"是同一件事。
// 默认态由调用方给(展开/收起策略不在这里):日期批次维持"最新一批默认展开",
// 项目卡"默认全部展开",本组件只管渲染 + 派发 onToggle,不持有状态。
// 「全选本组」/「去项目 →」必须留在本组件外部渲染(兄弟节点):嵌套 <button> 非法 HTML,
// 且语义上它们不是折叠动作。

type Props = {
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export default function GroupToggle({ open, onToggle, children }: Props) {
  return (
    <button
      type="button"
      className="grp-toggle"
      data-ui="group-toggle"
      aria-expanded={open}
      onClick={onToggle}
    >
      <span className="chev">{open ? "▾" : "▸"}</span>
      {children}
      <span className="rule" />
    </button>
  );
}
