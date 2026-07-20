// track opendesign-frontend-p3-polish 纯逻辑:§I6 侧栏项目名显示 + §I4 前端分流。
// 由 tests/test_project_name.mjs 直接单测(纯函数,不碰 DOM/网络)。

import type { WsRecent } from "../api";

// 「开文件」扩展名白名单(Gate C,design.md §I4)—— 与后端 bin/ds_web.py 的
// _OPEN_EXTS 同集合,单一真相源的前端镜像(前后端各自维护一份同名常量;
// 改一份必须同步另一份,否则前端分流按钮与后端安全闸会漂移)。
// 无任何可执行/脚本/快捷方式扩展名。
export const OPEN_FILE_EXTS = [
  ".dwg", ".dxf", ".skp", ".3ds", ".max", ".rvt", ".obj", ".fbx", ".stl",
  ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff",
  ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf",
];

const OPEN_PARENS = ["(", "（"];
const CLOSE_PARENS = [")", "）"];

/** §I6:名字以(半角/全角)左括号开头时,优先显示右括号之后的内容(裁首尾空白);
 * 括号后为空、找不到右括号、或不以括号开头 → 原样返回原名(永不返回空串)。
 * 只吃开头那一组括号,不做嵌套/多组处理。 */
export function displayProjectName(name: string): string {
  if (!name) return name;
  if (!OPEN_PARENS.includes(name[0])) return name;
  let closeIdx = -1;
  for (let i = 1; i < name.length; i++) {
    if (CLOSE_PARENS.includes(name[i])) {
      closeIdx = i;
      break;
    }
  }
  if (closeIdx === -1) return name;
  const rest = name.slice(closeIdx + 1).trim();
  return rest === "" ? name : rest;
}

function extOf(name: string): string {
  const idx = name.lastIndexOf(".");
  if (idx <= 0) return "";
  return name.slice(idx).toLowerCase();
}

export type OpenTarget = { kind: "file"; rel: string } | { kind: "folder"; sub?: string };

/** §I4 前端分流(纵深防御,不替代后端闸):白名单内扩展名 → 开该文件本身
 * (rel 带类目前缀,无类目则不带);白名单外(含无扩展名/双扩展名按真实末段判)
 * → 退化为开所在文件夹。 */
export function openTargetFor(recent: WsRecent): OpenTarget {
  const rel = recent.category ? `${recent.category}/${recent.name}` : recent.name;
  if (OPEN_FILE_EXTS.includes(extOf(recent.name))) {
    return { kind: "file", rel };
  }
  return { kind: "folder", sub: recent.category || undefined };
}
