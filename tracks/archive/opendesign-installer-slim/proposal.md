# Proposal: 安装包瘦身 —— 不装业主用不到的两万个文件

- Date: 2026-08-24
- 由来:**业主说安装和卸载都很慢**。他的原话:
  「安装包可以先去掉这些内容,不要完全删除,后期需要的时候可以加回来就行」。

## 现状(实测,不是估计)

量的是 `/root/aiwork/out/opendesign-0.94.0/pkg`(就是他装的那个包解开的样子):

- 整包 **22,118 个文件 / 276 MB**
- **其中 OpenDesign 自己只有 42 个文件 / 1.4 MB**
- 剩下 22,074 个是 Python 运行时 + 第三方库

慢在哪:Windows 装的时候要**一个一个写**这两万多个小文件、卸载时**一个一个删**,
每个还要过一遍杀毒扫描。**不是压缩算法的问题** —— 换压缩参数省不下这个。

## 要砍的

| 包 | 文件数 | 体积 | 它是干嘛的 |
|---|---|---|---|
| `lark_oapi` | 10,106 | 45 MB | 飞书机器人 SDK |
| `botocore` + `boto3` + `s3transfer` | 2,064 | 31 MB | 亚马逊云(Bedrock 大模型) |
| `telegram` | 234 | 4 MB | Telegram 机器人 |
| **合计** | **12,404(占全包 56%)** | **80 MB(占 31%)** |

它们是 `pip install nanobot-ai==0.2.2` 的**传递依赖**,对应 nanobot 三个**可选连接器**:
`channels/feishu.py`、`channels/telegram.py`、`providers/bedrock_provider.py`。
**业主的代码 0 处引用**(已 grep),**配置里 `feishu.enabled = false`**,
他的主入口是 websocket(WebUI)。

## Non-goals

- 不动 Python 运行时本体、不动 PIL/lxml/cryptography 这些真在用的
- 不改压缩参数(省不下这个量级)
- **不做"按需下载"**(要联网、要签名、要断点续传,复杂度不成比例)
- 不碰 nanobot 的代码本身 —— 只在**组包时**跳过这几个目录

## 可逆性(业主明确要的)

删除清单是 `tracks/…/spike/build-package.sh` 里一个数组,**一行一个包名**。
要加回来 = **删掉那一行,重新打包**。nanobot 的代码一个字节都没改,
所以将来真要用飞书/Telegram,把包装回去就直接能用。
