# Design: opendesign-workbench-p1

- Change: opendesign-workbench-p1
- Status: **plan v2**(v1 由主 agent 独立落盘 → sub Claude 评审
  PASS-with-changes,11 findings → 主 agent 逐条实证仲裁后合并,
  仲裁记录见文末)

> 非开放架构分叉(方向被用户反馈+上期 design 钉死),不跑 panel-explore。

## Approach

### A 视觉重皮肤 = token 变量整体替换,不动组件结构

P0 前端已是 React+CSS 变量驱动 → 改版 = `web/src` 全局样式层换成
`nanobot-tokens.md` 里的浅/深两套 shadcn 变量(HSL 空格分隔,
`hsl(var(--x))` 引用),同步三件非变量项:基准字号 13/14px、
`--cjk-line-height:1.625`、零阴影 1px 边框分区 + 侧栏半档色差。
深浅模式:两套变量都进 CSS,默认跟 `prefers-color-scheme`,设置页
占位里放手动切换(`.dark` class 打在根上,与 nanobot 同机制)。
**意向图到达的应对**:视觉全部走变量,图来了改 token 值即可,
不重做布局——这是"没图先打底"能成立的结构性保证。

### B IA 重排 = 侧栏五项,首屏路由改聊天

侧栏(hash 路由,沿 P0):**聊天(/,首屏)/ 待办 / 日历(占位)/
工具箱(占位页:卡片网格,先放"图片规整"一张灰卡)/ 设置(占位:
深浅切换 + 连接状态)**。待办页只换皮不动逻辑(fetch /api/todos)。
工具箱页第一版写死卡片,不做插件框架(7-07 与用户对齐)。

### C 聊天模块 —— 核心架构

已核实的协议事实(nanobot-ai==0.2.2 源码;v1 的 2/3/4 条被 sub Claude
评审推翻/补全,以下为 v2 修正版,主 agent 逐行复核过):

1. **ws 握手**:`ws://127.0.0.1:8765{path}?client_id=...&token=...`,
   `websocket_requires_token=True` 默认强制(websocket.py:82);
   `client_id` 仅作 allow_from 授权+日志标签,可任意取;
   **无 Origin 校验**(websocket.py:403-421)且全模块零
   `Access-Control-*` 头 → 浏览器直连 ws 可行、HTTP 跨源不可行。
2. **token 体系(v1 错误,v2 修正)**:`token_issue_path` 默认空 =
   端点不存在,且部署链路 `enable_webui.py` 不设它;它签的 token 也
   不进 `api_tokens`,对 HTTP API 无效。**唯一正解 =
   `GET /webui/bootstrap`**(ws_http.py:224/268/301-329):
   `Authorization: Bearer <口令>`(token_issue_secret 空则回落
   static token,恰是我们部署形状)→ 返回
   `{"token","ws_path","ws_url","expires_in",...}`,该 token 同时进
   issued+api 两个字典 = 一个端点解决 ws 握手 + HTTP API + ws 地址发现。
   **ws 握手 token 是一次性 pop 消费**(gateway_tokens.py:57)——
   每次开 ws 必须新签,复用必 401;连接建立后无到期踢线(20s ping
   保活),**在线聊天不因 TTL 断**;api token TTL 300s,HTTP 侧 401
   → 前端透明重 bootstrap(口令在手,无感)。
3. **会话 API(v1 路径错,v2 修正)**:列表 = `GET /api/sessions`
   (ws_http.py:653);历史 = `GET /api/sessions/<key>/webui-thread`
   (ws_http.py:350),key 形如 `websocket:<chat_id>`(attach 用裸
   chat_id,注意前缀映射),支持 `limit`/`direction=latest`/`before`
   分页;鉴权 `check_api_token` 只认 api_tokens(Bearer 或 `?token=`)。
4. **信封与事件(v1 不完整,v2 补全)**:入站
   `{"type": new_chat|attach|message|fork_chat|...}`;用户 message
   信封应带 `webui: true`(+`turn_id`)才实时进 webui transcript
   (websocket.py:762-788,不带走兜底回补路径)。出站:**流式是
   回复主通道**(`streaming=True` 默认,websocket.py:84)——
   `delta`(增量,:1075)→ `stream_end`(带全文,:1065)→
   `turn_end`(:1104);另有 `reasoning_delta/reasoning_end`、
   `message` 携带 `kind: tool_hint|progress` 中间态、
   `session_updated` 等;`ready` 每次连接发**全新随机 chat_id**
   (:522-537),回原会话必须显式 `attach`。

架构结论:**ws 直连 + HTTP 走 ds_web 同源代理**(sub Claude 复核成立)。

- **代理形态 = 纯转发管道,ds_web 不持有任何秘密(D-C1)**:
  白名单三条(写死,不透传任意路径):
  - `GET /api/chat/bootstrap` → `GET /webui/bootstrap`
  - `GET /api/chat/sessions` → `GET /api/sessions`
  - `GET /api/chat/sessions/<key>/thread` → `GET /api/sessions/<key>/webui-thread`
  上游硬编码 `127.0.0.1:8765`(仅端口 DS_NANOBOT_PORT 可覆盖)。
  转发细节(F10):`<key>` 先按上游字符集 `[A-Za-z0-9_:.-]{1,128}`
  白名单校验再拼路径(杜绝路径走私);查询串(`limit`/`before`/
  `direction`/`?token=`)原样透传;只透传 `Authorization`
  (必要时 `X-Nanobot-Auth`),剥离 hop-by-hop 头;上游不可达 →
  502+JSON 错误体。前端不无脑信 bootstrap 返回的 `ws_url`,
  用 `ws_path`+已知端口自拼兜底。
  备选"ds_web 读 ~/.nanobot/config.json 拿口令自动签发(免登录)"
  不选:让只读服务变成秘密持有者,爆炸半径大;登录一次的 UX 与
  stock WebUI 相同 = 用户要的"熟悉"。
- **登录/连接流(D-C2,按 v2 token 模型)**:聊天页首次进入输一次
  nanobot 口令 → localStorage(本机回环页面;XSS 面由 D-C3 禁 raw
  HTML 闭合)→ 每次开 ws 前经 `/api/chat/bootstrap` 新签(一次性
  token,多标签页/StrictMode 双连各自独立签)→ HTTP 401 = api token
  过期 → 透明重 bootstrap;重 bootstrap 也 401 = 口令失效 → 弹回登录。
- **断线自愈(D-C5,F5)**:重连 = **重签 + 对 `ready` 给的新 chat_id
  重发 `attach`(裸 chat_id)+ refetch webui-thread 补断线期间的
  消息缺口**(断线期间回复只落 transcript,ws 不重放);指数退避
  上限 30s。
- **消息渲染(D-C3)**:GFM markdown(表格/代码块/列表),**渲染器
  必须禁 raw HTML**(选 react-markdown,默认不渲染 HTML = 天然满足;
  这是 localStorage 口令不被模型输出 XSS 偷走的结构性前提,焊 oracle
  不靠自觉);代码高亮砍到常用语言子集;katex 不做(non-goal);
  流式渲染 = delta 增量 + stream_end 定稿 + turn_end 收尾,
  tool_hint/progress 安全降级显示或忽略;新依赖(必然新增,P0 依赖
  面只有 react/react-dom)进 package-lock 锁死。
  输入框 Enter 发送必须查 `isComposing`(+keyCode 229 兜底)——
  中文输入法候选确认不能把半截拼音发出去(F8)。
- **保底(D-C4)**:stock WebUI 8765 不下线;聊天页错误横幅里给
  "打开原版界面"链接,故障时用户永远有路。

### D 双端口整合(上期递延)

`ds-nanobot.ps1` 启动 gateway 后顺手拉起 ds_web(已在跑则跳过,
端口占用明确报错);`ds-web.ps1` 保留可独立跑。install-windows.md
§5b 更新为"一条命令两个服务"。

### 开工第一件事 = 协议基线快照(不可跳;F7 加硬)

Linux 开发机起真 gateway——**配置形状必须与 Windows 部署一致
(用 enable_webui.py 产出:静态 token、零 token_issue_path)**,
禁止为跑通手工加配置,否则快照与用户机形状永久分叉。实抓完整链路
`bootstrap→ws 握手→attach→message(webui:true)→delta/stream_end/
turn_end→sessions 列表/webui-thread 历史` 存
`docs/nanobot-ws-protocol.md`(含 F11 两种信封的历史差异核实);
同时落冒烟测试(gateway 不跑则 skip 并明示)。聊天前端对协议的
全部假设以快照为准,不以源码阅读为准。

## Key trade-offs / risks

- **协议漂移**:内部协议无契约。对策 = 钉 0.2.2 + 基线快照 + 冒烟;
  升级流程写进 docs。
- **流式渲染是工程量主体**(F3):按"收整条 message"估会碎;delta
  节流渲染、stream_end 对账定稿是 T5 的验收核心。
- **token 模型**(F4 修正):在线不断;每次握手新签一次性 token;
  HTTP 401=透明重签。错误处理别把"复用旧 token 的 401"误判成
  口令失效。
- **ds_web 首次出现"发起出站请求"的面**:上游硬编码回环+路径白名单
  +key 字符集校验,oracle 锁死(非白名单 404、非 GET 405 不变量保持)。
- **oracle 假阴性缝**(F7):mock 上游全绿 ≠ 上游端点真存在;
  verify 收口把"冒烟实跑过(非 skip)"列为必要条件。
- **msvcrt 强制锁咬读者**(老递延):聊天不碰 PKB,零新增暴露。
- **意向图中途到达**:视觉=变量层,改 token 值不返工;布局大改独立
  小轮次,不阻塞聊天。
- **Windows 真机 UNTESTED 面**:ps1 整合照惯例首装即验收。

## Alternatives considered

- **iframe 嵌 stock WebUI**:双层壳/双登录/无法融入 IA,用户明确要
  "自己自由的工作台",弃。
- **8766 全反代 8765(含 ws)**:stdlib 手写 ws 代理 = 自造屎山;
  ws 不受 CORS 管,直连即可,弃。
- **FastAPI/uvicorn 升级**:本期仍纯 GET 转发,stdlib 够,弃。
- **ds_web 持有 secret 自动签发**:换只读服务变秘密持有者,弃(D-C1)。
- **token_issue_path 方案**(v1 原案):部署上端点不存在 + 签的 token
  对 HTTP API 无效,被评审推翻,弃(F1)。

## Test strategy (oracle)

主 agent 拥有,off-limits 给任何 fix 委托。

1. 代理白名单:三条路径通(mock 上游断言转发头/路径/查询串),
   任意其他 `/api/chat/*` 404;`<key>` 非法字符(含 `../`、`%2e`
   变体、超长)400/404;POST 到代理路径 405+Allow(P0 不变量延续)。
2. 上游不可达:502+JSON 错误体,不挂进程。
3. token 语义(按 F4 修正):mock 上游 bootstrap 200 → API 401 →
   断言代理透传 401 不吞(前端据此透明重签);断言转发时剥
   hop-by-hop、`Authorization` 原样。
4. XSS 闸(F6):助手消息含 `<img onerror>`/raw HTML 样例,断言
   渲染为文本不执行(react-markdown 默认行为焊成 oracle)。
5. 协议冒烟(gated,F7 加硬):**enable_webui.py 形状**的真 gateway,
   走 bootstrap→ws→attach→message→delta/stream_end→sessions/thread
   全链路断言;不跑则 skip 并打印原因;**verify 收口要求本条实跑
   通过,skip 不算 PASS**。
6. 前端:Playwright(devDeps,开发机-only,T9 写明装法)截图实检
   (聊天首屏/待办页/深浅两态);侧栏五项路由可达;dist 构建后 `/`
   返回聊天壳;isComposing 回车用组件测试或 e2e 断言。
7. 回归:现有 92 测全绿,golden 逐字节不变(本期不碰 ds_todo 核心)。

## Sub Claude 评审仲裁记录(2026-07-08,plan v1 → v2)

sub Claude 总裁定 PASS-with-changes,11 findings。主 agent 逐条仲裁
(关键条已对源码复核,依据附后):

- **F1 [HIGH] 采纳(实证)**:token_issue_path 默认空且 enable_webui.py
  不写它(核:enable_webui.py 只设 enabled/token/host/port);
  `/webui/bootstrap` 同签 issued+api token(核:ws_http.py:224/268/315
  `api_token=True`)。v1 token 方案整体作废,改单端点 bootstrap——
  还比原案少一条代理路径。**这是 v1 最可能"装完聊天不能用"的洞,
  且 mock oracle 会全绿放行——sub Claude 评审的核心价值。**
- **F2 [HIGH] 采纳(实证)**:`/api/webui/threads*` 全库零命中(v1 我
  凭记忆写错);真路径 `/api/sessions`(:653)、
  `/api/sessions/<key>/webui-thread`(:350)。代理映射+查询串透传已改。
- **F3 [HIGH] 采纳(实证)**:streaming 默认开(websocket.py:84),
  delta(:1075)/stream_end(:1065)/turn_end(:1104)。T5 按流式估。
- **F4 [MED] 采纳(实证)**:issued token pop 消费
  (gateway_tokens.py:57)= 一次性;v1 "TTL 到期重连"模型写反,已改。
- **F5 [MED] 采纳**:重连 = 重签+re-attach(裸 chat_id)+refetch 补缺口;
  与 ready 发新 chat_id(:522-537)自洽。
- **F6 [MED] 采纳**:localStorage 口令 × markdown XSS 耦合成立;
  禁 raw HTML 焊进 D-C3+oracle #4。
- **F7 [MED] 采纳**:冒烟必须用部署形状配置 + verify 要求非 skip;
  这条恰好封死 F1 型假阴性,oracle 观最重要的一条修正。
- **F8-F11 [LOW] 全采纳**:isComposing(设计师 100% 中文输入)、
  依赖面文案修正(P0 无 markdown 渲染依赖,必然新增)、代理三细节
  (key 字符集/hop-by-hop/ws_url 兜底)、信封 webui:true+turn_id。
- **拒收:无。** 11/11 采纳,3 条 HIGH 全部推翻 v1 "已核实事实"——
  v1 的协议节是主 agent 读源码时凭 grep 摘要外推的,教训:**协议
  事实必须逐行读到返回体,不能从路由分发的邻近行推端点语义**
  (与 7-04 "扒接口别顺口外推,逐个核" 同一教训第二次出现)。
