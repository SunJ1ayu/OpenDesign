import { useEffect, useMemo, useState } from "react";
import type { Project, Ref } from "./api";
import { fetchFilesImages, fetchRefs, openFolder } from "./api";
import {
  albumKeyOf,
  buildGallery,
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

type Props = { project: Project | null };

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

export default function GalleryPage({ project }: Props) {
  const [refs, setRefs] = useState<Ref[] | null>(null);
  const [images, setImages] = useState<WsImage[] | null>(null);
  const [filter, setFilter] = useState<GalleryFilter>(EMPTY);
  // §I1「来源」下拉:按集合文件夹(album key,比 filter.group 的顶层类目更细一级)
  // 筛选——独立于 filter.group/space/style(那三维交给 filterGallery,群众口径
  // 不变,回归 test_gallery.mjs 锁死);来源筛选在 filterGallery 之前先收窄。
  const [sourceKey, setSourceKey] = useState<string | null>(null);
  const [openAlbum, setOpenAlbum] = useState<string | null>(null);
  const [zoom, setZoom] = useState<GalleryItem | null>(null);

  const key = project?.key ?? null;

  useEffect(() => {
    setRefs(null);
    setImages(null);
    setFilter(EMPTY);
    setSourceKey(null);
    setOpenAlbum(null);
    setZoom(null);
    if (!key) return;
    let stale = false;
    fetchRefs(key)
      .then((rs) => !stale && setRefs(rs))
      .catch(() => !stale && setRefs([]));
    fetchFilesImages(key)
      .then((d) => !stale && setImages(d.configured && d.mapped ? d.images : []))
      .catch(() => !stale && setImages([]));
    return () => {
      stale = true;
    };
  }, [key]);

  // 改筛选回到相册墙(避免停在一个筛掉后不存在的册)
  useEffect(() => setOpenAlbum(null), [filter, sourceKey]);

  const items = useMemo(
    () => (key ? buildGallery(key, refs ?? [], images ?? []) : []),
    [key, refs, images],
  );
  const facets = useMemo(() => galleryFacets(items), [items]);
  // 「来源」选项 = 全部集合文件夹(不随当前筛选收缩,与 facets 同规矩:选项池
  // 固定,选中后才收窄展示)。
  const sourceOptions = useMemo(
    () => groupAlbums(items).map((a) => ({ key: a.key, label: a.label })),
    [items],
  );
  const bySource = useMemo(
    () => (sourceKey === null ? items : items.filter((it) => albumKeyOf(it) === sourceKey)),
    [items, sourceKey],
  );
  const shown = useMemo(() => filterGallery(bySource, filter), [bySource, filter]);
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
        <p className="muted">先在侧栏选一个项目,图墙按项目展示。</p>
      </div>
    );
  }

  return (
    <div className="page gallery-page">
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
        {sourceOptions.length > 0 && (
          <div className="gallery-source">
            <select
              className="gallery-source-select"
              data-ui="gallery-source"
              value={sourceKey ?? ""}
              onChange={(e) => setSourceKey(e.target.value || null)}
            >
              <option value="">全部来源</option>
              {sourceOptions.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
            {sourceKey !== null && (
              <button
                className="gallery-source-clear"
                title="清除来源筛选"
                onClick={() => setSourceKey(null)}
              >
                ×
              </button>
            )}
          </div>
        )}
        <button
          className="open-folder"
          title="在资源管理器打开项目文件夹"
          onClick={() => openFolder(project.key).catch(() => {})}
        >
          打开文件夹
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

      {current && (
        <button className="g-back" onClick={() => setOpenAlbum(null)}>
          ← 返回相册 · {current.group === REF_GROUP ? "参考" : current.group}
        </button>
      )}

      {!loading && items.length === 0 ? (
        <div className="aside-empty" style={{ marginTop: 18 }}>
          还没有图片。参考图在对话里发图登记;项目文件夹里的图片会自动出现在这里。
        </div>
      ) : !loading && shown.length === 0 ? (
        <div className="aside-empty" style={{ marginTop: 18 }}>
          这个筛选组合下没有图(工作区图片没有空间/风格标签)。
        </div>
      ) : current ? (
        <div className="g-wall">
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
        <div className="g-wall">
          {albums.map((a) => (
            <button
              className="g-cell"
              key={`alb:${a.key}`}
              title={a.label}
              onClick={() => (a.count > 1 ? setOpenAlbum(a.key) : setZoom(a.cover))}
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
        </div>
      )}
    </div>
  );
}
