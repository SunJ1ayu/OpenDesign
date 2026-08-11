# Design: opendesign-note-clear

- Change: opendesign-note-clear
- Status: draft

- 规划双出: 触发(写口语义扩张:`note=""` 从"没给"变成"删数据",且 lane=full)。
  主 agent 方向先落盘于本文件(commit 后再读第二版),`gpt-5.6-sol` 独立出一版,
  日志 `/root/aiwork/logs/note-clear-plan-sol.log`,差异折叠进「Alternatives / 双出对差」。

## Approach

三层各修一处,契约统一成一句话:**`note` 缺省 = 不动;`note` 给了空串 = 删掉这条备注。**

1. **核心 `bin/ds_tools.py::edit_change`**
   `if note_s:` → `if note is not None:`,空串(含纯空白,`sanitize_field` 后为空)
   走新的 `_remove_note(lines, num)`:在 `## 变更历史` 段内按 `^- C{num} 备注[:：]` 定位
   并删行(与 `_upsert_note` 同一条正则、同一处定义,防两侧漂移)。
   - **没有备注可删 = 纯 no-op**:不置 `changed`,`box["write"]=False`,文件逐字节不动、
     页脚不 bump(与既有"改成同样的正文不留痕"同一条 no-op 契约)。
   - 删空之后**不清理 `## 变更历史` 段本身**(段里还可能有 `改于…` 留痕;空段留着,
     与 `_create_history_section` 的建段时机保持互补,不引入"删到最后把段也删了"的新形状)。
2. **`web/src/todo.ts::buildEditRequest`**
   `if (n && n !== originalNote.trim())` → 去掉 `n &&`,只留 `n !== originalNote.trim()`。
   于是:清空(原来有备注)⇒ 带 `note: ""`、`dirty=true`;两边都空 ⇒ 仍返回 `null`
   (既有断言不变,不产生无谓写)。
3. **`web/src/TodoPage.tsx::save`**
   乐观回显 `setNoted` 收到 `req.note === ""` 时**删键**,而不是存空串 ——
   否则行上会渲染出一个空的「备注:」标签(`note !== undefined` 才渲染)。
   工作区那侧(`ChangesColumn`)以服务端为真相源、保存后整列重拉,`note` 键消失即不渲染,
   无需改动。

## Key trade-offs / risks

- **删除不留痕**:清掉的备注不进 `## 变更历史` 的 `改于…` 行,删了就没了。
  理由:备注本来就是可覆盖的便签(现在"改备注"也不留痕),这一单不扩张语义;
  真要回收站是另一单(与 `delete_change` 那套软删同形)。**风险**:业主误删无从找回 ——
  可接受,因为备注是他自己刚打的字,且正文/状态不受影响。
- **`note=""` 复用成"删"**:与 `/api/refs/update` 的既有先例一致(那里空串早就是清空),
  不新增 `clear_note` 参数。风险是"缺省 vs 空串"这条区别全靠调用方守住 ——
  web 层 `_edit_change` 已经是 `body.get("note")`(没给 = `None`),天然分得开。
- **删行的定位正则**:`^- C{num} 备注[:：]`,`C1` 不会误伤 `C12`(后面是数字不是空格)。
  判据里放一条邻居锚断言(C1 与 C12 各有备注,清 C1 不许动 C12)。

## Alternatives considered

- 新增 `clear_note: true` 参数:更显式,但要动写口白名单 `_EDIT_ALLOWED_KEYS`
  = 扩写口面,且与 refs 那侧的既有约定分裂成两套语言。不选。
- 清空时写一条 `- Cn 备注删于 …` 留痕:多一种历史行格式,读侧 `parse_history` 也要跟着改,
  为一个便签字段付的代价过高。不选(留给"备注回收站"那一单)。

## Test strategy (oracle)

主 agent 亲写,执行腿逐字节 off-limits。三层各有判据,**红检先行**:

1. **核心(pytest,`tests/test_ds_tools.py::EditChangeOracle`)**
   - `note=""` 清掉该 cnum 的备注行;变更主行**逐字节不变**;`parse` 出的变更数不变;页脚 bump。
   - 纯空白 `"   "` 同样按清空处理(与前端 trim 口径一致)。
   - **邻居锚**:C1/C12 各有备注,清 C1 后 C12 的备注一字不动。
   - **无备注可删 = 文件逐字节不动**(no-op,不 bump 页脚),且仍回 `ok`。
   - 回归锚:`note="新内容"` 仍是 upsert 替换(既有 `test_e05` 不许退化)。
2. **前端纯逻辑(`node --test tests/test_workbench_p4.mjs`)**
   - 原备注非空 + 草稿清空 ⇒ `{project, cnum, note: ""}`;
   - 两边都空 ⇒ `null`(既有断言原样保留,防"为了修这个把 no-op 也发出去")。
3. **e2e(真 chromium + 真 ds_web,`tests/e2e/ws_change_note.e2e.mjs` 加两组)**
   - **G(工作区)**:清空备注框 → 保存 → 行上 `.note-tag` 消失 **且磁盘那行没了**。
   - **H(待办页)**:同一条上先写备注(tag 出现)→ 再清空保存 → **tag 整个消失**,
     不是留一个空的「备注:」—— 断言 `.note-tag` count === 0(不是断言文本为空)。

**这个 oracle 能被什么骗过?**

- 三层判据全绿、业主眼里仍然错的最可能形状:**他清空后点的不是「保存」而是 Enter/失焦**,
  或者他改的根本是**参考图备注 / 收件箱备注**那条路。判据只覆盖 `.btn-save` 这条路,
  Enter 键在待办页走 `save(it)`(同一函数)、工作区 Enter 也走 `saveEditText`,所以路径同源;
  但**"他到底点的哪个框"只有真机能答** ⇒ 交付时请他按原动作复验一次(验收清单一条)。
- 另一形状:e2e 只断言 `.note-tag` 消失,**不能证明页面刷新后仍然没有** ——
  待办页那个 tag 本来就是会话级的。所以 G 组用**磁盘内容**做锚(刷新后的真相源就是它),
  H 组只管"空标签不许出现"这一件事,别让它冒充持久化证据。
- 还有一形状:核心判据用 `_write_project` 造的档案是**理想格式**(备注行紧跟段头)。
  真档案里备注行可能夹在若干 `改于…` 行之间 ⇒ 判据里的 fixture 要**故意把备注行放在
  留痕行中间**,不然"只会删段内第一行"这种实现也能全绿。
