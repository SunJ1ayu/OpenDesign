// ds_web 只读 API 的类型与取数封装(P2 T2)。
// 形状 = bin/ds_web.py 四条 GET 的输出(单一真相源,字段勿在前端另造)。
import type { ChatSession } from "./chat/connection"; // type-only,无运行时依赖/无环

export type Project = {
  key: string;
  name: string;
  stage: string;
  // cockpit 速览:业主(已剥 [[ ]])与「当前状态」一句话;缺字段=空串。
  // 未建档条目不带这两个字段。
  owner?: string;
  status_note?: string;
  open_count: number;
  delivered: boolean;
  last_update: string | null;
  // p7:true = 工作区自动发现的未建档文件夹(key=文件夹名;文件区/图墙可用,
  // changes/refs 不请求,建档走对话)
  unregistered: boolean;
  // depth2:projectsDepth=2 时的分组名(年份/客户等);depth=1 为 ""。
  // cockpit 起已建档条目也带(三级绑定命中的夹子反查分组)。
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
// latest_mtime=类目最新文件 mtime(epoch 秒,活跃度信号);capped 时 null(宁缺勿假)
export type WsCategory = { name: string; count: number; capped: boolean;
                           latest_mtime: number | null };
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

/** track p3-polish §I4:打开单个文件(open-folder 同一受控开口,rel 分支)。
 * 后端白名单外一律 415,前端已按 openTargetFor 分流不该在此传白名单外的 rel,
 * 但即便传了后端仍会拒——这里不重复判断,失败照样抛错由调用方提示。 */
export async function openFile(key: string, rel: string): Promise<void> {
  const r = await fetch("/api/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, rel }),
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

/** 第五个非 GET(track opendesign-clickable-actions 写针孔⑤):变更记录「+ 记一条」。
 * space 可选(不带即不带前缀)。成功回传 change_id(如 "C13",快记 toast 用)+ 落盘行原文。
 * 失败抛错(带后端 error code)由调用方提示。 */
export type AddChangeBody = { project: string; content: string; space?: string };
export type AddChangeResult = { ok: true; change_id: string; line: string };
export async function addChange(body: AddChangeBody): Promise<AddChangeResult> {
  const r = await fetch("/api/changes/add", {
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
  return (await r.json()) as AddChangeResult;
}

/** 第六个非 GET(同上 track,写针孔⑥):未建档文件夹「一键建档」。
 * stage/address 可选(缺省时后端补默认「洽谈」/空)。成功回传 {project,client,stage}。
 * 失败抛错(带后端 error code)由调用方提示。 */
export type CreateProjectBody = {
  project: string;
  client: string;
  stage?: string;
  address?: string;
};
export async function createProject(body: CreateProjectBody): Promise<void> {
  const r = await fetch("/api/projects/create", {
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

/** 收件箱(track opendesign-intake):GET 清单+建议+待确认 plans;POST 确认执行。 */
export type IntakeCategory = {
  id: string;
  scope: "project" | "workspace";
  dir: string;
  mode: "auto" | "suggest";
};
export type IntakeEntry = {
  name: string;
  type: "file" | "dir";
  size: number;
  mtime: number;
  category: IntakeCategory | null;
  project: string | null;
};
export type IntakePlanOp = { op: string; src_rel: string; dst_rel: string };
export type IntakePlan = { plan_id: string; created: string | null; ops: IntakePlanOp[] };
export type IntakeData =
  | { configured: false; reason?: string; entries: IntakeEntry[]; pending: IntakePlan[] }
  | {
      configured: true;
      inbox: string;
      truncated: boolean;
      entries: IntakeEntry[];
      pending: IntakePlan[];
    };

export const fetchIntake = () => getJson<IntakeData>("/api/intake");

/** 第四个非 GET(intake 针孔④):收件箱卡片「确认执行」= 人工批准本体,
 * 后端 approve+apply 一气(快照复验/审计在核心)。失败抛错(带后端 error code)。 */
export async function approveIntake(planId: string): Promise<void> {
  const r = await fetch("/api/intake/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId }),
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

/** 第七个非 GET(track opendesign-inbox-scan 写针孔⑦):收件箱卡片「扫描整理」。
 * 空 body(后端键白名单=空集);把「确定性建议」自动采纳为一个待确认 plan,
 * 歧义/未知留 skipped 交人工。失败抛错(带后端 error code)由调用方提示。 */
export type ScanInboxSkipped = { name: string; reason: string };
export type ScanInboxResult = {
  ok: true;
  plan_id: string | null;
  staged: number;
  skipped: ScanInboxSkipped[];
};
export async function scanInbox(): Promise<ScanInboxResult> {
  const r = await fetch("/api/intake/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
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
  return (await r.json()) as ScanInboxResult;
}

/** 第八个非 GET(track opendesign-frontend-p1 写针孔⑧):收件箱卡片单条「跳过」。
 * drop = 要剔除的 operations 下标列表。成功回传剩余案 plan_id(全跳=null)/count/dropped;
 * 失败抛错(带后端 error code)由调用方提示。 */
export type AmendIntakeResult = { ok: true; plan_id: string | null; count: number; dropped: number };
export async function amendIntake(planId: string, drop: number[]): Promise<AmendIntakeResult> {
  const r = await fetch("/api/intake/amend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId, drop }),
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
  return (await r.json()) as AmendIntakeResult;
}

/** 第九个非 GET(同上 track,写针孔⑨):项目↔工作区文件夹关联。
 * folder_not_found/folder_ambiguous 时后端回传 folders 候选名单,随错误一并抛出
 * (message = code,候选名单挂在 Error 上供调用方按需读取)。 */
export class BindProjectError extends Error {
  folders?: string[];
  constructor(code: string, folders?: string[]) {
    super(code);
    this.folders = folders;
  }
}
export async function bindProject(project: string, folder: string): Promise<void> {
  const r = await fetch("/api/projects/bind", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, folder }),
  });
  if (!r.ok) {
    let code = "";
    let folders: string[] | undefined;
    try {
      const d = (await r.json()) as { error?: string; folders?: string[] };
      code = d.error ?? "";
      folders = d.folders;
    } catch {
      /* 非 JSON 响应:忽略,回落状态码 */
    }
    throw new BindProjectError(code || `服务返回 ${r.status}`, folders);
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
