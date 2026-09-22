import type { DesktopUpdateState } from "./desktopShell";

export const RESTART_HINT = "更新约需 2 分钟，期间请别关机";

export function desktopUpdateLabel(state: DesktopUpdateState, currentVersion: string): string {
  switch (state.phase) {
    case "checking": return "更新检查中…";
    case "latest": return `已是最新 v${currentVersion}`;
    case "downloading": {
      const progress = Number.isFinite(state.percent) ? `（${Math.round(state.percent!)}%）` : "";
      return `正在下载 ${state.version || "新版本"}${progress}`;
    }
    case "downloaded": return `${state.version || "新版本"} 已下载完成`;
    case "error": return state.version ? `${state.version} 下载失败` : "没查到更新，请稍后重试";
    case "idle":
    default: return `当前版本 v${currentVersion}`;
  }
}

export function showRestart(state: DesktopUpdateState): boolean {
  return state.phase === "downloaded";
}

export function showRetry(state: DesktopUpdateState): boolean {
  return state.phase === "error";
}

export function hasDesktopUpdateBadge(state: DesktopUpdateState | null | undefined): boolean {
  return !!state && (state.phase === "downloaded" || (state.phase === "error" && !!state.version));
}
