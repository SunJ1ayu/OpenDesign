import { useRef, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { radioKeyTarget } from "../theme";
import { clampRatio, type SidePaneTab } from "./sidePane";

// 项目页右侧面板(照 ZCode Side Pane):顶上一排标签(图片 · 文件 / 项目助手),左边缘可拖宽,
// 由主区右上角的开关收起 / 展开(开关在 WsMain 里,照 ZCode 放在主区的头部)。
//
// 🔴 keep-mounted:两个标签页、以及整块面板收起时,都只走 CSS 隐藏(route-hidden),不卸载 ——
//    「项目助手」里是一条活的聊天连接,卸载 = 丢对话(P3 红线 3,同 home-pane / ws-pane)。

const TABS: { id: SidePaneTab; label: string }[] = [
  { id: "files", label: "图片 · 文件" },
  { id: "assistant", label: "项目助手" },
];

type Props = {
  open: boolean;
  tab: SidePaneTab;
  ratio: number;
  onTab: (t: SidePaneTab) => void;
  onRatio: (r: number) => void;
  files: ReactNode;
  assistant: ReactNode;
};

export default function SidePane({ open, tab, ratio, onTab, onRatio, files, assistant }: Props) {
  const ref = useRef<HTMLElement>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const cur = Math.max(0, TABS.findIndex((t) => t.id === tab));

  // 拖左边缘调宽:比例按整个 ws-pane 的宽度算(面板 + 主区),照 ZCode 的百分比宽度
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    const host = ref.current?.parentElement;
    if (!host) return;
    e.preventDefault();
    const rect = host.getBoundingClientRect();
    const move = (ev: globalThis.PointerEvent) => onRatio(clampRatio((rect.right - ev.clientX) / rect.width, rect.width));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.classList.remove("spane-resizing");
    };
    document.body.classList.add("spane-resizing");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  // 键盘也能调宽(分隔条可聚焦):←/→ 每次 2%
  const onResizeKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const d = e.key === "ArrowLeft" ? 0.02 : e.key === "ArrowRight" ? -0.02 : 0;
    if (!d) return;
    e.preventDefault();
    const w = ref.current?.parentElement?.getBoundingClientRect().width ?? 0;
    onRatio(clampRatio(ratio + d, w));
  };

  return (
    <aside
      ref={ref}
      id="ws-side-pane"
      className={`side-pane${open ? "" : " route-hidden"}`}
      data-ui="side-pane"
      style={{ flexBasis: `${(ratio * 100).toFixed(2)}%` }}
    >
      <div
        className="spane-resize"
        data-ui="side-pane-resize"
        role="separator"
        aria-orientation="vertical"
        aria-label="拖动调整右侧面板宽度"
        aria-valuenow={Math.round(ratio * 100)}
        aria-valuemin={0}
        aria-valuemax={65}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onKeyDown={onResizeKey}
      />
      <div
        className="spane-tabs"
        role="tablist"
        aria-label="右侧面板"
        onKeyDown={(e) => {
          const next = radioKeyTarget(e.key, cur, TABS.length);
          if (next === null) return;
          e.preventDefault();
          onTab(TABS[next].id);
          tabRefs.current[next]?.focus();
        }}
      >
        {TABS.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => { tabRefs.current[i] = el; }}
            type="button"
            role="tab"
            id={`spane-tab-${t.id}`}
            aria-controls={`spane-panel-${t.id}`}
            aria-selected={i === cur}
            tabIndex={i === cur ? 0 : -1}
            data-ui={`side-pane-tab-${t.id}`}
            className={`spane-tab${i === cur ? " on" : ""}`}
            onClick={() => onTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="spane-body">
        <div id="spane-panel-files" role="tabpanel" aria-labelledby="spane-tab-files"
          className={`spane-panel${tab === "files" ? "" : " route-hidden"}`}>
          {files}
        </div>
        <div id="spane-panel-assistant" role="tabpanel" aria-labelledby="spane-tab-assistant"
          className={`spane-panel${tab === "assistant" ? "" : " route-hidden"}`}>
          {assistant}
        </div>
      </div>
    </aside>
  );
}
