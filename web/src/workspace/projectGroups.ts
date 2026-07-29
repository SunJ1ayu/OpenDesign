// 左栏项目按**阶段**分堆的纯逻辑(track opendesign-due-picker T3)。
// 判据:tests/test_project_groups.mjs(纯函数,不碰 DOM/网络)+ tests/e2e/side_stage_groups.e2e.mjs。
//
// 阶段词表**不在这里硬编码**:单一真相源是后端 ds_tools.PROJECT_STAGES,经
// /api/projects 的 stages 下发,由调用方传进来(与 stage-chip 下拉同一份)。
// 「已交付」同理不复制 DELIVERED_STAGES —— 用后端算好的 project.delivered。

import type { Project } from "../api";
import { loadBoolPrefs, type BoolPrefs } from "../boolPrefs.ts";

/** 没有阶段的项目(未建档文件夹、或档案头缺「- 阶段:」行)归到这一堆,恒垫底。 */
export const UNSTAGED_LABEL = "未建档";

/** localStorage 键。改名 = 所有人的折叠状态丢一次,oracle 锁死。 */
export const SIDE_STAGE_STORAGE_KEY = "ds.side.stageOpen";

export type StageGroup = { stage: string; projects: Project[] };

/** 阶段 → 是否展开。只存**用户显式点过**的堆;没有的键走默认(见 isStageGroupOpen)。 */
export type StagePrefs = BoolPrefs;

/** 按阶段分堆:词表顺序在前,词表外的非空阶段(手改坏的档案头)按首次出现序跟在后面,
 * 未建档垫底。空堆不出现,堆内保持传入相对序,**一个项目都不丢**。 */
export function groupProjectsByStage(projects: Project[], stages: string[]): StageGroup[] {
  const byStage = new Map<string, Project[]>();
  const extra: string[] = []; // 词表外的阶段,按首次出现序
  for (const p of projects) {
    const stage = p.stage || UNSTAGED_LABEL;
    let bucket = byStage.get(stage);
    if (!bucket) {
      bucket = [];
      byStage.set(stage, bucket);
      if (stage !== UNSTAGED_LABEL && !stages.includes(stage)) extra.push(stage);
    }
    bucket.push(p);
  }
  const order = [...stages, ...extra, UNSTAGED_LABEL];
  const out: StageGroup[] = [];
  for (const stage of order) {
    const bucket = byStage.get(stage);
    if (bucket && bucket.length) out.push({ stage, projects: bucket });
  }
  return out;
}

/** 这堆现在开着吗:存过偏好就听用户的;没存过则"整堆都已交付 → 默认收起"
 * (分堆的由来就是已交付项目最占地方),其余默认展开。
 * 空堆按展开算 —— `every` 对空数组恒真,不挡一下会把空堆判成"都已交付"。 */
export function isStageGroupOpen(group: StageGroup, prefs: StagePrefs): boolean {
  const saved = prefs[group.stage];
  if (typeof saved === "boolean") return saved;
  return !(group.projects.length > 0 && group.projects.every((p) => p.delivered));
}

/** localStorage 原文 → 偏好表。实现搬去 boolPrefs.ts 与待办批次共用(T4a):
 * 同一个问题不留第二个答案。此处保留具名导出,调用方与判据不动。 */
export const loadStagePrefs = loadBoolPrefs;

/** 选中的项目落在收着的堆里 → 把那堆展开(待办页「去项目 →」/ 搜索直达 都会这样进来)。
 * 已经开着就**原样返回**同一个对象:调用方据此判断"要不要写盘",否则 effect 自唤自醒写不停。
 * 这是 effect 语义、不是渲染期覆盖 —— 渲染期强制展开会让那个堆的折叠键点了没反应。 */
export function revealStage(prefs: StagePrefs, group: StageGroup): StagePrefs {
  if (isStageGroupOpen(group, prefs)) return prefs;
  return { ...prefs, [group.stage]: true };
}
