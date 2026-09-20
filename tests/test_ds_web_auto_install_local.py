#!/usr/bin/env python3
"""打开软件装的是**盘上那个已经下好的包**(track opendesign-startup-not-blocked-by-update,2026-09-20)。

主 agent 亲写。为什么要单独一卷:

0.98.8 的后台备货会在业主用软件的时候把 46MB 下好、校验好,放进 `Logs/pending/`,
并写下 `update-state.json`;下一次打开软件读到它才装。设计里白纸黑字写着
**「那时进度条是真的在装,不是在等网络」**。

但安装那一侧 `_update_apply_locked` 第一行就是 `ds_update.check_cached(VERSION)` ——
进程刚起来、缓存是冷的 ⇒ **又联一次网**(实测最坏 20.1 秒),
而且 `apply_update` 会**把同一个包重新下一遍**,压根不看 pending 里那个。
于是"有更新的那一次打开"业主照样干等 —— 正是本单要根除的东西,只是换了个位置。

🔴 **ai2 是这一卷的核心**:自动安装请求期间**一次网络取数都不许发**。
   故意不用"量耗时"来验(耗时判据会被"把超时调小"骗过,还会因机器快慢 flaky),
   改成把取数函数换成炸弹并**数调用次数** —— 与 su_net1~3 同一招。

夹具借 test_ds_web_auto_update 的那一套(装出来的桌面版 + 假外壳端口 + 离线)。
🔴 **借的是夹具,不是继承**:直接 `class X(AutoUpdate)` 会把那一卷的 27 道题在这里再跑一遍,
   而它们的前提被本卷的替身改过 —— 那种红是假红。
"""
import hashlib
import json
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import ds_update            # noqa: E402
import ds_update_apply      # noqa: E402
import ds_update_startup    # noqa: E402
import ds_auto_update       # noqa: E402
import test_ds_web_auto_update as base   # noqa: E402

LATEST = base.LATEST
AUTO = base.AUTO
MANUAL = base.MANUAL
_post = base._post
_get = base._get
# 🔴 **模块导入那一刻**抓真安装器。夹具 setUp 里抓是抓不到的 —— 那时父类已经把它换成替身了,
#    ai9 第一版就是这么写的,于是它"用真安装器"其实是在测替身,坏包当场"装成功"。
REAL_APPLY_UPDATE = ds_update_apply.apply_update


class AutoInstallFromLocal(unittest.TestCase):
    # 借夹具:这三个是未绑定函数,挂成本类的方法即可,不继承它的题目。
    setUpFixture = base.AutoUpdate.setUp
    _install = base.AutoUpdate._install
    _serve = base.AutoUpdate._serve

    def setUp(self):
        self.setUpFixture()
        self.pending_dir = os.path.join(self.data_root, "Logs", "pending")
        self.captured = []
        self.net_calls = []

        # 父类那个 fake_apply 会自己去 GET /api/update/check(它要问"产品这一刻怎么看这个版本"),
        # 那在本卷里会撞上网络炸弹。这里换一个只记账、不出门的。
        def fake_apply(decision, paths, **kw):
            self.order.append("apply")
            self.captured.append({"decision": decision, "download": kw.get("download"),
                                  "temp": paths.get("temp")})
            if self.apply_ok:
                return {"ok": True, "stage": "relay", "error": None, "relay": "C:/tmp/relay.cmd"}
            return {"ok": False, "stage": "verify", "error": "sha256 对不上", "relay": None}
        ds_update_apply.apply_update = fake_apply

    # --- 夹具 ---------------------------------------------------------------

    def _armed(self):
        """把查更新的两个取数口换成炸弹,并记下每一次调用。"""
        def boom(*a, **kw):
            self.net_calls.append("fetch")
            raise OSError("自动安装路径上不许联网")
        ds_update.fetch_releases = boom
        ds_update.fetch_atom = boom
        ds_update.cache_clear()

    def _stock(self, version=LATEST, payload=b"pretend installer bytes"):
        """摆出"后台已经下好并校验过"的样子:pending 里一个真文件 + 一份 ready 状态。"""
        os.makedirs(self.pending_dir, exist_ok=True)
        name = "OpenDesign-Setup-%s.exe" % version
        path = os.path.join(self.pending_dir, name)
        with open(path, "wb") as fh:
            fh.write(payload)
        state = {"schema": 1, "phase": "ready", "version": version,
                 "asset": {"name": name, "size": len(payload),
                           "sha256": hashlib.sha256(payload).hexdigest(),
                           "url": "https://github.com/SunJ1ayu/OpenDesign/releases/download/"
                                  "win-installer-%s/%s" % (version, name)},
                 "path": path, "updated_at": time.time()}
        ds_update_startup.write_state(
            ds_update_startup.state_path(self.data_root), state)
        return path, state

    # --- ai1 / ai2:装的是本地那个包,而且全程不联网 ---------------------------

    def test_ai1_auto_install_uses_the_package_already_on_disk(self):
        path, state = self._stock()
        self._armed()
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), True, "盘上备好的新版没装成:%r" % (body,))
        self.assertEqual(self.order.count("apply"), 1, "没走到安装:%r" % (self.order,))

        got = self.captured[0]
        self.assertEqual((got["decision"] or {}).get("latest"), LATEST,
                         "装的不是盘上那一版:%r" % (got["decision"],))
        asset = (got["decision"] or {}).get("asset") or {}
        self.assertIsNotNone(ds_update_apply.parse_digest(asset.get("digest")),
                             "交给安装的这份决定没有可信摘要 ⇒ 真 apply_update 会当场拒绝:%r" % (asset,))
        self.assertTrue(asset.get("url"), "决定里没有下载地址 ⇒ 真 apply_update 会当场拒绝")

        # 🔴 "用的是本地那个包"怎么验:让它按自己的方式把安装包取到 dest,
        #    再比字节。不问它内部怎么实现,只问结果对不对。
        self.assertIsNotNone(got["download"], "没给安装步骤指路 ⇒ 它会照旧去网上重下一遍 46MB")
        dest = os.path.join(self.tmp, "fetched.exe")
        got["download"](asset.get("url"), dest)
        with open(dest, "rb") as fh:
            fetched = fh.read()
        with open(path, "rb") as fh:
            self.assertEqual(fetched, fh.read(), "取到的不是盘上那个已经校验过的包")
        self.assertEqual(self.net_calls, [], "取包的时候联网了")

    def test_ai2_auto_install_makes_no_network_call_at_all(self):
        self._stock()
        self._armed()
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertEqual(self.net_calls, [],
                         "🔴 自动安装期间去联网了 %d 次 —— 业主在这一次打开时照样干等" % len(self.net_calls))
        self.assertIs(body.get("ok"), True, body)

    # --- ai3:没备好就别装,更不许临时联网去下 --------------------------------

    def test_ai3_without_a_local_package_auto_install_refuses_instead_of_going_online(self):
        self._armed()          # 盘上什么都没有
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), False, "盘上没有包却报装成功:%r" % (body,))
        self.assertEqual(body.get("stage"), "auto_skipped",
                         "该安静跳过(软件照常可用),而不是别的死法:%r" % (body,))
        self.assertEqual(self.net_calls, [],
                         "🔴 没备好就退回联网下载 —— 那就是把 20 秒干等原样搬回了启动路径")
        self.assertEqual(self.order.count("apply"), 0, "没有包还去装:%r" % (self.order,))

    # --- ai4:手动更新一行不变,仍然联网查 ------------------------------------

    def test_ai4_manual_update_still_checks_online(self):
        self._stock()
        with self._serve() as port:                 # 不装炸弹:手动这条路本来就该联网
            st, body = _post(port, "/api/update/apply", MANUAL)
        self.assertEqual(st, 200, body)
        self.assertEqual(self.order.count("apply"), 1, "手动更新没走到安装:%r" % (body,))
        self.assertIsNone(self.captured[0]["download"],
                          "手动更新也改成用盘上的包了 —— 那是另一件事,本单不许顺手改")

    # --- ai5:防循环的闸仍然管用 ----------------------------------------------

    def test_ai5_a_version_already_attempted_is_not_installed_even_if_stocked(self):
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._stock()
        self._armed()
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), False, "这一版已经自动试过一次,不许再自动装:%r" % (body,))
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        self.assertEqual(self.order.count("apply"), 0, "已经试过的版本又装了一遍")
        self.assertEqual(self.net_calls, [], "被拒的自动请求也不许联网")

    # --- ai9:坏包绝不许装上(接管 su8 的那句话,由真安装器来守)----------------

    def test_ai9_a_corrupt_package_never_gets_installed(self):
        """ai9:大小对得上、字节对不上的包 —— **真安装器**必须在碰活树之前拒掉它。

        🔴 这是 su8「摘要对不上 ⇒ 进工作区」搬过来的落点。启动那一步不再算哈希
        (su15:O(包大小) 的活儿配一个写死 500ms 的上限,超时之后单向永久失效),
        所以"绝不许装一个校验不过的包"这句话必须由后面两道来守:
        下好那一刻(pr3/pr9)与**真装之前**(既有锁定判据 t4)。
        这一条走的是**生产那条路**:startup 说该装 ⇒ 自动 apply ⇒ 真 apply_update 校验。
        本卷其它用例把 apply_update 换成了替身,只有这一条用真的。
        """
        path, state = self._stock()
        with open(path, "r+b") as fh:          # 同样长度,内容不同
            fh.seek(0); fh.write(b"Z" * 8)
        self._armed()
        ds_update_apply.apply_update = REAL_APPLY_UPDATE    # 这一条用真安装器
        with self._serve() as port:
            startup = _get(port, "/api/update/startup")[1]
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual((startup or {}).get("action"), "install",
                         "前提没摆好:启动这一步该说「该装」(它不再验字节)")
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), False, "坏包被装上了:%r" % (body,))
        self.assertEqual(body.get("stage"), "verify",
                         "坏包该死在校验那一步(活树零改动),实得:%r" % (body,))
        self.assertEqual(self.order, [], "坏包走到了交棒/外壳那一步:%r" % (self.order,))
        self.assertEqual(self.net_calls, [], "拒坏包的路上联网了")

    # --- ai7/ai8:装不成的那一版,别让它每次打开都空演一遍 ----------------------

    def test_ai7_a_refused_auto_install_clears_the_ready_package(self):
        """ai7:这一版已经自动试过 ⇒ 盘上那份 ready 必须清掉,别留着每次打开空演一遍。

        🔴 由来(2026-09-20 第 1 轮外审,subcursor HIGH-2,我核实成立):
        `record_attempt` 在 `apply_update` **之前**写,失败之后没有人清 `update-state.json`。
        于是下一次打开:startup 仍回 install ⇒ 前端弹「正在更新到 X」⇒ apply 回
        `auto_skipped` ⇒ 而 `autoFailureText` 对 auto_skipped **故意返回空串** ⇒
        业主看到的是"闪一下更新界面,然后一声不吭掉进工作区",**每次打开都来一遍,永远**。
        """
        import ds_auto_update
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._stock()
        self._armed()
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        state = ds_update_startup.read_state(ds_update_startup.state_path(self.data_root))
        self.assertNotEqual((state or {}).get("phase"), "ready",
                            "被拒之后 ready 还留着 ⇒ 下次打开还会空演一遍更新界面")
        after = ds_update_startup.startup_decision(state, "0.90.0")
        self.assertEqual(after.get("action"), "enter",
                         "下一次打开仍然会被带进更新界面:%r" % (after,))

    def test_ai8_a_failed_auto_install_clears_the_ready_package(self):
        """ai8:真的装了但没装成,同样要清 —— 这一版从此只能手动,留着它只会每次打开空演。"""
        self._stock()
        self._armed()
        self.apply_ok = False
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), False, body)
        self.assertEqual(self.order.count("apply"), 1, "前提没摆好:没走到安装")
        state = ds_update_startup.read_state(ds_update_startup.state_path(self.data_root))
        self.assertNotEqual((state or {}).get("phase"), "ready",
                            "装失败之后 ready 还留着 ⇒ 下次打开继续空演")

    # --- ai6:包在决策之后变了样,宁可不更新 -----------------------------------

    def test_ai6_a_package_that_changed_after_the_decision_is_not_installed(self):
        path, _state = self._stock()
        with open(path, "wb") as fh:          # 大小与摘要都对不上了
            fh.write(b"short")
        self._armed()
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), False, "包已经不是原来那个了,还照装:%r" % (body,))
        self.assertEqual(self.order.count("apply"), 0, "坏包送进了安装步骤")
        self.assertEqual(self.net_calls, [], "坏包时退回联网下载")


if __name__ == "__main__":
    unittest.main()
