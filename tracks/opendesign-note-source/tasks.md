# Tasks: opendesign-note-source

- base-ref: dd05720（起 track 那笔；实现基线以判据 commit 为准）

> 派给 `delegate-codex --model gpt-5.5`(verify 里写了理由)。主 agent 先写判据并单独
> commit,判卷文件对它 off-limits(`--protect` 全列);起端口的两层(HTTP/e2e)由主 agent
> 当测试机亲跑,失败输出原样退回,**有界 2 轮**,不绿收回自己修。

- [x] T0 规划双出(`gpt-5.6-sol`,禁读本目录)→ 抓到 4 条我原方案的错
      (状态假 bump / 改过假标记 / 覆盖窗口变大 / 同源相等题是假绿)→ 已折进 design
- [x] T1 判据:`test_ds_todo.py` —— collect 带 note(**写死具体值**)、无备注不带键、
      留痕行夹缝、邻居 cnum、**跨项目同号不串**、残缺行不认领
- [x] T2 判据:`test_ds_tools.py` —— `changed_fields` 四条(全同值 `[]`/只改备注/只改状态/
      **状态同值不 bump**)+ 归一算真改动 + 清空后 collect 读不到
- [x] T3 判据:`test_ds_web_api.py` —— `/api/todos` 带 note(具体值);三态分得开
      (缺键=不动 / `""`=删 / `null`=400 且零写入,三个字段各一条);响应带 `changed_fields`
- [x] T4 判据:`test_workbench_p4.mjs` —— 六条旧断言逐条换成更强的(对照表在 design)、
      删 `originalNote` 参数、`draft={}` 也返回可寻址请求;`test_todo_batch.mjs` 同值项也进请求
- [x] T5 判据:e2e I 组 —— I1 冷启动(最强)/ I2 刷新 / I3 清空后刷新 / I4 跨面一致
- [x] T6 红检:`redcheck` 退回实现跑判据,**必须红**,且红在目标断言上;
      六条被推翻的旧断言要能看出"新断言在旧实现下红"
- [x] T7 判据单独 commit(不夹带实现)
- [x] T8 攻自己的题(`--attack-log`,落**仓外**)→ 才能派活
- [x] T9 实现(派 codex gpt-5.5):
      ① `ds_todo` 收编 `## 变更历史` 读模型(含写侧锚)+ `collect` 带 note;
      ② `ds_tools` 改用新家的锚、`new_status` 同值比较、返回 `changed_fields`;
      ③ `ds_web` `_changes` 改调新家、`_edit_change` 三态分辨 + 透传 `changed_fields`;
      ④ `todo.ts` `buildEditRequest` 只装配碰过的字段(删 `originalNote`)、`batchEditRequests` 不跳同值;
      ⑤ `api.ts` 类型 + `editChange` 回 `changed_fields`;
      ⑥ `TodoPage.tsx` 删 `noted`、draft 只记碰过的、`edited` 以 `changed_fields` 为准;
      ⑦ `ChangesColumn.tsx` 同样改成"碰过才发"
- [x] T10 收货三闸:① `--receive`(diff+status 双空)② 主 agent 亲跑 ③ 亲读 diff
      (**特别读 `save()` 的全部提前 return**,纯函数判据照不到那儿)
- [x] T11 **build 出 web/dist 并入库**(ds_web 服务的是 dist)
- [x] T12 亲跑 `tests/run-all.sh` + 本单 e2e;bump `VERSION` 到 0.84.0
- [x] T13 真机验收清单加一组(冷启动看备注 / 换台电脑 / 挑一条**很久以前**写的备注)
- [x] T14 verify lane=full(panel-review)→ 主裁 → 归档
- [x] T15 backlog:把"待办页备注不是档案来源"标成已解决,**另外三条一个字不动**

## 收口记账(照工件数,不写序号账)

- 攻题**四轮**(r1–r4 有料,r5 只回了"没有。"、日志 9 字节 ⇒ 记作没给裁决),
  汇编在 `/root/aiwork/logs/note-source-attack-all.log`。
- 执行腿 codex gpt-5.5:**返工 0 轮,自身错误 0 处**;它报回来的那处冲突根因在我的判据。
- 四审 2/4 腿给了裁决(submimo / subdeepseek,均 PASS);subglm=off、subkimi 额度挂。
- 主 agent 自审抓到 3 条(M1–M3),四审抓到 4 条(F5–F8),攻题抓到 4 条(F1–F4)。
- 判据五笔全部先于对应实现入库:`c5855d9` / `6988bc7` / `3fe3aba` / `6b41e58` / `8f2737c`。
