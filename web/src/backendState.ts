// 外壳里后台(管家 → 网关 + ds-web)起没起好(track opendesign-instant-ui)。
// 窗口现在一打开就是工作台,后台在旁边起;这几秒里页面的数据请求被外壳挂着、就绪后自动补上。
// 这条横幅只负责告诉业主「不是卡了,是在等后台」。浏览器里(没有外壳)永远不显示。

export type BackendState = { phase: "starting" | "ready" };

export function backendBanner(state: BackendState | null | undefined): string | null {
  if (!state || state.phase !== "starting") return null;
  return "正在启动后台,项目和助手马上就好…";
}
