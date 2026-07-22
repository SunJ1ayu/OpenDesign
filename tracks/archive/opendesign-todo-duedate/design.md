# Design: opendesign-todo-duedate

- Change: opendesign-todo-duedate
- Status: draft

> 非开放架构分叉 —— 单一走法(账本尾 token + 共享 split helper)。方向已定如下。

## Approach

### 账本格式(durable,用户已拍板)

变更行:`- [状态] Cn 记录日期 【空间】正文` **尾部**可选加截止日 token `⏳YYYY-MM-DD`:
```
- [待确认] C7 2026-07-15 【玄关】玄关柜改高 ⏳2026-07-31
                                            └─ 截止日(可选)
```
无 `⏳` 的旧行 = due 为 null,**零迁移、字节不变**。

### 核心:共享 split helper(读写同源,消漂移)

**不改 `ds_todo.CHANGE_RE` 的贪婪 text 组**(避免动到已有行解析);改为在命中后用一个**共享 helper**
从 text 尾部切出 due。放 `ds_common`(读侧 ds_todo / 写侧 ds_tools 都 import 它):
```python
# ds_common.py
DUE_SUFFIX_RE = re.compile(r"\s*⏳(\d{4}-\d{2}-\d{2})\s*$")
def split_due(text: str) -> tuple[str, str | None]:
    """把行尾 ⏳YYYY-MM-DD 从正文切出。无则原文返回、due=None。"""
    m = DUE_SUFFIX_RE.search(text)
    if not m:
        return text, None
    return text[:m.start()], m.group(1)
def format_due_suffix(due: str | None) -> str:
    return f" ⏳{due}" if due else ""
```
- 无 `⏳` 的 text → `(text, None)` 原样返回:**旧行/无截止日行字节不变**,不碰 golden。
- `⏳` 只识别在**行尾**(`$` 锚定),正文中间出现的 ⏳ 不误伤。

### 读侧(ds_todo.py)

`parse_change` 命中后:`text, due = ds_common.split_due(m.group(5))`,返回 dict 加 `"due": due`;
`collect` 的 open_items 加 `"due"`。(render golden 不变——无截止日行 split 后 text 原样。)

### 写侧(ds_tools.py)

- **新 `set_due_date(project, cnum, due, ...)`**(镜像 set_change_status 定位:line_re `C{num}\b`
  命中且唯一):
  - 校验 due:`None`/`""` = 清除;否则必须 `\d{4}-\d{2}-\d{2}` 且 `date.fromisoformat` 合法,
    非法 → `{"error":"invalid_due"}`。
  - 改法:`base = ds_common.DUE_SUFFIX_RE.sub("", lines[i]).rstrip(); lines[i] = base +
    ds_common.format_due_suffix(due)`。**只动尾 token,状态/C号/记录日期/【空间】/正文逐字节不变。**
  - no-op(due 与现值相同)不写(`box["write"]=False`),与既有 no-op 纪律一致。
  - locked_rw 全程;bump_last_updated(有改动时)。
- **`edit_change` 改正文保留截止日**:`_EDIT_PREFIX_RE` 保持不动;取 `old_full = pm.group("text")`
  后 `old_text, due = ds_common.split_due(old_full)`;比较/留痕用 `old_text`(不含 ⏳);重写
  `lines[i] = pm.group(1) + new_text_s + ds_common.format_due_suffix(due)`。**改正文不丢截止日、
  历史 `原:` 不含 ⏳。** append_change 不变(新变更无截止日)。

### ds_web.py

- `_changes`:回传加 `"due": c["due"]`(读侧宽容,旧无字段=None)。
- `/api/todos`:collect 已带 due,透出。
- **新 POST 写针孔 `/api/changes/due`**(精确匹配,posture 逐条照抄 `_edit_change`):CT json →
  body 0<n≤上限 → 键白名单 `{project, cnum, due}`(多余键拒,防走私)→ Host 闸 → ds_tools.set_due_date。
  due 可为 null/字符串;错误码 → HTTP(invalid_due 400 / change_not_found 404 / ambiguous 409)。

### MCP(ds_tools.py 工具注册)

新 `set_due_date_tool(project, cnum, due)`(due 空串=清除),docstring 说明"设/清一条变更的截止日"。

### 前端

- `api.ts`:`Change` 加 `due: string | null`;`OpenItem`(todo.ts)加 `due: string | null`;
  新 `setDueDate({project, cnum, due})` → POST `/api/changes/due`(due:null 清除)。
- **纯函数** `todo.ts::dueStatus(due, today)` → `"overdue" | "today" | "upcoming" | null`
  (due=null→null;due<today→overdue;==today→today;>today→upcoming)。契约见
  `tests/test_todo_duedate.mjs`。供行内截止日着色 + 下一 track 日历/今日跟进复用。
- **ChangesColumn(项目工作区)变更行**:row-actions 加 `📅` 按钮 → 原生 `<input type=date>`
  设/清截止日(调 setDueDate,成功后 reload);meta 行显示截止日(有 due 时「截止 M月D日」,
  按 dueStatus 着色:overdue 红 / today 琥珀 / upcoming 弱)。
- **TodoPage 行**:只读显示截止日(同 dueStatus 着色),**不加设置入口**(triage 设置留下一 track)。

## Key trade-offs / risks

- `⏳`(U+23F3)进账本:UTF-8 存储,ds 文件恒 utf-8,读写一致、greppable;选它因视觉直观且与
  记录日期/【空间】无歧义。
- split 只认行尾:若用户正文**本身**以 `⏳日期` 结尾会被当截止日——极不可能(正文是中文诉求),接受。
- 非贪婪风险规避:用 post-split 而非改 CHANGE_RE 贪婪组 → 无截止日行解析**字节不变**,render golden 不破。
- 新写针孔 `/api/changes/due`:与既有 5 个写针孔同 posture,审查面已知。

## Alternatives considered

- 改 CHANGE_RE 为非贪婪 + 尾 due 组:会改动无截止日行的 text 尾空白语义,可能碰 golden。否决,用 post-split。
- 截止日单独存一行(如 `## 截止` 段):偏离"一条变更=一行"心智,读写都要跨行关联。否决。
- 复用记录日期字段当截止日:语义冲突(记录≠到期),且无法同时表达"何时记的/何时到期"。否决。

## Test strategy (oracle)

主 agent 亲写、先 commit、对执行腿 off-limits:
1. **`tests/test_ds_duedate.py`(后端)**:
   - `ds_common.split_due`/`format_due_suffix`:有/无 ⏳、行尾锚定、正文中间 ⏳ 不误伤、round-trip。
   - `ds_todo.parse_change`:带 ⏳ 行 due 提取 + text 不含 ⏳;无 ⏳ 行 due=None 且 text 字节不变;
     带【空间】+ ⏳ 共存。
   - `ds_tools.set_due_date`:设/更新/清;**保状态/C号/记录日期/【空间】/正文逐字节**;非法 due→invalid_due;
     不存在→change_not_found;no-op 不写;round-trip(set→parse_change 读回)。
   - `ds_tools.edit_change` 改正文:**截止日保留**、历史 `原:` 不含 ⏳、无 due 行行为不变(回归)。
   - append_change 新行无 ⏳(回归)。
2. **`tests/test_todo_duedate.mjs`(前端)**:`dueStatus(due, today)` 四分支 + null。
3. **e2e**(执行腿写、主 agent 亲跑)`tests/e2e/duedate.e2e.mjs`:真 ds_web,
   POST /api/changes/due 设截止日 → /api/changes 读回带 due → 清除 → 读回 null;改正文后 due 仍在。
4. 回归:全量 py 套件(render golden 必绿)+ 全量 mjs + build 全绿。

verify lane = **full 四审**(新账本字段 + 新写针孔 + 写核心正则面 = 数据一致性)。
