// 图墙纯逻辑层(P5 T5)——数据合并与筛选,零 DOM,进 mjs oracle。
// 数据两路:refs 索引(带空间/风格标签,共享参考图库)∪ 工作区项目图片
// (按类目分组,无标签)。两路物理上不同文件树,不做内容去重(v1 取舍:
// 02-参考图 的冻结副本与库里真身可能同图两条,诚实展示来源)。

// 显式 .ts 扩展:tsconfig allowImportingTsExtensions + node --test 原生 strip-types 两头兼容
import type { Ref } from "./api.ts";
import { refImageUrl, filesImageUrl } from "./api.ts";

export type WsImage = { rel: string; category: string; mtime: number };

export type GalleryItem = {
  id: string; // "ref:<id>" | "ws:<rel>",稳定 key
  url: string;
  label: string;
  group: string; // "参考图库"(refs)或工作区类目名
  space: string[]; // 仅 refs 有;ws 图空数组
  style: string[];
  mtime: number | null;
};

export const REF_GROUP = "参考图库";

/** refs 缩略标签:note > 空间·风格 > id(与 CompanionColumn 同口径)。 */
export function refLabel(r: Ref): string {
  if (r.note) return r.note;
  const bits = [...r.space.slice(0, 1), ...r.style.slice(0, 1)];
  return bits.join("·") || r.id;
}

/** 合并两路数据:refs 保持索引序在前,工作区图按 mtime 降序(同刻按 rel)。 */
export function buildGallery(
  projectKey: string,
  refs: Ref[],
  images: WsImage[],
): GalleryItem[] {
  const a: GalleryItem[] = refs.map((r) => ({
    id: `ref:${r.id}`,
    url: refImageUrl(r.file),
    label: refLabel(r),
    group: REF_GROUP,
    space: r.space,
    style: r.style,
    mtime: null,
  }));
  const b: GalleryItem[] = images
    .slice()
    .sort((x, y) => y.mtime - x.mtime || x.rel.localeCompare(y.rel))
    .map((i) => ({
      id: `ws:${i.rel}`,
      url: filesImageUrl(projectKey, i.rel),
      label: i.rel.split("/").pop() ?? i.rel,
      group: i.category || "未分类",
      space: [],
      style: [],
      mtime: i.mtime,
    }));
  return [...a, ...b];
}

export type GalleryFilter = {
  group: string | null;
  space: string | null;
  style: string | null;
};

/** 可用筛选值(chip 数据源):按首现序去重;空间/风格只来自 refs 标签。 */
export function galleryFacets(items: GalleryItem[]) {
  const uniq = (xs: string[]) => [...new Set(xs)];
  return {
    groups: uniq(items.map((i) => i.group)),
    spaces: uniq(items.flatMap((i) => i.space)),
    styles: uniq(items.flatMap((i) => i.style)),
  };
}

/** 三维 AND 筛选;空间/风格选中时,无标签的工作区图自然被排除。 */
export function filterGallery(
  items: GalleryItem[],
  f: GalleryFilter,
): GalleryItem[] {
  return items.filter(
    (i) =>
      (!f.group || i.group === f.group) &&
      (!f.space || i.space.includes(f.space)) &&
      (!f.style || i.style.includes(f.style)),
  );
}
