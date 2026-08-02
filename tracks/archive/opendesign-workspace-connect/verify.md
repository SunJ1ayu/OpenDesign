# Verify: opendesign-workspace-connect

- Date: 2026-07-16
- Verdict: PASS

## Mechanical checks

- [x] build passes（`cd web && npm run build` tsc+vite 绿;dist 已提交)
- [x] tests pass（test_ds_tools 63 含 SetWorkspaceOracle 12 / test_ds_todo golden 未破 /
  ds_workspace / ds_web_api 38 / ds_web_files 25 / mjs 4 文件 65 例,全绿)
- [x] red-check 双向咬（注掉 isabs→test_w02 红;注掉 list_todos prepend→test_w10 红;还原全绿)
- [x] e2e 真起 ds_web 10/10（未接入提醒→set_workspace(folder_count=2)→**免重启**即时
  configured+mapped;health=0.12.0)
- [x] no secrets / unsafe ops（set_workspace 只写 config/workspace.json;不碰 os.environ/organize)

## Review

- lane: **full**（主 agent + submimo + subsense；subglm 因 429 余额不足失败 → 单缺席,2/3 跑成)
- 主 agent 独立评审(先于读 employee):`/root/aiwork/tasks/opendesign-workspace-connect-my-review.md`
  → PASS,安全不变量 code-verified。
- employee findings 逐条裁决(每条附依据):
  1. **`.bak` 连续坏 JSON 覆盖**(submimo+subsense 均标,低):真实但近乎不可达——首次
     set_workspace 于坏 JSON 后已写入**合法**文件,后续调用读到合法 JSON 不再产 .bak;要覆盖 .bak
     需 workspace.json 在两次调用间被外部再次损坏。两家均判非阻塞。**接受为 nit,不改**(最简方案)。
  2. **symlink root 测试覆盖缺失**(subsense #9):非缺陷。核实下游 ds_workspace.project_dir/
     project_folders 用 realpath+`ds_common.within`+`follow_symlinks=False`,root 即便是 symlink 也被
     解析且读侧权威闸兜底。**拒作必改**,可选增强。
  3. **`D:\` 示例在 Linux 显怪**(subsense #11):纯 cosmetic;部署目标就是 Windows 真机。**拒**。
- **arbitrated verdict(主裁):PASS。** 无 employee 发现主 agent 漏报的真缺陷;无安全逃逸/数据丢失/
  逻辑回归;三家未报的共享假阴风险由主 agent code-verified 的安全不变量兜底。

## Accepted deviations

- `.bak` 仅保护最近一次损坏写入(见 review#1),近乎不可达,不加复杂度旋转。
- 未补 symlink-root / 并发写测试(见 review#2):下游权威闸已覆盖,可选增强,非阻塞。

## 部署要点(部署目标规则)

- dist 已提交:用户 Windows 只需 `git pull` + 重启 ds-web(不必 npm build)。
- **AGENTS.md 是部署副本**:workspace/AGENTS.md 的改动须随 install 拷到 `%USERPROFILE%\.nanobot\
  workspace`(install-windows.md §5)才对运行中的 agent 生效——否则 agent 仍读旧契约。
- 验收:浏览器 Ctrl+F5 页脚 / `/api/health` version 显 **0.12.0**;对话里说一句项目文件夹路径 →
  agent 调 set_workspace → 文件区从空态变列文件(workspace.json 写完免重启即时生效)。
