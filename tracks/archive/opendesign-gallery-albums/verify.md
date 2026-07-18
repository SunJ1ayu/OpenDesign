# Verify: opendesign-gallery-albums

- Date: 2026-07-18
- Verdict: PASS

## Mechanical checks
- [x] build passes(tsc -b + vite,301 模块;dist 重建)
- [x] tests pass — oracle 先行全绿:test_ds_workspace 45 / test_gallery.mjs 10 /
      test_ds_web_files 25(深图第5层经真 ds_web /api/files/images 服务)/ 全 py 套件 OK /
      resolver 27 / 全 mjs 8。ws_protocol_smoke=无 gateway 的设计 SKIP(rc=3),非回归。
- [x] no secrets / unsafe ops(零新写面;分册纯展示;只读铁律不破)

## Review
- lane: fast(主审 + submimo)
- findings:
  - 主审(tasks/opendesign-gallery-albums-my-review.md,写于读 submimo 前):PASS 零必改;
    记 4 条 follow-up/deviation(放深全局生效/MAX_PER_CAT 静默截断/浏览器交互未 e2e/深扫无缓存)。
  - submimo:PASS,逐点独立复核主审全部结论(id.slice(3) 稳/封面=最新/galleryDepth bool-先于-int
    钳位/`_ws_proj` 三元组降级安全/放深副作用可接受/覆盖充分)。两 minor:①label 同名折叠=
    cosmetic(key=全路径驱动导航,非阻塞,接受);②React key。
  - **主裁对 submimo minor②的独立加固**:`a.key || "未分类"` 会让根散图册(key="")与真名为
    "未分类" 的文件夹册撞 React key。submimo 判"safe"漏了这条边;主审复核成立 → 改
    `key={`alb:${a.key}`}`(册 key 由 Map 保证唯一,前缀消歧)。rebuild + gallery oracle 10/10 复绿。
- arbitrated verdict(主裁):**PASS**。submimo 未推翻主审;唯一实修=主裁自查加固的 React key 边。

## Accepted deviations
- 放深默认(6)全局生效(overview/cockpit 计数同步变深)——意图内。
- MAX_PER_CAT=2000 每类目静默截断(images 不暴露 capped),放深后风险微增;真机大项目才触发,记债。
- 深扫无缓存,大 3dmax 工程每开图墙全树重扫——真机需测性能(F9),记债。
- 浏览器交互(点封面进册/返回/单图直放)未 e2e——fast lane,分册/深度纯逻辑已 oracle 全覆盖,
  交用户装机验(部署目标规则)。
- label 同名折叠(不同父路径同末段名)=cosmetic,key 全路径驱动导航无功能影响。
