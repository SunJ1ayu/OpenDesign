# QA-执行 操作录像(主 agent 在真界面上走一遍;截图 NN.jpg 同目录)

台面:真 ds_web + 当前 web/dist;假外壳应答重启(1.5 秒后起好);本机假厂商(只认 gpt-4.1-mini)。key 都是假的。

## 01 首次打开(一把 key 都没有)

- 地址:`/#/settings/models`
- 这一步要看的:自动进「设置 · 模型设置」,右边是第一家 MiMo
- 截图:01.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 未就绪":
      - text: MiMo(小米)
      - img "未就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 还没填 API Key
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 输入 API Key
  - button "显示正在输入的 key": 显示
  - button "保存"
  - paragraph: 设置 API Key 后即可在聊天里选这家的模型。
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
```

## 02 填 MiMo 的 key(还没点保存)

- 地址:`/#/settings/models`
- 这一步要看的:输入框是密码框;「显示」只管正在输入的这把
- 截图:02.jpg

页面无障碍文本(读屏看到的):

```
(这一步输入框里有 key,不取读屏文本)
```

## 03 MiMo 保存后

- 地址:`/#/settings/models`
- 这一步要看的:提示正在重启后台;左栏 MiMo 圆点在重启完成前是黄的(未就绪)
- 截图:03.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - status: 后台已重启,这把 key 已生效,可以在聊天里选这家的模型了。
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
```

## 04 后台重启完成

- 地址:`/#/settings/models`
- 这一步要看的:MiMo 变成就绪(绿点),状态句「在用 · 已存 …」
- 截图:04.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - status: 后台已重启,这把 key 已生效,可以在聊天里选这家的模型了。
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
```

## 05 返回工作区(首页)

- 地址:`/#/`
- 这一步要看的:输入框右下角是模型按钮
- 截图:05.jpg

页面无障碍文本(读屏看到的):

```
- navigation:
  - text: OpenDesign
  - button "新对话"
  - button "搜索"
  - button "待办事项"
  - button "技能 ›"
  - text: 项目 0
  - button "+"
  - text: 还没有项目——在对话里说「新建项目…」
  - button "设置 ›"
- text: 今天想聊点什么?
- textbox "聊设计、找参考,或「记一下…」"
- button "+"
- button "✎ 记一下"
- button "mimo-v2.5 ▴"
- button "发送" [disabled]
- button "新建一个项目"
- button "这周有哪些变更没确认?"
- button "找一张客厅参考图"
```

## 06 点模型按钮

- 地址:`/#/`
- 这一步要看的:向上弹;每家一行(当前那家 ✓ 和 ›),底行「管理模型」
- 截图:06.jpg

页面无障碍文本(读屏看到的):

```
- navigation:
  - text: OpenDesign
  - button "新对话"
  - button "搜索"
  - button "待办事项"
  - button "技能 ›"
  - text: 项目 0
  - button "+"
  - text: 还没有项目——在对话里说「新建项目…」
  - button "设置 ›"
- text: 今天想聊点什么?
- textbox "聊设计、找参考,或「记一下…」"
- button "+"
- button "✎ 记一下"
- button "mimo-v2.5 ▴" [expanded]
- menu:
  - menuitem "MiMo(小米)"
  - menuitem "管理模型"
- button "发送" [disabled]
- button "新建一个项目"
- button "这周有哪些变更没确认?"
- button "找一张客厅参考图"
```

## 07 移到 MiMo

- 地址:`/#/`
- 这一步要看的:向右弹出 MiMo 的模型(含 v2.6-pro / v2.6-flash),当前那个打勾
- 截图:07.jpg

页面无障碍文本(读屏看到的):

```
- navigation:
  - text: OpenDesign
  - button "新对话"
  - button "搜索"
  - button "待办事项"
  - button "技能 ›"
  - text: 项目 0
  - button "+"
  - text: 还没有项目——在对话里说「新建项目…」
  - button "设置 ›"
- text: 今天想聊点什么?
- textbox "聊设计、找参考,或「记一下…」"
- button "+"
- button "✎ 记一下"
- button "mimo-v2.5 ▴" [expanded]
- menu:
  - menuitem "MiMo(小米)" [expanded]
  - menu:
    - menuitemradio "mimo-v2.5" [checked]
    - menuitemradio "mimo-v2.5-pro"
    - menuitemradio "mimo-v2.6-pro"
    - menuitemradio "mimo-v2.6-flash"
  - menuitem "管理模型"
- button "发送" [disabled]
- button "新建一个项目"
- button "这周有哪些变更没确认?"
- button "找一张客厅参考图"
```

## 08 选了 mimo-v2.6-pro

- 地址:`/#/`
- 这一步要看的:菜单收起,按钮上的字换成新模型
- 截图:08.jpg

页面无障碍文本(读屏看到的):

```
- navigation:
  - text: OpenDesign
  - button "新对话"
  - button "搜索"
  - button "待办事项"
  - button "技能 ›"
  - text: 项目 0
  - button "+"
  - text: 还没有项目——在对话里说「新建项目…」
  - button "设置 ›"
- text: 今天想聊点什么?
- textbox "聊设计、找参考,或「记一下…」"
- button "+"
- button "✎ 记一下"
- button "mimo-v2.6-pro ▴"
- button "发送" [disabled]
- button "新建一个项目"
- button "这周有哪些变更没确认?"
- button "找一张客厅参考图"
```

## 09 点「管理模型」

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:进设置页模型设置,落在当前那家 MiMo
- 截图:09.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
```

## 10 添加模型弹窗

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:模型 ID + 上下文窗口
- 截图:10.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - dialog "添加模型":
    - heading "添加模型" [level=3]
    - paragraph: 给 MiMo(小米) 加一个模型,加完就能在聊天里选。
    - text: 模型 ID
    - textbox "例如 mimo-v2.6-pro"
    - text: 上下文窗口
    - textbox "可不填,例如 262144"
    - button "取消"
    - button "保存"
```

## 11 填错模型 ID(带空格)

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:弹窗里说人话,不新增
- 截图:11.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - dialog "添加模型":
    - heading "添加模型" [level=3]
    - paragraph: 给 MiMo(小米) 加一个模型,加完就能在聊天里选。
    - text: 模型 ID
    - textbox "例如 mimo-v2.6-pro": mimo v2.7
    - text: 上下文窗口
    - textbox "可不填,例如 262144"
    - paragraph: "模型 ID 不对:只能用字母、数字和 . _ - : / +,不超过 128 个字符"
    - button "取消"
    - button "保存"
```

## 12 加好了 mimo-v2.7-preview

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:列表多一行,上下文 26.2万,有「删除」;内置模型没有「删除」
- 截图:12.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - status: 已添加 mimo-v2.7-preview
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.7-preview 26.2万
  - button "测试"
  - button "编辑"
  - button "删除"
```

## 13 选 DeepSeek(还没填)

- 地址:`/#/settings/models?provider=deepseek`
- 这一步要看的:状态句「还没填 API Key」,有「获取 API Key」链接
- 截图:13.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "DeepSeek 官方" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 还没填 API Key
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://api.deepseek.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.deepseek.com/api_keys
  - textbox "API Key":
    - /placeholder: 输入 API Key
  - button "显示正在输入的 key": 显示
  - button "保存"
  - paragraph: 设置 API Key 后即可在聊天里选这家的模型。
  - text: 模型列表
  - button "+ 添加模型"
  - text: deepseek-v4-flash
  - button "测试"
  - button "编辑"
  - text: deepseek-v4-pro
  - button "测试"
  - button "编辑"
```

## 14 存 DeepSeek 的 key

- 地址:`/#/settings/models?provider=deepseek`
- 这一步要看的:当前模型不变;提示正在重启后台
- 截图:14.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未就绪":
      - text: DeepSeek 官方
      - img "未就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "DeepSeek 官方" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 已保存 sk-q…89ab,正在重启后台…重启完成后就能在聊天里选
  - status: 已保存,正在自动重启后台服务,稍等片刻即可继续使用;若稍后仍连不上,请手动重启 OpenDesign。
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://api.deepseek.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.deepseek.com/api_keys
  - textbox "API Key":
    - /placeholder: 已保存 sk-q…89ab,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: deepseek-v4-flash
  - button "测试"
  - button "编辑"
  - text: deepseek-v4-pro
  - button "测试"
  - button "编辑"
```

## 15 禁用 DeepSeek

- 地址:`/#/settings/models?provider=deepseek`
- 这一步要看的:圆点变灰,状态句「已禁用 …」,末四位还在
- 截图:15.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 未启用":
      - text: DeepSeek 官方
      - img "未启用"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "DeepSeek 官方" [level=3]
  - text: 未启用
  - switch "启用供应商"
  - paragraph: 已禁用 · 已存 sk-q…89ab(不会出现在换模型菜单里)
  - status: 已禁用 DeepSeek 官方
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://api.deepseek.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.deepseek.com/api_keys
  - textbox "API Key":
    - /placeholder: 已保存 sk-q…89ab,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: deepseek-v4-flash
  - button "测试"
  - button "编辑"
  - text: deepseek-v4-pro
  - button "测试"
  - button "编辑"
```

## 16 想禁用正在用的 MiMo

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:拒绝并说为什么,开关不动
- 截图:16.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - status: MiMo(小米) 正在用,先在聊天框里换到别家的模型再禁用
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.7-preview 26.2万
  - button "测试"
  - button "编辑"
  - button "删除"
```

## 17 添加供应商表单

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:名称 / Base URL / API Key / API 格式(只读)/ 每行一个模型
- 截图:17.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - status: MiMo(小米) 正在用,先在聊天框里换到别家的模型再禁用
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.7-preview 26.2万
  - button "测试"
  - button "编辑"
  - button "删除"
  - dialog "添加模型供应商":
    - heading "添加模型供应商" [level=3]
    - paragraph: 配置一个完全自定义的 API 端点和初始模型。
    - text: 名称
    - textbox "如:我的中转"
    - text: Base URL
    - textbox "https://api.example.com/v1"
    - text: API Key
    - textbox "输入 API Key"
    - text: API 格式 Chat Completions (/v1/chat/completions) 模型
    - textbox "每行一个模型名称"
    - button "取消"
    - button "添加供应商"
```

## 18 Base URL 填成小米的

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:拒收并说明
- 截图:18.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - paragraph: 暂无自定义模型供应商
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - status: MiMo(小米) 正在用,先在聊天框里换到别家的模型再禁用
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.7-preview 26.2万
  - button "测试"
  - button "编辑"
  - button "删除"
  - dialog "添加模型供应商":
    - heading "添加模型供应商" [level=3]
    - paragraph: 配置一个完全自定义的 API 端点和初始模型。
    - text: 名称
    - textbox "如:我的中转": 冒充小米
    - text: Base URL
    - textbox "https://api.example.com/v1": https://token-plan-cn.xiaomimimo.com/v1
    - text: API Key
    - textbox "输入 API Key"
    - text: API 格式 Chat Completions (/v1/chat/completions) 模型
    - textbox "每行一个模型名称": gpt-4.1-mini
    - paragraph: 这个地址已经是「MiMo(小米)」了,直接在它那页配置
    - button "取消"
    - button "添加供应商"
```

## 19 加好了「公司中转」

- 地址:`/#/settings/models?provider=c_1`
- 这一步要看的:左栏「自定义供应商」下多一家;右边是它的详情(名称、Base URL 可改,格式只读)
- 截图:19.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - button "公司中转 未就绪":
      - text: 公司中转
      - img "未就绪"
  - textbox "名称": 公司中转
  - button "删除供应商"
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 已保存 sk-q…abcd,正在重启后台…重启完成后就能在聊天里选
  - status: 已保存,正在自动重启后台服务,稍等片刻即可继续使用;若稍后仍连不上,请手动重启 OpenDesign。
  - text: Base URL
  - textbox "Base URL":
    - /placeholder: https://api.example.com/v1
    - text: http://127.0.0.1:40441/v1
  - text: API 格式 Chat Completions (/v1/chat/completions)
  - button "保存名称和地址" [disabled]
  - text: API Key
  - textbox "API Key":
    - /placeholder: 已保存 sk-q…abcd,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: gpt-4.1-mini
  - button "测试"
  - button "编辑"
  - button "删除"
  - text: claude-lite
  - button "测试"
  - button "编辑"
  - button "删除"
```

## 20 点「测试」(gpt-4.1-mini)

- 地址:`/#/settings/models?provider=c_1`
- 这一步要看的:不等重启就能测,显示连接成功
- 截图:20.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - button "公司中转 未就绪":
      - text: 公司中转
      - img "未就绪"
  - textbox "名称": 公司中转
  - button "删除供应商"
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 已保存 sk-q…abcd,正在重启后台…重启完成后就能在聊天里选
  - status: 已保存,正在自动重启后台服务,稍等片刻即可继续使用;若稍后仍连不上,请手动重启 OpenDesign。
  - text: Base URL
  - textbox "Base URL":
    - /placeholder: https://api.example.com/v1
    - text: http://127.0.0.1:40441/v1
  - text: API 格式 Chat Completions (/v1/chat/completions)
  - button "保存名称和地址" [disabled]
  - text: API Key
  - textbox "API Key":
    - /placeholder: 已保存 sk-q…abcd,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: gpt-4.1-mini
  - button "测试"
  - button "编辑"
  - button "删除"
  - text: claude-lite
  - button "测试"
  - button "编辑"
  - button "删除"
  - status: 公司中转 / gpt-4.1-mini 连接成功
```

## 21 点「测试」(claude-lite,假厂商没有这个模型)

- 地址:`/#/settings/models?provider=c_1`
- 这一步要看的:失败给可读原因
- 截图:21.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - button "公司中转 未就绪":
      - text: 公司中转
      - img "未就绪"
  - textbox "名称": 公司中转
  - button "删除供应商"
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 已保存 sk-q…abcd,正在重启后台…重启完成后就能在聊天里选
  - status: 已保存,正在自动重启后台服务,稍等片刻即可继续使用;若稍后仍连不上,请手动重启 OpenDesign。
  - text: Base URL
  - textbox "Base URL":
    - /placeholder: https://api.example.com/v1
    - text: http://127.0.0.1:40441/v1
  - text: API 格式 Chat Completions (/v1/chat/completions)
  - button "保存名称和地址" [disabled]
  - text: API Key
  - textbox "API Key":
    - /placeholder: 已保存 sk-q…abcd,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: gpt-4.1-mini
  - button "测试"
  - button "编辑"
  - button "删除"
  - text: claude-lite
  - button "测试"
  - button "编辑"
  - button "删除"
  - status: 公司中转 / claude-lite 连接失败:404 model not found
```

## 22 换模型菜单(三家)

- 地址:`/#/`
- 这一步要看的:MiMo ✓、DeepSeek、公司中转;移到公司中转弹出它的两个模型
- 截图:22.jpg

页面无障碍文本(读屏看到的):

```
- navigation:
  - text: OpenDesign
  - button "新对话"
  - button "搜索"
  - button "待办事项"
  - button "技能 ›"
  - text: 项目 0
  - button "+"
  - text: 还没有项目——在对话里说「新建项目…」
  - button "设置 ›"
- text: 今天想聊点什么?
- textbox "聊设计、找参考,或「记一下…」"
- button "+"
- button "✎ 记一下"
- button "mimo-v2.6-pro ▴" [expanded]
- menu:
  - menuitem "MiMo(小米)"
  - menuitem "DeepSeek 官方"
  - menuitem "公司中转" [expanded]
  - menu:
    - menuitemradio "gpt-4.1-mini"
    - menuitemradio "claude-lite"
  - menuitem "管理模型"
- button "发送" [disabled]
- button "新建一个项目"
- button "这周有哪些变更没确认?"
- button "找一张客厅参考图"
```

## 23 设置 · 常规

- 地址:`/#/settings/general`
- 这一步要看的:原来设置弹层里的各项;浏览器里显示版本与发布页
- 截图:23.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "常规" [level=2]
  - text: 外观 浅色 深色即将支持 数据与备份 /tmp/ds-qa-tour-W3QPaI/ds
  - button "工作区文件夹 哪些算项目 ›"
  - button "危险动作确认 每次问我 ›"
  - text: 快捷键 ⌘N 新对话 · ⌘K 搜索
  - heading "软件更新" [level=2]
  - link "当前版本 v0.98.11 发布页 ›":
    - /url: https://github.com/SunJ1ayu/OpenDesign/releases
```

## 24 项目页右栏的换模型菜单

- 地址:`/#/workspace`
- 这一步要看的:按钮贴着窗口右边:子菜单右边放不下时应翻到左边
- 截图:24.jpg

页面无障碍文本(读屏看到的):

```
- navigation:
  - text: OpenDesign
  - button "新对话"
  - button "搜索"
  - button "待办事项"
  - button "技能 ›"
  - text: 项目 0
  - button "+"
  - text: 还没有项目——在对话里说「新建项目…」
  - button "设置 ›"
- text: 还没有项目 在右侧对话里说「新建项目:小区名-户号」,项目会出现在左侧列表。 图片
- button "参考 0"
- button "项目图"
- text: 还没有参考图。 在对话里发图并说「
- button "登记参考图"
- text: 」,会出现在这里。 项目文件 读取中… 项目助手
- button "+"
- button "»"
- paragraph: 就着这个项目,让我替你搭把手——
- button "催一下没回的业主"
- button "整理这个项目的文件夹"
- button "汇总还没确认的"
- textbox "问这个项目,或「记一下…」"
- button "+"
- button "✎ 记一下"
- button "mimo-v2.6-pro ▴" [expanded]
- menu:
  - menuitem "MiMo(小米)" [expanded]
  - menuitem "DeepSeek 官方"
  - menuitem "公司中转"
  - menu:
    - menuitemradio "mimo-v2.5"
    - menuitemradio "mimo-v2.5-pro"
    - menuitemradio "mimo-v2.6-pro" [checked]
    - menuitemradio "mimo-v2.6-flash"
    - menuitemradio "mimo-v2.7-preview"
  - menuitem "管理模型"
- button "发送" [disabled]
```

## 25 窄窗口(1024×700)· 模型设置

- 地址:`/#/settings/models?provider=mimo`
- 这一步要看的:看左右两栏、按钮是否挤坏
- 截图:25.jpg

页面无障碍文本(读屏看到的):

```
- navigation "设置":
  - button "返回工作区" [expanded]
  - text: 设置
  - button "常规"
  - button "模型设置"
- main:
  - heading "模型设置" [level=2]
  - paragraph: 管理模型供应商与 API Key,配置后可在聊天时选择使用。
  - button "刷新"
  - button "添加供应商"
  - complementary:
    - heading "内置供应商" [level=3]
    - button "MiMo(小米) 就绪":
      - text: MiMo(小米)
      - img "就绪"
    - button "DeepSeek 官方 就绪":
      - text: DeepSeek 官方
      - img "就绪"
    - button "Kimi 按量 未就绪":
      - text: Kimi 按量
      - img "未就绪"
    - button "GLM 套餐(Coding Plan) 未就绪":
      - text: GLM 套餐(Coding Plan)
      - img "未就绪"
    - button "GLM 按量 未就绪":
      - text: GLM 按量
      - img "未就绪"
    - heading "自定义供应商" [level=3]
    - button "公司中转 就绪":
      - text: 公司中转
      - img "就绪"
  - heading "MiMo(小米)" [level=3]
  - text: 已启用
  - switch "禁用供应商" [checked]
  - paragraph: 在用 · 已存 tp-q…cdef
  - text: Base URL(只读)
  - textbox "Base URL(只读)": https://token-plan-cn.xiaomimimo.com/v1
  - text: API Key
  - link "获取 API Key ↗":
    - /url: https://platform.xiaomimimo.com/token-plan
  - textbox "API Key":
    - /placeholder: 已保存 tp-q…cdef,粘贴新的 key 即可替换
  - button "显示正在输入的 key": 显示
  - button "保存"
  - text: 模型列表
  - button "+ 添加模型"
  - text: mimo-v2.5 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.5-pro 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-pro 在用 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.6-flash 12.8万
  - button "测试"
  - button "编辑"
  - text: mimo-v2.7-preview 26.2万
  - button "测试"
  - button "编辑"
  - button "删除"
```
