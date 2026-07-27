import { useEffect, useRef, useState } from "react";
import type { FolderRow, WorkspaceHealth } from "../api";
import { fetchWorkspaceHealth, saveFolderVisibility } from "../api";

// 工作区体检卡(track opendesign-workspace-health,阶段二前端 T8)。
//
// 这一单要解决的真问题:程序会**猜**哪些文件夹是结构目录(收件箱/归档/共享资源)
// 而不列进项目列表。猜错了用户没有任何纠正入口 —— 侧栏只有一句被动提示,
// 一个真项目就这么从列表里消失了,而他不会去翻配置文件。
//
// 两条设计红线(照 design A6 / 盲点①,**改文案前先读**):
//  ① **猜出来的绝不预勾在「不显示」一侧**。开关初值只认 reason==="declared"。
//     预勾之后用户随手一点保存,猜测就固化成了正式声明 —— 恰好把本单要防的事故焊死。
//     所以「什么都不动直接保存」= 撤销所有猜测、全部显示,这是刻意的不对称取舍:
//     多列一个文件夹只是碍眼,藏错一个真项目是事故。
//  ② 文案只能说「显示 / 不显示在项目列表」,**绝不能**说成「设为收件箱」。
//     用户在这里的选择只影响列不列出来,不改变那个文件夹的任何用途;
//     说成「设为收件箱」会让人以为自己在给文件夹分类,那是另一回事。
//
// 款式对齐 InboxCard:没事(不适用/没有可调的行)整卡不渲染;默认收成一行摘要。

type Props = {
  /** 每轮聊天回复后 bump:agent 刚改过工作区时即刻反映。 */
  dataEpoch: number;
  /** 路由门:仅工作区路由可见时拉数据。 */
  active: boolean;
  /** 存成功后通知外层刷新项目列表(藏/显直接改变左侧列表)。 */
  onSaved?: () => void;
};

const REASON_LABEL: Record<FolderRow["reason"], string> = {
  declared: "你设过的",
  guessed: "按常见名字猜的",
  default: "显示中",
};

export default function FolderVisibilityCard({ dataEpoch, active, onSaved }: Props) {
  const [data, setData] = useState<WorkspaceHealth | null>(null);
  const [expanded, setExpanded] = useState(false);
  /** 用户当前勾选的「不显示」集合。null = 还没从服务端数据初始化过。 */
  const [hidden, setHidden] = useState<Set<string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [localEpoch, setLocalEpoch] = useState(0);
  const fetched = useRef<string | null>(null);

  useEffect(() => {
    if (!active) return;
    const stamp = `${dataEpoch}/${localEpoch}`;
    if (fetched.current === stamp) return;
    fetched.current = stamp;
    let stale = false;
    fetchWorkspaceHealth()
      .then((d) => {
        if (stale) return;
        setData(d);
        // 开关初值 = preselect(**不是** currentlyHidden,见红线①)
        setHidden(new Set(d.folders.filter((f) => f.preselect).map((f) => f.name)));
      })
      .catch(() => {
        // 拉不到就整卡不渲染:这张卡是"纠正入口",自己报错没有任何用处
        if (!stale) setData(null);
      });
    return () => {
      stale = true;
    };
  }, [active, dataEpoch, localEpoch]);

  if (!data || !data.configured || !data.applicable) return null;
  const rows = data.folders;
  if (rows.length === 0 || hidden === null) return null;

  const nowHidden = rows.filter((f) => f.currentlyHidden);
  // 「保存后会变成什么样」——落差只按开关的当前状态算,不看 reason
  const willHide = rows.filter((f) => hidden.has(f.name));
  const willShow = rows.filter((f) => !hidden.has(f.name));
  const appearing = nowHidden.filter((f) => !hidden.has(f.name));
  const disappearing = rows.filter((f) => !f.currentlyHidden && hidden.has(f.name));
  const dirty =
    appearing.length > 0 || disappearing.length > 0 ||
    // 首次把猜测落成正式声明(内容没变但语义变了)也算要存
    (!data.declared && willHide.length > 0);

  const toggle = (name: string) => {
    setMsg("");
    setErr("");
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const save = () => {
    setBusy(true);
    setMsg("");
    setErr("");
    saveFolderVisibility(data.reviewId, [...hidden])
      .then((r) => {
        if (r.ok) {
          setMsg("已保存。项目列表按你的选择更新了。");
          setLocalEpoch((n) => n + 1); // 重新拉一份,reviewId 换新
          onSaved?.();
          return;
        }
        if (r.code === "stale_review") {
          setErr("工作区在你看这张卡的时候变了(比如新建了文件夹)。已重新读一遍,请再确认一次。");
          setLocalEpoch((n) => n + 1);
        } else if (r.code === "workspace_not_configured") {
          setErr("还没连上工作区。");
        } else if (r.code === "not_applicable") {
          setErr("你的项目放在子文件夹里,不会被误藏,这张卡不适用。");
        } else {
          setErr("保存失败。文件夹名可能刚被改过,请重新打开这张卡。");
        }
      })
      .catch(() => setErr("保存失败:连不上服务。"))
      .finally(() => setBusy(false));
  };

  return (
    <div className="card fvis-card" data-ui="folder-visibility">
      <button className="fvis-head" onClick={() => setExpanded((v) => !v)}>
        <span className="t">工作区文件夹</span>
        <span className="fvis-sum">
          {nowHidden.length > 0
            ? `${nowHidden.length} 个没列进项目列表`
            : "全部都列在项目列表里"}
        </span>
        <span className="fvis-caret">{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && (
        <div className="fvis-body">
          <p className="fvis-why">
            下面是工作区根目录下的所有文件夹。取消勾选的<b>不会</b>出现在左边的项目
            列表里 —— 只影响列不列出来,不改变文件夹本身的任何用途。
          </p>
          <ul className="fvis-list">
            {rows.map((f) => {
              const off = hidden.has(f.name);
              return (
                <li key={f.name} className={off ? "off" : ""}>
                  <label>
                    <input
                      type="checkbox"
                      checked={!off}
                      disabled={busy}
                      onChange={() => toggle(f.name)}
                    />
                    <span className="fvis-name">{f.name}</span>
                  </label>
                  <span className="fvis-tag" title={
                    f.reason === "guessed"
                      ? "程序按常见名字猜的,没有正式设过 —— 所以默认给你显示出来"
                      : f.reason === "declared"
                        ? "你之前设过不显示" : "正常显示中"
                  }>
                    {REASON_LABEL[f.reason]}
                    {f.missing ? " · 文件夹当前不存在" : ""}
                  </span>
                </li>
              );
            })}
          </ul>

          <p className="fvis-preview">
            保存后:<b>{willShow.length}</b> 个显示、<b>{willHide.length}</b> 个不显示。
            {appearing.length > 0 && (
              <> 会<b>重新出现</b>:{appearing.map((f) => f.name).join("、")}。</>
            )}
            {disappearing.length > 0 && (
              <> 会<b>不再显示</b>:{disappearing.map((f) => f.name).join("、")}。</>
            )}
            {!dirty && <> 跟现在一样。</>}
          </p>

          <div className="fvis-actions">
            <button className="primary" onClick={save} disabled={busy}>
              {busy ? "保存中…" : "保存"}
            </button>
            {msg && <span className="fvis-ok">{msg}</span>}
            {err && <span className="fvis-err">{err}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
