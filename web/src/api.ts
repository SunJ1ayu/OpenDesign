// ds_web 只读 API 的类型与取数封装(P2 T2)。
// 形状 = bin/ds_web.py 四条 GET 的输出(单一真相源,字段勿在前端另造)。
import type { ChatSession } from "./chat/connection"; // type-only,无运行时依赖/无环

export type Project = {
  key: string;
  name: string;
  stage: string;
  open_count: number;
  delivered: boolean;
  last_update: string | null;
  // p7:true = 工作区自动发现的未建档文件夹(key=文件夹名;文件区/图墙可用,
  // changes/refs 不请求,建档走对话)
  unregistered: boolean;
  // depth2:projectsDepth=2 时未建档条目的分组名(年份/客户等,key=`组:名`);
  // depth=1 为 "",已建档条目不带此字段
  group?: string;
};

export type Change = {
  cnum: number | null;
  status: string; // 待确认 | 进行中 | 已完成 | 已关闭
  text: string;
  date: string | null; // YYYY-MM-DD
  space: string | null; // 变更行可选【空间】前缀(p4 T1);旧行 null=未标注
  source: string | null;
};

export type Ref = {
  id: string;
  style: string[];
  space: string[];
  file: string; // refs/ 下相对路径,取图走 /api/refs/file/<file 去掉 refs/ 前缀>
  note: string;
};

// P5 文件工作区(bin/ds_web.py /api/files/*;未配置/未映射诚实降级)
export type WsCategory = { name: string; count: number; capped: boolean };
export type WsRecent = { name: string; category: string; mtime: number; size: number };
export type FilesOverview =
  | { configured: false }
  | { configured: true; mapped: false }
  | { configured: true; mapped: true; categories: WsCategory[]; recent: WsRecent[] };
export type FilesImages =
  | { configured: false }
  | { configured: true; mapped: false }
  | { configured: true; mapped: true; images: { rel: string; category: string; mtime: number }[] };

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

export const fetchFilesOverview = (key: string) =>
  getJson<FilesOverview>(`/api/files/overview/${encodeURIComponent(key)}`);

export const fetchFilesImages = (key: string) =>
  getJson<FilesImages>(`/api/files/images/${encodeURIComponent(key)}`);

/** 工作区项目图片静态路由(rel 来自 /api/files/images,posix 分隔)。 */
export function filesImageUrl(key: string, rel: string): string {
  return (
    `/api/files/file/${encodeURIComponent(key)}/` +
    rel.split("/").map(encodeURIComponent).join("/")
  );
}

/** 唯一非 GET:打开本机项目文件夹(open-folder 受控例外)。失败抛错由调用方提示。 */
export async function openFolder(key: string, sub?: string): Promise<void> {
  const r = await fetch("/api/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sub ? { key, sub } : { key }),
  });
  if (!r.ok) throw new Error(`服务返回 ${r.status}`);
}

/** 第二个非 GET(p7 会话删除针孔):经 session.apiFetch 带鉴权走代理。
 * key 传裸串不 encode(_KEY_RE 无 %,p6 e2e 实抓的坑);字符集本就 URL 安全。 */
export type DeleteSessionResult = { deleted: boolean; blocked_by_automations?: boolean };
export async function deleteChatSession(
  session: Pick<ChatSession, "apiFetch">,
  key: string,
): Promise<DeleteSessionResult> {
  const r = await session.apiFetch(`/api/chat/sessions/${key}/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (r.status !== 200) throw new Error(`服务返回 ${r.status}`);
  return (await r.json()) as DeleteSessionResult;
}

/** 第三个非 GET(track opendesign-todo-edit 写针孔):待办行内编辑。
 * body 只含要改的字段(见 todo.buildEditRequest);后端 ds_tools.edit_change 保格式 + 留痕。
 * 失败抛错(带后端 error code)由调用方提示。 */
export type EditChangeBody = {
  project: string;
  cnum: number;
  new_status?: string;
  new_text?: string;
  note?: string;
};
export async function editChange(body: EditChangeBody): Promise<void> {
  const r = await fetch("/api/changes/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let code = "";
    try {
      code = ((await r.json()) as { error?: string }).error ?? "";
    } catch {
      /* 非 JSON 响应:忽略,回落状态码 */
    }
    throw new Error(code || `服务返回 ${r.status}`);
  }
}

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
