import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchWorkspaceHealth, previewWorkspace, setWorkspaceRoot, WorkspacePickError,
  type WorkspaceLayout, type WorkspacePreview,
} from "../api";
import { pickFolderApi } from "../desktopShell";

// 业主手动选工作区(track opendesign-workspace-picker)。
//
// 以前工作区只能靠助手设:首次在项目页填个路径,其实是替你往聊天里发一句"把我的项目文件夹接进来";
// 接好之后想换,界面上没有任何入口,也没有"选择文件夹"的对话框。
//
// 流程:① 选文件夹(桌面版弹系统自己的对话框;浏览器里没有,退回手填路径)
//       ② 预览:三种摆法各认出几个项目、举几个名字 —— 业主不该需要懂 projectsDir / depth,
//          看名字对不对就能挑;默认选中认出最多的那种(有「01-项目」总夹时优先它)
//       ③ 接入。业主亲手选的文件夹 = 同意本身,不再弹同意卡(同意卡拦的是助手,不是业主)。
//          但影响面照样写在这里:接入后助手能读这里的资料文档,会随对话发给大模型。

type Props = {
  /** 现在接的是哪个文件夹(对话框从这里打开;没有就不传)。 */
  currentRoot?: string | null;
  onClose: () => void;
  /** 接好了:外层刷新项目列表等。 */
  onDone: (r: { root: string; folder_count: number }) => void;
};

const LAYOUT_TEXT: Record<WorkspaceLayout["layout"], (l: WorkspaceLayout) => string> = {
  auto: (l) => `项目都放在「${l.projects_dir}」里`,
  direct: () => "项目直接放在这个文件夹里",
  grouped: () => "先按年份 / 客户分了一层,项目在第二层",
};

/** 默认选哪种:有总夹且认出了项目 ⇒ 它;否则认出最多的(并列时靠前的,也就是"直接放在这里")。 */
function bestLayout(ls: WorkspaceLayout[]): number {
  const auto = ls.findIndex((l) => l.layout === "auto" && l.count > 0);
  if (auto >= 0) return auto;
  let best = 0;
  ls.forEach((l, i) => { if (l.count > ls[best].count) best = i; });
  return best;
}

export default function WorkspacePicker({ currentRoot: rootHint, onClose, onDone }: Props) {
  const picker = pickFolderApi();
  // 现在接的是哪个文件夹:打开时**自己拉一次**,不靠外层传进来的那份 —— 外层是异步拉的,
  // 业主一进设置页就点「更换」时它可能还没到,系统对话框就从空路径打开、"现在接的是"那行也不见了
  // (云沙箱 e2e W2 偶发红就是这个竞态)。外层那份只当拉到之前的占位。
  const [currentRoot, setCurrentRoot] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    let stale = false;
    fetchWorkspaceHealth()
      .then((h) => { if (!stale) setCurrentRoot(h.configured ? h.root ?? null : null); })
      .catch(() => { if (!stale) setCurrentRoot(rootHint ?? null); });
    return () => { stale = true; };
  }, [rootHint]);
  const [path, setPath] = useState("");
  const [preview, setPreview] = useState<WorkspacePreview | null>(null);
  const [sel, setSel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState<{ root: string; folder_count: number } | null>(null);
  const started = useRef(false);

  const runPreview = useCallback(async (p: string) => {
    setErr("");
    setBusy(true);
    try {
      const pv = await previewWorkspace(p.trim());
      setPreview(pv);
      setSel(bestLayout(pv.layouts));
    } catch (e) {
      setErr(e instanceof WorkspacePickError ? e.message : "没能读取这个文件夹,请再试一次。");
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }, []);

  const pick = useCallback(async () => {
    if (!picker) return;
    const p = await picker(preview?.root ?? currentRoot ?? undefined).catch(() => null);
    if (!p) {
      if (!preview) onClose();   // 一上来就取消 = 不换了
      return;
    }
    setPath(p);
    void runPreview(p);
  }, [picker, preview, currentRoot, onClose, runPreview]);

  // 桌面版:一打开就弹系统对话框(业主点的就是"更换…",没必要再多点一下)。
  // 等"现在接的是哪个"拉到了再弹,对话框才能从那个文件夹打开。
  useEffect(() => {
    if (started.current || !picker || currentRoot === undefined) return;
    started.current = true;
    void pick();
  }, [picker, pick, currentRoot]);

  const apply = async () => {
    if (!preview) return;
    setErr("");
    setBusy(true);
    try {
      const r = await setWorkspaceRoot(preview.root, preview.layouts[sel]);
      setDone(r);
      onDone(r);
    } catch (e) {
      setErr(e instanceof WorkspacePickError ? e.message : "没能接入,工作区没有被改动。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="connect-modal-mask" data-ui="ws-picker-mask" onClick={onClose}>
      <div className="ws-picker" data-ui="ws-picker" role="dialog" aria-label="选择项目文件夹"
           onClick={(e) => e.stopPropagation()}>
        <div className="ws-picker-head">选择项目文件夹</div>
        {currentRoot && !done && (
          <div className="ws-picker-cur">现在接的是:<span className="mono">{currentRoot}</span></div>
        )}

        {done ? (
          <>
            <div className="ws-picker-done" data-ui="ws-picker-done">
              已接入 <span className="mono">{done.root}</span>,认出 {done.folder_count} 个项目。
            </div>
            <div className="ws-picker-actions">
              <button className="btn-primary" onClick={onClose}>好</button>
            </div>
          </>
        ) : (
          <>
            {picker ? (
              <div className="ws-picker-path">
                <span className="mono">{preview?.root ?? (busy ? "…" : "还没选")}</span>
                <button className="btn-secondary sm" onClick={() => void pick()} disabled={busy}>
                  {preview ? "换一个文件夹…" : "选择文件夹…"}
                </button>
              </div>
            ) : (
              /* 浏览器里没有系统对话框:手填路径 */
              <form className="ws-picker-path" onSubmit={(e) => { e.preventDefault(); void runPreview(path); }}>
                <input
                  autoFocus
                  data-ui="ws-picker-input"
                  value={path}
                  placeholder="例如 D:\设计工作区"
                  onChange={(e) => setPath(e.target.value)}
                />
                <button type="submit" className="btn-secondary sm" disabled={busy || !path.trim()}>
                  看看
                </button>
              </form>
            )}

            {preview && (
              <>
                <div className="ws-picker-q">你的项目是怎么放的?</div>
                <div className="ws-picker-opts" role="radiogroup">
                  {preview.layouts.map((l, i) => (
                    <button
                      key={l.layout}
                      type="button"
                      role="radio"
                      aria-checked={i === sel}
                      data-ui="ws-picker-layout"
                      data-layout={l.layout}
                      className={`ws-picker-opt${i === sel ? " selected" : ""}`}
                      onClick={() => setSel(i)}
                    >
                      <span className="t">{LAYOUT_TEXT[l.layout](l)}</span>
                      <span className="n">
                        {l.count > 0
                          ? `认出 ${l.count} 个:${l.sample.join("、")}${l.count > l.sample.length ? "…" : ""}`
                          : "认不出项目"}
                      </span>
                    </button>
                  ))}
                </div>
                {preview.layouts[sel]?.count === 0 && (
                  <div className="ws-picker-warn">这种摆法一个项目都认不出来,确定是这个文件夹吗?</div>
                )}
                <div className="ws-picker-impact">
                  接入后,助手就能读取这里各个项目的资料文档(合同、报价、业主意见),内容会随对话发给大模型。
                </div>
              </>
            )}

            {err && <div className="ws-picker-err" data-ui="ws-picker-err">{err}</div>}

            <div className="ws-picker-actions">
              <button className="btn-secondary" onClick={onClose} disabled={busy}>取消</button>
              <button className="btn-primary" data-ui="ws-picker-apply"
                      onClick={() => void apply()} disabled={busy || !preview}>
                接入
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
