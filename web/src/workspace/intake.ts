// 收件箱卡片纯逻辑(track opendesign-intake):零 DOM,tests/test_intake_ui.mjs 直测。
// 卡片只展示+确认(design D2:改派走聊天);plan 预览行 = src 文件名 → dst 目录。
import type { IntakeData, IntakeEntry, IntakePlan } from "../api.ts";

/** 卡片五态:loading(拉取中)/ unconfigured(工作区或收件箱没就绪)/
    empty(箱空且无待确认)/ ok(有文件待认领)/ pending(有待确认 plan,优先亮)。 */
export type IntakeState = "loading" | "unconfigured" | "empty" | "ok" | "pending";

export function intakeState(data: IntakeData | null): IntakeState {
  if (data === null) return "loading";
  if (!data.configured) return "unconfigured";
  if (data.pending.length > 0) return "pending";
  if (data.entries.length > 0) return "ok";
  return "empty";
}

/** 项目 key 的短显示:`日期 地点 楼盘 楼栋#户号` 四段起 → 剥前两段(日期/地点);
    不足四段的名字原样显示,不硬剥。depth2 的 `分组:项目` 先取项目段。 */
function shortProject(key: string): string {
  const name = key.includes(":") ? key.slice(key.indexOf(":") + 1) : key;
  const parts = name.split(" ").filter(Boolean);
  return parts.length >= 4 ? parts.slice(2).join(" ") : name;
}

/** 收件箱条目的建议标签:
    类目+项目 → "→ 项目短名 · 类目";仅类目 → "→ 类目";没建议 → "待认领";
    文件夹 → 前缀 "文件夹 · "(整夹认领,不给扩展名建议)。 */
export function entrySuggestion(e: IntakeEntry): string {
  const prefix = e.type === "dir" ? "文件夹 · " : "";
  if (!e.category) return `${prefix}待认领`;
  if (e.category.scope === "project" && e.project) {
    return `${prefix}→ ${shortProject(e.project)} · ${e.category.id}`;
  }
  if (e.category.scope === "project") {
    return `${prefix}→ ${e.category.id}(项目待定)`;
  }
  return `${prefix}→ ${e.category.id}`;
}

export type PlanRow = { src: string; dstDir: string };
export type PlanPreview = {
  planId: string;
  created: string;
  count: number;
  rows: PlanRow[];
};

/** plan 预览:src 取文件名、dst 取目录,反斜杠归一成 /(后端在 Windows 上
    relpath 会给 \\);多 plan 保服务端顺序(created 序)。纯函数,不改入参。 */
export function planPreview(pending: IntakePlan[]): PlanPreview[] {
  return pending.map((p) => ({
    planId: p.plan_id,
    created: p.created ?? "",
    count: p.ops.length,
    rows: p.ops.map((op) => {
      const src = op.src_rel.replace(/\\/g, "/");
      const dst = op.dst_rel.replace(/\\/g, "/");
      return {
        src: src.slice(src.lastIndexOf("/") + 1),
        // 工作区根直落(无目录段,organize 泛化 plan 可能出现)显示占位而非空串
        dstDir: dst.includes("/")
          ? dst.slice(0, dst.lastIndexOf("/"))
          : "(工作区根)",
      };
    }),
  }));
}
