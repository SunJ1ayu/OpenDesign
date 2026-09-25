我先读快照 diff 和聊天事件处理代码，核对「出错时什么都不显示」是否真由丢弃无 `kind` 的 `message` 造成。
diff 里的方案文件是空模板，真正的行为在聊天事件处理和设置文案里。我接着核对这些代码，以及 nanobot 出错消息的实际形状。
网关把出错原文怎么发出、历史里怎么落成助手行，决定分类函数会不会把正常回复也改写。我接着读这两处。
## 1. 完全照做后，业主目标仍会失败

业主按提示去改密钥或充值，聊天却仍不回复：网关给聊天的不是 HTTP 状态码，而是 `Error: ` 加上厂商正文前 500 字，或被整句换掉的英文。

证据：`openai_compat_provider.py:1409` 把异常收成 `Error: {body}`；欠费在 `runner.py:602-606` 被换成固定英文，厂商原文（含 `insufficient_quota`）到不了网页。探针里的 `Invalid API key` 只是假厂商的一句。真机常见的是 `Incorrect API key provided` 这类 `invalid_request_error`，而 `invalid_request_error` 也用于模型名错误、图片被拒。关键词对上就把人送去重填密钥；对不上就落进「稍后再试」。另外 `runner.py:475` 的工具崩溃也是无 `kind` 的 `Error: …`，会被同一套前缀收成「模型出错」。回放更糟：`hydrateFromThread`（`transcript.ts:150-172`）只有 `content`，模型若原样引用那句欠费英文，切走再回来会变成「去充值」，原来的回答没了。原文若塞进同一条助手气泡，`ChatPage.tsx:1040` 的 `renderMarkdown` 会把 `invalid_request_error` 里的下划线当成强调，备查小字是花的。

## 2. 哪个前提为假就要推倒

「出错原文形状稳定，能靠固定前缀加厂商关键词分成四条去向」已经不成立，分类器要重做。

证据：前缀本身在（`Error:` / `Error calling LLM:`，`openai_compat_provider.py:1409`、`1614`；欠费整句 `runner.py:60-63`）。关键词不稳定：正文是 `str(body)[:500]`，欠费路径把正文换掉；设置页能说人话是因为 `_plain_http_reason`（`ds_credential.py:1351-1361`）看得到 HTTP 码，聊天这条线没有这个字段。无 `kind` 的 `message` 就是「没走过流式」的那条完整答复，这半截前提成立：成功流式会打上 `_streamed` 并不再 `send`（`loop.py:1364-1365`，`channels/manager.py:393-394`），所以「凡无 kind 的 message 都追加成助手气泡」不会把正常回答再显示一遍。

## 3. 更稳的方向，以及怎么分辨

聊天里不要猜四类原因；只认 nanobot 自己的壳，统一告诉业主去点那一行的「测试」。

最小实验：纯函数喂 8 条字符串——探针五句、一条 OpenAI 式 `Error: {"message":"Incorrect API key provided","type":"invalid_request_error"}`、一条同样 type 但 message 是模型不存在、一条 `Error: RuntimeError: …`、一条正常回答里引用欠费整句。拟议分类器会把密钥说成重试、或把非密钥 400 / 工具错误 / 引用句说成去改密钥。下面这个函数只改写前五句加「Incorrect API key」那条，后三条原文不动。

Direction: 无 `kind` 的 `message` 仍追加为助手气泡；人话只认 nanobot 的壳（`Error: {` / `Error: {'`、`Error calling LLM:`、欠费那句整句、`Sorry, I encountered an error.`），一律写成「这句没答成。打开模型设置，对正在用的那一行点「测试」，测试会说明是密钥、额度还是连不上。」原文用纯文本附在后面，不进 markdown。`modelSettings.ts:252` 的「打开「启用」」改成和开关一致的「未启用 / 已启用」（`ModelSettings.tsx:330`）。

Core bet: 业主要的是知道下一步按哪里，不是在聊天里重做一套厂商错误分类。HTTP 码和厂商原话已经在「测试」里说清楚了；聊天这条线拿不到状态码，硬分类会把人指去错误的门口。

How it works: `applyEvent` 与 `hydrateFromThread` 共用一个函数：整段命中上述壳才换成那一句中文加纯文本原文；`Error: RuntimeError:` 这类工具错误和普通回答保持原文。实时和回放因此是同一句。

Best at: 探针里的五种模型失败都会马上出现同一句中文，切走再回来不变；密钥措辞和假厂商不一致时也不会叫人干等。

Sacrifices: 聊天里不区分「去充值」和「去改密钥」，多一次「测试」点击；工具崩溃仍然是英文原文（至少看得见）。

Blind spots in the brief: 限流/500/断线前网关会先重试约 7 秒，这段只有「思考中」点点（`goal_status` → `transcript.ts:234-237`），气泡要等重试结束。简报把五种失败写成同一条序列，但没写 `invalid_request_error` 并不等于密钥错，也没写回放分不清「报错」和「模型在引用这句报错」。

Smallest first step: 在 `transcript.ts` 旁加一个纯函数和上面 8 条夹具，先锁「谁改写、谁保持原文」，再接到 `applyEvent` / `hydrateFromThread`。

结论: 需改
