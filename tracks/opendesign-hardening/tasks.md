# Tasks: opendesign-hardening

- base-ref: 68651f790790864a65b80730960c27285ee8cf1f

> 全部先红后绿:每条修复先写失败测试(oracle)见红,再窄范围实现转绿。
> 报告 = /root/aiwork/logs/opendesign-fullrepo-blindreview-20260713.md(含仲裁与队列)。

- [ ] T1 队列①-H1:ds_tools 四个写入口(create_project/create_client/append_change/
      set_change_status)复用 ds_workspace.PROJECT_NAME_RE 拒 `/ \`;oracle 红检
      `a/b` → error(不落盘),存量合法名回归不受影响
- [ ] T2 队列①-H2:ds_web Handler 入口 Host 校验(∈ {127.0.0.1:PORT, localhost:PORT,
      [::1]:PORT} 否则 403);oracle 红检伪 Host → 403、正常 Host 全端点回归绿
- [ ] T3 队列②-M2:文件枚举 _scan 与文件服务 _REFS_PATH_RE/_SUB_RE 字符集收敛为
      同一真相源(列得出必服务得到);oracle 红检 `12#1802-客厅.jpg` 列出且 200
- [ ] T4 队列②-M5+L3:前端 turn_end → dataEpoch bump(变更列/待办角标/项目列表
      免 F5);SearchPanel 跳过 unregistered 项目;mjs oracle + 手动/e2e 验证
- [ ] T5 队列③-M1:collect() 逐文件 try + errors 字段;test_ds_web.py 的"坏文件
      → 500"契约改钉"坏一个不影响其余"(先红后绿)
- [ ] T6 队列④杂项批:M3 link_ref 存在性走 _resolve(红检 `../index`);
      L1 preset 解析共享 helper;L7 部署 AGENTS.md space 参数(核实);
      R2-M3 冒烟 SKIP → exit 3;R2-L1 --border-light→--border-soft;
      R2-L5 apply 复验补嵌套重跑(红检伪造嵌套 plan 零执行);
      R2-L6 冒烟断言收窄+schemaVersion;L8 add_style 锁内复查;
      R2 文档批:refs SKILL.md(link_ref 只写索引/file_not_found↔path_escape
      映射/_tool 后缀/add_ref file 口径)+ vocab 模板措辞
- [ ] T7 收口:全套件 py+mjs 绿;e2e 真 gateway(H2 改动过代理必跑);
      VERSION bump 0.8.1;verify.md 按 full lane(安全改动)走 panel-review
