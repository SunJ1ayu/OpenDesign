# Design: opendesign-workbench-p5

- Change: opendesign-workbench-p5
- Status: accepted(方向已与用户当面收敛,非开放分叉,不跑 panel-explore)

## Approach

### 1. 工作区根 + 项目映射(不动 PKB schema)

- 新配置 `config/workspace.json`(DS_ROOT 下,gitignored 同业主数据待遇):
  ```json
  { "root": "D:\\设计工作区",
    "projects": { "<PKB项目key>": "01-项目/20260612 周宁 龙腾世纪 12#1802" } }
  ```
- 解析逻辑进 `bin/ds_workspace.py` 新模块(纯函数为主,可单测):load 配置、
  key→绝对路径解析(realpath + within(root) 权威闸)、类目扫描、图片列举。
  坏配置/缺文件 = 功能整体降级为"未配置"(前端显示引导),**不炸其他端点**。
- 映射由用户/agent 手编 json(config 非 PKB 账本,只读铁律不涉及);首装采纳
  流程将来自动生成它——本 track 手写夹具即可。

### 2. ds_web 新端点(全部复用 refs 三闸模式)

| 端点 | 方法 | 内容 |
|---|---|---|
| `/api/files/overview/<key>` | GET | 按 taxonomy 类目(项目夹下一级目录)计数 + 最近 N=8 文件(名/类目/mtime/size);跳过 `.opendesign`;扫描上限(每类目 ≤2000 文件,深度 ≤4)防大目录挂死 |
| `/api/files/images/<key>` | GET | 项目夹内图片清单(rel path + 类目 + mtime),扩展白名单同 `_IMG_CTYPES`;与已有 `/api/projects/<key>/refs`(refs 索引,带空间/风格)在前端合并 |
| `/api/files/file/<key>/<rel>` | GET | 图片静态服务:Gate A 字符集 → Gate B realpath within(项目夹) → Gate C 图片扩展白名单;404 不回显路径 |
| `/api/open-folder` | POST | **唯一受控例外**,见下 |

### 3. open-folder(本 track 的敏感面)

- `do_POST` 不再整体 405:精确匹配 `/api/open-folder` 走处理,**其余 POST 及
  PUT/DELETE/PATCH 全部维持 405**(oracle 锁死)。
- body `{"key": "...", "sub": "03-CAD"?}`;闸序:key 白名单(`_valid_proj_key`)→
  映射存在 → sub 字符集白名单(可选,单层类目名)→ realpath within(workspace root)
  → isdir。全过才执行。
- 执行:Windows `os.startfile(path)`;其他平台 `subprocess.Popen(["xdg-open", path])`
  列表形式无 shell。失败 → 500 不回显路径。响应 `{"ok": true}`。
- 仅本机可达(server 绑 127.0.0.1,现状即如此),不加 token(与其余端点一致)。

### 4. 前端

- **CompanionColumn(2a 文件列)真数据化**:文件段 = overview(类目行:名称+计数,
  最近文件短列表);头部"打开文件夹"按钮(带 sub 的类目行也可点开对应子夹);
  未配置工作区 → 引导空态。图片段维持 refs 缩略条,点击进图墙。
- **图墙 GalleryPage(新路由 `#/gallery/<key>`)**:网格墙(CSS columns 瀑布),
  数据 = refs(带空间/风格标签)∪ 工作区图片(按类目分组:参考图/效果图);
  顶部筛选 chip(空间/风格,来自 refs 词表;工作区图按类目筛);点击 = 大图
  lightbox(原图,esc/点击关闭)。侧栏项目行/文件列入口进入。
- 路由 Route 类型加 `"gallery"`;keep-mounted 不涉及(图墙无会话态,正常卸载)。

## Key trade-offs / risks

- **POST 例外**:405 焊死是 P0 以来的不变量,本次开一个针孔。风险压制 = 精确路径
  匹配 + 三闸 + oracle red-check(改坏任一闸测试变红)+ verify full lane。
- **不做缩略图**:几 MB 渲染图直出会慢;接受,`loading="lazy"` + 性能真痛再做
  (proposal 非目标)。
- **映射手编**:装机体验欠一步(将来采纳引擎生成);本 track 接受。
- **扫描上限**:超限类目计数显示 `2000+`,诚实降级不假装全量。

## Alternatives considered

- 文件树浏览器进前端 —— 用户明确拒(资源管理器更好用,重造必残)。
- open-folder 用"复制路径"替代 —— 用户拍板要直达;保守版弃。
- 映射写进项目档案.md 字段 —— 动 PKB schema + ds_tools 写面,成本大于收益,弃。
- PKB 整体迁进工作区(07-08 愿景)—— 正确的终态,但牵动 ds_tools/todo/refs 全部
  路径假设,单独 track;本次只读窗口先兑现价值。

## Test strategy (oracle)

主 agent 拥有,先写后实现:

1. `tests/test_ds_workspace.py`:配置解析(正常/缺文件/坏 json/root 不存在)、
   key 解析(合法/逃逸 `../`/symlink 外指/未映射)、类目扫描(计数/最近文件排序/
   `.opendesign` 跳过/上限截断)、图片列举(扩展过滤)。夹具 = tmpdir 按
   taxonomy v1.0 造样例树。
2. `tests/test_ds_web_api.py` 扩展:四端点契约 + **红检**:
   - open-folder:非法 key/未映射/sub 逃逸/不存在目录 → 4xx 且**未执行**
     (monkeypatch 启动器断言零调用);合法 → 启动器收到 realpath 后的目录。
   - 其余 POST 路径仍 405(不变量回归);PUT/DELETE/PATCH 全路径 405。
   - files/file 三闸逐闸突变验红(照 refs 先例)。
3. 前端纯逻辑(筛选/合并/分组)进 `tests/test_gallery.mjs` node 测试。
4. e2e 真 gateway(Playwright):登录 → 2a 文件列出概览 → 点图墙 → 筛选 →
   lightbox;open-folder 在 e2e 里 mock 启动器(Linux 无桌面)。
5. 回归:现有 py + mjs 全套必须全绿。
