# nanobot WebUI 协议基线快照(T0)

- 抓取日期:2026-07-08,nanobot-ai==**0.2.2**(install.ps1 已钉)
- 抓取条件:**部署形状配置**(`bin/enable_webui.py` 产出:websocket
  enabled + 静态 token + `tokenIssuePath` 空 + `streaming: true` 默认
  + path `/`),Linux 开发机真 gateway + 真 MiMo 实抓,非源码推导。
- 原则:工作台聊天前端对协议的**全部假设以本文为准**。协议是 nanobot
  内部实现、无版本契约——**升级 nanobot 前必须先跑
  `tests/test_ws_protocol_smoke.py`(见文末升级流程)**。
- ⚠️ **本文档只记"抓到过的形状",不等于 nanobot 的全部能力** —— 2026-07-26 因此
  误判过一次(见 `media` 字段一节)。要断言"协议不支持 X",必须去看 nanobot 源码,
  不能只看本文档没写。
- 本期前端不用的形状(transcribe_audio、fork_chat、file_edit、
  reasoning 展示等)只记不实现。

## 1. 鉴权模型(全链路一个端点)

**`GET /webui/bootstrap`** 是 token 唯一来源(`tokenIssuePath` 部署上
恒空,不存在也不要用):

```
GET /webui/bootstrap
Authorization: Bearer <WebUI 口令>        ← 即 config websocket.token
→ 200 {
  "token": "nbwt_…",              ← 一张 token 同时可用于 ws 握手 + HTTP API
  "ws_path": "/",
  "ws_url": "ws://127.0.0.1:8765/",  ← 按 Host 头拼的;前端用 ws_path+已知端口自拼,别无脑信
  "expires_in": 300,
  "model_name": "mimo-v2.5",
  "runtime_surface": "browser",
  "runtime_capabilities": { "can_restart_engine": false, … }
}
无/错 Authorization → 401(空 body)
```

token 语义(实测):
- **ws 握手是一次性消费**:同一 token 第二次握手被拒
  (`server rejected WebSocket connection: HTTP 401`)。
  → 每次开 ws 前必须新 bootstrap;多标签页/StrictMode 双连各自签。
- **HTTP API 侧 TTL 300s**:过期后 401 → 前端透明重 bootstrap
  (口令在手,无感);重 bootstrap 仍 401 = 口令改了 → 弹回登录。
- 连接建立后**无到期踢线**(20s ping 保活),在线聊天不因 TTL 断。

## 2. WebSocket

```
ws://127.0.0.1:8765/?client_id=<任意串>&token=<bootstrap 的 token>
```
- `client_id` 任意(仅 allowFrom 授权+日志);无 Origin 校验 → 跨源
  页面直连可行;HTTP 端点零 CORS → 必须走 ds_web 同源代理。
- 连接即收:`{"event":"ready","chat_id":"<全新随机 uuid>","client_id":…}`
  ——**每次连接都是新 chat_id**,回旧会话必须显式 attach。

### 入站信封(客户端 → gateway)

```json
{"type":"message","chat_id":"…","content":"…","webui":true,"turn_id":"<uuid>"}
{"type":"message","chat_id":"…","content":"…","media":[{"data_url":"data:image/png;base64,…","name":"客厅.png"}],"webui":true,"turn_id":"<uuid>"}
{"type":"attach","chat_id":"<旧 chat_id,裸 uuid 无前缀>"}
{"type":"new_chat"}
```

**`media` 字段(2026-07-26 补记 —— 本文档此前漏记,主 agent 据此误判"协议只能传文字")**:
- 形状 `list[{"data_url": str, "name"?: str}]`,data URL 必须是 `data:<mime>;base64,…`。
- 服务端限额(`nanobot/channels/websocket.py`):**每条消息 ≤4 张图(单张 8MB)**、
  ≤1 个视频(20MB);图片白名单 png/jpeg/webp/gif —— **svg 被显式排除**(内嵌脚本 XSS 面)。
  任一项解码失败 → 整条消息不发布,已写盘的临时文件回滚(不留半截)。
- 落盘位置 = **nanobot 自己的媒体目录**(`get_media_dir("websocket")`),
  不是项目工作区 —— 要归档进项目仍需另一步。
- **模型看不看得见,取决于模型**:2026-07-26 用真 gateway 实测 `mimo-v2.5`
  → **能看见**(4 块紫/橙/白/粉,颜色与左右顺序全对;换 2 块黄/黑同样答对)。
  探针脚本形状见本节末注。

> 探针做法(可复现):`/webui/bootstrap` 取 token → ws 连上 → 发带 `media` 的
> `message` → 收 `delta` 拼接。判据必须用**蒙不中的图**(非常规配色 + 问左右顺序);
> 首版探针用"红绿蓝三块"= 最容易蒙中的组合,且第二张图块宽不等(1/3 vs 2/3)
> 导致假阴性 —— **夹具自己错了三次里的第三次**,记此备忘。
其余 type(fork_chat / set_workspace_scope / transcribe_audio)本期不用。
- `webui:true` + `turn_id`:一等路径,消息实时进 webui transcript 且
  历史带 `turnId/turnSeq`。**实测不带也能用**(兜底回补进历史,但缺
  turnId 字段)——前端一律带上。
- attach 成功回 `{"event":"attached","chat_id":"<旧 id>"}`;非法 id 回
  `{"event":"error","detail":"invalid chat_id"}`。

### 出站事件:一轮回复的实抓序列

```
{"event":"goal_status","status":"running","started_at":…}
{"event":"reasoning_delta","text":"…","turn_id":…,"turn_phase":"reasoning"}   × N
{"event":"reasoning_end", …}
{"event":"delta","text":"收到收到","stream_id":"websocket:<chat_id>:<ns>:0",
 "turn_id":"…","turn_phase":"answer","turn_seq":8}                            × N
{"event":"stream_end","stream_id":同上,"turn_seq":9}
{"event":"turn_end","latency_ms":3390,"goal_state":{"active":false},
 "turn_phase":"complete","turn_seq":10}
```
夹杂:`session_updated`(scope: thread|metadata)、`goal_status`(idle)。
前端渲染规则(T5):**`delta` 增量拼接(按 `stream_id` 归组)→
`stream_end` 定稿 → `turn_end` 收尾解锁输入**;`reasoning_*` 本期忽略;
`message` 事件带 `kind: tool_hint|progress` 的中间态安全降级;
未知 event 一律忽略不崩(协议会长)。

#### `message` / `kind:"progress"` 的实抓形状(2026-08-04,track opendesign-chat-reconnect)

此前这里只有上面那一句话、**没有字段**,于是 T5b 差点照猜的形状写判据。真抓一次
(本机活 gateway,问「有什么待办」逼它调 `list_todos`),完整时序:

```
ready → goal_status(running) → reasoning_delta×19 → reasoning_end → stream_end
      → message(kind:"progress")          ← 就这一帧
      → reasoning_delta×5 → reasoning_end → delta×79 → stream_end → turn_end
```

```jsonc
{"event":"message","kind":"progress","chat_id":"…","turn_id":"…",
 "turn_phase":"activity","turn_seq":23,
 "text":"",                      // ← **空字符串**,别指望拿它当提示文案
 "tool_events":[{"version":1,"phase":"end",     // ← 只见 end,没见 start
                 "call_id":"call_…","name":"mcp_design-studio_list_todos_tool",
                 "arguments":{"stale_days":7},"result":"{…工具原始返回…}",
                 "embeds":…,"error":…,"files":…}]}
```

**三条会决定前端怎么做的事实**:
1. **它是"事后回执"不是"进度"** —— `phase:"end"`,工具**已经跑完**才发。
   拿它显示「正在查资料…」,那行字会在用户等完之后才出现,等于没有。
2. `text` 是空的;有信息量的是 `tool_events[].name` 与 `arguments`。
3. **等待期间真正有信号的是 `reasoning_delta`(思考中就在流)和 `goal_status:running`**
   —— 前端今天把 `reasoning_*` 全忽略,所以从发出到出字的那几十秒界面是死的。
   要做"活着的反馈",信号得从这两个来,不是从 `message/progress` 来。

⚠️ `kind:"tool_hint"` 这一次**一帧都没出现**(只有 `progress`)。它是否还存在、
什么条件下发,**未实抓** ⇒ 前端按"两种都可能、都当活动事件"处理,不许断言必然出现。
注意:echo 回来的 `turn_id` 只在**带 webui:true 的信封**那轮出现。

## 3. HTTP API(经 ds_web 代理,鉴权同一张 token)

```
GET /api/sessions
Authorization: Bearer <token>     (也认 ?token= 查询参数)
→ 200 {"sessions":[{"key":"websocket:<chat_id>","created_at":"…",
       "updated_at":"…","title":"收到收到","preview":"<首条用户消息>",
       "workspace_scope":{…}}, …]}     ← 按 updated_at 倒序可用于会话列表
```
```
GET /api/sessions/<key>/webui-thread[?limit=N&direction=latest&before=…]
→ 200 {"schemaVersion":3,"sessionKey":"websocket:<chat_id>",
  "messages":[
    {"id":"u-0-…","role":"user","content":"…","turnId":"…",
     "turnPhase":"user","turnSeq":1,"createdAt":<ms>},
    {"id":"as-1-…","role":"assistant","content":"收到收到",
     "isStreaming":false,"reasoning":"…","activitySegmentId":"activity-1",
     "turnId":"…","turnPhase":"answer","createdAt":<ms>,"latencyMs":3390}
  ],
  "has_pending_tool_calls":false,"workspace_scope":{…}}
坏 token → 401(空 body)
```
- **key 前缀映射**:sessions/thread 的 key = `websocket:<chat_id>`;
  ws 的 attach 用裸 `<chat_id>`。key 字符集 `[A-Za-z0-9_:.-]{1,128}`
  (代理层先验)。
- 分页实测可用:`?limit=1&direction=latest` 返回最新 1 条。
- assistant 消息自带 `reasoning` 全文字段(本期不展示)。

## 4. 重连流(断线自愈,T6 依据)

断线期间的回复只落 transcript,ws **不重放** → 重连三步:
1. 重 bootstrap(旧 ws token 已被消费,复用必 401——**别把这个 401
   误判成口令失效**);
2. 新连接收 `ready`(新 chat_id)后,对旧 chat_id 发 `attach`;
3. refetch `webui-thread` 补消息缺口。

## 5. 升级 nanobot 流程

1. 改版本前先跑 `python tests/test_ws_protocol_smoke.py`(gateway 在跑,
   基线绿);2. 升级;3. 再跑,红了逐条对本文档核对差异并更新文档+前端;
4. install.ps1 钉的版本号同步改。冒烟 skip(gateway 没跑)不算通过。
5. **再跑一次 `tracks/opendesign-turn-id/evidence/probe_turnid.py`**(2026-08-05 加):
   重连对账整套押在**一条外部契约**上 —— gateway 把我们发的 `turn_id` 与消息原文
   逐字节写回 `webui-thread`。这条契约一旦漂移,前端不会报错,而是**每次重连都把全部
   本地消息当成"服务端没有"再追加一遍**(满屏重复气泡)。单测与 e2e 的 turnId 都是
   夹具自己填的,**照不出上游行为变化**,只有这个探针能。红了先改前端别改探针。
