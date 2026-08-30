/**
 * 启动上报 —— 让外壳知道「网页这一层到底走到哪一步了」。
 *
 * 为什么有这个文件(2026-08-30,track opendesign-startup-observability):
 * 08-25 业主装 0.98.0 后「打开全是白的」,而外壳那边**完全不知道网页发生了什么** ——
 * 窗口开了、后端通了,日志里一片正常。白屏和"正在加载"在事后长得一模一样。
 *
 * 🔴 注入时机:`window.pywebview.api` 到位得**比首帧晚**(0.89/0.90 两版的窗口栏
 *    就是栽在这上面)。所以这里先把事件**缓存在内存里**,等 `pywebviewready` 再补发。
 *    形状抄 WindowChrome.tsx 里已经验证过的那段,不另发明。
 *
 * 🔴 `frame_submitted` 只说明**浏览器提交了一帧**,不等于业主眼睛看见了。
 *    真实像素只有 Windows 那边的截图作得了准。别把这个信号当"一切正常"用。
 */

type ReportApi = { report_startup(event: string, detail?: string): Promise<unknown> };

// 外壳那边也有一份同名白名单(bin/ds_diag.py UI_EVENTS)。两边都收窄,
// 网页这边写错名字会被外壳直接丢掉 —— 这里列出来只是为了让打字错误在本地就现形。
const EVENTS = [
  "frontend.bundle_started",
  "frontend.react_committed",
  "frontend.frame_submitted",
  "frontend.error",
  "frontend.resource_failed",
] as const;
export type StartupEvent = (typeof EVENTS)[number];

const MAX_BUFFER = 20;          // 没有外壳时(普通浏览器)不许无限攒
const DETAIL_CAP = 200;         // 和外壳侧一致,截断在源头

let buffered: Array<[string, string]> = [];
let flushed = false;

function api(): ReportApi | null {
  const w = window as unknown as { pywebview?: { api?: Partial<ReportApi> } };
  const a = w.pywebview?.api;
  return a && typeof a.report_startup === "function" ? (a as ReportApi) : null;
}

function flush(): void {
  const a = api();
  if (!a) return;
  flushed = true;
  const pending = buffered;
  buffered = [];
  for (const [event, detail] of pending) {
    // 失败就算了 —— 观测层绝不能成为新的故障源。
    try { void a.report_startup(event, detail)?.catch?.(() => {}); } catch { /* 忽略 */ }
  }
}

export function report(event: StartupEvent, detail = ""): void {
  const d = String(detail).slice(0, DETAIL_CAP);
  if (flushed && api()) {
    try { void api()!.report_startup(event, d)?.catch?.(() => {}); } catch { /* 忽略 */ }
    return;
  }
  if (buffered.length < MAX_BUFFER) buffered.push([event, d]);
  flush();
}

/** 尽可能早地装上 —— 越早装,越多的失败能被抓到。 */
export function installStartupReporting(): void {
  window.addEventListener("pywebviewready", flush, { once: true });

  window.addEventListener("error", (e) => {
    // 资源加载失败(<script>/<link> 挂了)不带 message,但 target 是那个元素 ——
    // 这正是"JS 没下下来 ⇒ 整页全白"那条路,必须和普通异常分开报。
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === "SCRIPT" || t.tagName === "LINK" || t.tagName === "IMG")) {
      const url = (t as HTMLScriptElement).src || (t as HTMLLinkElement).href || "";
      report("frontend.resource_failed", `${t.tagName} ${url}`);
      return;
    }
    report("frontend.error", e.message || String(e.error ?? ""));
  }, true);   // 捕获阶段:资源加载失败不冒泡

  window.addEventListener("unhandledrejection", (e) => {
    report("frontend.error", String((e as PromiseRejectionEvent).reason ?? ""));
  });

  report("frontend.bundle_started");
}

/** 等根节点真的有内容的帧预算。约 4 秒(60fps),之后才算"真的没画出来"。 */
const FRAME_BUDGET = 240;

export function reportFirstFrame(): void {
  report("frontend.react_committed");
  // 🔴 **不许只等固定两帧就下结论**(第一版就是那么写的,自审时抓到):
  //    `createRoot().render()` 在 React 18 里是**异步**的 —— 提交可能发生在
  //    两帧之后。那样健康启动会被报成"根节点尺寸异常"、而且永远不报成功
  //    ⇒ 外壳那边的首帧看门**每次开机都误报**。
  //    误报比没有报警器更坏,这个项目实证过很多次 ⇒ 改成在预算内轮询等它出现。
  let left = FRAME_BUDGET;
  const tick = () => {
    const r = document.getElementById("root")?.getBoundingClientRect();
    if (r && r.width >= 1 && r.height >= 1) {
      report("frontend.frame_submitted", `${Math.round(r.width)}x${Math.round(r.height)}`);
      return;
    }
    if (--left <= 0) {
      // 预算烧完还是 0 尺寸/不存在 —— 这才是真的"业主眼里一片白"。
      report("frontend.error", `根节点等了 ${FRAME_BUDGET} 帧仍没有尺寸`);
      return;
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
