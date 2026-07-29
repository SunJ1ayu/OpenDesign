// localStorage 里"键 → 开/关"偏好表的容错解析。**同一个问题只留一个答案**:
// 左栏阶段堆(workspace/projectGroups.ts)与待办批次(todoBatches.ts)共用这一份。
// 判据:tests/test_todo_batches.mjs(并与 tests/test_project_groups.mjs 交叉断言同源)。

/** 键 → 是否展开。只记**用户显式点过**的键;没有的键由各自的默认规则决定。 */
export type BoolPrefs = Record<string, boolean>;

/** 原文 → 偏好表。坏 JSON / 非对象 / 数组 / null 一律退空表;非布尔值剔除。
 * 本机偏好丢了不该让页面白屏,所以只吞不抛。 */
export function loadBoolPrefs(raw: string | null): BoolPrefs {
  if (!raw) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {};
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
  const out: BoolPrefs = {};
  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    if (typeof v === "boolean") out[k] = v;
  }
  return out;
}
