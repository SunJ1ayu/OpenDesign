# Tasks: opendesign-owner-review-0808

派给: 主 agent 写 oracle + 判据先行提交;**实现最终也是主 agent 直接干**(原定
codex/gpt-5.5,开工时改判 —— 理由写在 verify.md 的「派给」格里,不在这儿抄第二遍)

- [x] T0. oracle 先行:按 design.md「Oracle」段,写好全部新判据(python 4 类 + mjs 1 类),
      跑一遍确认全红(功能还没实现),**单独 commit**,不与后面任何实现改动同一个 commit。
      → commit `b8e5114`。
- [x] T1. AGENTS.md 规则 A(建档前先核对)+ 规则 B(工具做不到必须先问)—— 纯文档改动,
      主 agent 直接写,不用外包。→ commit `582ddea`。
- [x] T2. 后端:`bin/ds_tools.py` 新增 `delete_change`(`已删除` **不进** `STATUSES`,
      只有这个专用出口能写 —— 见 design.md 更正后的那一条 + `test_dc06`);
      `bin/ds_todo.py` 的 `STATUS_WORDS`/`CHANGE_RE` 同步加 `已删除`。
- [x] T3. 后端:`bin/ds_tools_server.py` 注册 `delete_change` 为 MCP 工具;
      `workspace/AGENTS.md` 工具表补一行说明。**agent 侧仍须先复述内容得到确认再调**
      —— 前端那个确定/取消弹窗只覆盖网页点按钮这条路径,agent 走 MCP 聊天路径时
      根本没有前端弹窗,纪律同 `delete_project`。
      > (2026-08-08 四审 DeepSeek 指出:这条原来写的是"会弹前端二次确认,agent 只管
      > 调工具,不用自己再问一遍" —— 那是基于"前端确认能覆盖 agent 路径"的错误假设。
      > 实现选了更安全的一侧(AGENTS.md 与 MCP docstring 都要求 agent 先复述确认),
      > 是这份任务书的表述错了。)
- [x] T4. 后端:`bin/ds_web.py` 新增 `POST /api/changes/delete`(对齐 edit/add/due 三个
      现成写口的写法),`_changes` 端点过滤掉 `已删除` 状态的行,行内注释同步更正。
- [x] T5. 前端:`web/src/api.ts` 加删除请求封装;`TodoPage.tsx` 加删除按钮 +
      `window.confirm` 确认/取消弹窗,确定后调接口并 reload。
      (`web/src/workspace/changes.ts` 最终**没动** —— 它是纯计数/分组逻辑,
      已删除的条目在更上游的端点就被过滤掉了,到不了这一层,不用改。)
- [x] T6. 全量跑判据:`tests/run-all.sh` 总跑,收据进 evidence/(见 verify.md)。
- [x] T7. 收货三闸(diff / 亲跑 / 亲读)+ full 四审 → 三腿(MiMo/DeepSeek/Kimi)
      全 PASS,GLM 那条腿是 off;四审抓到的 4 条见 verify.md findings。
- [x] T8. verify.md 收口,版本号 bump(ds-web),挂在本 track 下(track-guard 会查)。
      **留给主 agent** —— 本轮执行方不下最终裁决、不 bump 版本、不归档。
      ✅ **08-10 回勾:08-08 当天就做完了** —— `51a0668`(主裁修 + bump 0.81.0)、
      `73da804`(主裁 PASS 收口),只是清单没勾。

## 备注

T0 与 T1 是主 agent 亲自做的部分(判据+纯文档),T2–T5 原计划按 delegate 抽屉的分层
规则派给执行腿,开工时改判成主 agent 直接干(理由在 verify.md「派给」格)。
