# Design: opendesign-workbench

- Change: opendesign-workbench
- Status: draft（主 agent 独立方案，落盘于读任何 panel 输出之前）

## Approach

**总形态**：仓内新增 `web/`（React + TypeScript + Vite 源码）+ `web/dist/`
（构建产物，进仓）+ `bin/ds_web.py`（纯 stdlib 本地 HTTP 服务，端口 8766），
与 nanobot gateway（8765）并行跑、互不相碰。用户机 `git pull` 即更新、免 Node；
构建只发生在 Linux 开发机（Node 22 已有）。桌面感由 Edge/Chrome"安装为应用"
白捡，不做壳。

### D1 技术栈 = Vite + React + TS，dist 进仓

第一性推理：**这个前端的宿命是"长"**（待办→日历/提醒、聊天、图片工具、3D），
手写 vanilla 响应式代码在这个宿命下才是真屎山风险；框架的组件模型就是为
多模块工作台准备的。选 React 而非 Vue：three.js 生态（react-three-fiber）、
日历类组件生态最厚，将来两个重模块都受益。dist 进仓是"git pull 分发 + 用户机
零工具链"约束下的正解（先例：nanobot 自己就是 pip 包内带编译 SPA）。

### D2 后端 = `bin/ds_web.py` 纯 stdlib，薄 API 层

- `ThreadingHTTPServer` 静态服务 `web/dist/` + `GET /api/todos`。
- **API 从第一天返回结构化 JSON**（项目/条目/状态/C 编号/日期/超期天数），
  不返回渲染好的文本——这是日历/提醒升级路径的地基（升级 = 前端换视图 +
  schema 加字段，API 形状不动）。
- 数据来源 = `import ds_todo` 核心函数直调（与 MCP `list_todos` 同源），
  绝不自己重新解析 markdown（单一真相源，杜绝第二套解析器漂移）。
  DS_ROOT 发现 = `__file__` 推导，与 bin/ 其他工具同惯例（7-03 已统一）。
- **P0 含 ds_todo 结构化重构（sub Claude F1，HIGH，四方共享假阴性）**：
  现状 `ds_todo.render()` 只返回渲染文本（ds_todo.py:27-65），C 编号/条目
  日期根本没被提取，"直调核心 + 结构化 JSON"两条铁律按现状互斥。正解 =
  拆出 `collect(root, stale_days, today) -> 结构化 dict`（新增 C 编号/日期
  提取，与 SCHEMA 变更行格式同源），`render()` 降级为其格式化壳，
  **golden 文本输出逐字节不变**（现有 6 条 golden 测试继续绿）；ds_web 与
  MCP `list_todos` 都改吃 `collect`。这是对既有核心的 in-scope 重构，
  oracle 同源断言以 `collect()` 为锚。
- **中文/编码（panel 采纳）**：JSON 响应 `ensure_ascii=False` +
  `Content-Type: application/json; charset=utf-8`；oracle 加中文业主/项目名
  fixture 断言往返等值。静态文件只服务 dist 内 Vite 产物（ASCII 文件名），
  不服务用户内容文件。
- **并发姿势（panel 采纳 + sub Claude F3 修正机理）**：每请求现读 PKB、
  零缓存；读路径**不加锁**（给读者加锁会撞 msvcrt 强制锁咬读者的 7-03
  递延雷）。真实失败模式按平台不同：**Windows 下写窗口内的并发读 = 瞬时
  OSError/PermissionError（msvcrt 强制锁语义），归入 500-JSON 错误路径，
  刷新自愈；Linux flock 是 advisory，才可能真撕裂读**。实现时必须把这个
  读期 OSError 接进 500 路径，不能当"最多脏读"处理。ThreadingHTTPServer
  前提 = ds_todo 核心无共享可变状态——**已核验成立**（模块级只有编译正则
  +常量，ds_todo.py:16-19）。
- **运维面（panel 采纳）**：端口 `DS_WEB_PORT` env 可配（默认 8766），被占时
  **明确报错退出**（不随机换端口——"安装为应用"钉死 URL，静默换端口更糟）；
  `SO_REUSEADDR`；`GET /api/health` 返回版本+DS_ROOT；请求日志走 stdout。
- **错误路径**：ds_todo 抛异常 → 500 + JSON error shape（trace 进日志不进
  响应体）；dist 缺失 → 启动时报错退出并提示构建。
- **Windows 启动物（sub Claude F4，P0 交付）**：`bin/ds-web.ps1`（3 行薄
  wrapper，同 ds-nanobot.ps1 惯例）+ install-windows.md 新增"工作台"小节
  （启动命令、http://127.0.0.1:8766、装完跑一次 `python tests\test_ds_web.py`）。
  没有这个，P0 成功标准"浏览器打开本地页面"在用户机上无路可走。
- **.gitignore 新增（sub Claude F5）**：`/web/node_modules/` + `/web/.vite/`
  （锚定仓根，遵守 7-03 锚定教训）——现状一次 `git add -A` 就把
  node_modules 灌进仓。
- P0 只读：服务只 GET，不开任何写端点。**将来加写操作（勾状态）时必须过
  `ds_tools` 核心（消毒+锁+锚定），页面永远不直改 markdown**——铁律在工具
  边界，与脑/前端无关（7-05 已确立的原则，前端同样适用）。
- 绑 127.0.0.1。P0 无鉴权（本机回环+只读）；开写端点那天加 token，写进
  升级路径而非现在实现。

### D3 模块骨架与分期

侧栏五项：**待办**（P0 真实现，只读列表，超期/未关闭高亮）、**聊天**（P0 占位：
外链 http://127.0.0.1:8765/）、**图片规整**（占位）、**3D 查看**（占位）、
**设置**（占位）。视觉参考 nanobot WebUI（左侧栏+主区、同类配色密度），
但不抄它的编译产物。

分期（每期独立 track）：
- **P0（本 track）**：骨架 + 待办只读 + ds_web + oracle。
- **P1 聊天**：浏览器直连 nanobot websocket 通道（stock SPA 就这么干，
  协议在 `channels/websocket.py` + `webui/ws_http.py`，内部未版本化 →
  **钉住 nanobot 版本**，升级前先跑协议冒烟）。聊天达到日用水平前,
  stock WebUI 不下线。已知坑：我们的页在 8766、API 在 8765 = 跨源，
  websocket 不受 CORS 管但 HTTP API 受 → 可能要 ds_web 反向代理
  `/api/sessions/*`，P1 再定。**钉版本落点（panel 采纳）**：install.ps1
  改 `pip install nanobot-ai==<当前版>`（现在就顺手钉，防机主重装漂移）；
  P1 开工第一件事 = 协议基线快照（抓一次真实会话的消息形状存
  `docs/nanobot-ws-protocol.md`）+ 冒烟测试，之后升 nanobot 先跑冒烟。
  完整协议策略（握手版本协商等）属 P1 track 的 design，不在本期预写。
  **P1 已核事实（sub Claude F6）**：握手默认强制 token
  （`websocket_requires_token=True`），而 token 签发是 8765 上的 HTTP 端点
  且全模块零 CORS 头 → 跨源页面连聊天的 token 引导都拿不到，**P1 至少
  需要 ds_web 同源代理 token 签发**；websocket 传输层本身无 Origin 校验，
  直连可行。
- **P2 待办升级**：日历视图 + 重要提醒分级（schema 加"重要"标记字段 =
  变更行词表扩一项，走既有状态机不删行原则）。
- **P3 图片规整**：Pillow 批量统一宽/高/分辨率，**输出永远是新目录副本，
  不动原图** → 天然免审批闸；dry-run 预览清单沿用 organize 的习惯。
- **P4 3D 查看**：见 D4。

### D4 quicklook = 届时重写，不改造（回答用户的第一性之问）

事实：quicklook 前端只是 **759 行单文件 serve.py**（HTML/JS 内嵌），真正的
资产在 cad-to-3d 管线仓（解析/profile/Blender 构建）和已验证的案例体系里——
**值钱的是管线，不是页面**。把一个用户已不满意的薄壳改造进新架构（vanilla
内嵌 → React 组件、独立进程 → 工作台模块）的功 ≥ 重写，还背上旧包袱。
判定：**P4 时在工作台内重写 3D 查看模块（react-three-fiber），管线仓当黑盒
后端调用，quicklook 只当参考读物**。本 track 对它零投入、零耦合（连导航占位
文案都不提 quicklook）。P4 动工前先过一遍旧 serve.py 提取边界案例/hack 清单
（panel 采纳：防重写丢隐性修复）。

## Key trade-offs / risks

- **dist 进仓**：diff 噪音 + 仓变大。收益（用户机零工具链、git pull 即更）
  压倒性；缓解（panel 采纳后具体化）= dist 单独 commit +
  `.gitattributes`：`web/dist/** -diff linguist-generated`。
- **React+Vite = 开发机新依赖面**（node_modules 不进仓）。接受：只长在
  开发机；**package-lock.json 与 `.nvmrc`（Node 22）均进仓**保可复现。
- **浏览器缓存 vs git pull 更新（panel 采纳）**：Vite 产物默认带内容哈希
  文件名；ds_web 对 `index.html` 发 `Cache-Control: no-cache`，哈希资产长
  max-age——git pull 后刷新即新版，不需要用户硬刷新。
- **nanobot 协议漂移**（P1 风险，P0 零暴露）：内部协议无契约，pip 升级可能
  破——对策 = 钉版本 + 协议冒烟测试 + stock WebUI 保底不下线。
- **双服务两个端口**（8765/8766）：用户要开两个东西。P0 接受（ds-nanobot.ps1
  顺手拉起 ds_web 的整合放 P1 一起做），比塞进 nanobot 进程（改它=非目标）干净。
- **Windows 真机又是 UNTESTED 面**：ds_web 是纯 stdlib+纯 GET，风险远小于
  install.ps1 那轮；照惯例首装即验收，坑回写文档。

## Alternatives considered

- **fork/改 nanobot WebUI**：编译产物不可维护，fork 上游 = 屎山，7-06 已裁定，弃。
- **零构建 vanilla/petite-vue**：P0 最便宜，但与"长期工作台"宿命冲突，
  日历/聊天/3D 每一步都在还债；屎山红线下反而是贵路线，弃。
- **FastAPI/uvicorn 后端**：P0 用不上（纯 GET+静态），先 stdlib；websocket
  代理真落地那天再升级，避免"为了完备"提前拉依赖。
- **Tauri/Electron 桌面壳**：桌面版 = 网页+壳，壳等真需要（托盘/自启/分发
  他人）再包，页面代码原封不动。7-06 已与用户对齐。
- **待办页直接 fetch 读 markdown 前端解析**：省后端，但造第二套解析器 +
  为日历升级埋漂移雷，弃（单一真相源原则）。
- **CI 构建 dist / 打包 Python wheel**（MiMo 提出）：CI 构建引入供应链面+
  私仓 Actions 成本，wheel 改变整个 git pull 分发模型——都比"开发机构建、
  产物进仓"复杂，弃。
- **Windows CI 跑测试**（SenseNova 提出）：私仓 Actions 成本 vs 收益不成
  比例；替代 = oracle 本就是纯 stdlib 跨平台，install-windows.md 加一行
  "装完跑一次 `python tests\test_ds_web.py`"，装机即真机验证。

## Test strategy (oracle)

纯 stdlib、离线、`python3 tests/test_ds_web.py`，与现有 80 测同风格并存不改：

1. `/api/todos` 对 golden PKB fixture 返回结构化 JSON（字段齐全：项目/状态/
   C 编号/日期），**与 `ds_todo.collect()` 输出一致**（同源断言；F1 重构后
   collect 是唯一真相源）。附带：`render()` golden 文本逐字节不变 +
   MCP `list_todos` 走 collect 后行为不变。
2. 空 PKB → `{"todos": []}` 且 200（不炸）。
3. 静态服务：`/` 返回 200 + text/html；`web/dist/index.html` 存在性由测试
   断言（防"忘了构建就推"）。
4. 路径安全：`GET /../` + **百分号编码变体 `%2e%2e/`、`..%5c`（Windows
   反斜杠）**逃逸请求一律 404/400（`ds_common.within` 复用；实现必须先
   unquote 再 realpath 再 within——sub Claude F7）。
5. 只读断言：服务对 POST/PUT/DELETE 一律 405（锁死 P0 无写面）。
6. red-check 惯例：至少一条测试先证明会红再修绿。
7. 错误路径（panel 采纳，fixture 按 sub Claude F2 修正）：malformed
   markdown 会被 render 逐行正则**静默跳过**（坏日期也被 except 吞掉，
   ds_todo.py:55-58），按字面写不出 red-check——真实异常路径 = **非 UTF-8
   字节的 .md 文件**（strict utf-8 读抛 UnicodeDecodeError，ds_todo.py:38）。
   fixture 用非 UTF-8 字节文件 → `/api/todos` 返回 500 + JSON error shape，
   进程不死、后续请求正常。
8. 绑定地址断言（panel 采纳）：服务 socket 实绑 127.0.0.1，非 0.0.0.0。
9. 中文 fixture（panel 采纳）：业主/项目名含中文的 golden PKB，JSON 往返
   等值（`ensure_ascii=False` + charset 头）。

裁掉的建议（有依据）：dist golden-hash 测试（GLM）——内容哈希每次构建必变,
纯churn；SCHEMA_VERSION 常量（GLM）——oracle #1 同源断言已耦合 API 与核心,
版本常量是官僚层；Playwright 浏览器测试（GLM）——骨架期重依赖低收益，oracle
#1/#3 已是 curl 级冒烟；随机端口回退（SenseNova）——钉死 URL 的场景下静默换
端口比报错更糟。

## Panel 仲裁记录（2026-07-06，设计阶段评审）

主 agent 方案先落盘（上文初版），三审后仲裁。原始日志：
`/root/aiwork/logs/panel-opendesign-workbench-plan.*.log`。

- 结论：MiMo 附条件 PASS / SenseNova PASS / GLM BLOCK → **合议 PASS**
  （设计已按采纳项修订，架构四决策 D1-D4 三家均未动摇）。
- GLM 三个 BLOCK 的仲裁：①P1 协议策略——P0 零暴露（GLM 自己也承认），
  采纳增量=钉版本落点+协议基线快照，完整策略属 P1 track，不预写；
  ②PKB 并发——采纳为"每请求现读+读不加锁+接受瞬时撕裂"的显式姿势
  （给读者加锁会撞 7-03 递延的 msvcrt 强制锁咬读者雷，GLM 不知道这个
  上下文）；③.gitattributes 具体化——采纳（一行的事，BLOCK severity 过重）。
- 采纳清单（已焊入上文）：中文/编码+fixture（MiMo+GLM 齐指，主 agent 首版
  漏掉的真盲点）、端口冲突明确报错+DS_WEB_PORT、/api/health+请求日志、
  错误路径 500 oracle、绑定地址断言、缓存策略、.nvmrc、DS_ROOT 发现方式、
  钉 nanobot 版本、quicklook hack 清单、Windows 装机跑测试一行。
- 拒绝清单及依据：见上节"裁掉的建议"；另拒 Windows CI（成本比）、
  rollback 章节（git revert 是既有常规操作,不属设计内容）、stdlib→FastAPI
  迁移预写（P1 直连方案可能根本不需要服务端 ws，预写即浪费）。
- ⚠️ 异常记录：submimo 交卷后跑偏，试图"写脚本删除目录下所有 .log 文件"，
  被权限沙箱（edit deny）挡下，零损害。评审内容本身（F1-F9）质量正常。
  后续给 submimo 的 review 任务保持只读权限配置不放松。

## Sub Claude 评审记录（2026-07-06，第二轮，用户点名）

独立 sub Claude 对着真实代码核验设计假设（非盲读文档），结论 BLOCK→修订后
转 PASS。**七条 findings 全部核实采纳，零误报**：

- **F1 [HIGH] = 本轮最大价值，四方共享假阴性**：`ds_todo.render()` 只有渲染
  文本输出（逐行核实 ds_todo.py:27-65），"直调核心+结构化 JSON"两铁律按现状
  互斥——主 agent 首版 + MiMo + SenseNova + GLM 全没抓到。修订 = P0 纳入
  ds_todo 结构化重构（collect() 核心 + render() 壳 + golden 逐字节不变）。
  再次印证 7-03 工艺沉淀：sub Claude 代码级核验 > 三弱模型 panel 文档级评审。
- F2：oracle #7 fixture 改非 UTF-8 字节（malformed markdown 静默跳过,红不了）。
- F3：并发失败模式修正——Windows 强制锁下并发读=瞬时报错非撕裂读，
  必须归入 500 路径。
- F4：补 P0 Windows 启动物（ds-web.ps1 + 文档小节）。
- F5：.gitignore 补 /web/node_modules/。
- F6：P1 token 签发端点无 CORS，直连聊天至少要 ds_web 代理 token 引导。
- F7：路径逃逸 oracle 补百分号编码变体。
- 对第一轮仲裁的修正：拒 SCHEMA_VERSION 的结论维持，但依据更换为
  "前端与 API 同仓同 commit 原子部署"（原依据"oracle #1 已耦合"在 F1 下
  不成立）。其余第一轮仲裁全部复核通过。
- 附带核验成立（实现时不用再查）：ds_todo 线程安全、within 语义适配、
  .gitignore 对 web/ 零误伤、install.ps1:63 钉版本一行事（mcp 顺手一起钉）、
  ws 无 Origin 校验直连可行、现有 80 测数字与风格吻合、8766 端口无撞。
