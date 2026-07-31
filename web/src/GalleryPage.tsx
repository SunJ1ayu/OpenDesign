import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Project, Ref, RefsVocab } from "./api";
import { fetchFilesImages, fetchRefsData, fileToDataUrl, openFolder, updateRef,
         uploadErrMsg, uploadToInbox } from "./api";
import {
  buildGallery,
  sameTags,
  filterGallery,
  galleryFacets,
  groupAlbums,
  REF_GROUP,
  type GalleryFilter,
  type GalleryItem,
  type WsImage,
} from "./gallery";

// 图墙(P5 T5,一等面):refs 索引(空间/风格标签)∪ 工作区项目图片。
// 两层:相册墙(每个集合文件夹一张封面)→ 点开看该册全部图 → 点图 lightbox。
// 合并/facets/筛选/分册逻辑全在 gallery.ts(mjs oracle);此处纯展示。

/** onBack:回到这个项目的工作区。图墙是从伴随列「打开图墙」进来的一层,
 *  自己不提供出口就是"进得去出不来"(真机反馈 2026-07-27 #3)。
 *  ⚠️ 2026-07-31 起题头只有**一个**「返回」键,语义是**回上一级**:
 *  册内 → 封面墙,封面墙 → 调用 onBack 回工作区。原来那个页内的
 *  `.g-back`(「← 返回相册 · X」)已删。用户原话:「一个返回就好了,按一下默认返回
 *  上一级,如果用户想返回的是项目工作区,直接点左边栏的目录就可以了」。 */
type Props = { project: Project | null; onBack: () => void };

const EMPTY: GalleryFilter = { group: null, space: null, style: null };

function Chips({
  label,
  values,
  active,
  onPick,
}: {
  label: string;
  values: string[];
  active: string | null;
  onPick: (v: string | null) => void;
}) {
  if (values.length === 0) return null;
  return (
    <div className="g-chiprow">
      <span className="g-dim">{label}</span>
      {values.map((v) => (
        <button
          key={v}
          className={`g-chip${active === v ? " on" : ""}`}
          onClick={() => onPick(active === v ? null : v)}
        >
          {v}
        </button>
      ))}
    </div>
  );
}

const EMPTY_VOCAB: RefsVocab = { style: [], space: [] };

export default function GalleryPage({ project, onBack }: Props) {
  const [refs, setRefs] = useState<Ref[] | null>(null);
  const [images, setImages] = useState<WsImage[] | null>(null);
  // 参考图词表(#8):单一真相源经 /api/projects/<key>/refs 的 vocab 下发,
  // lightbox 编辑区的风格 chip 直接列它,不硬编码副本。
  const [vocab, setVocab] = useState<RefsVocab>(EMPTY_VOCAB);
  const [filter, setFilter] = useState<GalleryFilter>(EMPTY);
  const [openAlbum, setOpenAlbum] = useState<string | null>(null);
  const [zoom, setZoom] = useState<GalleryItem | null>(null);
  // 标签/备注编辑区状态(#8):zoom 切到别的图时重新以当前值预填。
  const [editStyles, setEditStyles] = useState<Set<string>>(new Set());
  const [editSpaces, setEditSpaces] = useState<Set<string>>(new Set());
  const [editNote, setEditNote] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [editSaved, setEditSaved] = useState<string | null>(null); // 保存成功/无改动的轻提示

  const key = project?.key ?? null;
  const pageRef = useRef<HTMLDivElement>(null); // 滚动容器(.page 自带 overflow-y)
  const wallScroll = useRef(0); // 进子相册前记下的墙面滚动位置(#10b)

  // ── 拖拽上传(track opendesign-image-upload)────────────────────────────────
  // 落点是**收件箱**,不是当前项目的图墙 —— 直接写项目夹会新开一条"网页可任意写
  // 工作区"的路,与「暂存 + 人工确认才动文件」这条底线相抵。上传完提示去点
  // 伴随列的「扫描整理」(网页那条针孔自带 allowed_roots,不依赖任何环境变量)。
  // 缩放(真机反馈 2026-07-27):放大看封面 = 一行少几个,缩小 = 回到密排。
  // 用**列数**而不是像素:用户说的就是"一行 3 个 / 一行 7 个"。记住选择,下次还是它。
  // 默认 4:缩放之前是 `auto-fill minmax(200px,1fr)`,1280 视口下正好一行 4 个。
  // 0.51.0 加旋钮时默认取了 COLS_MAX=7(最密),等于顺手把所有人的默认观感改了
  // ——**加"可调+记住选择"的旋钮时,默认值就是一次行为变更**,不能随手取端点值。
  // 已经存过偏好的照旧听用户的(下面 localStorage 优先),改默认只影响没调过的人。
  const COLS_MIN = 3, COLS_MAX = 7, COLS_DEFAULT = 4;
  const [cols, setCols] = useState<number>(() => {
    const raw = Number(localStorage.getItem("ds.gallery.cols"));
    return raw >= COLS_MIN && raw <= COLS_MAX ? raw : COLS_DEFAULT;
  });
  const setColsPersist = (n: number) => {
    const v = Math.min(COLS_MAX, Math.max(COLS_MIN, n));
    setCols(v);
    try { localStorage.setItem("ds.gallery.cols", String(v)); } catch { /* 隐私模式 */ }
  };

  const [dragOver, setDragOver] = useState(false);
  const [upMsg, setUpMsg] = useState<string | null>(null);
  const [upBusy, setUpBusy] = useState(false);

  async function uploadFiles(files: File[]) {
    // 按**扩展名**过滤,不只看 mime:svg 的 mime 也是 image/svg+xml,只看 mime 会把它
    // 放到服务端才拒(四审 subkimi F4:那时提示语给的还是错药方)。
    const OK_EXT = /\.(png|jpe?g|webp|gif)$/i;
    const imgs = files.filter((f) => OK_EXT.test(f.name));
    if (!imgs.length) {
      setUpMsg("只收图片(png/jpg/webp/gif)。");
      return;
    }
    setUpBusy(true);
    const stored: string[] = [];
    let dir = "";
    try {
      for (const f of imgs) {
        const r = await uploadToInbox(f.name, await fileToDataUrl(f));
        stored.push(r.name);       // 后端回显真实落盘名(可能截短/换名)
        // 落盘目录(绝对路径):0.48.0 只说"已存进收件箱",用户当场问"在我电脑哪个
        // 文件夹" —— 一个本地工具让人搞不清文件去哪了,是提示不合格。
        if (!dir && r.path) dir = r.path.slice(0, r.path.length - r.name.length);
      }
      // 逐字回显落盘名:名字被改过时用户当场看得见,而不是三天后发现文件"没了"
      setUpMsg(`已存进收件箱${dir ? `(${dir})` : ""}:${stored.join("、")}`
        + " —— 去伴随列点「扫描整理」归档");
    } catch (e) {
      const done = stored.length ? `已存 ${stored.length} 张;` : "";
      setUpMsg(done + uploadErrMsg((e as Error).message));
    } finally {
      setUpBusy(false);
    }
  }

  const reloadRefs = () => {
    if (!key) return Promise.resolve();
    return fetchRefsData(key).then(({ refs: rs, vocab: v }) => {
      setRefs(rs);
      setVocab(v);
    });
  };

  useEffect(() => {
    setRefs(null);
    setImages(null);
    setVocab(EMPTY_VOCAB);
    setFilter(EMPTY);
    wallScroll.current = 0; // 换项目=另一堵墙,别拿上一个项目的位置复位(#10b 的边界:
    // 开着子相册切项目时 openAlbum→null 会触发复位,而 setFilter(EMPTY) 在本来就没
    // 筛选时被 React bail-out 吃掉,清零那条路走不到)
    setOpenAlbum(null);
    setZoom(null);
    if (!key) return;
    let stale = false;
    fetchRefsData(key)
      .then(({ refs: rs, vocab: v }) => {
        if (stale) return;
        setRefs(rs);
        setVocab(v);
      })
      .catch(() => !stale && setRefs([]));
    fetchFilesImages(key)
      .then((d) => !stale && setImages(d.configured && d.mapped ? d.images : []))
      .catch(() => !stale && setImages([]));
    return () => {
      stale = true;
    };
  }, [key]);

  // 切到另一张图(或关闭):编辑区重新以当前值预填,不沿用上一张的草稿。
  useEffect(() => {
    setEditStyles(new Set(zoom?.style ?? []));
    setEditSpaces(new Set(zoom?.space ?? []));
    setEditNote(zoom?.note ?? "");
    setEditErr(null);
    setEditSaved(null);
  }, [zoom?.id]);

  async function saveRefEdit() {
    if (!zoom?.refId || editSaving) return;
    if (editStyles.size === 0 || editSpaces.size === 0) {
      setEditErr("风格和空间都至少要留一个标签。");
      return;
    }
    if (sameTags(editStyles, zoom.style) && sameTags(editSpaces, zoom.space)
        && editNote === (zoom.note ?? "")) {
      setEditErr(null);
      setEditSaved("没有改动");  // 一个字段都没改就别发请求(核心会判 no_fields)
      return;
    }
    setEditSaving(true);
    setEditErr(null);
    setEditSaved(null);
    try {
      // **只发真改过的字段**(核心的「缺省=不动」语义):老索引里可能有不在词表里的
      // 手写标签(词表可扩也可删),原样发回会被核心判 style_unknown,连备注都改不了
      // ——那条错误还提示"刷新重试",刷新根本没用(2026-07-21 收货闸③实抓)。
      const styleChanged = !sameTags(editStyles, zoom.style);
      const spaceChanged = !sameTags(editSpaces, zoom.space);
      await updateRef({
        ref_id: zoom.refId,
        ...(styleChanged ? { style: [...editStyles].join(",") } : {}),
        ...(spaceChanged ? { space: [...editSpaces].join(",") } : {}),
        ...(editNote !== (zoom.note ?? "") ? { note: editNote } : {}),
      });
      // 写已经成功了:重拉失败只影响"看到的是不是最新",不能报成"保存失败"
      // (subglm 提的:两者原本同一个 try,一起被当成保存失败)
      setEditSaved("已保存");   // 成功要有反馈(同快记卡 toast 范式),否则人不知道存没存上
      try {
        await reloadRefs(); // 保存后必须重拉,否则下一次筛选用的是旧标签
      } catch {
        setEditSaved("已保存(列表没刷新上,重开图墙看最新)");
      }
    } catch (e) {
      const code = (e as Error).message;
      setEditErr(
        code === "style_unknown" || code === "space_unknown"
          // 刷新解决不了:这条标签本来就不在词表里(词表被改过 / 索引是手写的),
          // 要么改选词表里的词,要么先让助手 add_style 把词加进去(subdeepseek 提的)
          ? "这个标签不在词表里。换一个,或先让助手把它加进风格词表。"
          : `保存失败(${code})。`,
      );
    } finally {
      setEditSaving(false);
    }
  }

  function toggleEditTag(set: Set<string>, setSet: (s: Set<string>) => void, v: string) {
    setEditSaved(null);
    const next = new Set(set);
    if (next.has(v)) next.delete(v);
    else next.add(v);
    setSet(next);
  }

  // 改筛选回到相册墙(避免停在一个筛掉后不存在的册)。
  // 顺带把记着的墙面滚动位置清零:筛完是另一批内容,拿旧位置复位等于随机落点。
  useEffect(() => {
    wallScroll.current = 0;
    setOpenAlbum(null);
  }, [filter]);

  // 真机反馈 2026-07-24 #10b:点进子相册再返回,直接弹回最顶端,翻到一半的位置全丢。
  // 进册前记下墙面滚动位置,回来时复位。用 useLayoutEffect 而非 useEffect:
  // 必须在浏览器绘制前落位,否则会看见"先闪到顶再跳回来"。
  const openAlbumAt = (key: string) => {
    wallScroll.current = pageRef.current?.scrollTop ?? 0;
    setOpenAlbum(key);
  };
  useLayoutEffect(() => {
    const el = pageRef.current;
    if (!el) return;
    if (openAlbum !== null) {
      el.scrollTop = 0; // 进册:从册子顶端开始看
      return;
    }
    // 回墙面:回到刚才那一格所在的位置。写 scrollTop 会强制同步重算布局,
    // 所以这里直接落位就够,不需要 rAF 重试(实测 240 → 240 一次到位)。
    el.scrollTop = wallScroll.current;
  }, [openAlbum]);

  const items = useMemo(
    () => (key ? buildGallery(key, refs ?? [], images ?? []) : []),
    [key, refs, images],
  );
  const facets = useMemo(() => galleryFacets(items), [items]);
  const shown = useMemo(() => filterGallery(items, filter), [items, filter]);
  const albums = useMemo(() => groupAlbums(shown), [shown]);
  const current = openAlbum ? albums.find((a) => a.key === openAlbum) ?? null : null;

  // esc:先关 lightbox,否则退出当前相册。←/→(修改单 H):lightbox 打开时在
  // 当前列表(册内 current.items,或顶层墙面平铺——每张封面代表一格)切换。
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (zoom) setZoom(null);
        else if (openAlbum) setOpenAlbum(null);
        return;
      }
      if (!zoom || (e.key !== "ArrowRight" && e.key !== "ArrowLeft")) return;
      const list = current ? current.items : albums.map((a) => a.cover);
      if (list.length === 0) return;
      const idx = list.findIndex((it) => it.id === zoom.id);
      if (idx === -1) return;
      const next =
        e.key === "ArrowRight" ? (idx + 1) % list.length : (idx - 1 + list.length) % list.length;
      setZoom(list[next]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoom, openAlbum, current, albums]);
  const loading = key !== null && (refs === null || images === null);

  if (!project) {
    return (
      <div className="page gallery-page">
        {/* 没选中项目这一支同样要有出口 —— 空页面比有内容的页面更容易把人困住。
            ⚠️ 0.64/0.65 两轮只改了主分支、漏了这一支,于是这里一度留着旧文案 +
            已被删掉的样式类(= 无样式裸按钮)。判据 gallery_head_buttons G 段现在
            专门起一个空档案库的 ds_web 把这一支逼出来判。 */}
        <button className="btn-secondary" data-ui="gallery-back-ws" onClick={onBack}
                title="回到项目工作区">
          返回
        </button>
        <p className="muted">先在侧栏选一个项目,图墙按项目展示。</p>
      </div>
    );
  }

  return (
    <div
      className={`page gallery-page${dragOver ? " drag-over" : ""}`}
      // 「当前在不在某个相册里」的对外信号(册内=相册 key,封面墙=空)。
      // 合并成一个返回键之后,判据不能再靠 `.g-back` 这个元素在不在来判断层级。
      data-album={current ? current.key : ""}
      ref={pageRef}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();                 // 不 preventDefault 浏览器会直接打开图片
        setDragOver(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget.contains(e.relatedTarget as Node)) return; // 子元素间移动不算离开
        setDragOver(false);
      }}
      onDrop={(e) => {
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        setDragOver(false);
        void uploadFiles(Array.from(e.dataTransfer.files));
      }}
      data-ui="gallery-drop"
    >
      {(dragOver || upBusy || upMsg) && (
        <div className="upload-note" data-ui="upload-note">
          {dragOver ? "松手就存进收件箱" : upBusy ? "上传中…" : upMsg}
          {!dragOver && !upBusy && upMsg && (
            <button className="link-act inline" onClick={() => setUpMsg(null)}>知道了</button>
          )}
        </div>
      )}
      <header className="page-head">
        <h2 className="serif">图墙 · {project.name}</h2>
        <span className="g-dim">
          {loading
            ? "读取中…"
            : current
              ? `${current.label} · ${current.count} 张`
              : `${albums.length} 组 · ${shown.length} 张`}
        </span>
        <span className="grow" />
        <div className="g-zoom" data-ui="gallery-zoom" title="放大/缩小封面">
          <button className="icon-btn" onClick={() => setColsPersist(cols + 1)}
                  disabled={cols >= COLS_MAX} aria-label="缩小(一行放更多)">−</button>
          <span className="g-zoom-n">一行 {cols}</span>
          <button className="icon-btn" onClick={() => setColsPersist(cols - 1)}
                  disabled={cols <= COLS_MIN} aria-label="放大(一行放更少)">+</button>
        </div>
        {facets.groups.length > 0 && (
          <div className="gallery-source">
            <select
              className="gallery-source-select"
              data-ui="gallery-source"
              value={filter.group ?? ""}
              onChange={(e) =>
                setFilter((f) => ({ ...f, group: e.target.value || null }))
              }
            >
              <option value="">全部来源</option>
              {facets.groups.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
            {filter.group !== null && (
              <button
                className="gallery-source-clear"
                title="清除来源筛选"
                onClick={() => setFilter((f) => ({ ...f, group: null }))}
              >
                ×
              </button>
            )}
          </div>
        )}
        {/* 题头最右边是一组「离开这一页」的动作(真机反馈 2026-07-31):
            打开文件夹 = 去资源管理器,← 项目工作区 = 回工作区。两者同款 .btn-secondary
            —— 共享次按钮,不各自造一份(`.open-folder` 原本就是 .btn-secondary 的
            一次性复制品,仅 26px vs 28px 之差,本次收编掉)。
            ⚠️ 「← 项目工作区」曾是文字链接款(`86cf466`),理由是要和册内的
            `.g-back`(← 返回相册)区分开 —— 那个控件 07-31 已被合并掉,
            而文字链接混在按钮排里读起来是"次要"—— 对整页唯一的出口是错的信号。
            两级返回不混淆由 gallery_head_buttons 的 E 段 + ws_collapse_back #3b 继续锁。 */}
        <button
          className="btn-secondary"
          data-ui="gallery-open-folder"
          title="在资源管理器打开项目文件夹"
          onClick={() => openFolder(project.key).catch(() => {})}
        >
          打开文件夹
        </button>
        {/* 文字就是「返回」,**不带箭头**(用户 07-31:「不需要箭头,太傻了」)。
            **一个键、回上一级**:册内 → 封面墙;封面墙 → 项目工作区。
            去哪由 title 说明(会跟着层级变),不靠符号暗示。
            与 Esc 的行为对齐(Esc 本来就是"先关大图,否则退出当前相册")。 */}
        <button
          className="btn-secondary"
          data-ui="gallery-back-ws"
          onClick={() => (current ? setOpenAlbum(null) : onBack())}
          title={current ? "回到封面墙" : "回到这个项目的工作区"}
        >
          返回
        </button>
      </header>

      <Chips
        label="空间"
        values={facets.spaces}
        active={filter.space}
        onPick={(v) => setFilter((f) => ({ ...f, space: v }))}
      />
      <Chips
        label="风格"
        values={facets.styles}
        active={filter.style}
        onPick={(v) => setFilter((f) => ({ ...f, style: v }))}
      />

      {!loading && items.length === 0 ? (
        <div className="aside-empty" style={{ marginTop: 18 }}>
          还没有图片。参考图在对话里发图登记;项目文件夹里的图片会自动出现在这里。
        </div>
      ) : !loading && shown.length === 0 ? (
        <div className="aside-empty" style={{ marginTop: 18 }}>
          这个筛选组合下没有图(工作区图片没有空间/风格标签)。
        </div>
      ) : current ? (
        <div className="g-wall" style={{ ["--wall-cols" as string]: cols }}>
          {current.items.map((it) => (
            <button className="g-cell" key={it.id} title={it.label} onClick={() => setZoom(it)}>
              <img src={it.url} alt={it.label} loading="lazy" />
              <span className="g-cap">
                <span className="l">{it.label}</span>
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className="g-wall" style={{ ["--wall-cols" as string]: cols }}>
          {albums.map((a) => (
            <button
              className="g-cell"
              key={`alb:${a.key}`}
              title={a.label}
              onClick={() => (a.count > 1 ? openAlbumAt(a.key) : setZoom(a.cover))}
            >
              <img src={a.cover.url} alt={a.label} loading="lazy" />
              {a.count > 1 && <span className="g-badge">{a.count}</span>}
              <span className="g-cap">
                <span className="l">{a.label}</span>
                <span className="g">{a.group === REF_GROUP ? "参考" : a.group}</span>
              </span>
            </button>
          ))}
        </div>
      )}

      {zoom && (
        <div className="g-light" onClick={() => setZoom(null)}>
          <img src={zoom.url} alt={zoom.label} />
          <div className="g-light-cap">
            {zoom.label}
            <span className="g-dim"> · {zoom.group}</span>
          </div>
          {/* #8:refs 来源的图给标签/备注编辑区;ws 图(不在索引里)零渲染,
              不是 bug——它压根没有 refId(design.md §8)。stopPropagation:
              lightbox 背景点任意处关闭,编辑区内的点击不该穿透触发关闭。 */}
          {zoom.refId !== undefined && (
            <div className="ref-edit" data-ui="ref-edit" onClick={(e) => e.stopPropagation()}>
              <div className="ref-edit-row">
                <span className="ref-edit-label">风格</span>
                <div className="ref-edit-chips">
                  {vocab.style.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`g-chip${editStyles.has(s) ? " on" : ""}`}
                      data-ui="ref-style-option"
                      disabled={editSaving}
                      onClick={() => toggleEditTag(editStyles, setEditStyles, s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="ref-edit-row">
                <span className="ref-edit-label">空间</span>
                <div className="ref-edit-chips">
                  {vocab.space.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`g-chip${editSpaces.has(s) ? " on" : ""}`}
                      data-ui="ref-space-option"
                      disabled={editSaving}
                      onClick={() => toggleEditTag(editSpaces, setEditSpaces, s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="ref-edit-row">
                <span className="ref-edit-label">备注</span>
                <input
                  className="ref-edit-note"
                  data-ui="ref-note-input"
                  value={editNote}
                  onChange={(e) => { setEditSaved(null); setEditNote(e.target.value); }}
                  disabled={editSaving}
                  placeholder="备注(可留空)"
                />
              </div>
              {editErr && <div className="error-note sm">{editErr}</div>}
              {!editErr && editSaved && (
                <div className="ref-edit-saved" data-ui="ref-edit-saved">{editSaved}</div>
              )}
              <div className="ref-edit-actions">
                <button
                  type="button"
                  className="btn-primary"
                  data-ui="ref-save"
                  disabled={editSaving}
                  onClick={saveRefEdit}
                >
                  {editSaving ? "保存中…" : "保存"}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={editSaving}
                  onClick={() => setZoom(null)}
                >
                  关闭
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
