# Design: opendesign-stage-history

- Change: opendesign-stage-history
- Status: draft
- base-ref: 5b7f40a(ds-web 0.32.0)

> Panel hook:本 track 无开放架构分叉(两个新针孔都有既有先例可逐条照抄,一条纯展示),
> 不跑 panel-explore。两个新写口的安全面在 verify 阶段吃 **full 四审**。

## Approach

### #7 切阶段 —— 新写针孔 ⑩ `POST /api/projects/stage`

核心 `ds_tools.set_stage` 已具备全部安全性质(词表**精确匹配**后才落盘 ⇒ 注入面由构造
消灭;`_resolve` 名字闸;`locked_rw`;`bump_last_updated`)。针孔只做**薄壳**,posture
逐条照抄 `_edit_change`(既有先例,不另起炉灶):

```
CT application/json(CSRF 纵深:跨站带该类型必 preflight,本服务无 OPTIONS 面)
→ 0 < Content-Length ≤ OPEN_BODY_MAX
→ JSON dict + 键白名单 {project, stage}(多余键即拒,防夹带 ds_root/today 走私)
→ 两个键都必须是非空 str
→ ds_tools.set_stage(project, stage, ds_root=self.server.ds_root)
```

错误码沿用既有映射表风格:`bad_stage` → 400、`project_not_found` → 404、
`bad_name`/`path_escape` → 404。**响应体不回显 `stages` 词表**(词表走下面的 GET,
写口只回结果,少一条外泄面)。

**词表下发(单一真相源)**:`GET /api/projects` 响应加顶层 `"stages": [...]`,值直接取
`ds_tools.PROJECT_STAGES`。前端**不得**硬编码副本 —— 词表将来改了,UI 自动跟。

前端:`ChangesColumn` 的 stage-chip 由 `<span>` 变 `<button>`,点开下拉列全部阶段
(当前项打勾),选中即调针孔;esc / 外点关闭(复用 p3-polish 的 `…` 菜单同规矩)。
保存中禁用,失败显示行内错误,成功后 bump 数据(不做乐观改写:阶段是档案头部字段,
以后端回值为准)。

### #8 参考图标签/备注就地改 —— 新核心 `ds_refs.update_ref` + 针孔 ⑪

**新核心函数**(本单唯一的新写工具),形状逐条对齐同文件里的 `link_ref` 先例:

```python
update_ref(ref_id, style=None, space=None, note=None, ds_root=..., today=None)
```

- `ref_id` 必须 `r\d+`,否则 `ref_not_found`;定位用 `^- \[r<num>\]\s` 整体锚定
  (防 r2 误伤 r12,同 link_ref)。
- 三个字段**全为 None → `no_fields`**(不接受空调用,避免"只 bump 页脚"的假写)。
- `style` / `space`:逗号(含全角)拆分 → 逐项过词表(`_load_styles(ds_root)` /
  `SPACES`),空列表或任一项不在词表 → `style_unknown` / `space_unknown`(带 vocab)。
  **不自动建词**(建词有 `add_style` 专属工具,人工确认闸不破)。
- `note`:`sanitize_field(ban_pipe=True)`(折行 + 禁 `|`,与 add_ref 同);**允许空串
  = 清空备注**(与"不传=不动"区分开)。
- 只重写「头段(`- [rN] 风格|空间`)」与「`备注:` 段」;`来源:` / `文件:` / `用于:`
  三段**逐字节不变**(分段重组,不做整行正则替换)。缺 `备注:` 段的畸形行 →
  `malformed_entry`,不猜不补。
- 全程 `locked_rw`,末尾 `bump_last_updated`。

MCP 工具 `update_ref_tool` 一并注册(聊天里也能改,与工作台同一条核心)。

**针孔 ⑪ `POST /api/refs/update`**:posture 同 ⑩,键白名单 `{ref_id, style, space, note}`;
`style`/`space`/`note` 缺省=不动,给了就必须是 str。错误码:`ref_not_found` → 404、
`ambiguous_ref` → 409、`malformed_entry` → 409、`style_unknown`/`space_unknown`/
`no_fields` → 400。

**词表下发**:`GET /api/refs/<key>` 响应加 `"vocab": {"style": [...], "space": [...]}`。

前端:图墙 lightbox 里,**refs 来源**的图(`id` 以 `ref:` 开头)给一块编辑区
——风格/空间用词表 chip 多选、备注单行输入、保存/取消;工作区图(`ws:`)没有索引条目,
**不给编辑入口**(不是 bug,是它压根不在索引里)。为此 `GalleryItem` 加
`refId?: string` 与 `note?: string`(纯函数层,进 mjs oracle)。

### #9 变更修改历史 —— 纯前端

后端已返回 `history: [{date, old}]` 与可选 `note`。`web/src/api.ts` 的 `Change` 类型补
这两个字段;`ChangesColumn` 的变更行:

- 有 `note` → meta 行显示「备注:…」(与待办页同口径);
- `history.length > 0` → meta 行出「改过 N 次」小按钮,点开列出每条
  `<日期> 原:<原文>`(时序 = 后端给的顺序,前端不重排);再点收起。

纯逻辑(计数文案、日期格式、展开态 key)抽 `web/src/workspace/history.ts` 纯函数,进
mjs oracle;组件只做渲染。

## Key trade-offs / risks

- **两个新写口叠一单**:风险高于单口,所以 verify 锁死 full 四审,且两个针孔都不写
  自己的校验逻辑 —— 一切名字/路径/词表/锁的判断都在核心函数里(薄壳原则)。
- **阶段不做乐观更新**:多一次往返,换"UI 显示的一定是盘上的值"。阶段是档案头部字段,
  比变更状态更"权威",宁慢不假。
- **`update_ref` 允许清空备注**(传空串)但**不允许清空标签**(风格/空间至少各一项,
  与 `add_ref` 的必填约束一致)—— 否则索引行会退化成没有任何检索维度的死条目。
- **词表经 GET 下发**:多了两处响应字段,但换掉"前端硬编码副本 + 后端改了不同步"的
  经典漂移;与 `PROJECT_NAME_RE`/`NAME_CHARS` 的单一真相源原则同源。
- 图墙 lightbox 里编辑 = 在"看图"的场景里塞了个写口。取舍:标签本来就是看着图才想改的;
  但**保存后必须重拉 refs**,否则下一次筛选用的是旧标签(oracle 钉死)。

## Alternatives considered

- **#7 复用 `/api/changes/edit` 加个 `stage` 字段** —— 拒:那是"变更行"的针孔,项目头部
  字段混进去会让键白名单与错误码语义都变浑;新针孔的边界更干净。
- **#7 前端硬编码 11 个阶段** —— 拒:词表在 `ds_tools` 已是单一真相源,复制一份就是给
  下一次改词表埋静默漂移。
- **#8 直接让前端 PATCH 索引行** —— 拒:破「PKB 写操作必须过 ds_tools/ds_refs 核心」的
  项目级铁律。
- **#8 把编辑放 CompanionColumn 缩略图** —— 拒:那里是 5 张小图的概览,没有承载词表多选
  的空间;lightbox 是唯一能看清整张图 + 有版面的地方。
- **#9 把历史做成悬浮 tooltip** —— 拒:历史条目可能多行长文本,tooltip 放不下且不可选中
  复制;就地展开更朴素。

## Test strategy (oracle)

主 agent 亲写、先 commit、先红检;执行腿逐字节 off-limits。

1. `tests/test_ds_refs_update.py` —— 新核心 `update_ref`:happy(单字段/多字段)、
   非法 ref_id / 不存在 / 重复行歧义、词表外风格/空间、空标签、备注清空、
   `|` 与换行注入被消毒、**未列字段逐字节不变**(来源/文件/用于)、缺备注段畸形行、
   页脚 bump、并发锁(与既有 lock 测同套路)。
2. `tests/test_ds_web_stage.py` —— 针孔 ⑩ 全 posture(CT/尺寸/非 dict/多余键/类型/
   词表外/未知项目/名字闸)+ GET 该路径 405 + `/api/projects` 的 `stages` **等于**
   `ds_tools.PROJECT_STAGES`(漂移即红)。
3. `tests/test_ds_web_refs_update.py` —— 针孔 ⑪ 全 posture + 错误码映射 +
   `/api/refs/<key>` 的 `vocab` 等于核心词表。
4. `tests/test_change_history.mjs` —— `history.ts` 纯函数(计数文案/日期/空态)与
   `gallery.ts` 新增 `refId`/`note` 透传。
5. `tests/e2e/stage_history.e2e.mjs` —— 真 chromium + 真 ds_web(无 gateway):
   点 chip 改阶段 → **markdown 文件里真的变了** + UI 回显;lightbox 改标签 → 索引行变了
   且筛选跟着变;变更行「改过 N 次」展开看到原文。
