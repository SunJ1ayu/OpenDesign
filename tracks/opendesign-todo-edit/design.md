# Design: opendesign-todo-edit

- Change: opendesign-todo-edit
- Status: draft (v2 — 合并 sub-Claude 评审)

> 评审:独立 sub-Claude 冷读评审 = GO-with-changes;主 agent 仲裁后采纳其"独立 `## 变更历史`
> 段"替代方案(消除 BLOCK-1)+ BLOCK-2/3 + NIT。评审日志见对话;主 agent 为最终仲裁者。

## Approach（v2:留痕/备注放独立 `## 变更历史` 段,按 C 编号挂钩）

**关键改动(相对 v1 子行方案)**:留痕/备注**不插在变更行正下方**,而是放进项目 .md 的一个
**独立 `## 变更历史` 段**,按 `C编号` 挂钩:
```
## 变更记录
- [进行中] C3 2026-07-15 【客厅】改地板为鱼骨拼      ← edit 只改这条的正文尾段
- [待确认] C4 2026-07-15 主卧加衣柜

## 变更历史
- C3 改于 2026-07-15｜原:改地板为人字拼              ← 留痕(按 C3 挂钩)
- C3 备注:业主看了样板间后改主意                     ← 备注(按 C3 挂钩)

## 沟通日志
…
```
**为什么这样**(sub-Claude 评审 BLOCK-1,已核实 ds_tools.py:124-128):agent 每记一条新需求
都走 `append_change`,它的插入锚点是"`## 变更记录` 段内最后一条变更行之后"。若把留痕子行插在
变更行正下方,`insert_at=last_change+1` 会把新变更插进"上一条变更与其留痕之间"=**把留痕嫁接到
错的变更**,污染审计线索,恰打穿"防扯皮"立项目的。独立 `## 变更历史` 段让 `append_change` 的扫描
边界(line 122:遇下一个 `## ` 即止)天然停在 `## 变更历史` 之前 → **append_change / set_change_status
一行都不用动、逐字节不变**,风险从"改 agent 热写路径"降为"只新增 edit 面"。

- `## 变更历史` 条目以 `- C{n} …` 起头,**不匹配 CHANGE_RE**(要求 `^- \[状态\]`)⇒
  parse_change/collect/_max_change_num 全部无视 ⇒ 不成待办、不参与编号、零迁移。
- `_field`/`_title` 只吃头部 `- 名:值` 固定字段名,`- C3 改于…` 不被误取。
- agent `read_project` 读全文 → `## 变更历史` 是它的上下文(有益)。

**写路径**:前端 → POST `/api/changes/edit`(受控针孔,**精确匹配**) → `ds_tools.edit_change` →
_resolve 名字闸 → `ds_common.locked_rw` 锁内保格式改写。只读铁律的又一受控开口,posture 抄
open-folder(ds_web.py:492-495)/session-delete(541-544):`Content-Type==application/json` 强制
preflight 拦跨站、body 键白名单、trace 不进响应体;Host 闸由 do_POST 入口继承(ds_web.py:248)。

**edit_change(project, cnum, new_status?, new_text?, note?) 语义**:
1. `_resolve(projects, project)` → 名字闸 + realpath;`locked_rw` 锁内读改写。
2. 按 `C{cnum}` 在 `## 变更记录` 段定位主变更行(复用 set_change_status 定位:CHANGE_RE 命中且
   cnum 相等);找不到 → `{"error":"change_not_found"}`。
3. new_status:校验 ∈ STATUSES(否则 `invalid_status`),只改主行 `[状态]` 段。
4. **new_text(BLOCK-2)**:`sanitize_field(new_text)`(折换行,**不 ban 竖线**——与 append_change
   同字符集,ds_tools.py:98)。空 → `empty_text`。**不从 parse_change 字段重拼主行**,用前缀捕获正则
   `^(- \[状态\](?:\s+C\d+\b)?(?:\s+\d{4}-\d{2}-\d{2})?\s*(?:【[^】]*】\s*)?)(.*)$` 只 `sub` group(2),
   保证状态/C号/日期/【空间】前缀**逐字节不变**。若 new_text==旧 → no-op,不写留痕(避免 `原:X`==新值噪声)。
   否则向 `## 变更历史` 追加 `- C{n} 改于 {today}｜原:{旧正文}`(段不存在则先建,置于 `## 变更记录`
   段之后)。
5. note:`sanitize_field`(折换行,不 ban 竖线)。`## 变更历史` 段内**该 cnum 已有 `备注:` 条**则替换,
   否则追加 `- C{n} 备注:{内容}`。**按 cnum 键定位**(BLOCK-3:非位置扫描,不会串改邻条)。
6. `bump_last_updated`(复用)。返回 `{"ok":true, cnum, ...}` 或 error。

**changes 端点扩展**:解析 `## 变更记录`(现状)+ 解析 `## 变更历史`(按 cnum 分桶),join 输出
`{cnum, status, date, space, text, note?, history:[{date, old}]}`。隔离天然由 cnum 键保证。

**前端**:TodoPage 行加轻量编辑态——状态点选、正文内联可编、备注输入;改过显"改过 · 看原文"
(悬浮出 history);成功后 bump dataEpoch(M5)即时刷新。**工作台可见行为与 v1 承诺一致**(照样
"底下能看到原文/备注"),只是底层落在 `## 变更历史` 段、前端按 cnum 聚合到该条下展示。

## Key trade-offs / risks

- **打破只读铁律**:第一个写内容口。控制=单一受控**精确匹配**针孔 + 保格式 + 锁 + 名字闸 + CT/键白名单;
  verify full lane 三审。
- **v2 消除了 BLOCK-1**:代价=raw .md 里留痕不再物理紧贴变更行,而在 `## 变更历史` 段。对"渲染展示 +
  扯皮时翻记录"的实际用途无损(前端按 cnum 聚合展示;raw 文件里 `- C3 原:…` 一样可指认)。
- **BLOCK-2**:改正文只替换文本尾段、绝不重拼主行,守住"agent 与工作台共用的同一主行逐字节稳定"。
- **留痕经工具口径不可绕**:唯一改正文的路径是 edit_change,先写历史后改文;手改文件绕过=v1 非目标。
- **段生命周期**:edit_change 需在 `## 变更历史` 缺失时创建它(置于 `## 变更记录` 段后、`## 沟通日志` 前),
  不得破坏 append_change 的段边界。← 实现要点 + oracle。

## Alternatives considered

- **v1 子行(变更行正下方)**:raw 邻接感好,但强制改 append_change 锚点(agent 热写路径,BLOCK-1)。
  仲裁:改为独立段,把危险从"守住热写路径"降为"不碰热写路径"。若用户重视 raw 文件邻接可回退 v1
  (须 append_change 锚点修复 + 红检)。
- **独立 audit.log 文件**:分离干净但历史不在项目记录里=扯皮时不可见,且多一处存储。否决。
- **行内字段 `｜备注:` / 备注并入正文**:改 CHANGE_RE 或污染业主原话与批注。否决。
- **覆盖不留痕**:用户明确要留痕。否决。

## Test strategy (oracle) —— 主 agent 拥有,先红后绿

1. **改状态**:主行状态变、cnum/date/space/text 原样、页脚 bump。
2. **改正文·前缀字节不变(BLOCK-2)**:改带【空间】变更正文后,`- [状态] C{n} {date} 【空间】` 前缀
   逐字节==原值,仅尾段变;`## 变更历史` 多出 `- C{n} 改于…原:<旧>`。
3. **改正文·no-op**:new_text==旧 → 不写历史行(无 `原:X`==新值噪声)。
4. **多次改正文**:累积多条 `- C{n} 改于…` 历史,顺序合理;parse_change 对该 .md 仍只解析出原变更数。
5. **加/改备注**:`- C{n} 备注:` 追加/替换;parse_change 数不变。
6. **子行/历史段不成待办**:含 `## 变更历史` 的 .md,collect 未办结数==仅按 `## 变更记录`;
   `## 变更历史` 段任何行都不进 open/stale。
7. **多变更隔离(BLOCK-3)**:两条变更各带 history+note,改/读 C2 不动 C5(按 cnum 键)。
8. **append_change 逐字节不变(BLOCK-1 反向锁)**:对已含 `## 变更历史` 段的项目 append 新变更 →
   新行落在 `## 变更记录` 段内、`## 变更历史` 段**原封不动**;两次 append 产物与无历史段时逐字节相同。
9. **set_change_status 不受影响**:对带历史的变更改状态,只主行状态变,`## 变更历史` 段不动。
10. **非法**:未知 cnum→change_not_found;非法 status→invalid_status;空 new_text→empty_text。
11. **段创建**:无 `## 变更历史` 段的旧项目首次 edit → 正确建段(位置对,append 段边界不破)。
12. **针孔安全**:`/api/changes/edit` 精确匹配(非前缀,防走私);CT 非 json→400;body 超限→400;
    缺 cnum→change_not_found;其余未白名单 POST 路径仍 405(补不变量测试);Host 闸继承。
13. **真 ds_web roundtrip**:POST 编辑 → GET changes/todos 见新值 + 历史。
14. **前端 mjs**:编辑态纯函数/请求装配。
oracle:`python3 -m pytest tests/ -q` 全绿 + 4 mjs rc=0;verify full lane 三审。
