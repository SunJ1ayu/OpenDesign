# Verify: opendesign-hardening

- Date: 2026-07-14
- Verdict: PASS(主审 + panel-review full lane 三家 employee 全 PASS,2026-07-14 补跑;见下)

## Mechanical checks

- [x] build passes（`cd web && npm run build` 通过,dist 已重建入仓）
- [x] tests pass（py 14 套件全绿,含冒烟 SKIP rc=3 符合预期;mjs 4 套件全绿;
      每条修复先红后绿已实证）
- [x] e2e：headless chromium + 真 dist + 真 ds_web(fixture DS_ROOT)6/6 PASS
      —— 应用启动/变更含空间前缀/M1 坏文件隔离/M2 #-图 roundtrip(naturalWidth>0)/
      M2 列出=可服务/H2 浏览器同源 Host 通过+回显 0.8.1
- [x] no secrets / unsafe ops：e2e 只 cp 备份用户 config(未跑 enable_webui),
      跑完 diff 确认 `~/.nanobot/config.json` 原封未动

## Review

- lane: full(安全改动理应 full)——**主审已独立审并全程先红后绿实现;三家 employee
  评审(submimo/subsense/subglm)已于 2026-07-14 补跑**,协议齐备:oracle 先跑(rc=0)、
  主审评审先落盘(反锚定,`/root/aiwork/tasks/opendesign-hardening-my-review.md`)、三家
  并行以 `PANEL_DIFF_BASE=origin/main` 看真实提交 diff。日志:
  `/root/aiwork/logs/panel-opendesign-hardening-20260714-213643.{submimo,subsense,subglm}.log`。
- 主审 findings(= 本 track 修的即盲评两轮全部成立项,逐条 file:line 见
  `/root/aiwork/logs/opendesign-fullrepo-blindreview-20260713.md`):H1/H2/M1/M2/M3/M5/
  L1/L3/L5(R2)/L6(R2)/L8/L7/文档批,全部实现并验证。
- 三家结论:submimo=PASS(3 条非阻塞观察:errors 上报不对称/裸形态 Host 接受/
  `_REFS_PATH_RE` 放行 `.` 靠 Gate B 收敛 `..`——三条主审均已 code-verify=真实但非阻塞);
  subsense=PASS(M2 措辞"widens enumeration"方向不准,不采纳表述,结论与代码一致);
  subglm=PASS(唯一部分触及 M2 收窄隐藏文件的 trade-off;另提 H2"403 后仍继续解析 route"
  被主审否决——`do_GET/do_POST` 里 `self._json(403); return` 立即中断,GLM 自认非安全洞)。
- arbitrated verdict(主裁,唯一仲裁者):PASS。核心防线(名字闸单一真相源、Host 校验、
  字符集收敛、坏文件隔离、apply 嵌套复验、add_style TOCTOU)均有直接 oracle 红检 + 真运行
  验证;三家 PASS 不降主审自有的判据,且无一抓出主审漏掉的 BLOCK 级缺陷。

## Accepted deviations

- **M2 字符集收窄=静默隐藏**(主审独立发现,三家仅 subglm 部分触及)——收敛靠「收窄枚举」
  实现「列得出=服务得到」,则名字含 `NAME_CHARS` 外常见标点(`&`/`+`/`,`/`'`/`=`…)的文件、
  乃至整个含此类字符的子目录子树,从工作台列表**静默消失**(如 `报价&终稿.png`、`水电&暖通/`)。
  旧码是「列出但点开 404」,新码是「不列出」——二者都服务不了该文件,故非服务能力回归;是
  可发现性/数据可见性取舍。权威闸是 realpath+within,放宽 servable 字符集是安全的,故亦可
  改为「放宽服务端」而非「收窄枚举」以surface这些文件。**交用户拍板** NAME_CHARS 是否够宽,
  或加「因不支持字符被隐藏」的提示。非阻塞。
- **M5(聊完免 F5 刷新)未在浏览器观测**——需真 LLM turn + 完整 gateway MCP 接线
  (当前 gateway 未配 ds_tools MCP、workspace 指向 dev),重建代价大且要动用户真实
  config。前端 build 编译干净 + 底层端点单测覆盖 + 简单 wiring;归**用户 Windows
  浏览器验收**(同历轮 track 交接惯例:聊一轮,变更列/待办角标不刷新即回归)。
- **R2-L6 冒烟 except 收窄未做**——只在 SKIP-gated 测试体内,无 live gateway 无法验证,
  broad except 安全;仅加了 schemaVersion 断言。留待下次有 gateway 时收窄。
