# Tasks: opendesign-gallery-albums

- base-ref: 6944fe6301a319babb0ca865dde4f238d5969006

> 真机反馈:图墙里效果图"看不全(埋太深被截)+ 看着乱(一套十几张平铺混在一起)"。
> 两件一起治:①可配扫描深度+放深默认;②图墙按"集合文件夹"分相册(封面→点开看全部)。
> 纯前端 + 小后端;不碰只读铁律/taxonomy。oracle 先行,主 agent 写。

- [ ] T1 后端:ds_workspace 扫描深度可配(DEFAULT_MAX_DEPTH=6 放深默认;overview/images/
      _scan/_walk_cat 加 max_depth 参数;load_config 解析可选 galleryDepth 钳到[2,8],
      坏值回落默认不整体下线=display 旋钮非解析/安全字段);ds_web _files_meta 透传
- [ ] T2 前端逻辑:gallery.ts groupAlbums(筛选后按 ws 图父文件夹分册;refs 归一册
      参考图库;根散图归"未分类";封面=册内首项=最新;册序=首现序)
- [ ] T3 前端展示:GalleryPage 两层(相册墙:封面+册名+张数 → 点开:该册图网格+返回 →
      点图:现有 lightbox);facets 筛选保持在分册前
- [ ] T4 版本 0.27.0;py 回归 + mjs oracle 全绿;e2e 图墙相册一条
- [ ] T5 verify(lane fast:主审+submimo;纯展示+小后端,非脊梁级安全面)
