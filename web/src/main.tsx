import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./app.css";
import { installStartupReporting, reportFirstFrame } from "./startupReport";
import { applyTheme, loadThemePref, watchSystemTheme } from "./theme";

// 尽可能早 —— 装在 render 之前,连"App 自己炸了"也能被报出去。
installStartupReporting();

// 外观(index.html 已在第一帧前设过;这里再按同一份偏好设一次,并在「跟随系统」时跟着系统变)
applyTheme(loadThemePref());
watchSystemTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// render() 是异步提交的,所以不能在这儿直接说"画好了";交给 rAF 等真的过了两帧。
reportFirstFrame();
