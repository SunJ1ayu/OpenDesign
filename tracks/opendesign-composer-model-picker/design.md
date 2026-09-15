# Design: opendesign-composer-model-picker

- Change: opendesign-composer-model-picker
- Status: draft(主 agent;方向由业主 09-15 四项拍板 + 我读 DSH 设计笔记与 nanobot 源码)

## Approach

```
后端 ds_web
  GET  /api/llm/models  → {provider, label, current, models:[{id,label}]}
        provider = providers.custom.apiBase 对上 PROVIDERS 的哪一家(同 ds_credential.status 的判法)
        current  = ds_model.resolve_model(cfg)(preset 优先规则的唯一真相源)
        models   = 该厂商目录;对不上任何厂商 ⇒ provider=null、models=[]
  POST /api/llm/model {model} → 只许当前厂商目录里的 id;确保 model_presets[id] 存在(缺则按该厂商 apiBase 建)
        → agents.defaults.modelPreset = id → 原子写配置(ds_credential._atomic_write)→ 回同 GET 的形状
        其余字段一个不碰;key.txt 不碰;不重启网关。
        生效:nanobot 每条入站消息前重读配置(loop.py:1255 → factory.py:251),**下一句起**用新模型。

目录(ds_credential.PROVIDERS 加 models)
  mimo     = 出货模板 config/nanobot.config.windows.jsonc 的 model_presets 里全部 provider=custom 的名字(不抄第二份)
  deepseek = ["deepseek-v4-flash", "deepseek-v4-pro"](08-15 现拉核过的两个;会过期,判据钉)

前端
  ChatPage 输入卡 .tools:[+][✎ 记一下] ……… [● 模型名 ▴][发送]
    - 只在 view.kind === "connected" 时渲染模型按钮(重连中不许出现:否则界面在谎称已连接,chat_reconnect 那条语义保留)
    - 标签:GET 回来的 current,拿不到时退回 view.model(网关 hello 报的)
    - 点开向上菜单:分组标题「<厂商名> · 当前这把 key」,各模型一行(当前那行打勾),分隔线,「换厂商 / 换 key…」
    - 选中 ⇒ POST ⇒ 成功后标签换成新模型、菜单关;失败 ⇒ 菜单里一行人话错误,标签不变
    - 「换厂商 / 换 key…」⇒ 新 prop onOpenLlmKey(App 已有 setLlmKeyOpen,侧栏同款)
  删:.chat-meta 头部整块(已连接·模型名 + … + 退出登录菜单)、error 横幅里的「退出登录」按钮。logout 函数若无其他调用点一并删。
```

## Key trade-offs / risks

1. **全局而非会话级**:切了之后所有对话(含右栏项目助手、待办助手)下一句都用新模型。单人用,可接受;UI 文案不说"这个对话"。
2. **正在回复的那一轮不受影响**:nanobot 在入站消息处刷新,进行中的 turn 用旧模型跑完。
3. **POST 是新写口**:走 do_POST 已有的 `_host_ok` / `_same_site_ok`;只收目录内 id,不接受任意字符串写进配置。
4. **DeepSeek 目录会过期**:官方下架模型时菜单里会有一个选了就报错的项 —— 判据钉住目录,过期时改目录。
5. `.chat-meta` 是 e2e 判"连上了"的标记(20 处):改认 `[data-ui="chat-model"]`,**语义不变**(只在真连上时出现)。

## Alternatives considered

- **发 `/model <preset>` 聊天命令**:能即时切,但只存内存(重启回默认)、对话里冒一条英文回执;业主要"记住"。否掉。
- **改配置 + 重启网关**:能用,但会打断正在进行的回复、等几秒重连;读源码确认不需要重启。否掉。
- **输入框下面单独一行**:业主选了右下角。

## Test strategy (oracle)

主 agent 拥有,先行落盘、单独 commit。编号前缀 `lm`(后端)/ `mp`(前端纯逻辑)/ e2e 场景。

| id | 断言 | 文件 |
|---|---|---|
| `lm1` | GET:MiMo 配置 ⇒ provider=mimo、current=mimo-v2.5、models 恰为模板里的 mimo-v2.5 / mimo-v2.5-pro | `tests/test_ds_llm_model.py` |
| `lm2` | POST mimo-v2.5-pro ⇒ modelPreset 改了、其余字段逐值不变、key.txt 字节不变;回包 current 为新值 | 同上 |
| `lm3` | **nanobot 自己读得出来**:POST 之后用 nanobot 的 `load_provider_snapshot(配置)` 读,model == 新值(跨组件契约,不跑网关) | 同上 |
| `lm4` | 不在当前厂商目录里的 id(别家的、随便的串、空)⇒ 400,配置字节不变 | 同上 |
| `lm5` | DeepSeek 配置:目录恰为 v4-flash / v4-pro;POST v4-pro ⇒ 建出带 deepseek apiBase 的 preset | 同上 |
| `lm6` | 配置缺失/损坏/对不上任何厂商 ⇒ GET 回 provider=null models=[];POST 拒绝且不创建任何文件 | 同上 |
| `lm7` | 跨站 POST(Origin 非本机)⇒ 403,配置不变 | 同上 |
| `lm8` | 目录 MiMo 那半从模板读(结构:ds_credential 里不出现 "mimo-v2.5-pro" 字面) | 同上 |
| `mp1~` | 菜单项构造:分组标题含厂商名、当前项打勾、最后一项恒为「换厂商 / 换 key…」;models 为空时只剩最后一项 | `tests/test_model_picker.mjs` |
| `e2e` | 真 chromium + 真 ds_web + stub ws:连上 ⇒ 输入卡里出现模型按钮且显示模型名;页面上**没有** `.chat-meta`、**没有**「退出登录」;点开 ⇒ 菜单在按钮上方;点 pro ⇒ 真发出 POST、配置文件变了、按钮显示 pro;点「换厂商 / 换 key…」⇒ AI 模型 key 弹窗出现;重连中 ⇒ 按钮不出现 | `tests/e2e/model_picker.e2e.mjs` |

### 这个 oracle 能被什么骗过?

1. 我们写对了配置、nanobot 却不认 ⇒ `lm3` 用 nanobot 自己的读取函数问,不是我们自己的 resolve_model。
2. 界面换了标签、后端没写 ⇒ e2e 读配置文件本身。
3. "重连中也显示绿点" ⇒ e2e 断线场景断言按钮不出现。
4. 真网关里"下一句真的换了"本机没有 LLM key 验不了 ⇒ 真机清单:换到 pro 之后问一句"你是哪个模型",看回复与日志。
