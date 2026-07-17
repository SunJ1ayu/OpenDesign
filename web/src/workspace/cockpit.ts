// 驾驶舱纯逻辑(track opendesign-cockpit):零 DOM,tests/test_cockpit.mjs 直测。
// 铁律:这里没有任何模板类目名(照用户现状认);时间显示统一走 relTime/relTimeFromEpoch,
// 组件别再手拼 new Date(mtime*1000)。
import type { FilesImages, FilesOverview } from "../api.ts";
import { relTime } from "../api.ts";

export type CockpitImage = { rel: string; category: string; mtime: number };

/** 项目图:全部工作区图片 mtime 降序;同刻按 rel 名序(与 gallery 排序口径一致)。
    降级态(未接入/未映射/加载中)恒空数组。纯函数,不改入参。 */
export function projectImages(images: FilesImages | null): CockpitImage[] {
  if (!images || !images.configured || !images.mapped) return [];
  return [...images.images].sort(
    (a, b) => b.mtime - a.mtime || a.rel.localeCompare(b.rel),
  );
}

/** epoch 秒 → 今天/昨天/M-DD;0/null/undefined → ""。
    与 relTime(ISO 入参)同一套显示语义,输入类型在此收拢,防两处漂移。 */
export function relTimeFromEpoch(sec: number | null | undefined): string {
  if (!sec) return "";
  return relTime(new Date(sec * 1000).toISOString());
}

/** 类目行显示模型。名序由服务端给定(用户自己的 01-/02- 前缀天然有序),
    这里零重排、零模板名匹配;capped 计数显示 N+、活跃度留空(截断后 max 不可信)。 */
export type CategoryRow = {
  name: string;       // open-folder 用的原始类目名("" = 顶层散文件)
  label: string;      // 显示名("" → 未分类)
  countLabel: string;
  activity: string;   // 相对时间;空串 = 不显示
};

export function categoryRows(overview: FilesOverview | null): CategoryRow[] {
  if (!overview || !overview.configured || !overview.mapped) return [];
  return overview.categories.map((c) => ({
    name: c.name,
    label: c.name || "未分类",
    countLabel: c.capped ? `${c.count}+` : String(c.count),
    activity: c.capped ? "" : relTimeFromEpoch(c.latest_mtime),
  }));
}

/** 文件区四态状态机:组件只 switch,不再散落三元表达式。 */
export type FilesState = "loading" | "unconfigured" | "unmapped" | "ok";

export function filesState(overview: FilesOverview | null): FilesState {
  if (overview === null) return "loading";
  if (!overview.configured) return "unconfigured";
  if (!overview.mapped) return "unmapped";
  return "ok";
}
