// 项目页右侧面板(照 ZCode Side Pane:可收起、可拖宽、顶上自己一排标签)的纯逻辑。
// 零 React 依赖:判据 tests/test_side_pane.mjs 用 Node 直接跑。
//
// 业主原话:"待办事项的图墙和项目助手也可以参考一下 zcode 的向右侧展开的设计"。
// 以前项目页是固定三栏(变更 | 图片·文件 400px | 项目助手 300px),中间那栏挤;现在:
// 变更记录占主位,「图片 · 文件」和「项目助手」收进右侧一块面板,标签切换,可收起、可拖宽。

export type SidePaneTab = "files" | "assistant";
export type SidePaneState = { open: boolean; tab: SidePaneTab; ratio: number };

export const SIDE_PANE_KEY = "od-side-pane";
/** 照 ZCode sidePaneLayout:默认占 45%,最宽 65%;最窄按像素(聊天输入框再窄就放不下)。 */
export const SIDE_PANE_DEFAULT: SidePaneState = { open: true, tab: "files", ratio: 0.45 };
export const SIDE_PANE_MAX_RATIO = 0.65;
export const SIDE_PANE_MIN_PX = 280;

/** 把宽度比例夹到 [最窄像素, 65%] 之间;宿主宽度未知(0)时只夹上限。 */
export function clampRatio(r: number, hostPx: number): number {
  if (!Number.isFinite(r)) return SIDE_PANE_DEFAULT.ratio;
  const min = hostPx > 0 ? Math.min(SIDE_PANE_MAX_RATIO, SIDE_PANE_MIN_PX / hostPx) : 0.2;
  return Math.min(SIDE_PANE_MAX_RATIO, Math.max(min, r));
}

export function parseSidePane(raw: unknown): SidePaneState {
  let v: Partial<SidePaneState> = {};
  try { v = typeof raw === "string" ? JSON.parse(raw) : {}; } catch { v = {}; }
  if (!v || typeof v !== "object") v = {};
  return {
    open: typeof v.open === "boolean" ? v.open : SIDE_PANE_DEFAULT.open,
    tab: v.tab === "assistant" || v.tab === "files" ? v.tab : SIDE_PANE_DEFAULT.tab,
    ratio: typeof v.ratio === "number" ? clampRatio(v.ratio, 0) : SIDE_PANE_DEFAULT.ratio,
  };
}

/** 有事要业主看项目助手时(往那条对话里发了话 / 冒出同意卡 / 从历史打开那段对话):
 *  面板打开并切到「项目助手」。卡片在收着的面板里 = 助手在等、业主看不见 —— 这条不许丢。 */
export function revealAssistant(s: SidePaneState): SidePaneState {
  return s.open && s.tab === "assistant" ? s : { ...s, open: true, tab: "assistant" };
}
