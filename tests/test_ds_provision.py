#!/usr/bin/env python3
"""判据:装完之后配置到不到位(`bin/ds_provision.py`,track opendesign-windows-installer S1c)。

    python3 tests/test_ds_provision.py

## 为什么这份判据存在

安装器把文件铺到盘上只是一半。另一半是**业主双击图标那一刻,后台起不起得来**——
而后台起不起得来,全看 `<数据目录>\\.nanobot\\config.json` 这一份文件对不对。
S1b 真机那次红的教训就在这儿:配置差一点,业主拿到的是一句英文,而我在 Linux 上
一条考卷都跑不了那一层。

这一次不重犯:**配置就绪这件事被做成一个可判定的脚本**,由这份考卷逐条锁住。
它问的不是"脚本跑完了没有",而是**"跑完之后,外壳那一边认不认"**——
所以下面好几条是直接拿 `ds_shell_core` 的真函数(`patch_config` / `missing_env_refs`)
去验的,而不是我自己再写一遍期望。两边对同一份配置的期望必须一致,
这正是 08-14 那次"两张考卷对同一前提做了相反假设"要防的东西。

## 它问不出什么

nanobot 真起不起得来 —— 那要 `DS_SHELL_E2E=1` 的两腿联跑,以及最终的 Windows 真机。
本文件只保证"配置这份数据是对的",不保证"这台机器跑得动"。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin"
sys.path.insert(0, str(BIN))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ 自己
import _tmpreg  # noqa: E402  临时目录登记表,见 tests/_tmpreg.py

import ds_shell_core as core  # noqa: E402

PROVISION = BIN / "ds_provision.py"
TEMPLATE = REPO / "config" / "nanobot.config.windows.jsonc"

# 🔴 跑这份判据的进程,不许够得着我这台机器的真家。
#
# 2026-08-15 实证(不是推演):红检的 M7 **故意**把写口改成 `expanduser("~")`,
# 而红检对每条变异都跑**整份**判据 —— 只有 c1/c2 自己伪造了 HOME,其余十几条
# 就这么把 `~/.nanobot/config.json` 的 gateway 口令换掉了。08-08 起的 gateway
# 内存里还是旧口令 ⇒ `test_ws_protocol_smoke` 红了整整一天,而我昨天以为红检"跑绿了"。
# 靶子红是对的,**但破坏不许真的发生**:变异测试的整个前提是"跑完机器和跑前一样"。
#
# 放在 setUpModule 而不是 import 时:第一版写在模块级,当场串味 —— 全量跑是**一个进程
# 导入所有判据**,`test_ws_protocol_smoke` 在 import 期就按 HOME 找 gateway 口令,
# 于是它整块 SKIP 了(而 SKIP 看起来很像绿)。改错一道防线的代价就是这个形状。
# 同源规矩见 [[judging-must-have-no-egress]] —— 那次是判据自己会花钱,这次是判据自己会改机器。
_JUDGE_HOME = None
_REAL_HOME: dict[str, str | None] = {}


def setUpModule():
    global _JUDGE_HOME
    _JUDGE_HOME = _tmpreg.mkdtemp("ds-provision-判据假家-")
    for k in ("HOME", "USERPROFILE"):
        _REAL_HOME[k] = os.environ.get(k)
        os.environ[k] = _JUDGE_HOME


def tearDownModule():
    for k, v in _REAL_HOME.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def has_nanobot() -> bool:
    try:
        import nanobot  # noqa: F401
        return True
    except ImportError:
        return False


class ProvisionTestBase(unittest.TestCase):
    def setUp(self):
        if not has_nanobot():
            # SKIP 不是 PASS。收据里会如实记账 —— 这条规矩是 07-05 那次
            #「pytest 全绿而整块闸被 SKIP」栽出来的。
            self.skipTest("这个解释器没装 nanobot(用 /root/.venvs/design-studio/bin/python 跑)")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "UserData"
        self.ds_root = self.base / "ds"
        (self.ds_root / "config").mkdir(parents=True)
        (self.ds_root / "bin").mkdir(parents=True)
        # 只搬这一步真正要用到的两个文件,别把整个仓拷过来 —— 拷整棵树的话,
        # 判据就分不清"脚本自己找得到东西"和"恰好本机什么都在"。
        (self.ds_root / "config" / TEMPLATE.name).write_bytes(TEMPLATE.read_bytes())
        (self.ds_root / "bin" / "ds_merge_config.py").write_bytes(
            (BIN / "ds_merge_config.py").read_bytes())

    def run_provision(self, *extra: str, home: Path | None = None) -> subprocess.CompletedProcess:
        argv = [sys.executable, str(PROVISION),
                "--home", str(home or self.home), "--ds-root", str(self.ds_root), *extra]
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=180)

    def config_path(self, home: Path | None = None) -> Path:
        return (home or self.home) / ".nanobot" / "config.json"

    def load_config(self, home: Path | None = None) -> dict:
        return json.loads(self.config_path(home).read_text(encoding="utf-8"))


class TestFreshInstall(ProvisionTestBase):
    def test_a1_fresh_home_gets_a_config(self):
        """全新装机:什么都没有 → 跑一次 → 配置在那儿,而且是合法 JSON。"""
        r = self.run_provision()
        self.assertEqual(r.returncode, 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}")
        self.assertTrue(self.config_path().is_file(), "配置文件没生成")
        self.load_config()  # 解析不了会直接抛

    def test_a2_the_shell_accepts_what_provision_produced(self):
        """**本文件最值钱的一条**:外壳的 `patch_config` 认不认这份配置。

        它是端到端的接口一致性检查 —— 配置就绪与外壳启动是两个人(两个脚本)写的,
        而业主机器上它们必须严丝合缝。任何一边改了期望,这条就红。
        """
        self.assertEqual(self.run_provision().returncode, 0)
        core.patch_config(self.config_path(), gateway_port=18790, ws_port=8765,
                          python_exe=r"C:\x\python.exe")   # 抛 ConfigUnusable 即失败
        cfg = self.load_config()
        self.assertEqual(cfg["gateway"]["port"], 18790)
        self.assertEqual(cfg["channels"]["websocket"]["port"], 8765)

    def test_a3_token_is_latin1_safe(self):
        """自动生成的口令必须是浏览器发得出去的。

        `patch_config` 为中文口令 fail closed(fetch 的头值只收 Latin-1),
        所以随机生成器要是哪天用了非 ASCII 字符,业主会看到"界面全好、
        唯独第一句话永远发不出去"——最难查的那种坏法。
        """
        self.assertEqual(self.run_provision().returncode, 0)
        token = self.load_config()["channels"]["websocket"]["token"]
        self.assertTrue(token, "口令是空的")
        token.encode("latin-1")  # 抛 UnicodeEncodeError 即失败
        self.assertGreaterEqual(len(token), 12, "口令太短")

        # 🔴 上面三行**只是抽样**:字母表里混进一个非 ASCII 字符时,16 位口令恰好抽中它的
        # 概率才四成 —— 红检 M1 当场证明了这一点(变异打上去,这条照样绿)。
        # 断言名说的是"生成器只产 latin-1 安全的口令",那就得**对生成器本身**下断言。
        # 同类账:S1a 那份考卷把"无地址栏"写进断言名却没验。
        import ds_provision
        self.assertTrue(ds_provision._ALPHABET.isascii(),
                        f"口令字母表里有非 ASCII 字符:{ds_provision._ALPHABET!r}")
        for _ in range(200):
            ds_provision.new_token().encode("latin-1")

    def test_a4_owner_can_find_the_token(self):
        """口令是随机生成的 ⇒ **业主必须能看到它**,否则聊天永远登不进去。"""
        self.assertEqual(self.run_provision().returncode, 0)
        note = self.home / ".openDesign" / "登录口令.txt"
        self.assertTrue(note.is_file(), f"没把口令写到 {note}")
        self.assertIn(self.load_config()["channels"]["websocket"]["token"],
                      note.read_text(encoding="utf-8"))

    def test_a5_mcp_servers_are_wired(self):
        """三个工具服务缺任何一个,助手就"什么都不会做"了,而业主自己修不好。"""
        self.assertEqual(self.run_provision().returncode, 0)
        servers = self.load_config()["tools"]["mcpServers"]
        for name in ("design-studio", "design-studio-organize", "design-studio-refs"):
            self.assertIn(name, servers, f"配置里缺 {name}")
            self.assertIn("ds_mcp.py", " ".join(servers[name].get("args", [])))

    def test_a6_no_credential_lands_in_the_config(self):
        """凭据只走环境变量。配置是要进日志、进截图、进我这边的收据的。"""
        text = self.config_path().read_text(encoding="utf-8") if self.config_path().exists() else ""
        self.assertEqual(self.run_provision().returncode, 0)
        text = self.config_path().read_text(encoding="utf-8")
        self.assertIn("${DS_LLM_KEY}", text, "apiKey 应该仍是环境变量引用")
        self.assertNotIn("sk-", text, "配置里出现了像 key 的东西")

    def test_a7_missing_key_is_named_exactly(self):
        """与 S1b-r2 真机已验证的行为对齐:没放 key 时,**恰好**点名 DS_LLM_KEY。

        多报 = 业主被吓到;少报 = 网关自己死掉甩英文(就是 08-14 那一跑)。

        🔴 **这条的题面改过一次,理由记在这儿**:第一版拿 `{}` 当环境去问,红了 ——
        报出来的是 `DS_LLM_KEY / USERPROFILE / DS_ROOT` 三个。查下来不是 bug 而是
        **问法本身问不出这件事**:外壳起后台用的环境永远是 `core.child_env()` 造的,
        那里面 DS_ROOT / USERPROFILE 一定在,空环境这个前提现实中不存在。
        改成用真的 `child_env` 之后这条**变强了** —— 将来 child_env 少设一个变量,
        网关会整个拒绝启动,而这条会当场红;空环境那版永远发现不了。
        """
        self.assertEqual(self.run_provision().returncode, 0)
        cfg = self.load_config()
        env_no_key = core.child_env({}, ds_root=str(self.ds_root), user_home=str(self.home),
                                    dsweb_port=8766, ws_port=8765, key=None)
        # 变量名从**这份刚装出来的真配置**读(T3 起 child_env 不许写死它)。
        # 于是这条顺带回答了一件 e8 问不到的事:env_var_name() 读出来的,
        # 和装机脚本写进去的,是不是同一个名字 —— 对不上,下面那条 assert 当场红。
        import ds_credential
        env_with_key = core.child_env({}, ds_root=str(self.ds_root), user_home=str(self.home),
                                      dsweb_port=8766, ws_port=8765, key="sk-假的",
                                      key_var=ds_credential.env_var_name(cfg))
        self.assertEqual(core.missing_env_refs(cfg, env_no_key), ["DS_LLM_KEY"])
        self.assertEqual(core.missing_env_refs(cfg, env_with_key), [])


class TestIdempotence(ProvisionTestBase):
    def test_b1_second_run_keeps_the_token(self):
        """业主记下来的口令,不许被第二次跑(修复安装 / 装新版)悄悄换掉。"""
        self.assertEqual(self.run_provision().returncode, 0)
        first = self.load_config()["channels"]["websocket"]["token"]
        self.assertEqual(self.run_provision().returncode, 0)
        self.assertEqual(self.load_config()["channels"]["websocket"]["token"], first)

    def test_b2_owner_chosen_token_survives(self):
        """他自己设过的口令(老装法 install.ps1 问过一次)必须原样留着。"""
        self.assertEqual(self.run_provision().returncode, 0)
        cfg = self.load_config()
        cfg["channels"]["websocket"]["token"] = "MyOwnPass123"
        self.config_path().write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.run_provision().returncode, 0)
        self.assertEqual(self.load_config()["channels"]["websocket"]["token"], "MyOwnPass123")

    def test_b3_explicit_token_wins(self):
        """给了 --token 就照做(将来的首启动向导会用这条口子改口令)。"""
        self.assertEqual(self.run_provision("--token", "Chosen999").returncode, 0)
        self.assertEqual(self.load_config()["channels"]["websocket"]["token"], "Chosen999")

    def test_b4_refuses_a_token_the_browser_cannot_send(self):
        """显式给的口令也要过 latin-1 闸,而且要**当场**说清楚,不能等到聊天时才炸。"""
        r = self.run_provision("--token", "中文口令")
        self.assertNotEqual(r.returncode, 0, "中文口令应当被拒")
        self.assertIn("字母数字", r.stdout + r.stderr)


class TestBlastRadius(ProvisionTestBase):
    def test_c1_does_not_touch_the_machines_own_nanobot(self):
        """**只写自己那棵树**。

        `enable_webui.py` 写死了 `~/.nanobot/config.json` —— 装机脚本里那样用没问题,
        但安装器跑的时候,业主机器上可能已经有一份**他自己在用**的 nanobot 配置。
        碰它 = 把他现有的 openclaw/nanobot 弄坏,而且他不会知道是我干的。
        """
        real_home = self.base / "机器上原来的家"
        (real_home / ".nanobot").mkdir(parents=True)
        victim = real_home / ".nanobot" / "config.json"
        victim.write_text('{"我是业主自己的配置": true}', encoding="utf-8")
        before = victim.read_bytes()

        env = dict(os.environ, HOME=str(real_home), USERPROFILE=str(real_home))
        r = subprocess.run(
            [sys.executable, str(PROVISION), "--home", str(self.home),
             "--ds-root", str(self.ds_root)],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(victim.read_bytes(), before, "把业主自己的 nanobot 配置改了")

    def test_c2_writes_nothing_outside_the_home(self):
        """跑完之后,数据目录之外一个新文件都不该多出来。"""
        outside = self.base / "别动我"
        outside.mkdir()
        self.assertEqual(self.run_provision().returncode, 0)
        self.assertEqual(list(outside.iterdir()), [], "在数据目录之外写了东西")


class TestBrokenInputs(ProvisionTestBase):
    def test_d1_says_human_words_when_the_template_is_missing(self):
        """包装坏了(模板没铺进去)⇒ 说人话并非零退出,不许静默产出半份配置。"""
        (self.ds_root / "config" / TEMPLATE.name).unlink()
        r = self.run_provision()
        self.assertNotEqual(r.returncode, 0)
        out = r.stdout + r.stderr
        self.assertIn("模板", out)
        self.assertNotIn("Traceback", out, "给业主看的不该是 Python 栈")

    def test_d2_leaves_a_corrupt_config_alone(self):
        """已有配置是坏 JSON:不许当成"没有配置"覆盖掉 —— 那可能是业主唯一的一份。"""
        self.config_path().parent.mkdir(parents=True, exist_ok=True)
        self.config_path().write_text("{ 这不是 JSON", encoding="utf-8")
        r = self.run_provision()
        self.assertNotEqual(r.returncode, 0, "坏配置应当拒绝往下走")
        # 光看退出码不够:脚本还不存在时退出码也是非零,这条会**空绿**。
        # 所以必须验它说的是不是这件事 —— 同款教训见 tasks.md「红在 AttributeError 上」。
        self.assertIn("配置", r.stdout + r.stderr)
        self.assertEqual(self.config_path().read_text(encoding="utf-8"), "{ 这不是 JSON")


class TestMalformedButParseable(ProvisionTestBase):
    """四审(subdeepseek F2/F3)抓到的两种:配置能被 json 解析、但形状不对。"""

    def test_e1_null_channels_does_not_throw_a_stack_at_the_owner(self):
        """`{"channels": null}` —— 合法 JSON,但 setdefault 拿到 None 再 .setdefault 就炸。

        本模块的规矩是"不许把 Python 栈甩给业主"(他没有终端、也不是程序员)。
        这一条盯的正是那句承诺,而不是"会不会崩"。
        """
        self.config_path().parent.mkdir(parents=True, exist_ok=True)
        self.config_path().write_text('{"channels": null}', encoding="utf-8")
        r = self.run_provision()
        out = r.stdout + r.stderr
        self.assertNotIn("Traceback", out, "给业主看的不该是 Python 栈")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("配置", out)

    def test_e2_websocket_of_wrong_type_is_refused_in_human_words(self):
        """`channels.websocket` 是个字符串 —— 同上,而且更像"被别的工具写坏了"。"""
        self.config_path().parent.mkdir(parents=True, exist_ok=True)
        self.config_path().write_text('{"channels": {"websocket": "开"}}', encoding="utf-8")
        r = self.run_provision()
        out = r.stdout + r.stderr
        self.assertNotIn("Traceback", out)
        self.assertNotEqual(r.returncode, 0)

    def test_e3_a_failing_merge_leaves_no_half_config_behind(self):
        """合并失败时,盘上不许留下一份"开了通道但没有工具服务"的半成品配置。

        本模块自己写着"半份配置比没有配置更坏"(外壳会拿着它去起后台,然后死在别处),
        而原来的顺序是**先落盘再合并** ⇒ 合并炸了就正好留下那种半成品。
        (subdeepseek F3。它指出的是"承诺与实现对不上",不是崩溃。)
        """
        # 模板是合法文件但不是合法 JSONC ⇒ 前置存在性检查过得去,合并这一步才炸
        (self.ds_root / "config" / TEMPLATE.name).write_text("{ 这不是 JSON", encoding="utf-8")
        r = self.run_provision()
        self.assertNotEqual(r.returncode, 0, "合并失败应当非零退出")
        self.assertFalse(self.config_path().exists(),
                         "合并失败却留下了一份半成品配置")

    def test_e4_a_failing_merge_does_not_damage_an_existing_config(self):
        """已经装过的机器上合并失败:他原来那份必须**一个字节都没变**。"""
        self.assertEqual(self.run_provision().returncode, 0)
        before = self.config_path().read_bytes()
        (self.ds_root / "config" / TEMPLATE.name).write_text("{ 坏了", encoding="utf-8")
        self.assertNotEqual(self.run_provision().returncode, 0)
        self.assertEqual(self.config_path().read_bytes(), before, "把他原来的配置改坏了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
