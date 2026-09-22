import { useEffect, useLayoutEffect, useState } from "react";
import { inDesktopShell } from "../shellWindow";
import { shellApi } from "../desktopShell";

// 我们自己的窗口栏(2026-08-16 业主:「为什么不能不要外面那个框,只留我们原来的
// 前端仅仅加上右上角的缩小放大和退出按钮」)。
//
// 🔴 只在桌面外壳里出现。用浏览器打开 127.0.0.1:8766 的时候没有窗口可以关,
//    画出来就是三个按下去没反应的按钮。分界见 shellWindow.ts 的 inDesktopShell。
//
// Electron 保留原生 thickFrame，拖边缘缩放由系统处理；标题区只负责拖动与三按钮。

export default function WindowChrome() {
  // 一次定死:分界读的是**地址**,首帧就定了,之后也不会变 —— 前端没有任何
  // `history.pushState/replaceState`(路由走 hash),外壳也从不 `load_url`。
  // 地址标记在首帧就可用，不依赖 preload API 的调用结果。
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

  // preload 先取一次当前状态，再订阅之后的最大化/还原变化。
  useEffect(() => {
    if (!shell) return;
    const api = shellApi(window);
    if (!api) return;
    void api.windowState().then((st) => st && setMaximized(!!st.maximized)).catch(() => {});
    return api.onWindowState((st) => setMaximized(!!st.maximized));
  }, [shell]);

  if (!shell) return null;

  const toggle = () => {
    shellApi(window)?.toggleMaximize()
      .then((st) => st && setMaximized(!!st.maximized))
      .catch(() => {});
  };

  return (
    <>
      <div className="win-bar" data-ui="window-bar" />
      {/* 按钮区独立于可拖动标题区，避免按钮点击被 app-region:drag 吞掉。 */}
      <div className="win-btns">
          <button className="win-btn" data-ui="window-min" title="最小化"
                  onClick={() => shellApi(window)?.minimize().catch(() => {})}>
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
                  onClick={() => shellApi(window)?.close().catch(() => {})}>
            <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M0.7 0.7l8.6 8.6M9.3 0.7l-8.6 8.6" stroke="currentColor"
                    strokeWidth="1.2" />
            </svg>
          </button>
      </div>
    </>
  );
}
