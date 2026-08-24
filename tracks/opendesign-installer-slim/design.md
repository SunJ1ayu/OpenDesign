# Design: 组包时按清单跳过

- Date: 2026-08-24

## P0 前提探针(**已跑,PASS** —— 这一单唯一的真风险)

**要证的**:删掉这几个包之后,nanobot 还起不起得来?
`channels/telegram.py` 的 `from telegram import ...` 是**模块级**的 ——
只要有谁无条件 import 那个模块,删了就是开不了机。

**怎么证的**:`probes/p0-import-graph.py`。用 `sys.meta_path` 拦截器把候选包
**从导入系统里抹掉**(对 import 来说与真删等价 —— 抛的就是 `ModuleNotFoundError`),
然后真跑 nanobot 0.2.2 的启动路径。收据:`evidence/p0-import-graph.txt`。

结论(5 步全 OK):

1. `import nanobot.cli.commands`(`python -m nanobot` 的入口)—— 过
2. `discover_channel_names()` 号称零 import —— 属实,`pkgutil.iter_modules` 只列名字
3. `discover_enabled({"websocket"})`(**业主的真实形态**)—— 只加载 websocket
4. `discover_all()`(**最坏路径**,把所有通道都 import 一遍)—— **优雅跳过**,不崩。
   `registry.py` 的 `load_channel_class` 外面接的就是 `except ImportError` → `logger.debug`
5. `import nanobot.providers.bedrock_provider` —— 过(`boto3` 是**函数内**导入)

**对照组**(什么都不抹):`discover_all()` 拿到 **15** 个;抹掉之后 **13** 个 ——
**正好少 feishu + telegram 两个,没有波及第三个**。
(16 个通道名里 `matrix` 在对照组就加载不了 —— **它本来就缺 SDK,不是本单造成的**。)

> 🔴 对照组这一步不能省。没有它,"13 < 16" 看起来像我砍多了。

## 做法

`tracks/opendesign-windows-installer/spike/build-package.sh`:在 `pip install --target`
之后、组包之前,按一个显式数组把目录删掉。

```
SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram ...)
```

**为什么是"装完再删"而不是"别装"**:`pip` 没有"装这个包但别装它的某个依赖"的开关;
`--no-deps` 会把**真需要的**依赖也一起挡掉。装完再删是唯一不碰 nanobot 打包元数据的做法。

**连带要删的**:`*.dist-info` 目录(否则 `importlib.metadata` 会说包在、实际不在,
`entry_points` 扫描时会拿到一个指向空气的入口)。这一条是判据 g4 守着的。

## 说清楚的代价

- **飞书 / Telegram / 亚马逊云 Bedrock 在这个包里用不了了。** 业主没用过,
  配置里 feishu 也是 `enabled: false`。要用就把那几行从清单里删掉重新打包。
- `nanobot channels list` 之类的命令会少列几个 —— 那是**期望行为**,不是 bug。

## 判据要问什么(**不许只问"删掉了没有"**)

0.92/0.93 连着两版的教训是**判据问了手段、没问结果**。这一单同理:

- g1 清单里的包**真的没进包**(问产物,不是问脚本里有没有那行)
- g2 **真在用的那些一个都没少**(PIL/lxml/cryptography/mcp/nanobot… 白名单反向查)
- g3 **删完之后 nanobot 还起得来** —— 这条是 P0 探针的**常驻版**,不是一次性探针
- g4 `dist-info` 与包**同生共死**(删了包留下元数据 = 更坏的状态)
- g5 清单是**显式数组**,不许写成通配符/正则(一个 `*` 能把 PIL 一起带走)
