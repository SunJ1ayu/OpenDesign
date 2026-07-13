# Design: opendesign-workbench-p7

- Change: opendesign-workbench-p7
- Status: final

## D1 删除对话 = 第二受控 POST 针孔(唯一写面例外的复制,不是新写面)
- nanobot 路由 `/api/sessions/<key>/delete` 不查 HTTP 方法(ws_http.py 亲验),但
  ds-web 侧必须包成 POST:GET 保持纯只读(oracle #5 不变量),浏览器预取/爬虫不可达。
- 闸序:Content-Type application/json(CSRF:跨站必 preflight,本服务无 OPTIONS 面)
  → body ≤ 4096 读净丢弃(防 keep-alive 脱轨)→ key 过 _KEY_RE(不 unquote,同 thread
  先例;e2e p6 已踩过 %xx 坑,前端传裸 key)→ `_proxy()` 复用(GET 上游,header
  白名单 Authorization/X-Nanobot-Auth,状态码原样透传)。
- 真正的鉴权在上游:无 Bearer token 上游 401。CT 闸是纵深不是本体。
- `blocked_by_automations` 透传给前端提示,不代理 delete_automations 参数(OpenDesign
  不暴露自动化 UI,越权删任务面不开)。
- 删除当前正续聊的会话:清 resumeTarget,已渲染的 transcript 不清(与 p3「新对话不
  重置」同语义)。accepted deviation:此时继续发消息会以同 key 重建会话。

## D2 项目列表直读工作区 = 只读联合 + 三级绑定解析
- `ds_workspace.project_folders(cfg)` → projects-dir 下一级目录 [(name, realpath)]:
  projectsDir 可配(相对 root,realpath within 闸,"." = root 本身);缺省候选
  `01项目|01-项目|01_项目|01 项目` 取首个存在者;symlink 目录跳过
  (follow_symlinks=False,同 _scan 先例);名字过字符集白名单(见 D3)不过者跳过。
- `project_dir(cfg, key)` 解析顺序:①显式映射(现状,权威)→ ②文件夹名 == key →
  ③key 按 `-` 切 token,全部 token 都是文件夹名子串且**恰好唯一**命中 → 绑定;
  歧义(0 或 ≥2 命中)不绑。误绑代价 = 文件区/open-folder 指向错文件夹,唯一性
  要求自保护;显式映射永远可纠偏。
- `/api/projects`:PKB 列表(现状)之后,追加未被消费的文件夹为
  `{key: 文件夹名, name: 同, unregistered: true, ...}`;消费集合 = 各 PKB key 的
  project_dir realpath ∪ 显式映射 rel 的 realpath(按路径比,不按 basename)。
- 未建档条目的文件区/图墙/open-folder 经解析②直接可用(key=文件夹名);
  changes/refs 不请求(前端按 unregistered 分支),不自动建档。
- 默认选中项目排除 unregistered(除非只有它们)。

## D3 key 字符集放宽:加 `#`
- 真实文件夹名含 `#`(命名约定 `日期 地点 楼盘 楼栋#户号`)。_PROJ_KEY_RE 与
  ds_workspace 文件夹白名单放行 `#`;权威闸仍是 realpath+within,字符集只防走私,
  `#` 不参与路径语义(wire 上是 %23,unquote 后才进比较)。

## D4 前端
- connection.ts `apiFetch(path, init?)`:可选 method/headers/body,Authorization 合并;
  401 重签行为不变(mjs oracle 补一条 init 透传)。chat 协议层其余零改动。
- Sidebar:hist-row ✕(span 阻冒泡,不嵌套 button),App 层 window.confirm →
  api.deleteChatSession → sessionsEpoch++;unregistered 项目行淡化 + 「未建档」chip。
- ChangesColumn:project.unregistered → 建档引导空态(预填「新建项目:<名>」)。

## D5 版本与判卷
- ds-web VERSION → 0.8.0(验收回显)。
- 判卷文件全部主 agent 手写:test_ds_workspace.py 扩展、test_ds_web_proxy.py 删除
  针孔组、test_ds_web_api.py 联合列表组、405 oracle 维持(非白名单 POST 仍 405)、
  mjs connection init 一条;e2e 真 gateway 两幕(删除流/未建档项目流)。
- verify lane = fast(主审+submimo;subglm 双腿 07-13 起 key 故障,subsense 连续
  两轮盲评无信号,缺席记 verify.md)。
