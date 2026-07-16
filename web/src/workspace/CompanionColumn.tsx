import { useEffect, useState } from "react";
import type { FilesImages, FilesOverview, Ref } from "../api";
import {
  fetchFilesImages,
  fetchFilesOverview,
  fetchRefs,
  filesImageUrl,
  openFolder,
  refImageUrl,
  relTime,
} from "../api";
import { refLabel } from "../gallery";

// 伴随列(handoff §3,290px):图片区(参考=refs 索引 / 效果=工作区 06-效果图)
// + 文件区(P5 真数据:类目计数+最近文件+打开文件夹;未配置/未映射诚实空态)。
// open-folder 是只读铁律的唯一受控例外(P5 design §3),失败静默降级为提示。

type Props = {
  projectKey: string | null;
  onOpenGallery: () => void;
  /** connect-ux:用户在表单里填好路径确认 → 组装完整消息发进聊天(浏览器拿
      不到真实磁盘路径,路径必须用户给;写只走 MCP=对话,405 铁律不破)。 */
  onConnectWorkspace: (path: string) => void;
};

function fmtSize(n: number): string {
  if (n >= 1 << 20) return `${(n / (1 << 20)).toFixed(1)}M`;
  if (n >= 1 << 10) return `${Math.round(n / (1 << 10))}K`;
  return `${n}B`;
}

export default function CompanionColumn({
  projectKey,
  onOpenGallery,
  onConnectWorkspace,
}: Props) {
  const [tab, setTab] = useState<"ref" | "render">("ref");
  const [refs, setRefs] = useState<Ref[] | null>(null);
  const [overview, setOverview] = useState<FilesOverview | null>(null);
  const [wsImages, setWsImages] = useState<FilesImages | null>(null);
  const [openErr, setOpenErr] = useState(false);
  // connect-ux:接入表单(点「接入工作区」展开;确认后收起,聊天里能看到消息)
  const [connectOpen, setConnectOpen] = useState(false);
  const [connectPath, setConnectPath] = useState("");

  useEffect(() => {
    setRefs(null);
    setOverview(null);
    setWsImages(null);
    setTab("ref");
    setOpenErr(false);
    if (!projectKey) {
      setRefs([]);
      return;
    }
    let stale = false;
    fetchRefs(projectKey)
      .then((rs) => !stale && setRefs(rs))
      .catch(() => !stale && setRefs([]));
    fetchFilesOverview(projectKey)
      .then((o) => !stale && setOverview(o))
      .catch(() => !stale && setOverview({ configured: false }));
    fetchFilesImages(projectKey)
      .then((im) => !stale && setWsImages(im))
      .catch(() => !stale && setWsImages({ configured: false }));
    return () => {
      stale = true;
    };
  }, [projectKey]);

  const doOpen = (sub?: string) => {
    if (!projectKey) return;
    setOpenErr(false);
    openFolder(projectKey, sub).catch(() => setOpenErr(true));
  };

  const list = refs ?? [];
  const renders =
    wsImages && wsImages.configured && wsImages.mapped
      ? wsImages.images.filter((i) => i.category.includes("效果图"))
      : [];
  // 2×2 格:>3 张时第 4 格是「+N 图墙」入口;≤3 张全部直接铺
  const pool = tab === "ref" ? list : [];
  const showMore = (tab === "ref" ? list.length : renders.length) > 3;
  const thumbs = showMore ? pool.slice(0, 3) : pool;
  const renderThumbs = showMore ? renders.slice(0, 3) : renders;

  const mapped = overview !== null && overview.configured && overview.mapped;

  return (
    <section className="aside">
      {/* 图片区 */}
      <div className="aside-head">
        <span className="t">图片</span>
        <span className="grow" />
        <div className="seg">
          <button className={`opt${tab === "ref" ? " on" : ""}`} onClick={() => setTab("ref")}>
            参考 {list.length}
          </button>
          <button
            className={`opt${tab === "render" ? " on" : ""}`}
            onClick={() => setTab("render")}
          >
            效果 {renders.length || ""}
          </button>
        </div>
      </div>
      {tab === "render" ? (
        renders.length === 0 ? (
          <div className="aside-empty">
            {mapped
              ? "项目文件夹里还没有效果图(06-效果图)。"
              : "关联项目文件夹后,效果图会出现在这里。"}
          </div>
        ) : (
          <div className="thumb-grid">
            {renderThumbs.map((i) => (
              <button className="thumb" key={i.rel} title={i.rel} onClick={onOpenGallery}>
                <img
                  src={filesImageUrl(projectKey!, i.rel)}
                  alt={i.rel}
                  loading="lazy"
                />
                <span className="tag">{i.rel.split("/").pop()}</span>
              </button>
            ))}
            {showMore && (
              <button className="thumb more" title="图墙" onClick={onOpenGallery}>
                <span className="m">+{renders.length - 3} 图墙 →</span>
              </button>
            )}
          </div>
        )
      ) : refs === null ? (
        <div className="aside-empty">读取中…</div>
      ) : list.length === 0 ? (
        <div className="aside-empty">
          还没有参考图。
          <br />
          在对话里发图并说「登记参考图」,会出现在这里。
        </div>
      ) : (
        <div className="thumb-grid">
          {thumbs.map((r) => (
            <button
              className="thumb"
              key={r.id}
              title={`${r.id} ${refLabel(r)}`}
              onClick={onOpenGallery}
            >
              <img src={refImageUrl(r.file)} alt={refLabel(r)} loading="lazy" />
              <span className="tag">{refLabel(r)}</span>
            </button>
          ))}
          {showMore && (
            <button className="thumb more" title="图墙" onClick={onOpenGallery}>
              <span className="m">+{list.length - 3} 图墙 →</span>
            </button>
          )}
        </div>
      )}

      {/* 文件区(P5 真数据) */}
      <div className="aside-head files">
        <span className="t">项目文件</span>
        <span className="grow" />
        {mapped && (
          <button
            className="open-folder"
            title="在资源管理器打开项目文件夹"
            onClick={() => doOpen()}
          >
            打开文件夹
          </button>
        )}
      </div>
      {openErr && <div className="aside-empty warn">打开失败:确认服务与文件夹都在。</div>}
      {overview === null ? (
        <div className="aside-empty">读取中…</div>
      ) : !overview.configured ? (
        <div className="file-list">
          <div className="aside-empty" style={{ margin: "4px 8px 0" }}>
            还没接入你电脑上的项目文件夹。
          </div>
          {!connectOpen ? (
            <button
              className="connect-workspace"
              onClick={() => setConnectOpen(true)}
              title="告诉 OpenDesign 你的项目文件夹在哪"
            >
              接入工作区
            </button>
          ) : (
            <form
              className="connect-form"
              onSubmit={(e) => {
                e.preventDefault();
                const p = connectPath.trim();
                if (!p) return;
                onConnectWorkspace(p);
                setConnectOpen(false);
                setConnectPath("");
              }}
            >
              <div className="hint">
                工作台在浏览器里看不到你的磁盘,把项目文件夹路径贴给助手:
              </div>
              <input
                autoFocus
                value={connectPath}
                placeholder="例如 D:\设计工作区"
                onChange={(e) => setConnectPath(e.target.value)}
              />
              <div className="acts">
                <button
                  type="submit"
                  className="chat-btn primary"
                  disabled={!connectPath.trim()}
                >
                  发给助手
                </button>
                <button
                  type="button"
                  className="chat-btn"
                  onClick={() => setConnectOpen(false)}
                >
                  取消
                </button>
              </div>
            </form>
          )}
        </div>
      ) : !overview.mapped ? (
        <div className="file-list">
          <div className="aside-empty" style={{ margin: "4px 8px 0" }}>
            此项目还没关联文件夹。
            <br />
            在 config/workspace.json 的 projects 里加一行映射即可。
          </div>
        </div>
      ) : (
        <div className="file-list">
          {overview.categories.map((c) => (
            <button
              className="cat-row"
              key={c.name || "(未分类)"}
              title={c.name ? "在资源管理器打开此类目" : "项目根目录散文件"}
              onClick={() => doOpen(c.name || undefined)}
            >
              <span className="n">{c.name || "未分类"}</span>
              <span className="grow" />
              <span className="c">{c.capped ? `${c.count}+` : c.count}</span>
            </button>
          ))}
          {overview.recent.length > 0 && (
            <>
              <div className="file-sub">最近更新</div>
              {overview.recent.map((r) => (
                <div className="recent-row" key={`${r.category}/${r.name}/${r.mtime}`}>
                  <span className="n" title={`${r.category}/${r.name}`}>
                    {r.name}
                  </span>
                  <span className="grow" />
                  <span className="m">
                    {fmtSize(r.size)} · {relTime(new Date(r.mtime * 1000).toISOString())}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </section>
  );
}
