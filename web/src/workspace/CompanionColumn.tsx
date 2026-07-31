import { useEffect, useRef, useState } from "react";
import type { FilesImages, FilesOverview, Ref, WsRecent } from "../api";
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
  // 这里曾有 `project: Project | null`,唯一用途是速览块显示「当前状态」。
  // 速览块 2026-07-28 删掉后它就没有读者了 —— tsc 的 TS6133 当场点名,顺手拆干净,
  // 不留一个「传进来但没人看」的 prop(那正是下一次误以为这里能拿到项目对象的起点)。
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
      {/* ⓪ 收件箱已搬去右列顶部(-p2,用户提的):它是**工作区级**的东西,
          本来就不该混在"这个项目的图片/文件"中间;搬走后本列 = 纯这个项目。 */}
      {/* ① 项目速览块(cockpit)**已整条删除**(2026-07-28,用户拍板)。
          它最后只剩「当前状态」一句话,而那个字段**没有任何写口** —— 建档时由
          `_PROJECT_TEMPLATE` 填一次「新建,待完善」,17 个 MCP 工具没一个改得动它,
          于是这行小字永远显示模板默认值,占着项目工作区最显眼的位置当摆设。
          根因不是"忘了做修改功能":**读侧挑显示对象时没人问过"这个字段谁来维护"**,
          而模板的默认值把"没人维护"伪装成了"有内容"(留空的话这里的守卫本会隐身)。
          要复活它就得先有写口(set_status 工具),不是把展示加回来。 */}

      {/* ② 图片区 */}
      <div className="aside-head">
        <span className="t">图片</span>
        {/* 这里原先有一条「图墙 →」小字。**2026-07-28 用户拍板删掉**:
            「点图片就进去了,这个没必要吧」—— 缩略图和「+N 图墙 →」溢出砖本来就都
            通向图墙,标题旁再挂一条是同一件事说三遍。
            ⚠️ 这推翻了 cockpit.e2e.mjs 里原先那条产品要求「图墙常驻入口(图少也可达)」。
            入口没堵死:缩略图仍是入口(新判据 inbox_pad_gallery.e2e.mjs 钉了)。
            已知代价、用户已知情:一张图都没有时进不去图墙 —— 那时图墙本来也是空的。 */}
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
                  className="btn-secondary"
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
        {/* 全应用「打开文件夹」统一成同一个次按钮(真机反馈 2026-07-31:
            「都用一样的白框然后里面字」)。原来这里是一次性的 `.open-folder`
            (与 .btn-secondary 只差 26px vs 28px),同一个动作却有三种写法。
            判据 gallery_head_buttons H 段量的是 computed 外观全等,不是 class 名。 */}
        {mapped && (
          <button
            className="btn-secondary"
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
