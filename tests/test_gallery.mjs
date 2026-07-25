// P5 T5 oracle:图墙纯逻辑层(合并/facets/三维 AND 筛选)
// 跑法:node --test tests/test_gallery.mjs(Node 22+,原生 strip-types)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildGallery,
  galleryFacets,
  filterGallery,
  groupAlbums,
  refLabel,
  REF_GROUP,
} from "../web/src/gallery.ts";

const REFS = [
  { id: "r1", style: ["奶油风"], space: ["客厅"], file: "refs/a.jpg", note: "" },
  { id: "r2", style: ["侘寂"], space: ["卧室"], file: "refs/b.png", note: "业主定稿" },
];
const IMGS = [
  { rel: "06-效果图/定稿/终版.png", category: "06-效果图", mtime: 200 },
  { rel: "02-参考图/冻结.jpg", category: "02-参考图", mtime: 300 },
  { rel: "06-效果图/过程.png", category: "06-效果图", mtime: 200 },
];

test("buildGallery:refs 索引序在前,ws 按路径自然序升序(对齐资源管理器)", () => {
  const g = buildGallery("龙腾世纪-1802", REFS, IMGS);
  assert.deepEqual(
    g.map((i) => i.id),
    ["ref:r1", "ref:r2", "ws:02-参考图/冻结.jpg",
     "ws:06-效果图/定稿/终版.png", "ws:06-效果图/过程.png"],
  );
});

// 真机反馈 2026-07-24 #10a:「文件夹第一张在图墙显示成最后一张」。根因=原实现按
// mtime **降序**,而资源管理器默认按文件名升序 → 用户眼里整册是倒的。
// 夹具刻意用**真实风格的中文文件名**(中文 + 空格 + 括号 + 多位数字):
// 造一组 a/b/c 式的假名字能绿,却证明不了用户机器上那种名字也对。
test("buildGallery:按文件名自然序升序,不受 mtime 影响(#10a 判据)", () => {
  const imgs = [
    // mtime 与文件名**同序**(真实情形:按顺序拷进文件夹,后面的更新)。
    // 这样 mtime 降序 = 文件名倒序,与正确答案正好相反 —— 夹具必须能区分两种实现。
    // (第一版夹具把 mtime 设成逆序,结果旧代码也绿:假绿,自查时抓到。)
    { rel: "05-3DMAX/主卧/翡翠湾-1801 主卧 (10).jpg", category: "05-3DMAX", mtime: 300 },
    { rel: "05-3DMAX/主卧/翡翠湾-1801 主卧 (2).jpg", category: "05-3DMAX", mtime: 200 },
    { rel: "05-3DMAX/主卧/翡翠湾-1801 主卧 (1).jpg", category: "05-3DMAX", mtime: 100 },
  ];
  const g = buildGallery("翡翠湾-1801", [], imgs);
  assert.deepEqual(
    g.map((i) => i.label),
    ["翡翠湾-1801 主卧 (1).jpg", "翡翠湾-1801 主卧 (2).jpg", "翡翠湾-1801 主卧 (10).jpg"],
    "(2) 必须排在 (10) 前 —— 纯字典序会把 10 排到 2 前面,要 numeric 自然序",
  );
});

test("buildGallery:url 路由正确且逐段编码", () => {
  const g = buildGallery("龙腾世纪-1802", REFS, IMGS);
  assert.equal(g[0].url, "/api/refs/file/a.jpg");
  const ws = g.find((i) => i.id === "ws:02-参考图/冻结.jpg");
  assert.equal(
    ws.url,
    `/api/files/file/${encodeURIComponent("龙腾世纪-1802")}/` +
      `${encodeURIComponent("02-参考图")}/${encodeURIComponent("冻结.jpg")}`,
  );
});

test("buildGallery:label = note > 空间·风格 > 文件名;group 归属", () => {
  const g = buildGallery("k", REFS, IMGS);
  assert.equal(g[0].label, "客厅·奶油风");
  assert.equal(g[1].label, "业主定稿");
  assert.equal(g[0].group, REF_GROUP);
  const ws = g.find((i) => i.id === "ws:06-效果图/定稿/终版.png");
  assert.equal(ws.label, "终版.png");
  assert.equal(ws.group, "06-效果图");
});

test("refLabel:全空回落 id", () => {
  assert.equal(refLabel({ id: "r9", style: [], space: [], file: "x", note: "" }), "r9");
});

test("galleryFacets:首现序去重;空间/风格只来自 refs", () => {
  const f = galleryFacets(buildGallery("k", REFS, IMGS));
  assert.deepEqual(f.groups, [REF_GROUP, "02-参考图", "06-效果图"]);
  assert.deepEqual(f.spaces, ["客厅", "卧室"]);
  assert.deepEqual(f.styles, ["奶油风", "侘寂"]);
});

test("filterGallery:三维 AND;空筛选=全量", () => {
  const g = buildGallery("k", REFS, IMGS);
  const none = { group: null, space: null, style: null };
  assert.equal(filterGallery(g, none).length, g.length);
  assert.deepEqual(
    filterGallery(g, { ...none, group: "06-效果图" }).map((i) => i.id),
    ["ws:06-效果图/定稿/终版.png", "ws:06-效果图/过程.png"],
  );
  assert.deepEqual(
    filterGallery(g, { ...none, space: "客厅" }).map((i) => i.id),
    ["ref:r1"],
  );
  // 空间+组 AND:ws 图无标签被空间筛除
  assert.deepEqual(filterGallery(g, { group: "06-效果图", space: "客厅", style: null }), []);
});

test("filterGallery/facets:空输入不崩", () => {
  assert.deepEqual(buildGallery("k", [], []), []);
  assert.deepEqual(galleryFacets([]), { groups: [], spaces: [], styles: [] });
});

test("groupAlbums:refs 归一册,ws 图按父文件夹分册,册序=首现序", () => {
  const albums = groupAlbums(buildGallery("k", REFS, IMGS));
  assert.deepEqual(
    albums.map((a) => [a.key, a.label, a.count]),
    [
      ["参考图库", "参考图库", 2],       // 两条 ref 收一册
      ["02-参考图", "02-参考图", 1],     // 直接摆类目下(单段)
      ["06-效果图/定稿", "定稿", 1],     // 册名=父夹末段
      ["06-效果图", "06-效果图", 1],     // 类目根下的散图独立成册
    ],
  );
});

test("groupAlbums:封面=册内首项(文件名最小);count/items 一致", () => {
  const imgs = [
    { rel: "05-3DMAX/客厅/a.png", category: "05-3DMAX", mtime: 100 },
    { rel: "05-3DMAX/客厅/b.png", category: "05-3DMAX", mtime: 200 },
  ];
  const albums = groupAlbums(buildGallery("k", [], imgs));
  assert.equal(albums.length, 1);
  const [客厅] = albums;
  assert.equal(客厅.label, "客厅");
  assert.equal(客厅.count, 2);
  // #10a 后:册内序 = 文件名升序 → 封面是 a.png(资源管理器里的第一张),不再是最新的 b.png
  assert.equal(客厅.cover.id, "ws:05-3DMAX/客厅/a.png");
  assert.deepEqual(客厅.items.map((i) => i.id), [
    "ws:05-3DMAX/客厅/a.png",
    "ws:05-3DMAX/客厅/b.png",
  ]);
  assert.equal(客厅.group, "05-3DMAX"); // 来源=顶层类目
});

test("groupAlbums:项目根散图归「未分类」;空输入=空", () => {
  const albums = groupAlbums(
    buildGallery("k", [], [{ rel: "封面.png", category: "", mtime: 1 }]),
  );
  assert.deepEqual(albums.map((a) => [a.key, a.label]), [["", "未分类"]]);
  assert.deepEqual(groupAlbums([]), []);
});
