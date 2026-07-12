// 待办页纯逻辑层(track p4 T3)—— 分组/排序不掺 DOM,oracle 直测
// (tests/test_workbench_p4.mjs)。数据形状 = /api/todos(ds_todo.collect 单一真相源)。

export type OpenItem = {
  project: string;
  line: number;
  raw: string;
  status: string; // 待确认 | 进行中
  cnum: number | null;
  date: string | null; // YYYY-MM-DD
  space: string | null; // 【空间】前缀(T1);旧行 null
  text: string;
};

export type StaleItem = { project: string; days: number; last: string };

export type ProjectGroup = { project: string; items: OpenItem[] };
export type SpaceGroup = { space: string | null; items: OpenItem[] };

/** 按项目分组,保持 collect 的遇见序(= projects/ 文件名序,稳定)。 */
export function groupByProject(open: OpenItem[]): ProjectGroup[] {
  const order: string[] = [];
  const map = new Map<string, OpenItem[]>();
  for (const it of open) {
    if (!map.has(it.project)) {
      map.set(it.project, []);
      order.push(it.project);
    }
    map.get(it.project)!.push(it);
  }
  return order.map((project) => ({ project, items: map.get(project)! }));
}

/** 卡内按空间分小节:遇见序;未标注(null)恒排最后(handoff §6 + design D4)。 */
export function groupBySpace(items: OpenItem[]): SpaceGroup[] {
  const order: (string | null)[] = [];
  const map = new Map<string | null, OpenItem[]>();
  for (const it of items) {
    const key = it.space;
    if (!map.has(key)) {
      map.set(key, []);
      order.push(key);
    }
    map.get(key)!.push(it);
  }
  const named = order.filter((s) => s !== null);
  const tail: (string | null)[] = map.has(null) ? [null] : [];
  return [...named, ...tail].map((space) => ({ space, items: map.get(space)! }));
}

/** 按时间视图:日期倒序平铺;无日期沉底;同日期保持原相对序(稳定排序)。 */
export function sortByDateDesc(open: OpenItem[]): OpenItem[] {
  return open
    .map((it, i) => ({ it, i }))
    .sort((a, b) => {
      const da = a.it.date ?? "";
      const db = b.it.date ?? "";
      if (da !== db) {
        if (da === "") return 1; // 无日期沉底
        if (db === "") return -1;
        return db.localeCompare(da);
      }
      return a.i - b.i;
    })
    .map((x) => x.it);
}

/** 项目名 → 超期天数(仅当超期);待办卡头「⛑ N 天没动静」用。 */
export function staleDays(stale: StaleItem[], project: string): number | null {
  const hit = stale.find((s) => s.project === project);
  return hit ? hit.days : null;
}
