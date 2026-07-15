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

// ── 行内编辑(track opendesign-todo-edit T6)──────────────────────────────────
// 纯逻辑层:编辑态草稿 → POST /api/changes/edit 的请求体装配。DOM/fetch 不在这里,
// 便于 mjs oracle 直测(tests/test_workbench_p4.mjs test 14)。后端 ds_tools.edit_change
// 是唯一写口径(名字闸/保格式/留痕全在核心);本层只负责"该不该发、发哪些字段"。

/** 四状态(与 ds_tools.STATUSES / ds_todo.STATUS_WORDS 同源)—— 状态点选用。 */
export const STATUSES = ["待确认", "进行中", "已完成", "已关闭"] as const;
export type Status = (typeof STATUSES)[number];

export function isValidStatus(s: string): s is Status {
  return (STATUSES as readonly string[]).includes(s);
}

/** 行内编辑草稿:三字段皆可选,未触碰的字段 undefined。 */
export type EditDraft = {
  status?: string; // 点选的新状态
  text?: string; // 编辑中的正文(未 trim)
  note?: string; // 备注输入(未 trim)
};

/** POST /api/changes/edit 请求体(仅含实际要改的字段;后端按缺省跳过)。 */
export type EditRequest = {
  project: string;
  cnum: number;
  new_status?: string;
  new_text?: string;
  note?: string;
};

/**
 * 草稿 → 请求体。只放"真的变了且合法"的字段:
 *  - new_status:是合法状态且 ≠ 原状态;
 *  - new_text:trim 后非空且 ≠ 原正文(no-op 不发,免后端写 `原:X`==新值噪声);
 *  - note:trim 后非空(追加/替换;空视同不改)。
 * cnum 缺失(残缺行)不可编辑 → null;三字段都无有效改动 → null(无可提交)。
 */
export function buildEditRequest(
  item: Pick<OpenItem, "project" | "cnum" | "status" | "text">,
  draft: EditDraft,
): EditRequest | null {
  if (item.cnum === null) return null;
  const req: EditRequest = { project: item.project, cnum: item.cnum };
  let dirty = false;

  if (
    draft.status !== undefined &&
    isValidStatus(draft.status) &&
    draft.status !== item.status
  ) {
    req.new_status = draft.status;
    dirty = true;
  }
  if (draft.text !== undefined) {
    const t = draft.text.trim();
    if (t && t !== item.text) {
      req.new_text = t;
      dirty = true;
    }
  }
  if (draft.note !== undefined) {
    const n = draft.note.trim();
    if (n) {
      req.note = n;
      dirty = true;
    }
  }
  return dirty ? req : null;
}
