# Verify: opendesign-windows-prep

- Date: 2026-07-03
- Verdict: PASS

## Mechanical checks

- [x] build passes(纯 Python,无构建;两解释器 import 均通过)
- [x] tests pass:系统 python3 51 绿(13+18+14+6,skip 2 个 MCP 表面);venv 下含 MCP
      表面 + skills 冒烟共 54 全绿
- [x] no secrets / unsafe ops(ps1/config 均走 env/占位符,无 key 落盘;grep bin/*.py
      无 `/root/` 残留)

## Review

- lane: fast(① 代码改动;②③④ 文档/草稿部分 self)
- **主 agent findings(在读 submimo 输出之前落此,2026-07-03)**:
  1. [自查通过] ds_todo.render 与原 print 序列逐行等价(golden 三形态 + CLI 端到端
     比对 render 输出,test_04 锁死 wrapper=core);DS_TODAY 只在 env 显式设置时生效,
     生产路径行为不变。
  2. [自查通过] list_todos 直调:monkeypatch 同模块对象,test_06 证实错误显式化;
     ds_todo.py 缺失从"运行时 error dict"变为"MCP server 启动时 ImportError"——
     可接受(文件随仓库走,启动即炸好过静默)。
  3. [minor,已知] docs/spec.md:64 仍写"调现成 bin/ds-todo"——实现细节漂移
     (行为"原文本返回"未变);记 accepted deviation,不动冻结 spec。
  4. [minor,已知] ds_todo.py 用 `date | None` 联合类型注解,需 Python≥3.10;
     nanobot 本身要求 3.11+,不构成实际约束。
  5. [自查通过] DEFAULT_DS_ROOT 改 __file__ 推导:四文件一致,本机推导值与旧常量
     逐字符相同(无 symlink);ds-approve 经 ds_organize.DEFAULT_DS_ROOT 同步受益。
  6. [自查通过] os.pathsep:Linux 行为不变(venv 含 MCP 表面 18/18 绿),Windows 语义修正。
  7. [风险标注] ps1 + windows config 为 UNTESTED 草稿,已在文件头声明;`${DS_ROOT}`
     依赖经 ps1 启动,loader 对未设 env 直接 ValueError(硬失败可见,不静默)。
- submimo findings(log:/root/aiwork/logs/opendesign-windows-prep-review.log,PASS,6 条):
  - F1 LOW:windows config 的 DS_ORGANIZE_ROOTS="" 缺"空=全拒"注释 → **收,已补注释**
    (核实:Linux 版有该注释、Windows 变体确实漏了)。
  - F2 LOW:golden 是自生成回归锁非独立基线 → 已知取舍(design.md 明示;bash 原版不可恢复),
    不动。
  - F3 LOW:list_todos except Exception 过宽 → 有意为之(带崩 MCP 更糟),记 P-later
    (窄 catch 已知失败模式)。
  - F4/F5/F6/F7 INFO:与主 agent findings 5/6/7 相互印证;F7 逐码核对 SKILL.md 错误码表
    与实现全一致(其表格多列了不存在的 `ambiguous_ref`,笔误,已核 ds_refs.py 无此码,
    不影响结论)。
- arbitrated verdict (主裁): **PASS** —— 双方独立 findings 高度重合且互无未解 BLOCK;
  F1 修复后复跑不需要(注释级改动);54 测试全绿维持。

### 事后追加(2026-07-03,用户要求补三审)

- 归档后用户要求把 fast lane 补成 full。补跑注意:subsense/subglm 是纯 chat 无 agent 底座,
  repo 又不在 git 内(diff 空)→ **必须 SENSENOVA_INCLUDE/ZHIPU_INCLUDE 手动喂文件**,
  否则盲评(首跑 subsense 即如此,作废重跑)。
- **subsense(deepseek-v4-flash,重试 1 次后交卷):PASS + 4 LOW**
  (log: /root/aiwork/logs/opendesign-windows-prep-review.subsense2.log;首跑空响应作废):
  - S1 DEFAULT_DS_ROOT 用 realpath 防 symlink → **收**,四文件已改,零行为变化;
  - S2 test_06 monkeypatch 污染并发 → **拒**:unittest 标准 runner 串行 + finally 还原,
    不存在并行 worker;
  - S3 SKILL.md 错误码表是子集 → **收改法**:两份 SKILL.md 各加一行"没列到的错误码 →
    原样告知用户,不要自行重试绕过"(比穷举稳);
  - S4 ps1 Write-Error 换 throw → **拒**:其修法与所指问题同病(throw 也走 error stream),
    $ErrorActionPreference=Stop 下 Write-Error 正常终止且控制台可见。
- **subglm:未交卷**(首跑 900s 读超时;1500s 重试中被用户叫停——额度告急)。
  按约定记录单缺席:full lane 实际完成度 = 主 agent + submimo + subsense(2/3 员工)。
- S1/S3 修复后全量回归:54 测试全绿,workspace skills 副本已同步。
- **最终 verdict 维持 PASS**(三方 PASS 一致:主 agent / submimo / subsense;subglm 缺席
  不改变判定——它的沉默本来也不是 clearance)。

## Accepted deviations

- docs/spec.md:64 的"调 bin/ds-todo"描述与实现(import 直调)漂移;行为契约未变,spec 冻结不改。
- ps1 / nanobot.config.windows.jsonc 未经真机验证,文件头已标 UNTESTED;真验证等目标机。
- ~/.nanobot/workspace/skills/ 是拷贝副本,规范源在 repo skills/;部署脚本(未来)负责同步。
