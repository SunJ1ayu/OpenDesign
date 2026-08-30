import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./app.css";
import { installStartupReporting, reportFirstFrame } from "./startupReport";

// 尽可能早 —— 装在 render 之前,连"App 自己炸了"也能被报出去。
installStartupReporting();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// render() 是异步提交的,所以不能在这儿直接说"画好了";交给 rAF 等真的过了两帧。
reportFirstFrame();
