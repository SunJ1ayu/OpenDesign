import { useEffect, useMemo, useState } from "react";
import type { Project, Ref, RefsVocab } from "./api";
import { fetchFilesImages, fetchRefsData, openFolder, updateRef } from "./api";
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

const EMPTY_VOCAB: RefsVocab = { style: [], space: [] };

export default function GalleryPage({ project }: Props) {
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
      await reloadRefs(); // oracle 钉死:保存后必须重拉,下一次筛选用的是新标签
      setEditSaved("已保存");   // 成功要有反馈(同快记卡 toast 范式),否则人不知道存没存上
    } catch (e) {
      const code = (e as Error).message;
      setEditErr(
        code === "style_unknown" || code === "space_unknown"
          ? "标签不在词表里,刷新页面重试。"
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

  // 改筛选回到相册墙(避免停在一个筛掉后不存在的册)
  useEffect(() => setOpenAlbum(null), [filter]);

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
