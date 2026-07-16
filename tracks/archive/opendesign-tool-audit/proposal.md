# Proposal: opendesign-tool-audit(工具层三审:覆盖矩阵/DRY/resolver eval)

- Date: 2026-07-17
- Status: open

## 背景
用户 07-16 问"给 agent 手的方式对不对、wiki 有没有参考"→ 对照 llm-wiki
Skillify 纪律(Check-Resolvable/resolver eval/DRY 审计)盘了一次:方向对,
但 resolver eval 一直挂"想法清单"没做——改名事故+用户"要不要每次点名工具"
就是路由层的真实案例,该转正了。用户拍板三件一起做。

## 方案
1. 覆盖矩阵桌面演练(动词×对象,找 delete_project 式的下一个空格)
2. DRY/可达性审计(18 工具,lane 交叉处置)
3. 轻量 resolver eval 脚本(意图→工具路由,直连 MiMo,docstring AST 同源)
产出 = docs/tool-audit-20260716.md + tests/evals/resolver_eval.py + 按发现修。

## 非目标
- 补空格工具本体(read_client/set_stage 各自立 track,吃各自的 oracle+panel)。
