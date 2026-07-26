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

/**
 * 上游 `error` 事件 → 人话;不是 error 事件 → null。
 *
 * 为什么需要它:`applyEvent` 的 `case "error"` 只解锁 busy、**什么都不显示**
 * (transcript.ts)。而 nanobot 拒图时明明说了理由:
 * `{"event":"error","detail":"image_rejected","reason":…}`,reason ∈
 * {too_many_images, too_many_videos, mime, size, decode, malformed}
 * (实读 `nanobot/channels/websocket.py` 的 `_save_envelope_media` 与 message 分支)。
 * 不转达的后果:用户的气泡在屏上、没有回复、没有解释 —— 从他的角度就是
 * "消息发出去然后没了"。上游好好说了话,我们必须翻给人听。
 */
export function chatErrorMsg(ev: unknown): string | null {
  if (typeof ev !== "object" || ev === null) return null;
  const e = ev as Record<string, unknown>;
  if (e.event !== "error") return null;
  if (e.detail === "image_rejected") {
    const reason = typeof e.reason === "string" ? e.reason : "";
    if (reason === "too_many_images") {
      return `图太多了,这条没发出去(一次最多 ${MAX_CHAT_IMAGES} 张)。`;
    }
    if (reason === "too_many_videos") return "视频太多了,这条没发出去。";
    if (reason === "size") return "图太大了,这条没发出去(单张上限 8MB,先压一下)。";
    if (reason === "mime") return "这种图片格式发不了(只收 png/jpg/webp/gif)。";
    if (reason === "decode") return "有张图读不出来,这条没发出去,换一张再试。";
    if (reason === "malformed") return "图片数据不对,这条没发出去。";
    return "有张图被拒了,这条没发出去。";
  }
  if (e.detail === "missing content") return "空消息发不出去,写点什么或带张图。";
  const d = typeof e.detail === "string" && e.detail ? e.detail : "未知原因";
  return `这条没发出去(${d})。`;
}

/** 上游白名单(nanobot `_UPLOAD_MIME_ALLOWED` 的图片半边),照源码抄。 */
const SENDABLE_MIMES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

/**
 * data URL 的 mime 是否在上游白名单内。
 *
 * 为什么不能只看扩展名:**前端按扩展名判,nanobot 按 data URL 里的 mime 判**
 * (`_extract_data_url_mime` → `_UPLOAD_MIME_ALLOWED`)。两者会分叉 —— 某些环境
 * `File.type` 是空的,data URL 就成了 `data:;base64,…`,名字再对上游也认不出,
 * 结果**整条消息被拒**。所以发送前用上游的同一判据再过一遍。
 */
export function isSendableDataUrl(dataUrl: string): boolean {
  const m = /^data:([^,;]+);base64,/.exec(dataUrl || "");
  if (!m) return false;
  return SENDABLE_MIMES.includes(m[1].trim().toLowerCase());
}
