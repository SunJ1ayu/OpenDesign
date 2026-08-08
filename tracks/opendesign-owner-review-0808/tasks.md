# Tasks: opendesign-owner-review-0808

派给: 主 agent 写 oracle + 判据先行提交;实现派 codex(gpt-5.5),我验收(见 delegate 抽屉)

- [ ] T0. oracle 先行:按 design.md「Oracle」段,写好全部新判据(python 4 类 + mjs 1 类),
      跑一遍确认全红(功能还没实现),**单独 commit**,不与后面任何实现改动同一个 commit。
- [ ] T1. AGENTS.md 规则 A(建档前先核对)+ 规则 B(工具做不到必须先问)—— 纯文档改动,
      主 agent 直接写,不用外包。
- [ ] T2. 后端:`bin/ds_tools.py` 加 `已删除` 到 `STATUSES` + 新增 `delete_change`;
      `bin/ds_todo.py` 的 `STATUS_WORDS`/`CHANGE_RE` 同步加 `已删除`。
- [ ] T3. 后端:`bin/ds_tools_server.py` 注册 `delete_change` 为 MCP 工具;
      `workspace/AGENTS.md` 工具表补一行说明(设计师说"删除这条待办"时用,会弹前端
      二次确认,agent 只管调工具,不用自己再问一遍"确定吗")。
- [ ] T4. 后端:`bin/ds_web.py` 新增 `POST /api/changes/delete`(对齐 edit/add/due 三个
      现成写口的写法),`_changes` 端点过滤掉 `已删除` 状态的行,行内注释同步更正。
- [ ] T5. 前端:`web/src/api.ts` / `web/src/workspace/changes.ts` 加删除请求封装;
      `TodoPage.tsx` 加删除按钮 + 确认/取消弹窗,确定后调接口并从本地列表移除该条。
- [ ] T6. 全量跑判据:T0 的判据全绿 + 现有 python(pytest)/mjs(tests/e2e 或对应跑法)
      回归不劣化,总跑汇总(不是单挑几个)。
- [ ] T7. 收货三闸(diff / 亲跑 / 亲读)+ full 四审(碰了新写口,针孔再薄也不打折,
      见主 CLAUDE.md 硬规矩)。
- [ ] T8. verify.md 收口,版本号 bump(ds-web),挂在本 track 下(track-guard 会查)。

## 备注

T0 与 T1 是主 agent 亲自做的部分(判据+纯文档),T2–T5 是实现,按 delegate 抽屉的分层
规则路由(当前默认档在抽屉里,不在这里复述)。T2–T4(后端+新写口)与 T5(前端 UI)
可以拆两次派活,也可以一次派完——由执行时的实际情况定,不预先锁死。
