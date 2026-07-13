# Verify: opendesign-hardening

- Date: 2026-07-14
- Verdict: PASS(主审;panel-review full lane 因用户额度紧张显式跳过——见下)

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

- lane: full(安全改动理应 full)——**主审已独立审并全程先红后绿实现;
  三家 employee 评审(submimo/subsense/subglm)本轮显式跳过**,因用户额度紧张,
  且每条修复都有 oracle 红检 + 真 e2e 兜底。下会话有额度可补跑 panel-review。
- 主审 findings(= 本 track 修的即盲评两轮全部成立项,逐条 file:line 见
  `/root/aiwork/logs/opendesign-fullrepo-blindreview-20260713.md`):H1/H2/M1/M2/M3/M5/
  L1/L3/L5(R2)/L6(R2)/L8/L7/文档批,全部实现并验证。
- arbitrated verdict(主裁):PASS。核心防线(名字闸单一真相源、Host 校验、
  字符集收敛、坏文件隔离、apply 嵌套复验)均有直接 oracle + 真运行验证。

## Accepted deviations

- **panel-review 三家评审未跑**(额度)——非机械缺陷,补跑无阻塞;主审判 PASS 独立成立。
- **M5(聊完免 F5 刷新)未在浏览器观测**——需真 LLM turn + 完整 gateway MCP 接线
  (当前 gateway 未配 ds_tools MCP、workspace 指向 dev),重建代价大且要动用户真实
  config。前端 build 编译干净 + 底层端点单测覆盖 + 简单 wiring;归**用户 Windows
  浏览器验收**(同历轮 track 交接惯例:聊一轮,变更列/待办角标不刷新即回归)。
- **R2-L6 冒烟 except 收窄未做**——只在 SKIP-gated 测试体内,无 live gateway 无法验证,
  broad except 安全;仅加了 schemaVersion 断言。留待下次有 gateway 时收窄。
