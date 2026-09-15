# Proposal: opendesign-composer-model-picker

- Date: 2026-09-15
- Status: open

## Goal

聊天输入框右下角(发送键左边)显示当前模型、点开能直接换;去掉左上角「已连接 · 模型名」那一行和「…」里用不上的「退出登录」。

## Motivation

业主 09-15 装 0.98.4 验收时提的两条。

## 真问题(第一性)

- 用户原话:
  1.「现在已连接mimo-v2.5显示在主窗口的左上角，我觉得这个位置不对，我用了挺多桌面端agent基本都在输入窗口下面，然后可以切换 这样才对吧，我也忘记了有点，你能不能看看deepseek harness的代码 他们是怎么做的」
  2.「右上角三个小点点一下显示退出登录，但是我们现在不需要登录 这个是什么东西」
- 真正要解决的是:**在说话的地方看得见、换得了"是谁在回答我"**;以及界面上别有一个点了没用、还会闪一下登录框的按钮。
- 我在这中间翻译了什么:
  - 我读了 deepseek-ai/deepseek-harness 的设计笔记(.agents/notes/archived/feature/2026-07-24-web-session-model-selector.zh.md):
    选择器在输入栏尾部控件区、发送键之前,紧凑触发器显示模型名,菜单向上展开按厂商分组。它是**会话级**的;我们的底座 nanobot 是**全局**的(所有对话一起换)。
  - 「切换」翻成:写 nanobot 配置的 `agents.defaults.modelPreset`。依据是读源码:nanobot 每处理一条入站消息前重读配置
    (`agent/loop.py:1255 _refresh_provider_snapshot` → `providers/factory.py:251 load_provider_snapshot`),
    它自带的网页界面也是走 `/api/settings/update?model_preset=` 且不置 restart_required ⇒ **下一句生效、不用重启、天然记住**。
  - 业主 09-15 拍板四项(AskUserQuestion):位置 = 输入框右下角发送键左边;菜单 = 当前 key 能用的模型 + 换厂商入口;换了要记住;「退出登录」连「…」一起删。

## Scope

- in:
  - 后端 `GET /api/llm/models`(当前厂商、当前模型、当前厂商可选模型)、`POST /api/llm/model`(写 modelPreset,只许当前厂商目录里的模型)。
  - 厂商模型目录:MiMo 从出货模板的 model_presets 读(不抄第二份),DeepSeek 为 v4-flash / v4-pro。
  - 前端:输入卡 tools 行加模型按钮(连上才显示、绿点);向上菜单;选中即 POST;最后一行打开现有「AI 模型 key」。
  - 删 `.chat-meta` 头部与「退出登录」(连接时的 … 菜单,以及连不上时横幅里那颗「退出登录」)。
  - 判卷面:e2e 里拿 `.chat-meta` 判"连上了"的 20 处改认新按钮(头部被业主拍板删掉,不是放水)。
- 版本号 bump 与发版:问业主。

## Non-goals

- 不做会话级选择(nanobot 是全局的;要会话级得改底座)。
- 不做多把 key 并存 / 菜单里直接切到没 key 的厂商(业主选了"只列当前 key 能用的")。
- 不改「连接聊天服务」口令卡本身(`view.kind === "login"` 那一支还服务于认证失效时的横幅,单独一单)。
- 不做推理强度(Effort)一行:我们的两家目录没有这层元数据。
