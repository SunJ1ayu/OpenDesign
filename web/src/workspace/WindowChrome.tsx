import { useEffect, useLayoutEffect, useState } from "react";
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
  // 一次定死:分界读的是**地址**,首帧就定了,之后也不会变 —— 前端没有任何
  // `history.pushState/replaceState`(路由走 hash),外壳也从不 `load_url`。
  // 🔴 这行原来的注释写着「pywebview 的注入发生在页面加载那一刻」,那是错的,
  //    而且 0.89/0.90 两版的窗口栏就是因此整块没画出来(见 shellWindow.ts)。
  const [shell] = useState(inDesktopShell);
  const [maximized, setMaximized] = useState(false);

  // 🔴 用 useLayoutEffect 而不是 useEffect:这条 class 决定整个界面往下让 30px,
  //    而窗口栏在**首帧**就画出来了。放在 useEffect 里等于"先画一帧压着内容的,
  //    再跳下去" —— 业主每次开窗口都会看见那一跳(08-17 四审 subdeepseek)。
  useLayoutEffect(() => {
    if (!shell) return;
    // 让整个界面往下让出这条栏的高度 —— 用绝对定位盖上去的话,顶部那一条里的东西
    // (侧栏标题、各列顶端)会被一条看不见的带子挡住点不着。
    document.body.classList.add("has-window-chrome");
    return () => document.body.classList.remove("has-window-chrome");
  }, [shell]);

  // 「我现在是不是最大化」只有 Python 那边知道,而 `pywebview.api` 到位得**比这一帧晚**
  // (注入发生在 on_navigation_completed 之后,见 shellWindow.ts)。
  // 🔴 窗口栏本身**不等它**(靠地址,首帧就画);但这一问必须等 —— 不等的话
  //    `api()` 是 null,这个 effect 就成了一句好看的空话(0.91.0 之前它正是如此:
  //    整个组件都没渲染过,所以没人发现)。
  //    pywebview 注完 finish.js 会派 `pywebviewready`;它可能在我们挂上监听**之前**
  //    就派过了(页面重挂、热更新),所以两条路都要走。
  useEffect(() => {
    if (!shell) return;
    const sync = () => {
      api()?.window_state().then((st) => st && setMaximized(!!st.maximized)).catch(() => {});
    };
    if (api()) { sync(); return; }
    window.addEventListener("pywebviewready", sync, { once: true });
    return () => window.removeEventListener("pywebviewready", sync);
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
          // 只有在栏本身的空白处按下才算拖窗口;按在按钮上不算 —— 按钮区是这条栏的
          // **兄弟节点**且压在它上面(见下),点击根本到不了这里。
          if (e.button !== 0) return;
          api()?.begin_drag().catch(() => {});
        }}
        onDoubleClick={toggle}
      />
      {/* 🔴 按钮区**不能放进窗口栏里**(08-17 四审 subkimi F-1)。
          栏是 `position:fixed` + `z-index`,它自己就是一个 stacking context ——
          按钮放在里面,层号再高也只在栏内部有效,根上下文里参与比较的是
          整个栏的层号。于是把手(层号比栏高)照样盖在按钮上沿。
          抬成栏的兄弟节点,200 < 210 < 220 才真的成立。判据 x8 现在先问结构。
          顺带:不再是父子 ⇒ 点/双击按钮本来就不会冒泡到栏,那两个
          stopPropagation 是白留的,一起去掉(x6 跟着改成问结构)。 */}
      <div className="win-btns">
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
      {RESIZE_EDGES.map(grip)}
    </>
  );
}
