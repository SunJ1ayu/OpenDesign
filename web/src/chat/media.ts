// 聊天发图的纯逻辑层(track opendesign-chat-image,design D1)。
// 零 DOM,tests/test_chat_media.mjs 直测。
//
// 协议限额以 docs/nanobot-ws-protocol.md §2 `media` 一节为准(源码实抄):
//   ≤4 图/条、单图 8MB、png/jpeg/webp/gif、**svg 排除**;
//   **任一项不合规 → nanobot 整条消息不发布**。
// ⇒ 所以必须前端先拦。拦不住的代价不是"报个错",是**用户的消息凭空消失** ——
//   他会以为软件坏了,而不会以为是那张 svg 的问题。所以被丢下的每一张都要说清为什么。

export const MAX_CHAT_IMAGES = 4;
export const MAX_CHAT_IMAGE_BYTES = 8 * 1024 * 1024;

/** 与 ds_workspace.IMG_EXTS 同表(svg 不在内:内嵌脚本 XSS 面,协议也显式排除)。 */
export const CHAT_IMG_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".gif"] as const;

export interface PickableFile {
  name: string;
  size: number;
}

export interface PickResult<T extends PickableFile> {
  accepted: T[];
  rejected: { name: string; why: string }[];
}

const extOf = (name: string) => {
  const i = name.lastIndexOf(".");
  return i < 0 ? "" : name.slice(i).toLowerCase();
};

/**
 * 挑出能发的图。`already` = 这条消息里已经挂着几张(拖两次不能突破 4 张)。
 * 顺序保持入参顺序;每个被丢下的都带一句人话理由(不给裸错误码)。
 */
export function pickChatImages<T extends PickableFile>(
  files: T[],
  already = 0,
): PickResult<T> {
  const accepted: T[] = [];
  const rejected: { name: string; why: string }[] = [];
  let slots = Math.max(0, MAX_CHAT_IMAGES - already);
  for (const f of files) {
    const ext = extOf(f.name);
    if (!(CHAT_IMG_EXTS as readonly string[]).includes(ext)) {
      rejected.push({ name: f.name, why: "只收 png/jpg/webp/gif(svg 和图纸文件发不了)" });
      continue;
    }
    if (!(f.size > 0)) {
      rejected.push({ name: f.name, why: "这个文件是空的(0 字节),换一张试试" });
      continue;
    }
    if (f.size > MAX_CHAT_IMAGE_BYTES) {
      rejected.push({ name: f.name, why: "这张图太大了(单张上限 8MB),先压一下再发" });
      continue;
    }
    if (slots <= 0) {
      rejected.push({ name: f.name, why: `一条消息最多 ${MAX_CHAT_IMAGES} 张图,这张没发` });
      continue;
    }
    slots--;
    accepted.push(f);
  }
  return { accepted, rejected };
}

/**
 * data URL 解码后的**真实字节数**;不是 data URL / 不是合法 base64 → -1。
 * 为什么不信 `File.size`:发出去的是 base64 后的字符串,而体积闸(8MB)是对
 * **解码后字节**的;真正决定 nanobot 收不收的是这个数,不是 File 报的数。
 * 回 -1 而不是 0:调用方据此拒,免得"读不出来"被当成"空文件放行"。
 */
export function dataUrlBytes(dataUrl: string): number {
  const m = /^data:[^,;]*(?:;[^,;]+)*;base64,([\s\S]*)$/.exec(dataUrl || "");
  if (!m) return -1;
  const b64 = m[1];
  if (!b64 || b64.length % 4 !== 0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(b64)) return -1;
  const pad = b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0;
  return (b64.length / 4) * 3 - pad;
}
