# Design: opendesign-note-source

- Change: opendesign-note-source
- Status: draft

- 规划双出: 触发(动档案读侧的共享层 + 写口契约从"动作型"改述为"状态型",
  且这单我自己干)。**主 agent 方向先落盘于本文件并 commit(反锚定),再让
  `gpt-5.6-sol` 对同一份需求独立出一版**(明令不许读本 track 的工件),
  日志 `/root/aiwork/logs/note-source-plan-sol.log`,差异折进「双出对差」。

## Approach

一句话:**备注的真相只有一处(档案文件),"变没变"的判断也只有一处(后端)。**

### 1. 读侧:`## 变更历史` 的解析挪进共享层 `ds_common`

今天 `parse_history` 和那两条读侧正则住在 `bin/ds_tools.py`,而待办页要的载荷由
`bin/ds_todo.py` 产出 —— **`ds_todo` 不能 import `ds_tools`**:`ds_tools` 已经
import 了 `ds_todo`(`bin/ds_tools.py:39`,`list_todos` 直调),反向再连就是环,
`tests/test_no_import_cycles.py` 会红(上一单 `ds_consent ↔ ds_tools` 刚被它抓过)。

所以把 `## 变更历史` 段的**格式知识整块**下沉到 `ds_common`(它本来就是这一层:
页脚锚定、截止日后缀、变更批次正则、字段消毒都在那儿):

- `HISTORY_HEADER` / `HISTORY_EDIT_RE` / `HISTORY_NOTE_RE`
- `history_bounds(lines)`(段边界)
- `parse_history(text)`(读侧,`{cnum: {note, history[]}}`)
- `note_line_re(num)`(**写侧**那条按 cnum 定位备注行的锚)

**写侧的锚也一起搬**,否则就又变成"读侧在 A、写侧在 B" —— 那正是 0.83.0 刚修掉的
病(写侧改第一条、读侧最后一条获胜)。`ds_tools` 的四个写函数
(`_upsert_note`/`_delete_note`/`_append_history_entry`/`_create_history_section`)
留在原地,只是改成用 `ds_common` 的锚;`ds_web:934` 的调用点改成 `ds_common.parse_history`,
**不留 `ds_tools.parse_history` 别名**(一个东西一个名字,别名会让人以为有两份)。

### 2. `/api/todos` 带上持久 `note`

`ds_todo.collect` 里每个 open 条目加 `note` —— 取自 `ds_common.parse_history(text)`
按 cnum 分桶的结果,**与 `/changes` 完全同源**(同一个函数,不是两份解析)。

**约定与 `/changes` 保持一致:有备注才带 `note` 键**(没有就没这个键)。
> 为什么读侧允许"缺席"、写侧不允许:**缺席的歧义只存在于有"动作"含义的地方**。
> 写侧的 `note` 缺席意味着"这次不动它",空串意味着"我要它变成没有" —— 两种意思,
> 所以必须分得开。读侧只有一种意思:**没这个键 = 这条没有备注**。不给读侧发明
> `note: null`,也就不用回答"null 和缺席差在哪"这种自找的问题。

### 3. 待办页:删掉 `noted` 会话映射

`TodoPage` 里 `const [noted, setNoted] = useState<Record<string, string>>({})` 整个删除:

- 显示:`it.note`(服务端来的)有值就渲染 `.note-tag`;
- 编辑预填:`startEdit` 用 `it.note ?? ""`,不再查会话映射;
- 保存后的乐观回显**整段删掉** —— `save()` 末尾本来就调 `reload()`,
  服务端现在带 note,乐观回显是多余的第二个真相源。
- `OpenItem` 类型加 `note?: string`。

业主能看见的变化:**在待办页写的备注,刷新页面、换台电脑打开,都还在**
(今天是刷新就没)。

### 4. 写口:前端不再判"变没变",只描述"你想要的最终样子"

`buildEditRequest` 去掉三处等值比较与 `dirty` 累加,永远返回请求对象:

| 字段 | 今天 | 改后 |
|---|---|---|
| status | 有效且 `!== item.status` 才带 | 有效就带 |
| text | 非空且 `!== item.text` 才带 | **非空就带**(空仍然不带) |
| note | `!== originalNote` 才带 | 给了就带(trim 后) |
| 返回 | 没有任何"改动"→ `null` | 恒为请求对象(cnum 缺失仍 `null`) |

**保留的和去掉的要分清**:去掉的是**"变没变"的判断**(那是后端的活,后端本来就在做:
`new_text_s != old_text` 才留痕、同值备注不 bump 页脚——0.83.0 刚补的);
保留的是**校验**(`cnum === null` 不可寻址 → 不发;正文 trim 后为空是非法输入 → 不带该字段,
因为一条变更不能没有正文)。校验属于前端,判定属于后端。

连带:`save()` / `quickSetStatus()` 里的 `if (!req) …` 分支消失。
点了编辑又原样保存 ⇒ 发一次 PUT ⇒ 后端判定 no-op ⇒ 文件逐字节不动、页脚不 bump、
`write=false` 回来。多一次请求换一处判定,值。

## Key trade-offs / risks

- **我们在推翻上一单刚写下的一条断言**(`test_workbench_p4.mjs`:"两边都空 ⇒ `null`,
  防为了修这个把 no-op 也发出去")。当时那条是对的——因为那时后端还不保证 no-op 不写文件。
  0.83.0 补上"同值备注不 bump"之后,前端那道判断就从"必要的保险"退化成"第二个判官"。
  **红检必须显示新断言在旧实现下是红的**,并且这条推翻要写进 verify,不许悄悄改。
- **多一次无谓 PUT**:原样保存/点同一个状态 pill 会真发请求。代价是一次锁 + 一次读改写
  判定,没有写盘。可接受;真要省,该省在"编辑框没动过就别调 save",那是 UI 的事,不是契约的事。
- **搬家的爆炸半径**:`parse_history` 有 `/changes`(工作区整列)和新的 `/api/todos`
  两个调用方,搬错=两个页面同时哑。缓解:搬家是纯移动(函数体一字不改),
  且既有 1001 条 python 判据里已有大量 `## 变更历史` 用例压着;另加一条**同源断言**
  (同一份档案文本,`/changes` 与 `/api/todos` 对同一条 cnum 给出的 note 必须相等)。
- **`collect` 变慢**:每个项目文件多跑一次 `parse_history`(整文一次线性扫)。
  待办页本来就是每请求现读、零缓存;项目数是几十量级,可忽略。**但要在判据里
  钉住"每文件只解析一次"**(别写成对每条变更行各解析一遍 —— 那是 O(n²))。
- **`note` 进了待办页载荷 = 多一处会显示业主原话的地方**。已经在工作区显示,
  不新增数据出口(同一台机器的同一个前端),不构成新面。

## Alternatives considered

- **让 `ds_web` 自己把 note 拼进 todos 载荷**(不动 `ds_todo.collect`):最省事,
  但 `collect` 的 docstring 自称"结构化核心(唯一真相源):render 与 /api/todos 都吃这个"
  —— 在 web 层旁路拼装等于再造一个真相源,与本单的目的正相反。不选。
- **新建 `bin/ds_history.py` 而不是塞进 `ds_common`**:更"整洁",但 `ds_common`
  已经是档案格式的共享层(页脚/截止日/批次/消毒都在),再开一个模块会让"格式知识在哪儿"
  这个问题多一个答案。不选。
- **读侧也改成 `note: string | null` 恒有键**:我一度想统一成"状态型载荷",
  但那会让 `/changes` 和 `/api/todos` 的既有约定分裂,或者逼我一起改 `/changes`
  (工作区那侧的读契约,不在本单范围)。理由见 Approach §2。不选。
- **保留前端等值判断,只补一条注释说明"后端也判"**:那是把今天的病写成文档。不选。

## Test strategy (oracle)

主 agent 亲写,执行腿逐字节 off-limits。**红检先行**(判据先单独 commit)。

1. **核心(pytest,`tests/test_ds_todo.py` / `test_ds_tools.py`)**
   - `collect` 的 open 条目:有备注 ⇒ 带 `note` 且值 == 档案里那行;无备注 ⇒ **没有该键**。
   - 备注行**夹在留痕行中间**、邻居 cnum(C1 / C12)各有备注 ⇒ 不串桶。
   - 端到端一小步:`edit_change` 清空备注后再 `collect` ⇒ 该条 **没有 `note` 键**
     (0.83.0 修的"存得进去"与本单修的"读得出来"接上了)。
   - **同源断言**:同一份档案,`ds_common.parse_history` 与 `collect` 对同一 cnum 的
     note 相等(防两侧各解析一份)。
   - 搬家后的回归锚:`ds_tools` 的写侧用例(⑤系列 + e01–e09)一条不许退。
   - 环闸:`tests/test_no_import_cycles.py` 已有,搬家后必须仍绿(**ds_todo 不许 import ds_tools**)。
2. **HTTP 面(`tests/test_ds_web_api.py`)**
   - `/api/todos` 载荷带 `note`;清空后该键消失。
   - **跨端点同源**:同一条 cnum,`/api/todos` 与 `/api/projects/<key>/changes` 的 note 一致。
3. **前端纯逻辑(`node --test tests/test_workbench_p4.mjs`)**
   - `buildEditRequest` **恒返回请求对象**:一字未改 ⇒ 仍返回(不再是 `null`);
     两边备注都空 ⇒ 返回且**不带 `note` 键之外的噪音**;`cnum===null` ⇒ 仍 `null`;
     正文 trim 后为空 ⇒ **不带 `new_text`**(校验保留)。
   - 上一单那条"两边都空 ⇒ null"的断言**在同一个 commit 里删掉并写明理由**
     (不是留着让它红)。
4. **e2e(真 chromium + 真 ds_web,`tests/e2e/ws_change_note.e2e.mjs` 加 I 组)**
   - **I:待办页写备注 → `page.reload()` → 备注标签仍在**(今天必红,这是业主眼里的那一格)。
   - 清空 → reload → 标签没了、磁盘那行也没了。

**这个 oracle 能被什么骗过?**

- **最可能的假绿**:我在判据里造的档案都是"备注写在 `## 变更历史` 段里"的**规范档案**,
  而业主机器上的老档案可能有**手写的、格式歪一点的**备注行(全角冒号已覆盖,
  前导零 `C03` 已知不覆盖、上一单记了账)。判据全绿 ≠ 他那份两年的档案里每条都读得出来。
  **接得住的只有真机**:验收清单让他挑一条**很久以前**写的备注看还在不在。
- **第二种**:e2e 的 `reload()` 证明了"刷新后还在",但**没有证明"换一台电脑还在"** ——
  这两件事在实现上是同一件(都从档案读),但只有真机能验第二件。写进验收清单。
- **第三种**:前端判据只测 `buildEditRequest` 这个纯函数,**测不到"点了保存到底发没发请求"**。
  如果 `save()` 里还留着别的短路(比如 `draft` 为空就 return),纯函数全绿而页面依旧不发。
  ⇒ I 组 e2e 用**磁盘内容**做锚,不看返回值;并且**读一遍 `save()` 的全部提前 return**
  (闸③人眼,写进 verify)。
