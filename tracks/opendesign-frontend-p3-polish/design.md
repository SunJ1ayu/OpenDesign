# Design: opendesign-frontend-p3-polish

- Change: opendesign-frontend-p3-polish
- Status: draft
- base-ref: e5bac70(ds-web 0.31.0)

> Panel hook:本 track 无开放架构分叉(五条纯打磨 + 一条有标准答案的安全面),
> 不跑 panel-explore。I4 的安全面在 verify 阶段吃 **full 四审**。

## Approach

六条里五条是纯 CSS/JSX 打磨,一条(I4)动后端安全面。逐条:

### I1 图墙「来源」chip 云 → 描边下拉

`GalleryPage.tsx` 的 `<Chips label="来源">` 换成单选 `<select>`(统一输入范式:
圆角 10px、边框 `--border-input`、聚焦转赤陶)。位置按修改单挪进标题行:
`图墙 · <项目> · N 组 · N 张 · [来源 ⌄] [打开文件夹]`。选中后显示来源名 + `×` 清除。
「空间」「风格」两组 chip **不动**(修改单只点名「来源」)。

### I2 「建档」→ 主按钮

`ChangesColumn.tsx:279` 的 `className="btn-save"` → `"btn-primary"`(p2-polish 已建三级
按钮体系,直接复用,不新写 CSS)。两个输入框维持现范式不动。

### I3 列宽重分配

`app.css`:`.aside` 290px → **400px**;`.chatcol` 340px → **300px**。
伴随列变宽后缩略图从 2 列改 **3 列**(`.thumb-grid` grid-template-columns 3 等分);
「+N 图墙」入口格逻辑随之从"取前 3"改"取前 5"(`showMore` 阈值 3 → 5)。
收起态 36px 竖条不变。

### I4 「最近更新」行可点 —— 唯一安全面

现状:类目行(`.cat-row`)已是可点按钮走 `open-folder`;**只有 `.recent-row` 是死 `<div>`**。
修改单要求「文件行点击用系统默认程序打开该文件」。

`open-folder` 是本项目"只读铁律的唯一受控例外",后端 `resolve_sub` 带 `isdir` 闸,
**只放行目录**。要开文件就等于把 `os.startfile`/`xdg-open` 喂给任意扩展名 —— 项目夹里
一个 `.lnk`/`.bat`/`.ps1`,一次点击就是本机任意代码执行。这是本 track 的真风险点。

**定夺:开文件,但加扩展名白名单;白名单外退化为打开所在文件夹。**

后端给 `POST /api/open-folder` 加可选 `rel` 字段(不新开端点,复用同一受控开口),
闸序**逐条对齐既有 `_files_file` 先例**(单一真相源,不另起炉灶):

1. Gate A:`ds_workspace.relpath_ok(rel)` —— 多段相对路径,禁 `\` `%` 控制符与 `.`/`..` 段
2. Gate B:`realpath` + `ds_common.within(项目夹, target)` —— 逃逸权威闸
3. Gate C:`os.path.splitext(target)[1].lower()` ∈ `_OPEN_EXTS` 白名单
4. `os.path.isfile(target)`
5. 全过才调 `OPEN_LAUNCHER`;任何拒绝路径 **零执行**(oracle 断言)

`_OPEN_EXTS`(设计师会双击的文档/图纸/图片类型,**无任何可执行/脚本/快捷方式**):

```
.dwg .dxf .skp .3ds .max .rvt .obj .fbx .stl
.pdf .jpg .jpeg .png .gif .webp .bmp .tif .tiff
.doc .docx .xls .xlsx .ppt .pptx .txt .md .csv .rtf
```

显式**不含**:`.exe .bat .cmd .com .scr .ps1 .vbs .js .wsf .msi .lnk .url .reg .dll .jar .sh .py .html .svg`
及一切压缩包。扩展名取自 realpath 后的真实文件名 ⇒ `报价.pdf.bat` 判为 `.bat` 被拒。
白名单外 → `415` + `{"error":"ext_not_allowed"}`,**不 fallback 到执行**。

`rel` 与 `sub` 互斥:两者同时给 → 400(不猜意图)。

前端(纵深防御,不替代后端闸):`CompanionColumn` 的 recent 行改可点按钮,
按扩展名分流 —— 白名单内调 `openFile(key, rel)`;白名单外直接调
`openFolder(key, category)` 打开所在文件夹(不留死路,满足"不允许存在不可点的列表")。
`rel` = ``category ? `${category}/${name}` : name``。hover 底 `--paper-hover`,
`title` 显完整 `category/name`。

### I5 助手头部降噪

`ChatPage.tsx` 的 `.chat-meta`:「已连接 · 模型」字号降到 10.5px / `--ink-5`;
内联 style 的「退出登录」按钮拆掉,改 `…` 图标按钮点开小菜单(复用设置弹层同款卡片
样式),菜单内一项「退出登录」。esc / 外点关闭(与设置弹层同规矩)。

### I6 侧栏项目名两行截断

`app.css` `.proj-row .nm`:单行 ellipsis → `-webkit-line-clamp: 2` 两行截断。
`Sidebar.tsx`:显示名走纯函数 `displayProjectName(name)` —— 名字以 `(`/`(` 开头时
优先显示右括号之后的内容(空则退回原名);`title` 永远含**完整原名**(现 title 被
unregistered/stage 占用,改为「全名 + 原有补充」拼接)。纯逻辑进新
`web/src/workspace/projectName.ts`,由 mjs oracle 直接单测。

## Key trade-offs / risks

- **I4 是本 track 唯一真风险**:受控开口从目录拓宽到文件。缓解=白名单 + 复用既有三闸
  先例 + oracle 断言"拒绝路径零 `OPEN_LAUNCHER` 调用"。**验收必走 full 四审**
  (AGENTS.md Tiered execution §4:新写口/权限面不打折)。
- I3 改列宽会挤动 2a 三列布局,窄窗下可能溢出;缩略图 3 列后单图变小(400px 列内
  约 120px/格,对比现 290px 列的 2 列 ≈ 135px —— 略小,可接受)。
- I6 括号启发式可能误伤正常含括号的名字;故只在**以括号开头**时生效,且 title 兜全名。

## Alternatives considered

- **I4 完全不开文件,recent 行一律打开所在文件夹**:零新增安全面,一行改完。没选:
  设计师明确要"打开该文件",且白名单已把执行风险关死。但这是最稳的退路,若四审对
  白名单有异议,回落此方案(改动极小)。
- **I4 整组删掉「最近更新」**(修改单给的另一选项):信息有价值,删了可惜,不选。
- **I4 另开 `/api/open-file` 新端点**:多一个非 GET 面,不如复用同一受控开口 + 同一套闸。
- **I1 保留 chip 但折叠成"展开更多"**:仍占位且多一次交互,不如下拉直接。

## Test strategy (oracle)

主 agent 亲写,执行腿逐字节 off-limits。三层:

1. **py 单测**(新增 `tests/test_ds_web_open.py`,I4 安全面主战场,注入 fake
   `OPEN_LAUNCHER` 记录调用):
   - 白名单内文件 → 200 且 launcher 收到正确 realpath
   - `.bat` / `.exe` / `.lnk` / 无扩展名 → **415 且 launcher 零调用**
   - `报价.pdf.bat` 双扩展名 → 415 零调用
   - `../` 逃逸、`\` 反斜杠、`%`、控制符、`.` / `..` 段 → 404 零调用
   - 符号链接指向项目夹外 → 404 零调用(Gate B)
   - `rel` 指向目录 → 404 零调用(isfile)
   - `rel` + `sub` 同给 → 400 零调用
   - 大小写扩展名(`.PDF`)→ 200(lower 归一)
   - 无 `rel` 的老 `sub` 行为不回归(既有 test_ds_web 用例全绿)
2. **mjs 单测**(新增 `tests/test_project_name.mjs`,纯逻辑):
   - `displayProjectName`:括号开头取括号后、非括号开头原样、只有括号/空退回原名、
     全角括号同规则
   - `openTargetFor(recent)` 分流:白名单内 → `{kind:"file"}`;`.bat` → `{kind:"folder"}`;
     无 category → rel 不带前缀
3. **e2e**(新增 `tests/e2e/frontend_p3_polish.e2e.mjs`,断 UI 事实):
   I1 下拉存在且 chip 云消失 / I2 建档按钮类名 / I3 两列宽计算值 / I4 recent 行是
   button 且 title 全名 / I5 `.chat-meta` 无常驻退出登录、`…` 可展开 / I6 nm 两行截断。

回归:`pytest tests/`、全量 `tests/*.mjs`、`npm run build`、`/api/health` 回显新版本。
