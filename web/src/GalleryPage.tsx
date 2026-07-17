import { useEffect, useMemo, useState } from "react";
import type { Project, Ref } from "./api";
import { fetchFilesImages, fetchRefs, openFolder } from "./api";
import {
  buildGallery,
  filterGallery,
  galleryFacets,
  REF_GROUP,
  type GalleryFilter,
  type GalleryItem,
  type WsImage,
} from "./gallery";

// 图墙(P5 T5,一等面):refs 索引(空间/风格标签)∪ 工作区项目图片(按类目)。
// 纯展示层——合并/facets/筛选逻辑全在 gallery.ts(mjs oracle 覆盖);
// lightbox 直出原图(v1 无缩略图,proposal 非目标)。

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
  const [zoom, setZoom] = useState<GalleryItem | null>(null);

  const key = project?.key ?? null;

  useEffect(() => {
    setRefs(null);
    setImages(null);
    setFilter(EMPTY);
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

  // esc 关 lightbox
  useEffect(() => {
    if (!zoom) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setZoom(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoom]);

  const items = useMemo(
    () => (key ? buildGallery(key, refs ?? [], images ?? []) : []),
    [key, refs, images],
  );
  const facets = useMemo(() => galleryFacets(items), [items]);
  const shown = useMemo(() => filterGallery(items, filter), [items, filter]);
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
          {loading ? "读取中…" : `${shown.length} / ${items.length} 张`}
        </span>
        <span className="grow" />
        <button
          className="open-folder"
          title="在资源管理器打开项目文件夹"
          onClick={() => openFolder(project.key).catch(() => {})}
        >
          打开文件夹
        </button>
      </header>

      <Chips
        label="来源"
        values={facets.groups}
        active={filter.group}
        onPick={(v) => setFilter((f) => ({ ...f, group: v }))}
      />
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
      ) : (
        <div className="g-wall">
          {shown.map((it) => (
            <button className="g-cell" key={it.id} title={it.label} onClick={() => setZoom(it)}>
              <img src={it.url} alt={it.label} loading="lazy" />
              <span className="g-cap">
                <span className="l">{it.label}</span>
                <span className="g">{it.group === REF_GROUP ? "参考" : it.group}</span>
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
