# Tasks: opendesign-key-onboarding

- base-ref: 9a641d24d48c8e598a363c61b46c0166ccb1b24f

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 已完成(判据先行 → 实现 → 红检,每步单独 commit)

- [x] **T1 凭据模块 + 外壳启动计划** —— `bin/ds_credential.py`(只收不读/只落一处/
      变量名从配置读/报错不带入参)+ `ds_shell_core` 起停计划改成
      「ds-web 无条件起、网关有 key 才起」(design 对差异 #2)。
      判据 `f5e37eb` 先行 → 实现 `1860c38` 14/14 → 红检 `df426ba` 9 变异 9 咬住 0 漏网。
- [x] **T2 两个接口 + 来源检查 + 口令代签** —— `GET/POST /api/llm/credential`、
      `_same_site_ok`(双向验,不带 Origin 的 curl 照常放行)、`_proxy` 在前端没带
      Authorization 时用 `_gateway_password()` 替它签(前端从此不必持有口令)。
      判据 `dd6fb09` 先行(11 条 10 红) → 实现 `5acf226` 12/12 →
      题面加强 `89ca1e7`(代理不再是「纯管道」,断言改强 + 给这份判据加隔离)。
- [x] **T2.5 全量回归** —— `89ca1e7` 上 node 350 / python 1197 / MCP 契约 / dist 新鲜度
      全绿,e2e 34 PASS 0 FAIL;收据在 `evidence/20260815T152602Z-01-regression-http-v2.txt`。
      ⚠️ **rc=3 不是通过**:2 条 e2e 因为没带 `--with-gateway` 是 SKIP,收口前要补跑。

## 待办

- [ ] **T3 外壳重启通道**(主 agent 自己写,涉及 IPC 与进程管理)。
      今天 `ds_web.ds_shell_bridge_restart()` 是**桩,恒回 `"manual"`**(:171)——
      诚实但没接通。按 design 第三节:给外壳单实例锁端口(`ds_shell.py:LOCK_PORT=18788`)
      **已有的唤醒握手**加一条 `restart-backend` 消息,**不新开端口、不新造 IPC**。
      没有外壳的形态(git-pull 那两台)通道连不上 ⇒ 仍如实回 `manual`,不假装成功。
      > 判据先行,且必须双向验:接得上→`restarted`,接不上→`manual`。
      > 🔴 **「真的重启完还能聊天」判据答不了**(design 骗法三)⇒ 进真机清单,别在这声称。
- [ ] **T4 前端模态框**(派 codex 腿;oracle 我先写并单独 commit)。
      一个组件两个入口(首次打开 / 设置里),选厂商 → 填 key → 保存;
      **key 只写不回显**(HTML/aria/console 都不许出现原文);
      `connection.ts` 拿掉手输口令那条主路(**保留为兜底**,代签失败时仍可手输)。
      前端读 `restart` 字段决定说哪句话(`manual` → 「配置好了,请重启一下程序」)。
- [ ] **T5 收口** —— 收货三闸(diff/亲跑/亲读)→ 全量回归**带 `--with-gateway`**
      (把 T2.5 那 2 条 SKIP 变成真跑)→ **lane=full 四审** → verify.md 落主裁判决 →
      bump 版本 + 真机清单 → push → 归档。
      > 真机清单必须写的两条:**key.txt 权限在 Windows 上是 ACL 语义,本单不声称文件级隔离**;
      > **重启后真能聊天**只有真机能答。
