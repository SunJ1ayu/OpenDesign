// ds_web 只读 API 的类型与取数封装(P2 T2)。
// 形状 = bin/ds_web.py 四条 GET 的输出(单一真相源,字段勿在前端另造)。

export type Project = {
  key: string;
  name: string;
  stage: string;
  open_count: number;
  delivered: boolean;
  last_update: string | null;
};

export type Change = {
  cnum: number | null;
  status: string; // 待确认 | 进行中 | 已完成 | 已关闭
  text: string;
  date: string | null; // YYYY-MM-DD
  space: string | null; // 现有 PKB 格式无此字段,读侧宽容恒 null(design 决策)
  source: string | null;
};

export type Ref = {
  id: string;
  style: string[];
  space: string[];
  file: string; // refs/ 下相对路径,取图走 /api/refs/file/<file 去掉 refs/ 前缀>
  note: string;
};

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`服务返回 ${r.status}`);
  return (await r.json()) as T;
}

export const fetchProjects = () =>
  getJson<{ projects: Project[] }>("/api/projects").then((d) => d.projects);

export const fetchChanges = (key: string) =>
  getJson<{ changes: Change[] }>(
    `/api/projects/${encodeURIComponent(key)}/changes`,
  ).then((d) => d.changes);

export const fetchRefs = (key: string) =>
  getJson<{ refs: Ref[] }>(
    `/api/projects/${encodeURIComponent(key)}/refs`,
  ).then((d) => d.refs);

export const fetchTodosOpenCount = () =>
  getJson<{ open: unknown[] }>("/api/todos").then((d) => d.open.length);

/** refs-index 的 file 字段是 "refs/xx.jpg";静态路由挂在 /api/refs/file/ 下。 */
export function refImageUrl(file: string): string {
  const rel = file.startsWith("refs/") ? file.slice(5) : file;
  return "/api/refs/file/" + rel.split("/").map(encodeURIComponent).join("/");
}

/** "2026-07-09" → "7月9日"(定稿元信息行口径);无日期给空串。 */
export function cnDate(date: string | null): string {
  if (!date) return "";
  const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(date);
  if (!m) return date;
  return `${Number(m[1])}月${Number(m[2])}日`;
}

/** ISO 时间 → 今天 / 昨天 / M-DD(侧栏历史对话相对时间)。 */
export function relTime(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const day = (x: Date) => `${x.getFullYear()}-${x.getMonth()}-${x.getDate()}`;
  if (day(d) === day(now)) return "今天";
  const yest = new Date(now);
  yest.setDate(now.getDate() - 1);
  if (day(d) === day(yest)) return "昨天";
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, "0")}`;
}
