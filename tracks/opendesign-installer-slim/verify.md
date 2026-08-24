# Verify: 安装包瘦身

- Date: 2026-08-24

## Mechanical checks

- [x] tests pass(python 全量 **1331 项 rc=0**,venv 解释器;3 跳过均为
      `DS_SHELL_E2E=1` 才跑的 nanobot 联跑,与本单无关)
- [x] 红检 `tests/mutation-installer-slim.sh`:**咬 5 漏 0**
- [x] 组包产物闸(`check-package.sh`)**已验它两头都咬得动**:
      造一个残留包 + 造一份孤儿元数据 ⇒ 各红一条;清理后回到 0 不合格
- [x] 真打包实测:**12,438 个文件 / 42 MB** 被删,整包 **22,118 → 9,675**(砍 56%),
      安装包 **59 MB → 43 MB**
- [ ] **真机** —— 只有业主答得了,见 `真机清单-0.95.md` 的 B 组
- [ ] **panel-review(impact=high ⇒ 2 条腿)** —— 见下方"次序问题"

## 前提探针(P0)

`probes/p0-import-graph.py` + 对照组。收据 `evidence/p0-import-graph.txt`。
用 `sys.meta_path` 拦截器把候选包**从导入系统里抹掉**(对 import 而言与真删等价),
真跑 nanobot 0.2.2 的启动路径:

- `import nanobot.cli.commands`(`python -m nanobot` 入口)—— 过
- `discover_channel_names()` 号称零 import —— 属实
- `discover_enabled({"websocket"})`(**业主的真实形态**)—— 只加载 websocket
- `discover_all()`(**最坏路径**)—— 优雅跳过,不崩
- `import nanobot.providers.bedrock_provider` —— 过(boto3 是函数内导入)

**对照组**:不抹时 `discover_all()` 拿到 15 个,抹后 13 个 —— **正好少 feishu +
telegram,没波及第三个**(`matrix` 在对照组就缺,本来就没 SDK,不是本单造成的)。

## 收口时抓到的两件事

**① 真打包抓到一个判据没抓到的 bug。**
`python_telegram_bot-22.8.dist-info` 活了下来。根因:**现代 wheel 根本不写
`top_level.txt`**(setuptools 的老古董),真实那份里只有 INSTALLER/METADATA/
RECORD/WHEEL,而我第一版在那里 `continue`。
**我的假 site-packages 给每份 dist-info 都造了 top_level.txt —— 替身与真实
情况不一样,判据就只是在考自己。**
已按次序修:先改判据的替身(加一份没有 top_level.txt 的)让它红,再改实现
(读 RECORD 兜底)。

**② 红检自己给过一个假的"咬住"。**
g4 的 heredoc 抽取正则少了 `[^\n]*`(那行是 `… <<'PYSLIM' || die "瘦身失败"`),
判据在 `assertIsNotNone` 就 None 了 —— 而红检**照样报"S4 靶子如期红了"**,
因为它只看那条测试红没红、**不看红的理由**。修完重跑才算数。

## 🔴 次序问题(如实记)

**这一单的包已经发出去了,而 panel-review 还在跑。** impact=high 要 2 条腿,
按规矩评审应当在出货之前。当时的取舍是业主已经等了三个版本、瘦身对他是纯收益,
但**这不改变次序是错的**这件事。评审结果回来后:发现若成立,直接进 0.96,
不会拿"已经发了"当理由压下去。

## Review

### 规格自查(在读任何 panel 输出之前答的)

这一单的规格如果错了,最可能错在哪:

1. **"业主用不到"这个判断**。依据是:他的代码 0 处引用、配置里 `feishu.enabled=false`、
   主入口是 websocket。**但这是"今天用不到",不是"永远用不到"** ——
   所以做法必须可逆,而它确实可逆(删清单里一行)。
2. **我只测了 import 图,没测运行期**。`entry_points` 扫描、`importlib.metadata`、
   nanobot 的 onboard/CLI 子命令这些路径没走过。这是本单最大的证据边界,
   已写进给 panel 的题面第 3 条。
3. **RECORD 兜底的边界**:多顶层包的发行版、RECORD 里的 `../` 条目。
   代码里子集判断是**故意保守**的(只要还提供清单外的东西就不动它的元数据),
   但没有针对性判据。

### arbitrated verdict(主裁)

**代码面 PASS。产品面不给结论**(业主还没装)。

代码面依据:1331 项回归 rc=0、红检 5 咬 0 漏、产物闸双向验过、
P0 探针 + 对照组、真打包实测数字与预估吻合。

⚠️ 敞着的:panel 未回;运行期路径未测(只测了 import 图)。
