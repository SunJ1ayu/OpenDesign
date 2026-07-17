# Verify: opendesign-set-stage

- Date: 2026-07-17
- Verdict: **PASS**(panel 修复轮后)

## Mechanical checks

- [x] test_ds_tools 129/129(SetStageOracle 8 例先红后绿,含修复轮 ss08/uc10)
- [x] pytest 全套 324 passed + 7 skipped
- [x] 突变红检:词表校验注掉 → ss02+ss06 红;还原复绿
- [x] resolver eval 实跑 20/20 ALL PASS(「万科城今天开始量房了」→ set_stage)
- [x] PANEL_ORACLE_CMD 前置 rc=0

## Review

- lane: **full**(主审 + submimo + subsense-agent + subglm 火山 chat 腿)
- 主审先行(仓外,panel 前落盘):PASS + 2 观察
- 三家:submimo PASS / subsense PASS(**本轮英文 Conclusion,gate 正常**)/
  subglm PASS + 2 LOW

### findings 仲裁

| 来源 | finding | 裁定 |
|---|---|---|
| **submimo+subsense 同标** | `[::]` 实为两个半角冒号(0x3a),全角从未被支持 | **成立,真 bug**:字节级核实,全角字面量在混排输出中被打成半角(测试初版复刻同一 typo=旁证)。修 `[:：]` 显式转义(update_client field_re 一并),ss08/uc10 先红后绿。**推翻主审 client-tools 轮的错误拒绝**(勘误已附归档 verify)——panel 抓主审盲点的教材案例 |
| subglm LOW#1 | bad_stage 先于 not_found 未被测试锁定 | 收测试锁(ss03 加断言),优先级本身维持(与 bad_field 契约一致) |
| subglm LOW#2 | ss06 零副作用是间接验证 | 收:改逐次快照逐字节比对 |
| 主审 观察1 | 头部字段行替换/补插逻辑第三份拷贝 | 记录:下个 hardening 抽 `_upsert_header_field`,本 track 不动 |

- panel 修复轮改动:2 正则 + 4 测试;全部先红后绿;pytest 全套复跑绿。
  修复为 2 字符正则扩容+纯增测试,无行为回退面,不再发第二轮 panel(先例:
  rename/bind track 收 findings 同姿势)。

## Accepted deviations

- bad_stage 先于 project_not_found(纯函数校验最便宜先拒,ss03 契约锁定)。
- 手建档案无页脚时 bump_last_updated 静默 no-op(bump 自身契约"无则不硬造")。
- create_project 的 stage 参数仍无词表闸(存量行为,非目标声明,单独议)。

## 教训(进记忆)

- **全角标点进代码一律 \uXXXX 显式转义 + hexdump 验证**;字面量在中英混排
  输出里会被静默打成半角,且同一手误会在"验证它的测试"里复刻(假绿)。
- 仲裁拒 finding 的依据要核到字节;两家独立同标的"低严重度"要提权重审。

## 用户验收断点(0.22.0+0.23.0 一批)

git pull → start.ps1 stop → start.ps1(重启 gateway 注册三个新工具)→ 回显
**0.23.0**;AGENTS.md 要 install.ps1 重跑(或手拷)。验:①「王姐预算改到45万」
→ 档案字段变;②「记住王姐家别提上一家装修公司」→ 备注追加带日期;③「王姐什么
偏好来着」→ 先读档案再答;④「万科城开始量房了」→ 阶段推进+播报"从洽谈进到量房"。
