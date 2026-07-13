# Proposal: opendesign-hardening

- Date: 2026-07-13
- Status: open

## Goal

一次性还清 07-13 两轮全库盲评(sub Claude 第一性 + 主审仲裁)合并修复队列 ①–④:
2 HIGH(写侧名字双真相 H1 / DNS rebinding H2)+ 体验 MEDIUM(M2/M5/L3)+
健壮性 MEDIUM(M1 坏编码全灭)+ 文档与测试契约批(M3/L1/L7 + R2 全部)。

## Motivation

盲评报告 = `/root/aiwork/logs/opendesign-fullrepo-blindreview-20260713.md`
(首轮 07-13 + 第二轮补五块,主审逐条仲裁全成立)。用户拍板"看完一起修"。
H1 会让落盘数据永不显示(静默丢活),H2 让恶意网页读全部业主档案——
都便宜且要害;其余按队列序一并清掉,避免碎片化多轮。

## Scope

- in ①: H1 ds_tools 写入口复用 ds_workspace.PROJECT_NAME_RE 拒 `/ \`;
        H2 ds_web Handler 入口 Host 白名单(127.0.0.1:port / localhost:port)否则 403
- in ②: M2 文件枚举与文件服务字符集双真相收敛(`#` 列得出 404);
        M5 turn_end bump dataEpoch(变更列/待办角标/项目列表免 F5);
        L3 SearchPanel 过滤 unregistered 项目(白打 404)
- in ③: M1 collect() 逐文件 try + errors 字段,改钉"坏一个不影响其余"
- in ④: M3 link_ref 存在性检查走 _resolve;L1 preset 解析抽共享 helper;
        L7 部署 AGENTS.md 工具表 space 参数(核实后);R2-M1/M2+L2/L3/L4
        refs SKILL.md 文档批;R2-M3 冒烟 SKIP rc=0→exit 3;R2-L1
        --border-light→--border-soft;R2-L5 apply 复验补嵌套重跑;
        R2-L6 冒烟断言收窄+schemaVersion;L8 add_style 锁内复查(顺手)

## Non-goals

- M4 locked_rw 非原子写(Windows 锁挪 sidecar,单独 track)
- start.ps1 版本比对自动重启(等用户确认 0.8.0)
- R2-L7 记债:connection.ts 8765 硬编码 / App.tsx limit 固化 / 429 未记载
- L2 口令 argv、L4 键盘可达、L5 start.ps1 杀前验进程名、L6 add_style 末节假设(首轮已定缓)
