// 变更修改历史纯逻辑层(P2 T3 #9,track opendesign-stage-history)——后端
// `/api/projects/<key>/changes` 每条变更早就返回 `history: [{date, old}]`
// (时序=后端顺序,前端不重排)与可选 `note`;这里只把它们变成可渲染的字符串/
// 列表,零 DOM、零 fetch。进 mjs oracle:tests/test_change_history.mjs。
// 显式 .ts 扩展:tsconfig allowImportingTsExtensions + node --test 原生 strip-types 两头兼容
import { cnDate } from "../api.ts";

type HistoryEntry = { date: string | null; old: string };
// 后端原始形状未知量:history 字段可能缺失/非数组(老缓存/异常),条目也可能
// 结构不对(不是 {date, old} 形态)——防御性接受 unknown。
type MaybeChange = { history?: unknown };
type RawEntry = { date?: unknown; old?: unknown };

function rawHistory(change: MaybeChange): unknown[] {
  return Array.isArray(change.history) ? change.history : [];
}

/** 折叠态那一行的文案:无历史 → 空串(调用方据此不渲染入口)。 */
export function historySummary(change: MaybeChange): string {
  const h = rawHistory(change);
  return h.length > 0 ? `改过 ${h.length} 次` : "";
}

/** 取出可渲染列表,顺序=后端给的时序(前端不重排)。结构不对的条目直接丢
 * (缺 old 的丢掉;缺 date 的保留,原文才是主体,日期是附加信息)。 */
export function historyEntries(change: MaybeChange): HistoryEntry[] {
  const out: HistoryEntry[] = [];
  for (const e of rawHistory(change)) {
    if (e && typeof e === "object") {
      const re = e as RawEntry;
      if (typeof re.old === "string") {
        out.push({ date: typeof re.date === "string" ? re.date : null, old: re.old });
      }
    }
  }
  return out;
}

/** 单条的展示文本:「<日期> 原:<原文>」;无日期只出原文,不留空格头。
 * 日期走 cnDate 中文短格式(与定稿元信息行同口径);坏日期原样透出,不猜不补。
 * 原文里的换行不参与渲染(索引层已消毒,这里只做兜底)。 */
export function formatHistoryEntry(entry: HistoryEntry): string {
  const clean = (entry.old || "").replace(/[\r\n]+/g, " ");
  const d = cnDate(entry.date);
  return d ? `${d} 原:${clean}` : `原:${clean}`;
}
