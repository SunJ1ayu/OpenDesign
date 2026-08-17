import { useEffect, useState } from "react";
import {
  RESIZE_EDGES,
  cursorFor,
  inDesktopShell,
  type ResizeEdge,
} from "../shellWindow";

// 我们自己的窗口栏(2026-08-16 业主:「为什么不能不要外面那个框,只留我们原来的
// 前端仅仅加上右上角的缩小放大和退出按钮」)。
//
// 🔴 只在桌面外壳里出现。用浏览器打开 127.0.0.1:8766 的时候没有窗口可以关,
//    画出来就是三个按下去没反应的按钮。分界见 shellWindow.ts 的 inDesktopShell。
//
// 🔴 无边框 = Windows 把"拖边缘改大小"也一起收走了。所以除了三个按钮,这里还铺了
//    八个透明的边角把手,按下去交给 Python 那边发一条原生的窗口消息 —— 拖动和
//    改大小都由 Windows 自己接管(手感和系统边框一样,也带吸附)。

type ShellApi = {
  minimize(): Promise<unknown>;
  toggle_maximize(): Promise<{ maximized: boolean } | null>;
  close_window(): Promise<unknown>;
  begin_drag(): Promise<unknown>;
  begin_resize(edge: string): Promise<unknown>;
  window_state(): Promise<{ maximized: boolean } | null>;
};

function api(): ShellApi | null {
  const w = window as unknown as { pywebview?: { api?: ShellApi } };
  return w.pywebview?.api ?? null;
}

export default function WindowChrome() {
  // 一次定死:pywebview 的注入发生在页面加载那一刻,之后不会变。
  const [shell] = useState(inDesktopShell);
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    if (!shell) return;
    // 加一条 body class,让整个界面往下让出这条栏的高度 —— 用绝对定位盖上去的话,
    // 顶部那一条里的东西(侧栏标题、各列顶端)会被一条看不见的带子挡住点不着。
    document.body.classList.add("has-window-chrome");
    api()?.window_state().then((st) => st && setMaximized(!!st.maximized)).catch(() => {});
    return () => document.body.classList.remove("has-window-chrome");
  }, [shell]);

  if (!shell) return null;

  const toggle = () => {
    api()?.toggle_maximize()
      .then((st) => st && setMaximized(!!st.maximized))
      .catch(() => {});
  };

  const grip = (edge: ResizeEdge) => (
    <div
      key={edge}
      className={`win-grip win-grip-${edge}`}
      style={{ cursor: cursorFor(edge) }}
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        api()?.begin_resize(edge).catch(() => {});
      }}
    />
  );

  return (
    <>
      <div
        className="win-bar"
        data-ui="window-bar"
        onMouseDown={(e) => {
          // 只有在栏本身的空白处按下才算拖窗口;按在按钮上不算(按钮自己 stopPropagation)。
          if (e.button !== 0) return;
          api()?.begin_drag().catch(() => {});
        }}
        onDoubleClick={toggle}
      >
        {/* 两个都要挡:mousedown 挡的是"按按钮顺带拖窗口",dblclick 挡的是
            "双击按钮顺带最大化" —— 后者漏了一版(08-17 四审 F1,判据 x6)。 */}
        <div className="win-btns"
             onMouseDown={(e) => e.stopPropagation()}
             onDoubleClick={(e) => e.stopPropagation()}>
          <button className="win-btn" data-ui="window-min" title="最小化"
                  onClick={() => api()?.minimize().catch(() => {})}>
            <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M0 5h10" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
          <button className="win-btn" data-ui="window-max"
                  title={maximized ? "还原" : "最大化"} onClick={toggle}>
            {maximized ? (
              <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                <path d="M2.5 0.5h7v7h-2M0.5 2.5h7v7h-7z" fill="none"
                      stroke="currentColor" strokeWidth="1.1" />
              </svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                <rect x="0.5" y="0.5" width="9" height="9" fill="none"
                      stroke="currentColor" strokeWidth="1.1" />
              </svg>
            )}
          </button>
          <button className="win-btn win-btn-close" data-ui="window-close" title="关闭"
                  onClick={() => api()?.close_window().catch(() => {})}>
            <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M0.7 0.7l8.6 8.6M9.3 0.7l-8.6 8.6" stroke="currentColor"
                    strokeWidth="1.2" />
            </svg>
          </button>
        </div>
      </div>
      {RESIZE_EDGES.map(grip)}
    </>
  );
}
