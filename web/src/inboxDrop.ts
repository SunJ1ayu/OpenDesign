import { useState, type DragEvent } from "react";
import { fileToDataUrl, uploadErrMsg, uploadToInbox } from "./api";

type InboxDropOptions = {
  rejectMessage?: string;
  successTail?: string;
  onUploaded?: () => void;
};

// 与后端 `_INBOX_UPLOAD`(bin/ds_web.py)同一组扩展名 —— 分类表认识什么,入口就收什么。
// 两边各存一份是刻意的:前端这份只为**提示才对症**(先拦掉才能说清"不收什么"),
// 真正的闸在后端;后端那份有判据钉住它与分类表不漂移。
const OK_EXT = /\.(png|jpe?g|webp|gif|pdf|docx?|xlsx?|pptx?|txt|csv|dwg|dxf|skp|max|psd)$/i;

function hasFiles(e: DragEvent<HTMLElement>) {
  return e.dataTransfer.types.includes("Files");
}

/** 收件箱上传的唯一前端拖放写法:图墙和收件箱卡共用同一个入口。 */
export function useInboxDrop({
  rejectMessage = "这个格式收不了。可以拖:图片、PDF、Word/Excel/PPT、CAD(dwg/dxf)、SU、3ds Max、PSD。",
  successTail = " —— 去伴随列点「扫描整理」归档",
  onUploaded,
}: InboxDropOptions = {}) {
  const [dragOver, setDragOver] = useState(false);
  const [upMsg, setUpMsg] = useState<string | null>(null);
  const [upBusy, setUpBusy] = useState(false);

  async function uploadFiles(files: File[]) {
    // 后端白名单见 ds_web.py 的 _INBOX_UPLOAD。这里先按扩展名拦一道,提示才对症
    // (svg/exe/zip 这类仍然不收)。
    const imgs = files.filter((f) => OK_EXT.test(f.name));
    if (!imgs.length) {
      setUpMsg(rejectMessage);
      return;
    }
    setUpBusy(true);
    const stored: string[] = [];
    let dir = "";
    try {
      for (const f of imgs) {
        const r = await uploadToInbox(f.name, await fileToDataUrl(f));
        stored.push(r.name);
        if (!dir && r.path) dir = r.path.slice(0, r.path.length - r.name.length);
      }
      setUpMsg(`已存进收件箱${dir ? `(${dir})` : ""}:${stored.join("、")}` + successTail);
      onUploaded?.();
    } catch (e) {
      const done = stored.length ? `已存 ${stored.length} 个;` : "";
      setUpMsg(done + uploadErrMsg((e as Error).message));
    } finally {
      setUpBusy(false);
    }
  }

  const dropProps = {
    onDragOver: (e: DragEvent<HTMLElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault(); // 不 preventDefault 浏览器会直接打开图片。
      setDragOver(true);
    },
    onDragLeave: (e: DragEvent<HTMLElement>) => {
      const next = e.relatedTarget;
      if (next instanceof Node && e.currentTarget.contains(next)) return;
      setDragOver(false);
    },
    onDrop: (e: DragEvent<HTMLElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      setDragOver(false);
      void uploadFiles(Array.from(e.dataTransfer.files));
    },
  };

  return {
    dragOver,
    upBusy,
    upMsg,
    setUpMsg,
    uploadFiles,
    dropProps,
  };
}
