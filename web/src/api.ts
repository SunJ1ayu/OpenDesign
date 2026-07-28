// ds_web 只读 API 的类型与取数封装(P2 T2)。
// 形状 = bin/ds_web.py 四条 GET 的输出(单一真相源,字段勿在前端另造)。
import type { ChatSession } from "./chat/connection"; // type-only,无运行时依赖/无环

export type Project = {
  key: string;
  name: string;
  stage: string;
  // 这里曾有 owner / status_note(cockpit 速览块)。**2026-07-28 整条下线**:
  // 速览块删了 ⇒ 没有消费者;而 status_note 那个档案字段本来就没有任何写口。
  // 故意不留成可选字段 —— 留着等于把坑保温,下一个人照样会拿它去渲染。
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

// 单条留痕(track opendesign-stage-history §9):edit_change 写侧每次改正文都往
// `## 变更历史` 段记一笔,读侧 ds_tools.parse_history 按 cnum 分桶回传,时序=后端顺序。
// date 可为 null:后端留痕行理论上可缺日期,history.ts 运行时也按 null 处理
export type ChangeHistoryEntry = { date: string | null; old: string };

export type Change = {
  cnum: number | null;
  status: string; // 待确认 | 进行中 | 已完成 | 已关闭
  text: string;
  date: string | null; // YYYY-MM-DD
  space: string | null; // 变更行可选【空间】前缀(p4 T1);旧行 null=未标注
  source: string | null;
  due: string | null; // 截止日 YYYY-MM-DD(track opendesign-todo-duedate);旧行 null
  // 后端 ds_web.py:_changes 早就在返回,history 恒为数组(无历史=空)、
  // note 可选(有才带该键,与"没备注"和"没有该字段"不必强区分——前端按 undefined 处理)。
  history: ChangeHistoryEntry[];
  note?: string;
};

export type Ref = {
  id: string;
  style: string[];
  space: string[];
  file: string; // refs/ 下相对路径,取图走 /api/refs/file/<file 去掉 refs/ 前缀>
  note: string;
};

// 参考图词表(track opendesign-stage-history §8):单一真相源 = 后端
// ds_refs._load_styles / ds_refs.SPACES,经 GET /api/projects/<key>/refs 下发;
// 前端(lightbox 编辑区)不许硬编码副本。
export type RefsVocab = { style: string[]; space: string[] };

// P5 文件工作区(bin/ds_web.py /api/files/*;未配置/未映射诚实降级)
// latest_mtime=类目最新文件 mtime(epoch 秒,活跃度信号);capped 时 null(宁缺勿假)
export type WsCategory = { name: string; count: number; capped: boolean;
                           latest_mtime: number | null };
// rel = 项目内完整相对路径(含子目录),后端权威载荷;前端「打开该文件」直接用它,
// 不许拼 `${category}/${name}` —— 嵌套文件会 404,同名不同子目录会开错文件。
export type WsRecent = { name: string; category: string; rel: string;
                         mtime: number; size: number };
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

// 阶段词表随项目列表一起下发(单一真相源 = 后端 ds_tools.PROJECT_STAGES);
// fetchProjects 保持既有返回形状(只给数组),要词表用 fetchProjectsData。
export const fetchProjectsData = () =>
  getJson<{ projects: Project[]; stages: string[]; excludedStructural?: string[] }>(
    "/api/projects");

export const fetchProjects = () => fetchProjectsData().then((d) => d.projects);

export const fetchChanges = (key: string) =>
  getJson<{ changes: Change[] }>(
    `/api/projects/${encodeURIComponent(key)}/changes`,
  ).then((d) => d.changes);

// refs 与 vocab 同一条 GET(避免图墙一次要两个字段却打两次请求);既有调用方
// (SearchPanel/CompanionColumn)只要 refs 数组,fetchRefs 保持原返回形状不变。
export const fetchRefsData = (key: string) =>
  getJson<{ refs: Ref[]; vocab: RefsVocab }>(
    `/api/projects/${encodeURIComponent(key)}/refs`,
  );

export const fetchRefs = (key: string) => fetchRefsData(key).then((d) => d.refs);

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
  /** 业主名。真机反馈 2026-07-24 #3 起**可选**:建档表单只填项目名,业主后补
   *  (核心 create_project 空业主时不写 `[[链接]]`、不建 stub)。 */
  client?: string;
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
  | {
      configured: false;
      reason?: string;
      /** 没有收件箱夹时,「帮我建收件箱」会建在哪(绝对路径)——点之前就要写给用户看。 */
      wouldCreate?: string;
      entries: IntakeEntry[];
      pending: IntakePlan[];
    }
  | {
      configured: true;
      inbox: string;
      /** 收件箱绝对路径(track opendesign-chat-image):用户问过"在我电脑哪个文件夹"。 */
      path?: string | null;
      truncated: boolean;
      entries: IntakeEntry[];
      pending: IntakePlan[];
    };

export const fetchIntake = () => getJson<IntakeData>("/api/intake");

// ── 工作区体检卡(track opendesign-workspace-health)────────────────────────
/** 一行 = 工作区根下的一个文件夹。
 *  `currentlyHidden` 是**事实**(它现在有没有被排除,含被程序猜掉的);
 *  `preselect` 是**开关初值**,只有 `reason==="declared"` 才为真 ——
 *  猜出来的绝不预勾,否则用户随手一点保存就把猜测固化成了正式声明。 */
export type FolderRow = {
  name: string;
  reason: "declared" | "guessed" | "default";
  currentlyHidden: boolean;
  preselect: boolean;
  missing: boolean;
};
export type WorkspaceHealth =
  | { configured: false; applicable: false; folders: []; projectCount: number; reviewId: string }
  | {
      configured: true;
      applicable: boolean;
      declared?: boolean;
      root?: string;
      projectsRoot?: string;
      projectCount: number;
      folders: FolderRow[];
      reviewId: string;
    };

export const fetchWorkspaceHealth = () =>
  getJson<WorkspaceHealth>("/api/workspace/health");

/** 一次存**整份**「不显示」清单(不是一次改一个名字 —— 增量写口会在声明第一个
 *  名字的瞬间让回落语义整层关闭,其他被猜掉的目录突然全冒出来)。
 *  `review_id` 绑「配置内容 + 目录快照」:你开着卡片时在资源管理器里新建了文件夹,
 *  按旧快照保存会静默把它藏掉 —— 所以服务端会回 409 `stale_review`,要求重看一遍。 */
export type SaveVisibilityError =
  | "stale_review" | "not_applicable" | "workspace_not_configured" | "bad_request";
export async function saveFolderVisibility(
  reviewId: string, hidden: string[],
): Promise<{ ok: true } | { ok: false; code: SaveVisibilityError }> {
  const r = await fetch("/api/workspace/folder-visibility", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_id: reviewId, hidden }),
  });
  if (r.ok) return { ok: true };
  let code = "";
  try {
    code = ((await r.json()) as { error?: string }).error || "";
  } catch {
    /* 服务端异常时没有 JSON 体,按通用失败处理 */
  }
  const known: SaveVisibilityError[] =
    ["stale_review", "not_applicable", "workspace_not_configured"];
  return { ok: false,
           code: known.includes(code as SaveVisibilityError)
             ? (code as SaveVisibilityError) : "bad_request" };
}

/** 打开收件箱(track -p2):复用 open-folder 唯一开口的 inbox 分支。
 * **不传路径** —— 收件箱在哪由服务端 _find_inbox 解析,网页给不了路径。 */
export async function openInbox(): Promise<void> {
  const r = await fetch("/api/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inbox: true }),
  });
  if (!r.ok) throw new Error(`服务返回 ${r.status}`);
}

/** 第十四个非 GET(track opendesign-chat-image,写针孔⑭):建收件箱夹。
 * 空 body(后端键白名单=空集:名字由规则表定,不由网页点名)。**人工点一下才建** ——
 * 上传口刻意不自己造目录(网页凭空建文件夹=越权),这个按钮是那条规矩下的正当出路。 */
export type CreateInboxResult = {
  ok: true;
  status: "created" | "already_exists";
  inbox: string;
  path: string;
};
export async function createInbox(): Promise<CreateInboxResult> {
  const r = await fetch("/api/inbox/create", {
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
  return (await r.json()) as CreateInboxResult;
}

/** 建收件箱的错误码 → 人话(同 uploadErrMsg 先例:不把裸码怼给设计师)。 */
export function createInboxErrMsg(code: string): string {
  if (code === "name_taken")
    return "工作区根目录下已经有个同名的**文件**了(不是文件夹),先把它改个名。";
  if (code === "inbox_outside_root")
    return "那个名字被一个快捷方式/软链接占了,指到了工作区外面,没敢动。";
  if (code === "workspace_not_configured") return "还没接入工作区,先在设置里接一下。";
  if (code === "taxonomy_bad" || code === "bad_inbox_name")
    return "整理规则表读不出来(config/taxonomy.json),先修一下它。";
  return `建收件箱失败(${code})。`;
}

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

/** 第十个非 GET(track opendesign-stage-history 写针孔⑩):切阶段。不做乐观改写
 * (阶段是档案头部字段,以后端回值为准);成功回传 {stage, prev} 供 UI 播报。
 * 失败抛错(带后端 error code)由调用方提示。 */
export type SetStageResult = { ok: true; project: string; stage: string; prev: string | null };
export async function setStage(project: string, stage: string): Promise<SetStageResult> {
  const r = await fetch("/api/projects/stage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, stage }),
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
  return (await r.json()) as SetStageResult;
}

/** 第十一个非 GET(track opendesign-stage-history 写针孔⑪):参考图标签/备注就地改。
 * style/space/note 缺省=不动,给了必须是 str(空串对 note = 清空,对 style/space
 * 会被核心拒 style_unknown/space_unknown——标签不许清空)。成功后调用方按 design
 * 约定重拉 refs(下一次筛选用的是新标签)。失败抛错(带后端 error code)。 */
export type UpdateRefBody = {
  ref_id: string;
  style?: string;
  space?: string;
  note?: string;
};
export async function updateRef(body: UpdateRefBody): Promise<void> {
  const r = await fetch("/api/refs/update", {
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

/** 第十二个非 GET(track opendesign-todo-duedate 写针孔⑫):设/清一条变更的截止日。
 * due=null 清除,否则须 YYYY-MM-DD(非法后端拒 invalid_due)。成功后调用方按 design
 * 约定重拉 changes(截止日改动即时反映在行内)。失败抛错(带后端 error code)。 */
export type SetDueDateBody = { project: string; cnum: number; due: string | null };
export async function setDueDate(body: SetDueDateBody): Promise<void> {
  const r = await fetch("/api/changes/due", {
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

/** 第十三个非 GET(track opendesign-image-upload,写针孔⑬):拖拽上传图片 → 收件箱。
 * **body 是 JSON + data URL,不是 multipart** —— 本服务全部写针孔的 CSRF 纵深靠
 * "必须 application/json → 跨站 fetch 必触发 preflight → 服务无 OPTIONS 面 → 浏览器拦";
 * multipart 是 simple content-type,不触发 preflight,收它等于给这个"能往用户硬盘
 * 写字节"的口开一个 CSRF 洞。
 * 返回**真正落盘的名字**(可能被截短或因撞名换名),调用方据此提示"已存为 xxx"。 */
/** `path` = 绝对落盘路径(0.49.0 起):提示条要能回答"东西到我电脑哪儿了"。 */
export type UploadResult = { ok: true; name: string; inbox: string; path?: string };
export async function uploadToInbox(name: string, dataUrl: string): Promise<UploadResult> {
  const r = await fetch("/api/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, data_url: dataUrl }),
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
  return (await r.json()) as UploadResult;
}

/** 上传错误码 → 人话(不把裸错误码怼给设计师,同 createProjectErrMsg 先例)。 */
export function uploadErrMsg(code: string): string {
  if (code === "bad_name") return "这个文件名不行(可能带了特殊符号),改个名再试。";
  if (code === "bad_type") return "只收 png/jpg/webp/gif(svg 和图纸文件先手动拷进文件夹)。";
  if (code === "too_large") return "这张图太大了(单张上限 8MB),先压一下再传。";
  if (code === "bad_image") return "图片读不出来(格式或编码不对),换一张试试。";
  // 0.49.0 起工作区页的收件箱卡片上有「帮我建收件箱」按钮 —— 提示必须指向它,
  // 否则等于让一个不是程序员的人自己去资源管理器里建文件夹(而按钮就在旁边)。
  if (code === "inbox_not_found")
    return "还没有收件箱文件夹 —— 去工作区页的收件箱卡片点「帮我建收件箱」,一下就好。";
  if (code === "workspace_not_configured") return "还没接入工作区,先在设置里接一下。";
  if (code === "too_many_duplicates") return "同名文件太多了,换个名字再传。";
  return `上传失败(${code})。`;
}

/** File → data URL(拖拽/粘贴拿到的是 File,针孔要 data URL)。 */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onerror = () => reject(new Error("读文件失败"));
    fr.onload = () => resolve(String(fr.result || ""));
    fr.readAsDataURL(file);
  });
}
