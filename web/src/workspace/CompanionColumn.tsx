import { useEffect, useRef, useState } from "react";
import type { FilesImages, FilesOverview, Project, Ref, WsRecent } from "../api";
import {
  BindProjectError,
  bindProject,
  fetchFilesImages,
  fetchFilesOverview,
  fetchRefs,
  filesImageUrl,
  openFile,
  openFolder,
  refImageUrl,
} from "../api";
import { refLabel } from "../gallery";
import {
  categoryRows,
  filesState,
  projectImages,
  relTimeFromEpoch,
} from "./cockpit";
import InboxCard from "./InboxCard";
import { openTargetFor } from "./projectName";

// 驾驶舱列(track opendesign-cockpit,原"伴随列"升级):速览 → 图片 → 类目 → 最近。
// 铁律:零模板类目名(照用户现状认);纯逻辑在 cockpit.ts(mjs oracle),组件只渲染。
// open-folder 是只读铁律的唯一受控例外(P5 design §3),失败静默降级为提示。

function fmtSize(n: number): string {
  if (n >= 1 << 20) return `${(n / (1 << 20)).toFixed(1)}M`;
  if (n >= 1 << 10) return `${Math.round(n / (1 << 10))}K`;
  return `${n}B`;
}

type Props = {
  projectKey: string | null;
  /** 速览块数据源(App 的 projects 列表选中项;未建档条目也来)。 */
  project: Project | null;
  /** M5 缺口偿还:每轮聊天回复后 bump → 重拉 refs/overview/images
      (agent 刚登记的参考图/刚接入的工作区即刻上屏,免切项目)。 */
  dataEpoch: number;
  /** 路由门:仅工作区路由可见时才拉数据,防隐藏列白扫全树。 */
  active: boolean;
  onOpenGallery: () => void;
  /** connect-ux:用户在表单里填好路径确认 → 组装完整消息发进聊天(浏览器拿
      不到真实磁盘路径,路径必须用户给;写只走 MCP=对话,405 铁律不破)。 */
  onConnectWorkspace: (path: string) => void;
  /** track opendesign-frontend-p1 §③:候选=工作区自动发现的未建档文件夹 key。
      App 传 projects.filter(p => p.unregistered).map(p => p.key)。 */
  folders: string[];
  /** 关联成功后 App bump dataEpoch,让联合列表/文件区重拉。 */
  onBound: () => void;
  /** 修改单 F(参考图空态「登记参考图」可点):预填聊天,复用现有 dispatch 通道
      (已连接直接发送;未连接降级为草稿+聚焦)。缺省时该处退化为纯文字,不可点。 */
  onPrefillRegRef?: () => void;
};

export default function CompanionColumn({
  projectKey,
  project,
  dataEpoch,
  active,
  onOpenGallery,
  onConnectWorkspace,
  folders,
  onBound,
  onPrefillRegRef,
}: Props) {
  const [tab, setTab] = useState<"ref" | "proj">("ref");
  const [refs, setRefs] = useState<Ref[] | null>(null);
  const [overview, setOverview] = useState<FilesOverview | null>(null);
  const [wsImages, setWsImages] = useState<FilesImages | null>(null);
  const [openErr, setOpenErr] = useState(false);
  // connect-ux:接入表单(点「接入工作区」展开;确认后收起,聊天里能看到消息)
  const [connectOpen, setConnectOpen] = useState(false);
  const [connectPath, setConnectPath] = useState("");
  // §③ 项目↔文件夹关联:unmapped 分支的下拉+按钮
  const [bindFolder, setBindFolder] = useState("");
  const [binding, setBinding] = useState(false);
  const [bindErr, setBindErr] = useState("");
  // 已拉取的 (key, epoch) 记账:路由切回来时数据没变就不重扫
  const fetched = useRef<string | null>(null);

  useEffect(() => {
    if (projectKey === null) {
      setRefs([]);
      setOverview(null);
      setWsImages(null);
      fetched.current = null;
      return;
    }
    if (!active) return; // 隐藏时不扫;切回时若 stamp 过期再拉
    const stamp = `${projectKey} ${dataEpoch}`;
    if (fetched.current === stamp) return;
    const keyChanged = !fetched.current?.startsWith(`${projectKey} `);
    fetched.current = stamp;
    if (keyChanged) {
      // 换项目清空转"读取中";同项目仅 epoch 变则原数据顶着,拉回后无感替换
      setRefs(null);
      setOverview(null);
      setWsImages(null);
      setTab("ref");
      setOpenErr(false);
      setBindFolder("");
      setBindErr("");
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
  }, [projectKey, dataEpoch, active]);

  const doOpen = (sub?: string) => {
    if (!projectKey) return;
    setOpenErr(false);
    openFolder(projectKey, sub).catch(() => setOpenErr(true));
  };

  /** §I4:「最近更新」行点击 —— 白名单内开该文件本身,白名单外退化为开所在文件夹
   * (纵深防御,后端仍是权威闸;不留死路,列表里每一行都可点)。 */
  const doOpenRecent = (r: WsRecent) => {
    if (!projectKey) return;
    setOpenErr(false);
    const target = openTargetFor(r);
    const p = target.kind === "file" ? openFile(projectKey, target.rel) : openFolder(projectKey, target.sub);
    p.catch(() => setOpenErr(true));
  };

  const doBind = () => {
    if (!projectKey || !bindFolder) return;
    setBindErr("");
    setBinding(true);
    bindProject(projectKey, bindFolder)
      .then(() => {
        setBindFolder("");
        onBound();
      })
      .catch((e: BindProjectError) => {
        let msg = e.message || "关联失败";
        if (e.message === "folder_ambiguous") msg = "这个文件夹名撞了,换更完整的名字再试。";
        else if (e.message === "folder_not_found") msg = "没找到这个文件夹,刷新后重试。";
        setBindErr(msg);
      })
      .finally(() => setBinding(false));
  };

  const list = refs ?? [];
  const projImgs = projectImages(wsImages); // 全部工作区图,mtime 降序,零类目名耦合
  // 3 列格(I3 伴随列 400px 后缩略图 2→3 列):>5 张时最后一格是「+N 图墙」入口;
  // ≤5 张全部直接铺(showMore 阈值随列宽从 3 提到 5)。
  const pool = tab === "ref" ? list : [];
  const showMore = (tab === "ref" ? list.length : projImgs.length) > 5;
  const thumbs = showMore ? pool.slice(0, 5) : pool;
  const projThumbs = showMore ? projImgs.slice(0, 5) : projImgs;

  const fstate = filesState(overview);
  const mapped = fstate === "ok";
  const rows = categoryRows(overview);
  const recent = mapped && overview !== null && overview.configured && overview.mapped
    ? overview.recent
    : [];

  return (
    <section className="aside">
      {/* ⓪ 收件箱(intake,工作区级,不随选中项目变;没事时隐身) */}
      <InboxCard dataEpoch={dataEpoch} active={active} />

      {/* ① 项目速览(cockpit,修改单 D2):阶段/业主/相对时间挪走或删——
          阶段挪中央列标题旁(ChangesColumn stage-chip),业主不再展示;
          「当前状态」一句话保留。 */}
      {project && project.status_note ? (
        <div className="cockpit-brief">
          <div className="note" title="档案「当前状态」字段">
            {project.status_note}
          </div>
        </div>
      ) : null}

      {/* ② 图片区 */}
      <div className="aside-head">
        <span className="t">图片</span>
        <button className="gallery-link" onClick={onOpenGallery} title="打开图墙">
          图墙 →
        </button>
        <span className="grow" />
        <div className="seg">
          <button className={`opt${tab === "ref" ? " on" : ""}`} onClick={() => setTab("ref")}>
            参考 {list.length}
          </button>
          <button
            className={`opt${tab === "proj" ? " on" : ""}`}
            onClick={() => setTab("proj")}
          >
            项目图 {projImgs.length || ""}
          </button>
        </div>
      </div>
      {tab === "proj" ? (
        projImgs.length === 0 ? (
          <div className="aside-empty">
            {mapped
              ? "项目文件夹里还没有图片。"
              : "关联项目文件夹后,项目里的图会出现在这里。"}
            {mapped && (
              <div>
                <button
                  className="btn-secondary sm"
                  data-ui="empty-open-folder"
                  onClick={() => doOpen()}
                >
                  打开文件夹
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="thumb-grid">
            {projThumbs.map((i) => (
              <button className="thumb" key={i.rel} title={i.rel} onClick={onOpenGallery}>
                <img
                  src={filesImageUrl(projectKey!, i.rel)}
                  alt={i.rel}
                  loading="lazy"
                />
                <span className="tag">{i.category || "未分类"}</span>
              </button>
            ))}
            {showMore && (
              <button className="thumb more" title="图墙" onClick={onOpenGallery}>
                <span className="m">+{projImgs.length - 5} 图墙 →</span>
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
          在对话里发图并说「
          {onPrefillRegRef ? (
            <button className="link-act inline" data-ui="empty-reg-ref" onClick={onPrefillRegRef}>
              登记参考图
            </button>
          ) : (
            "登记参考图"
          )}
          」,会出现在这里。
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
              <span className="m">+{list.length - 5} 图墙 →</span>
            </button>
          )}
        </div>
      )}

      {/* ③④ 文件区(P5 真数据 → cockpit 类目行+活跃度) */}
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
      {fstate === "loading" ? (
        <div className="aside-empty">读取中…</div>
      ) : fstate === "unconfigured" ? (
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
      ) : fstate === "unmapped" ? (
        <div className="file-list">
          <div className="aside-empty" style={{ margin: "4px 8px 0" }}>
            此项目还没关联文件夹。
          </div>
          {folders.length > 0 ? (
            <div className="bind-form">
              <div className="acts">
                <select
                  className="bind-select"
                  value={bindFolder}
                  onChange={(e) => setBindFolder(e.target.value)}
                >
                  <option value="">选择文件夹…</option>
                  {folders.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
                <button
                  className="chat-btn primary"
                  disabled={!bindFolder || binding}
                  onClick={doBind}
                >
                  {binding ? "关联中…" : "关联"}
                </button>
              </div>
              {bindErr && <div className="aside-empty warn">{bindErr}</div>}
            </div>
          ) : (
            <div className="aside-empty" style={{ margin: "4px 8px 0" }}>
              在右侧对话里说「XX 文件夹就是这个项目」即可关联(列表里未建档的
              那行名字照着说)。
            </div>
          )}
        </div>
      ) : (
        <div className="file-list">
          {rows.map((r) => (
            <button
              className="cat-row"
              key={r.name || "(未分类)"}
              title={r.name ? "在资源管理器打开此类目" : "项目根目录散文件"}
              onClick={() => doOpen(r.name || undefined)}
            >
              <span className="n">{r.label}</span>
              <span className="grow" />
              {r.activity && <span className="act">{r.activity}</span>}
              <span className="c">{r.countLabel}</span>
            </button>
          ))}
          {recent.length > 0 && (
            <>
              <div className="file-sub">最近更新</div>
              {recent.map((r) => (
                <button
                  className="recent-row"
                  data-ui="recent-row"
                  key={`${r.rel}/${r.mtime}`}
                  title={r.rel || (r.category ? `${r.category}/${r.name}` : r.name)}
                  onClick={() => doOpenRecent(r)}
                >
                  <span className="n">{r.name}</span>
                  <span className="grow" />
                  <span className="m">
                    {fmtSize(r.size)} · {relTimeFromEpoch(r.mtime)}
                  </span>
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </section>
  );
}
