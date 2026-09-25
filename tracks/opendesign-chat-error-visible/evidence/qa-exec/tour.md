# QA 执行 · 真界面操作录像(track opendesign-chat-error-visible)

台面:真管家 + 真网关 + 真工作台 + 真 chromium;包 = 本机按出货形状摆的一份(ds 来自 `git archive ab86b21 bin config web/dist`)。
主槽 MiMo 指到本机假厂商,回法按步骤切换(报错体 = 探针里的真厂商原文)。每步:截图 NN.jpg + 页面文字 + 当时的事实。

## 01. 打开软件,正常聊一句(基线:正常回复没有出错样式)

截图:01.jpg

- 回复:我是 MiMo,正常回复。
- 出错说明条数:0

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
你好
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 02. E1 key 不对:发一句

截图:02.jpg

- 等了毫秒:908
- 出错说明:["这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。\n原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}"]
- 还能发:true

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 03. E7 打开设置再回来

截图:03.jpg

- 出错说明:["这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。\n原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}"]

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 04. E8/故事B 从侧栏「历史对话」点回这段(走网关回放)

截图:04.jpg

- 出错说明:["这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。\n原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}"]
- 有没有英文原文当正文:false

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
✕
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 05. E2 欠费 / 额度(DeepSeek 402 原文 → 网关换成固定英文)

截图:05.jpg

- 最新出错说明:这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 06. E2b 额度(GLM 1113「余额不足」原文透传)

截图:06.jpg

- 最新出错说明:这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 07. E19 限流:网关在自己重试的那几秒(应只有思考动画,不是空白)

截图:07.jpg

- 思考动画:1

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 08. E3 限流:重试完之后

截图:08.jpg

- 等了毫秒:7841
- 最新出错说明:这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 09. E4 连不上厂商

截图:09.jpg

- 等了毫秒:7871
- 最新出错说明:这句没回上来:连不上模型厂商。
先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。
原文:Error calling LLM: Connection error.

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}
连不上的情况
这句没回上来:连不上模型厂商。
先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。
原文:Error calling LLM: Connection error.
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 10. E5 厂商服务器出错

截图:10.jpg

- 最新出错说明:这句没回上来:模型厂商那边出错了(不是你这边的问题)。
稍后再发一次;一直这样的话,在输入框右下角换一家模型。
原文:Error: {'message': 'internal server error', 'type': 'server_error'}

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}
连不上的情况
这句没回上来:连不上模型厂商。
先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。
原文:Error calling LLM: Connection error.
厂商出错的情况
这句没回上来:模型厂商那边出错了(不是你这边的问题)。
稍后再发一次;一直这样的话,在输入框右下角换一家模型。
原文:Error: {'message': 'internal server error', 'type': 'server_error'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 11. E6 认不出的错(invalid_request_error + 图片被拒)

截图:11.jpg

- 最新出错说明:这句没回上来:模型那边出错了。
再发一次试试;一直这样的话,到「设置 → 模型设置」点这家模型旁的「测试」,它会告诉你具体哪里不对。
原文:Error: {'message': 'Invalid image data', 'type': 'invalid_request_error'}

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}
连不上的情况
这句没回上来:连不上模型厂商。
先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。
原文:Error calling LLM: Connection error.
厂商出错的情况
这句没回上来:模型厂商那边出错了(不是你这边的问题)。
稍后再发一次;一直这样的话,在输入框右下角换一家模型。
原文:Error: {'message': 'internal server error', 'type': 'server_error'}
认不出的错
这句没回上来:模型那边出错了。
再发一次试试;一直这样的话,到「设置 → 模型设置」点这家模型旁的「测试」,它会告诉你具体哪里不对。
原文:Error: {'message': 'Invalid image data', 'type': 'invalid_request_error'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 12. E9/E12 改好之后再发:正常回复,没有出错样式,出错说明条数不变

截图:12.jpg

- 回复:我是 MiMo,正常回复。
- 出错说明条数:7 → 7

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}
连不上的情况
这句没回上来:连不上模型厂商。
先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。
原文:Error calling LLM: Connection error.
厂商出错的情况
这句没回上来:模型厂商那边出错了(不是你这边的问题)。
稍后再发一次;一直这样的话,在输入框右下角换一家模型。
原文:Error: {'message': 'internal server error', 'type': 'server_error'}
认不出的错
这句没回上来:模型那边出错了。
再发一次试试;一直这样的话,到「设置 → 模型设置」点这家模型旁的「测试」,它会告诉你具体哪里不对。
原文:Error: {'message': 'Invalid image data', 'type': 'invalid_request_error'}
现在好了吗
我是 MiMo,正常回复。
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 13. E13 key 错时连发两句:各有一条说明

截图:13.jpg

- 出错说明条数:9

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
我是 MiMo,正常回复
今天
项目
0
+
还没有项目——在对话里说「新建项目…」
设置
›
你好
我是 MiMo,正常回复。
帮我看看今天的待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
额度的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.
GLM 余额不足的情况
这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。
去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。
原文:Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}
限流的情况
这句没回上来:发得太频繁,厂商让等一会儿。
稍等一两分钟再发一次。
原文:Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}
连不上的情况
这句没回上来:连不上模型厂商。
先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。
原文:Error calling LLM: Connection error.
厂商出错的情况
这句没回上来:模型厂商那边出错了(不是你这边的问题)。
稍后再发一次;一直这样的话,在输入框右下角换一家模型。
原文:Error: {'message': 'internal server error', 'type': 'server_error'}
认不出的错
这句没回上来:模型那边出错了。
再发一次试试;一直这样的话,到「设置 → 模型设置」点这家模型旁的「测试」,它会告诉你具体哪里不对。
原文:Error: {'message': 'Invalid image data', 'type': 'invalid_request_error'}
现在好了吗
我是 MiMo,正常回复。
连发第一句
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
连发第二句
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 14. E10 项目助手栏里出错

截图:14.jpg

- 项目栏出错说明:["这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。\n原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}"]

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
【当前项目:翡翠湾-1801】这个项目的进度
翡翠湾-1801
今天
我是 MiMo,正常回复
今天
项目
1
+
▾
洽谈
1
翡翠湾-1801
设置
›
翡翠湾-1801
洽谈
0 天
变更记录
0 条
未办结
待确认
进行中
已办结
全部
按时间
按空间
✎
空间
⌄
记一条
还没有变更记录
在右侧对话里说「记一下:玄关柜改到 2.4 米」,会自动记进来。
记第一条变更
图片
参考 0
项目图
还没有参考图。
在对话里发图并说「登记参考图」,会出现在这里。
项目文件
还没接入你电脑上的项目文件夹。
接入工作区
项目助手
+
»
【当前项目:翡翠湾-1801】这个项目的进度
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 15. E11 待办页助手栏里出错

截图:15.jpg

- 待办栏出错说明:["这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。\n原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}"]

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
【当前项目:翡翠湾-1801】这个项目的进度
翡翠湾-1801
今天
我是 MiMo,正常回复
今天
项目
1
+
▾
洽谈
1
翡翠湾-1801
设置
›
待办事项
0 条未办结 · 0 个项目
所有项目都没有未办结事项,喝口茶吧。
项目助手
收起
帮我排一下待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 16. E24 重新打开软件,点回最早那段对话

截图:16.jpg

- 出错说明:["这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。\n原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}"]

页面文字(截取):
```
OpenDesign
新对话
搜索
待办事项
技能
›
历史对话
全部
帮我排一下待办
✕
【当前项目:翡翠湾-1801】这个项目的进度
翡翠湾-1801
今天
项目
1
+
▾
洽谈
1
翡翠湾-1801
设置
›
帮我排一下待办
这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。
到「设置 → 模型设置」找到发这句时用的那家,重新填 key,再点模型旁的「测试」确认能用。
原文:Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}
+
✎ 记一下
mimo-v2.5
▴
发送
```

## 17. E21 给「未启用」的 Kimi 存 key:提示的叫法

截图:17.jpg

- 提示:已保存。这家现在是「未启用」:把上面「未启用」旁边的开关打开,它才会出现在聊天框右下角的换模型里。
- 开关旁的字:未启用

页面文字(截取):
```
返回工作区
设置
常规
模型设置
模型设置
管理模型供应商与 API Key,配置后可在聊天时选择使用。
刷新
添加供应商
内置供应商
MiMo(小米)
DeepSeek 官方
Kimi 按量
GLM 套餐(Coding Plan)
GLM 按量
自定义供应商
暂无自定义模型供应商
Kimi 按量
未启用
未启用 · 已存 sk-q…6789(不会出现在换模型菜单里)
已保存。这家现在是「未启用」:把上面「未启用」旁边的开关打开,它才会出现在聊天框右下角的换模型里。
Base URL(只读)
API Key
获取 API Key ↗
显示
保存
模型列表
+ 添加模型
kimi-k3
测试
编辑
kimi-k2.7-code
测试
编辑
kimi-k2.6
测试
编辑
```

## 假厂商收到的请求(按模式计数)

```
{"401":7,"500":4,"ok":3,"quota":1,"glmquota":4,"rate":4,"down":4,"weird":1}
```

## 页面级 JS 报错

无
