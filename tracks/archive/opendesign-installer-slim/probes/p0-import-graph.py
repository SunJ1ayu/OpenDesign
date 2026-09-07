#!/usr/bin/env python3
"""探针:把候选包**从导入系统里抹掉**,看 nanobot 的启动路径还过不过得去。

为什么用 meta_path 拦截器而不是真删文件:
  - 真删要动 /root/.venvs/design-studio(被测环境),而且删了不好还原;
  - 拦截器对 import 系统来说与"包不存在"**完全等价** —— 抛的就是 ModuleNotFoundError,
    正是真删之后会发生的事。这一点是这个探针成立的前提。
"""
import sys, traceback

BLOCKED = {"lark_oapi", "botocore", "boto3", "telegram", "s3transfer"}


class Blocker:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        top = name.split(".")[0]
        if top in BLOCKED:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


sys.meta_path.insert(0, Blocker())

results = []


def step(label, fn):
    try:
        fn()
        results.append(("OK  ", label, ""))
    except BaseException as e:
        results.append(("FAIL", label, f"{type(e).__name__}: {e}"))
        traceback.print_exc()


# ① python -m nanobot 干的第一件事
step("import nanobot.cli.commands(python -m nanobot 的入口)",
     lambda: __import__("nanobot.cli.commands", fromlist=["app"]))

# ② 通道注册表:只列名字,应当零 import
def _names():
    from nanobot.channels.registry import discover_channel_names
    ns = discover_channel_names()
    assert "telegram" in ns and "feishu" in ns, ns
    print(f"    列出 {len(ns)} 个内置通道(零 import)")
step("discover_channel_names()(号称零 import)", _names)

# ③ 业主的真实配置:feishu enabled=false ⇒ 只启用 websocket
def _enabled():
    from nanobot.channels.registry import discover_enabled
    got = discover_enabled({"websocket"})
    print(f"    启用 websocket ⇒ 实际加载 {sorted(got)}")
step("discover_enabled({'websocket'})(业主的真实形态)", _enabled)

# ④ 最坏情况:有人调 discover_all()(会把所有通道都 import 一遍)
def _all():
    from nanobot.channels.registry import discover_all
    got = discover_all()
    print(f"    discover_all() 拿到 {len(got)} 个:{sorted(got)}")
    for gone in ("telegram", "feishu"):
        if gone in got:
            raise AssertionError(f"{gone} 在包被抹掉的情况下**仍然加载成功**,不合预期")
step("discover_all()(最坏路径,要求优雅跳过而不是崩)", _all)

# ⑤ bedrock provider(boto3)那条路
def _prov():
    import nanobot.providers as _p          # noqa
    from nanobot.providers import bedrock_provider   # noqa
    print("    bedrock_provider 模块本身导入成功(boto3 是函数内导入)")
step("import nanobot.providers.bedrock_provider(boto3 那条)", _prov)

print("\n==== 探针结果 ====")
for rc, label, err in results:
    print(f"[{rc}] {label}" + (f"\n        {err}" if err else ""))
bad = [r for r in results if r[0] == "FAIL"]
print(f"\n合计 {len(results)} 步,失败 {len(bad)} 步")
sys.exit(1 if bad else 0)
