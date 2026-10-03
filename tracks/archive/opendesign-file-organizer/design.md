# Design: opendesign-file-organizer

- Change: opendesign-file-organizer
- Status: frozen(2026-07-01 睡前与用户摊开确认;2026-07-02 用户拍板 MVP 砍 delete)

> 无 panel-explore:方向已与用户逐条敲定,不是开放分叉。

## Approach

新模块 `design-studio/bin/ds_organize.py`,照 `ds_tools.py` 风格:纯 Python 标准库核心
(可被 tests 直接 import)+ 末尾延迟 import 的 stdio FastMCP 包装。**LLM 提方案 /
工具管校验+执行**,三工具 + 一个人工 CLI:

1. **`scan_dir(root)`** — 只读。递归列 root 下文件/目录(相对路径、size、mtime、is_dir),
   条目封顶(默认 2000,超出返回 `truncated: true`)。root 必须落在允许根白名单内。
2. **`stage_plan(root, operations)`** — 校验 + 暂存,**零文件系统改动**(除写
   `plans/plan_<id>.json`)。operations = `[{op, src, dst}]`,`op ∈ {move, rename}`
   (同一原语两个名字;**delete 直接拒绝** `op_not_allowed`)。src/dst 为 root 相对路径。
   校验:src 存在、dst 不存在(不覆盖)、src/dst realpath 均在 root 内(防 `../` 逃逸)、
   ops 之间无 src 重复 / dst 冲突 / dst 撞另一 op 的 src(保证与执行顺序无关)。
   通过则对每个 src 记 **(size, mtime_ns) 快照**存进 plan json,返回人看的清单 + `plan_id`。
3. **`apply_plan(plan_id)`** — **仅当 `plans/plan_<id>.approved` 标记存在才执行**。
   执行前整体复验(src 仍在、dst 仍空、快照未漂移),**任一项失败 → 整个 plan 中止,
   零执行**(先验后动,不部分执行)。执行 = `os.rename`(dst 父目录允许在 root 内自动
   mkdir);逐条追加 `audit.log`;完毕把 plan 标记为 applied(**不可二次 apply**)。
4. **`bin/ds-approve <plan_id>`** — 人工批准 CLI,创建 `.approved` 标记。

### 确认闸为什么是"硬"的(本设计的核心)

批准通道 = 模型碰不到:MCP 只暴露 scan/stage/apply 三工具,**没有任何工具能创建
`.approved` 文件**;`.approved` 只能由人在终端敲 `ds-approve`(将来 = Windows WebUI 的
确认按钮,同样是工具层外的通道)产生。聊天里回"确认"不算数——那仍经模型的手。
plan_id 含随机分量,batch 批准不存在,**一个标记只解锁一个 plan,apply 一次即消耗**。

### 布局

- plans 与 audit 放 `DS_ROOT/organize/`(plans/、audit.log),**不在被整理的 root 里**
  (避免 scan 自见、避免 plan 文件本身被 move)。
- 允许根白名单:核心函数收 `allowed_roots` 参数(测试注入);MCP 包装读环境变量
  `DS_ORGANIZE_ROOTS`(冒号分隔),未设置则拒绝一切(默认关死,不是默认全开)。

## Key trade-offs / risks

- **MVP 只有 move/rename,无 delete**(用户 07-02 拍板)——回收站/回滚整组不做,风险面
  显著变小;move 不销毁数据,最坏是挪错位置,audit.log 可追溯手工挪回。
- **漂移检测用 size+mtime_ns**,不做内容 hash——够挡"stage 后文件被改过",省大文件 IO;
  mtime 伪造不在威胁模型里(对手是模型失误,不是恶意 root 用户)。
- **先验后动,不做执行中途回滚**:整体复验通过后逐条 rename 仍可能中途失败(如权限),
  此时 audit.log 记录已执行部分;接受此残余风险(MVP,同 root 文件系统 rename 极少半途死)。
- **跨设备 move 不支持**(os.rename 同 fs 限制)——root 内整理天然同 fs,报错即可。
- plan 文件本身可被模型经 stage_plan 写入(内容受控于 schema 校验),但 `.approved`
  后缀永远不经它的手——闸的强度只依赖这一条。

## Alternatives considered

- 聊天回"确认"当批准 —— 否。仍经模型的手,不够硬(07-01 已修正)。
- 每原语独立工具(move_file/rename_file 各带确认)—— 否。批量整理会变成 N 次确认,
  plan 粒度确认才符合"出一张清单、人扫一眼、一次批"的使用形态。
- 自动分类规则引擎 —— 否。归类是大脑(LLM)的活,工具只管校验与执行,职责分明。
- delete→回收站 `.ds_trash/<ts>/` —— 推迟(用户砍),设计留档于此,将来按真实需要再上。

## Test strategy (oracle)

`tests/test_ds_organize.py`,零依赖零网络,全部跑在 tmpdir。矩阵(主 agent 拥有,
对任何受托实现方 off-limits):

1. scan:正确列出文件/目录;root 不在白名单 → `root_not_allowed`;`../` root 逃逸拒绝。
2. stage:src/dst 含 `../` 或绝对路径逃出 root → `path_escape`,零改动。
3. stage:dst 已存在 → `would_overwrite`;两 op 同 dst → `conflict`;src 重复 → `conflict`;
   dst 撞另一 op 的 src → `conflict`。
4. stage:`op: delete` → `op_not_allowed`(MVP 砍掉);未知 op 同拒。
5. stage 成功:文件系统零改动(除 plan json);返回 plan_id + 人看清单;快照落盘。
6. apply 未批准 → `not_approved`,零改动。
7. `ds-approve` 后 apply:精确执行所有 move/rename,dst 子目录自动创建,audit.log 逐条落。
8. 漂移:stage+approve 后改 src 内容 → apply 整体中止 `plan_drift`,零执行。
9. stage+approve 后 src 消失 / dst 被占 → apply 整体中止,零执行。
10. 二次 apply → `already_applied`。
11. 批准 plan A 不解锁 plan B。
12. MCP 包装冒烟:server 能列出 3 工具(venv 有 mcp 才跑,没有则跳过)。
