#!/usr/bin/env python3
"""安装包瘦身的机械闸(track opendesign-installer-slim)。

由来(2026-08-24 业主):**安装和卸载都很慢**。实测整包 22,118 个文件,
而 OpenDesign 自己只占 42 个 —— 剩下全是 Python 运行时和 nanobot 拖来的第三方库。
砍掉业主用不到的三族(飞书 SDK / 亚马逊云 / Telegram)= 12,404 个文件、80 MB。

🔴 **这道闸问的不是"脚本里有没有写那行删除"**,那是手段。
0.92/0.93 连着两版栽在"判据问了手段、没问结果"上,这一单不重犯:

  g3 问的是**结果**:把清单里的包从导入系统里抹掉之后,**nanobot 还起不起得来**。
     这是 P0 探针的常驻版 —— 探针只跑一次,闸每次都跑。

  g5 问的是**清单的形状**:必须是显式数组。一个通配符就能把 PIL 一起带走,
     而那种错**不会报错**,只会让业主装完之后某个功能悄悄没了。

**清单的唯一来源是 `spike/build-package.sh` 里的 `SLIM_DROP`。**
这个文件**读它**,不抄第二份 —— 同一个事实存在两处、只更新其中一处,
是这个项目反复栽的跟头。
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_PKG = os.path.join(
    ROOT, "tracks", "opendesign-windows-installer", "spike", "build-package.sh")

# 这些是**真在用的**,谁把它们写进删除清单,g2 必须红。
# (业主的代码或 nanobot 的主路径直接依赖;删了就是功能悄悄消失。)
MUST_KEEP = (
    "nanobot", "mcp", "anydoc", "PIL", "lxml", "cryptography",
    "pydantic", "pydantic_core", "httpx", "loguru", "typer",
)


def _build_script() -> str:
    with open(BUILD_PKG, encoding="utf-8") as fh:
        return fh.read()


def _slim_drop() -> list[str]:
    """从 build-package.sh 里读出 SLIM_DROP 数组。**唯一来源在那边。**"""
    src = _build_script()
    m = re.search(r"^SLIM_DROP=\(\s*(.*?)\s*\)\s*$", src, re.M | re.S)
    if not m:
        return []
    body = m.group(1)
    # 去掉行注释,再按空白切
    body = re.sub(r"#[^\n]*", " ", body)
    return [tok.strip().strip('"').strip("'") for tok in body.split() if tok.strip()]


class SlimListShape(unittest.TestCase):
    """g5 / g2:清单本身的形状与内容。"""

    def test_g5_slim_drop_exists_and_is_an_explicit_array(self):
        """必须存在,而且必须是**显式数组** —— 不许通配符/正则。

        🔴 为什么单列一条:`rm -rf $SP/lark*` 这种写法看着省事,
        但 `PIL*` 会带走 `PIL`,`bot*` 会带走 `botocore` **和** 别的。
        通配符删错**不会报错**,业主装完之后是某个功能悄悄没了 —— 最难查的那种。
        """
        src = _build_script()
        # 🔴 `(?m)` 不能省:assertRegex 走的是 re.search **不带 MULTILINE**,
        #    `^` 于是只锚整个文件的开头 —— 第一版就是这么写的,数组明明在文件里
        #    却报"没有 SLIM_DROP",红的是判据不是实现。
        self.assertRegex(
            src, r"(?m)^SLIM_DROP=\(",
            "build-package.sh 里没有 SLIM_DROP 数组 —— 瘦身根本没做。")

        drop = _slim_drop()
        self.assertTrue(drop, "SLIM_DROP 是空的,等于没瘦身。")
        for name in drop:
            self.assertRegex(
                name, r"^[A-Za-z_][A-Za-z0-9_.-]*$",
                f"删除清单里的 {name!r} 不是一个老实的包名。"
                "通配符/正则/路径一律不许 —— 删错了不会报错,只会让功能悄悄消失。")

    def test_g2_never_drop_something_we_actually_use(self):
        """真在用的一个都不许写进清单。"""
        drop = set(_slim_drop())
        hit = sorted(drop & set(MUST_KEEP))
        self.assertEqual(
            [], hit,
            f"删除清单里有真在用的包:{hit}\n"
            "这些是业主的代码或 nanobot 主路径直接依赖的,删了功能会悄悄消失。")

    def test_g4_dist_info_is_dropped_together_with_the_package(self):
        """`dist-info` 必须跟着包一起删 —— **真跑一遍,不是查字符串**。

        🔴 只删包、留下元数据 = **比不删更坏**:`importlib.metadata` 会说包还在,
        `entry_points` 扫描时会拿到一个指向空气的入口,报错报在离现场很远的地方。

        🔴 **这条第一版是 `assertRegex(src, "dist-info")`,红检 S4 当场证明它是瞎的** ——
        把整个删除循环换成 `for info in []:` 它照样绿,因为注释里还写着 dist-info。
        "名字出现过" != "真的做了这件事",这个项目在同一形状上栽过不止一次。
        所以改成:把脚本里那段删除逻辑**抠出来真跑**,对着一棵假的 site-packages 看结果。

        顺带,这也是**唯一**一条验到"发行名 != 导入名"的闸:
        `telegram` 来自发行版 `python-telegram-bot`,照导入名去 glob 一个都删不着。
        """
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        src = _build_script()
        # 🔴 `[^\n]*` 不能省:那一行是 `… <<'PYSLIM' || die "瘦身失败"`,
        #    标记后面还跟着东西。第一版少了它 ⇒ 判据在这里就 None 了,
        #    而红检**照样报"靶子如期红了"**(它只看那条测试红没红,不看红的理由)
        #    —— 假的"咬住"。修完必须重跑红检才算数。
        m = re.search(r"<<'PYSLIM'[^\n]*\n(.*?)\nPYSLIM", src, re.S)
        self.assertIsNotNone(
            m, "build-package.sh 里找不到 PYSLIM 那段删除逻辑 —— 瘦身没做,或者改了名字。")
        code = m.group(1)

        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "site-packages"
            sp.mkdir()

            def _pkg(name, dist=None, top=None, *, with_top_level=True):
                """造一个包 + 它的 dist-info。

                🔴 `with_top_level=False` 那一支是 2026-08-24 真打包**当场**加的:
                   我原来的替身给每份 dist-info 都造了 `top_level.txt`,
                   于是判据绿、真打包却留下 `python_telegram_bot-22.8.dist-info` ——
                   **现代 wheel 根本不写 top_level.txt**(它是 setuptools 的老古董),
                   真实的那份里只有 INSTALLER/METADATA/RECORD/WHEEL。
                   替身与真实情况不一样,判据就只是在考自己。
                """
                (sp / name).mkdir()
                (sp / name / "__init__.py").write_text("", encoding="utf-8")
                if dist:
                    d = sp / dist
                    d.mkdir()
                    if with_top_level:
                        (d / "top_level.txt").write_text(
                            (top or name) + "\n", encoding="utf-8")
                    else:
                        # 只有 RECORD 可推:它列出这个发行版装了哪些文件
                        (d / "RECORD").write_text(
                            f"{dist}/METADATA,sha256=x,100\n"
                            f"{dist}/RECORD,,\n"
                            f"{top or name}/__init__.py,sha256=y,0\n",
                            encoding="utf-8")

            # 要被删的:注意 telegram 的 dist-info 名字**对不上**导入名,
            # 而且它**没有 top_level.txt** —— 真实那份就是这样(实测)。
            _pkg("lark_oapi", "lark_oapi-1.4.dist-info")
            _pkg("telegram", "python_telegram_bot-20.7.dist-info", top="telegram",
                 with_top_level=False)
            _pkg("botocore", "botocore-1.34.dist-info")
            _pkg("boto3", "boto3-1.34.dist-info")
            _pkg("s3transfer", "s3transfer-0.10.dist-info")
            # 必须活下来的
            _pkg("PIL", "pillow-10.2.dist-info", top="PIL")

            drop = _slim_drop()
            r = subprocess.run(
                [sys.executable, "-c", code, str(sp), *drop],
                capture_output=True, text=True)
            self.assertEqual(
                0, r.returncode,
                f"删除逻辑自己跑挂了:\n{r.stdout}\n{r.stderr}")

            left = sorted(p.name for p in sp.iterdir())
            for gone in ("lark_oapi", "telegram", "botocore", "boto3", "s3transfer"):
                self.assertNotIn(gone, left, f"{gone} 没被删掉。剩下:{left}")
            self.assertNotIn(
                "python_telegram_bot-20.7.dist-info", left,
                "🔴 telegram 的 dist-info 留下来了 —— **发行名与导入名不一样**"
                "(python-telegram-bot vs telegram),照导入名 glob 是删不着它的。\n"
                f"剩下:{left}")
            for gone in ("lark_oapi-1.4.dist-info", "botocore-1.34.dist-info"):
                self.assertNotIn(gone, left, f"{gone} 留下来了。剩下:{left}")

            self.assertIn("PIL", left, f"把不该删的 PIL 删了。剩下:{left}")
            self.assertIn(
                "pillow-10.2.dist-info", left,
                f"把 PIL 的元数据删了(包还在、元数据没了,同样是坏的)。剩下:{left}")
            shutil.rmtree(sp, ignore_errors=True)


class PrunedRuntimeStillStarts(unittest.TestCase):
    """g3:**结果**闸 —— 按清单抹掉之后,nanobot 还起不起得来。

    这是 P0 探针(tracks/opendesign-installer-slim/probes/p0-import-graph.py)的常驻版。
    用 `sys.meta_path` 拦截器模拟"包被删了" —— 对 import 系统来说与真删等价。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import nanobot  # noqa: F401
        except ImportError as e:      # pragma: no cover
            raise unittest.SkipTest(
                f"这台机器没装 nanobot,g3 跑不了:{e}\n"
                "⚠️ 这不是'通过' —— 全量回归用的 venv 是装了 nanobot 的,"
                "在那里它必须真跑。") from e

    def _blocked(self, names):
        class Blocker:
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in names:
                    raise ModuleNotFoundError(f"No module named {name!r}", name=name)
                return None
        return Blocker()

    def test_g3_nanobot_startup_survives_the_prune(self):
        drop = set(_slim_drop())
        if not drop:
            self.fail("SLIM_DROP 是空的 —— g5 会红,这里不重复报,但也不算通过。")

        blocker = self._blocked(drop)
        sys.meta_path.insert(0, blocker)
        # 抹掉已经加载过的,否则拦截器对它们无效(它们已经在 sys.modules 里)
        saved = {k: v for k, v in sys.modules.items()
                 if k.split(".")[0] in drop or k.startswith("nanobot")}
        for k in saved:
            del sys.modules[k]
        try:
            # ① python -m nanobot 的入口
            __import__("nanobot.cli.commands", fromlist=["app"])
            # ② 业主的真实形态:配置里 feishu.enabled=false,主入口是 websocket
            from nanobot.channels.registry import discover_enabled, discover_all
            got = discover_enabled({"websocket"})
            self.assertIn(
                "websocket", got,
                f"按清单删完之后,业主真正用的 websocket 通道加载不了了:{sorted(got)}")
            # ③ 最坏路径:有人调 discover_all(),它会把所有通道都 import 一遍
            all_ch = discover_all()
            self.assertTrue(
                all_ch,
                "discover_all() 一个都没拿到 —— 删过头了或者注册表崩了。")
        except Exception as exc:                      # noqa: BLE001
            self.fail(
                f"按 SLIM_DROP={sorted(drop)} 删完之后,nanobot 起不来了:\n"
                f"  {type(exc).__name__}: {exc}\n"
                "⇒ 这个包**不能删**,或者删了之后得同时处理它的引用方。\n"
                "(业主装完打不开软件就是这个形状 —— 0.93 已经让他遇到过一次。)")
        finally:
            sys.meta_path.remove(blocker)
            for k in list(sys.modules):
                if k.split(".")[0] in drop or k.startswith("nanobot"):
                    del sys.modules[k]
            sys.modules.update(saved)


if __name__ == "__main__":
    unittest.main()
