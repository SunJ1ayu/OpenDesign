# Verify: opendesign-client-tools

- Date: 2026-07-17
- Verdict: **PASS**

## Mechanical checks

- [x] pytest 全套 315 passed + 7 skipped;test_ds_tools 120/120(新 13 用例先红后绿)
- [x] 突变红检 2/2(白名单校验注 → uc05 红;sanitize 去除 → uc07 红;已还原复绿)
- [x] resolver eval 实跑 19/19 ALL PASS(暗区探针翻转 → read_client 命中;
      update_client 两条新说法命中)
- [x] no secrets / unsafe ops(纯 stdlib,_resolve 咽喉复用,无新写出面)
- [x] PANEL_ORACLE_CMD 前置:test_ds_tools rc=0(panel 发出前)

## Review

- lane: **full**(主审 + submimo + subsense-agent + subglm;GLM 走火山方舟
  chat 腿 glm-5-2-260617——当天刚修好,首战真卷)
- 主审先行:/root/aiwork/tasks/opendesign-client-tools-review-my-review.md
  (仓外,panel 发出前落盘)= PASS + 3 nit
- 三家结论:submimo **PASS** / subsense **PASS**(内容完整核了注入面/路径闸/
  白名单/锁语义+13 测试逐条对应;结尾写中文「结论: PASS」被 wrapper verdict 闸
  误判 rc=1——纯 gate 假阴性,复发工具债,见 follow-ups)/ subglm **PASS** + 2 LOW

### findings 仲裁(全部核过代码)

| 来源 | finding | 裁定 |
|---|---|---|
| 主审+submimo 同标 | exists→locked_rw TOCTOU 窗口(删文件竞态裸抛) | 记录不改:append_change/log_communication 同款既有模式,盲评队列⑤ M4 预存基建债,非本 diff 引入 |
| subsense | `[::]` 字符类可读性 | 拒:有意匹配半/全角冒号(手建档案兼容),功能中性,subsense 自己也标"良性" |
| subglm LOW#1 | re.compile 在锁内 | 拒:compile 在 else 分支=只有替换路径才编译(备注路径不浪费);编译µs级,锁是单进程 MCP per-file,无争用影响 |
| subglm LOW#2 | 空文件+备注自建产生行首空行 | 记录不改:核实为真(lines=[""] 时残留空行),纯外观;create_client 建的档案恒有 H1,不可达;GLM 自己也判"无需修" |

- 无任何一家抓到主审漏掉的需改缺陷;主审 3 nit 中 TOCTOU 被 submimo 独立
  复现=交叉验证。零代码改动出 panel。

## 顺路评估(审计空格③)

index.md 挂行:create_client 本来不写 index,新工具也不碰——维持"记债不排队"。

## Accepted deviations

- 错误优先级:bad_field 先于 client_not_found(白名单是纯函数校验,先拒最便宜的;
  uc08 锁的是合法字段的 not_found 路径)。
- 全角冒号字段行被替换后归一为半角 `: `(轻微规范化,手建档案兼容代价)。

## Follow-ups(不阻塞)

- subsense wrapper verdict 闸不认中文「结论:」——Track B 已见过一次,本次复发,
  该在 subsense-agent 的 verdict grep 加 `结论[:：]`(工具债,记 review-tooling 队列)。
- 用户验收断点:git pull → start.ps1 stop → start.ps1(重启 gateway=新工具注册)
  → 回显 **0.22.0**;AGENTS.md 两行工具表要 install.ps1 重跑(或手拷 workspace/
  AGENTS.md)才对运行 agent 生效。验:①「王姐预算改到45万」→ 档案字段变;
  ②「记住王姐家别提上一家装修公司」→ 备注多一条带日期;③「王姐什么偏好来着」
  → 读档案回答不臆造。

## ⚠️ Erratum(同日 set-stage panel 揭穿)

上表「subsense `[::]` 字符类可读性 → 拒:有意匹配半/全角冒号」的拒绝依据**是错的**:
实际文件里两个冒号都是半角 0x3a(全角字面量在混排输出中被打成了半角),全角冒号
从未被支持。set-stage panel 两家(submimo+subsense)独立指出后经字节级核实成立,
已在 set-stage track 修复:两处正则改 `[:：]` 显式转义 + ss08/uc10 先红后绿。
教训:①中文全角标点进代码一律用 \uXXXX 显式转义,字面量必须 hexdump 验证;
②仲裁"拒"一个 finding 时,依据要核到字节,不能核到"我记得我是这么写的"。
