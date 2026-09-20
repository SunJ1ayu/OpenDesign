#!/usr/bin/env python3
"""「这一版还够不够格自动更新」必须是**一处判断、三处共用**
(track opendesign-startup-not-blocked-by-update,第 2 轮外审后重做,2026-09-20)。

主 agent 亲写。为什么要单独一卷,而不是往 ai/pr 卷里再加两条:

第 1 轮外审报「装失败后备货不清 ⇒ 每次打开空演一遍更新界面」,我的修法是在**末端**
(apply 判不合格时)`discard_ready` 把包删掉。第 2 轮两条不同家族的腿
(subcursor / subdeepseek)**各自独立**指出:删了也没用 ——

    打开 A(enter)→ 开着满 60s,前端无条件 POST 备货 → 后台把**同一个装不上的包**
    重新下 46MB → 打开 B:startup 说 install、界面弹「正在更新到 X」→ apply 判
    `attempted` → auto_skipped(界面**静默**)+ discard → 打开 C:enter → 又下 46MB → ……

症状没根除,只是周期从"每次"变成"每两次",外加每轮 46MB 流量。

🔴 **共同根因**:`auto-update-attempts.json` 这本账,链上**三个**决策点只有一个在读:

    prepare(要不要下)  ❌ 只问 check_cached
    startup(要不要弹界面装) ❌ 只看 update-state.json
    apply(真装)        ✅ 唯一读的一处

末端删文件永远追不上前端重下。**这是同一类问题连续第二次打补丁 ⇒ 按 panel SKILL 4c 停手,
改抽象:把资格判断做成单一判据,三处共用**,而不是再补第三个补丁。

**这份考卷防的五种"看起来修好了"**:
① **把功能关死**:干脆不备货 / startup 永远 enter ⇒ 症状确实没了,自动更新也没了。
   **el3 反向钉**(没试过的版本必须照常备货、照常装)。这是最可能的假修法,所以它是本卷第一题。
② **只改 prepare 不改 startup**:不重下了,但盘上残留的旧 ready 照样弹界面。**el2 钉**。
③ **只改 startup 不改 prepare**:不弹界面了,但每轮照样白下 46MB。**el1 钉**。
④ **把 discard 扩大成"不合格就删"**:临时条件(没外壳/开关关着/出错)下把业主的 46MB
   白白删掉,条件恢复后还得重下。**el4 钉**。
⑤ **拿时效性的 `recent_failure` 冒充资格**:过 24 小时又重新下、又空演一遍。
   **el1b 钉**(记录是 30 天前的,照样不许备货)。

🔴 **el5 是本卷的核心**:它不钉任何一个函数,它把业主真实经历的那条链**连着走两轮**
   ——装失败 → 清货记账 → 后台再备货 → 再打开。上面任何一处漏了,el5 都会红。
   钉行为不钉实现:实现者怎么共用那个判据我不管,但这条链必须收敛。

夹具借 test_ds_web_auto_update / test_ds_web_auto_install_local 那一套(装出来的桌面版 +
假外壳端口 + 离线)。**借的是夹具不是继承**:直接继承会把那两卷的题在这里重跑一遍,
而它们的前提被本卷的替身改过 —— 那种红是假红(同 ai 卷文件头的那条教训)。
"""
import hashlib
import json
import os
import sys
import time
import unittest
from unittest import mock

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
AUTO_KNOB = base.AUTO_KNOB
_post = base._post
_get = base._get

PAYLOAD = b"pretend installer bytes for eligibility"


class UpdateEligibility(unittest.TestCase):
    """资格判据必须在 prepare / startup / apply 三处一致。"""

    setUpFixture = base.AutoUpdate.setUp
    _install = base.AutoUpdate._install
    _serve = base.AutoUpdate._serve

    def setUp(self):
        self.setUpFixture()
        self.pending_dir = os.path.join(self.data_root, "Logs", "pending")
        self.downloads = []
        self.net_calls = []

        def fake_apply(decision, paths, **kw):
            self.order.append("apply")
            if self.apply_ok:
                return {"ok": True, "stage": "relay", "error": None, "relay": "C:/tmp/relay.cmd"}
            return {"ok": False, "stage": "verify", "error": "sha256 对不上", "relay": None}
        ds_update_apply.apply_update = fake_apply

    # --- 夹具 ---------------------------------------------------------------

    def _armed(self):
        """把查更新的两个取数口换成炸弹:本卷任何一题都不许真去联网。"""
        def boom(*a, **kw):
            self.net_calls.append("fetch")
            raise OSError("这条路上不许联网")
        ds_update.fetch_releases = boom
        ds_update.fetch_atom = boom
        ds_update.cache_clear()

    def _info(self, version=LATEST, payload=PAYLOAD):
        """后台备货用的那份"查更新结果"。"""
        return {"current": "0.98.2", "update_available": True, "latest": version,
                "asset": {"name": "OpenDesign-Setup-%s.exe" % version,
                          "url": "https://github.com/SunJ1ayu/OpenDesign/releases/download/"
                                 "win-installer-%s/OpenDesign-Setup-%s.exe" % (version, version),
                          "size": len(payload),
                          "digest": "sha256:" + hashlib.sha256(payload).hexdigest()}}

    def _spy_download(self):
        """记账用的下载替身:调用一次就记一次,顺便把字节写到位。"""
        def dl(url, dest):
            self.downloads.append(url)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(PAYLOAD)
        return dl

    def _stock(self, version=LATEST, payload=PAYLOAD):
        """摆出"后台已经下好并校验过"的样子:一个真文件 + 一份 ready 状态。"""
        os.makedirs(self.pending_dir, exist_ok=True)
        name = "OpenDesign-Setup-%s.exe" % version
        path = os.path.join(self.pending_dir, name)
        with open(path, "wb") as fh:
            fh.write(payload)
        state = {"schema": 1, "phase": "ready", "version": version,
                 "asset": {"name": name, "size": len(payload),
                           "sha256": hashlib.sha256(payload).hexdigest(),
                           "url": self._info(version, payload)["asset"]["url"]},
                 "path": path, "updated_at": time.time()}
        ds_update_startup.write_state(
            ds_update_startup.state_path(self.data_root), state)
        return path, state

    def _startup_action(self):
        """走**真端点**问"打开软件时该干什么" —— 不问纯函数。

        🔴 故意走端点:资格判据下沉到 startup_decision 之后,端点忘了把 data_root
           传进去,纯函数级的判据是查不出来的(它自己测自己,永远绿)。
        """
        with self._serve() as port:
            st, body = _get(port, "/api/update/startup")
        self.assertEqual(st, 200, body)
        return (body or {}).get("action"), (body or {}).get("reason")

    def _drain_prepare(self, port, timeout=15.0):
        """prepare 端点立刻返回、下载在后台线程里 ⇒ 判据要等那条线程落地再断言。

        靠端点自己的重入标志判完成:`running` 清了就说明 work() 跑完了
        (不靠 sleep 猜时间,那会 flaky)。
        """
        import time as _t
        deadline = _t.time() + timeout
        while _t.time() < deadline:
            st, body = _post(port, "/api/update/prepare", b"{}")
            if st == 200 and (body or {}).get("reason") != "already_running":
                # 这一次要么没起(被资格闸拦下)、要么又跑了一轮并已结束
                if (body or {}).get("started") is not True:
                    return body
                continue
            _t.sleep(0.1)
        raise AssertionError("prepare 后台线程 %.1fs 没落地" % timeout)

    def _package_exists(self, path):
        return os.path.isfile(path)

    # === el3:反向题 —— 没试过的版本,一切照旧 ==============================
    # 放第一题是有意的:本卷其余各题都在"少做事",最省事的过关办法就是把功能关死。

    def test_el3_a_version_never_attempted_is_still_prepared_and_installed(self):
        self._armed()
        got = ds_update_startup.prepare_update(
            self._info(), self.data_root, download=self._spy_download())
        self.assertIs(got.get("ok"), True, "没试过的版本竟然备不了货:%r" % (got,))
        self.assertEqual(len(self.downloads), 1,
                         "🔴 没试过的版本没有被下下来 —— 自动更新被关死了,不是修好了")

        action, reason = self._startup_action()
        self.assertEqual(action, "install",
                         "🔴 备好的新版在启动时不装了(reason=%r)—— 自动更新被关死了" % (reason,))

    # === el1:prepare 侧认账 —— 已试过的版本不许再下 ========================

    def test_el1_prepare_refuses_to_restock_a_version_already_attempted(self):
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._armed()

        got = ds_update_startup.prepare_update(
            self._info(), self.data_root, download=self._spy_download())

        self.assertEqual(self.downloads, [],
                         "🔴 这一版已经自动试过一次(装不上),后台又把 46MB 下了一遍:%r" % (got,))
        self.assertIsNot(got.get("ok"), True,
                         "备货居然报成功 —— 那下一次打开又会空演一遍更新界面:%r" % (got,))
        state = ds_update_startup.read_state(ds_update_startup.state_path(self.data_root))
        self.assertNotEqual((state or {}).get("phase"), "ready",
                            "没下却写了 ready 状态:%r" % (state,))

    def test_el1b_eligibility_is_permanent_not_a_24h_window(self):
        """拿 `recent_failure`(24h 时效)冒充资格 ⇒ 过一天又重下、又空演一遍。"""
        long_ago = time.time() - 30 * 24 * 3600
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST, now=long_ago)
        self.assertTrue(ok, err)
        self.assertFalse(ds_auto_update.recent_failure(self.data_root, LATEST),
                         "夹具没摆对:30 天前的记录不该算 recent_failure")
        self._armed()

        ds_update_startup.prepare_update(
            self._info(), self.data_root, download=self._spy_download())

        self.assertEqual(self.downloads, [],
                         "🔴 用 24 小时的时效窗口当资格:过一天就又下一遍 46MB、又空演一次")

    # === el2:startup 侧认账 —— 已试过的版本不许弹更新界面 ==================

    def test_el2_startup_does_not_offer_to_install_a_version_already_attempted(self):
        """盘上那份 ready 完全合格(大小/摘要/版本全对),唯一的问题是这一版已经试过。"""
        self._stock()
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._armed()

        action, reason = self._startup_action()

        self.assertEqual(action, "enter",
                         "🔴 已经试过装不上的那一版,打开软件又弹了一次更新界面"
                         "(action=%r reason=%r)—— 业主看到的就是「闪一下,什么都没说」" % (action, reason))

    # === el4:清货的条件 —— 只清"这一版真的不会再自动装的" ==================

    def test_el4_transient_ineligibility_keeps_the_package(self):
        """没外壳 / 开关关着 / 出错:一行账都没记,这一版**本来还能装**,不许删业主的 46MB。"""
        for label, env in (("no_shell", {"DS_SHELL_LOCK_PORT": ""}),
                           ("disabled", {AUTO_KNOB: "off"})):
            with self.subTest(why_not=label):
                path, _ = self._stock()
                self._armed()
                with mock.patch.dict(os.environ, env):
                    with self._serve() as port:
                        st, body = _post(port, "/api/update/apply", AUTO)
                self.assertEqual(st, 200, body)
                self.assertIs(body.get("ok"), False, body)

                self.assertTrue(
                    self._package_exists(path),
                    "🔴 %s 是**临时**条件(账一行没记,条件恢复就能自动装),"
                    "却把已经下好校验好的 46MB 删了 —— 白丢,还得重下一遍" % label)
                self.assertIsNone(
                    ds_auto_update.attempted_at(self.data_root, LATEST),
                    "%s 不该被记成「已经试过一次」" % label)

    def test_el4b_attempted_still_discards_the_package(self):
        """反向:这一版真的不会再自动装了 ⇒ 那 46MB 留着没用,该清(第 1 轮 ai7 的行为不许丢)。"""
        path, _ = self._stock()
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._armed()
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertEqual(body.get("stage"), "auto_skipped", body)
        self.assertFalse(self._package_exists(path),
                         "这一版已经不会再自动装了,那个包该清掉(ai7)")

    # === el5:核心 —— 业主真实经历的那条链,连着走两轮必须收敛 ==============

    def test_el5_a_failed_auto_install_does_not_come_back_every_other_launch(self):
        """装失败 → 清货记账 → 后台再备货 → 再打开。这是第 2 轮两条腿报的那条链。

        🔴 钉的是**行为不是实现**:资格判据放哪、怎么共用,我不管;
           但走完这四步之后,业主不许再看到一次更新界面,也不许再被下一次 46MB。
        """
        path, _ = self._stock()
        self.apply_ok = False          # 这一次自动更新装失败
        self._armed()

        # 第 1 步:打开 A —— 有货,去装,失败
        with self._serve() as port:
            st, body = _post(port, "/api/update/apply", AUTO)
        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), False, "夹具没摆对:这一次本该装失败")
        self.assertIsNotNone(ds_auto_update.attempted_at(self.data_root, LATEST),
                             "装失败了却没记账 ⇒ 下一次还会自动试(第 1 轮 ai8)")
        self.assertFalse(self._package_exists(path), "装失败之后那份备货该清掉(第 1 轮 ai7)")

        # 第 2 步:他继续用软件,满 60 秒,前端无条件让后台备货
        got = ds_update_startup.prepare_update(
            self._info(), self.data_root, download=self._spy_download())
        self.assertEqual(self.downloads, [],
                         "🔴 同一个装不上的包又被下了一遍 46MB(第 2 轮 subcursor/subdeepseek "
                         "各自独立报的那条 HIGH):%r" % (got,))

        # 第 3 步:下一次打开软件
        action, reason = self._startup_action()
        self.assertEqual(action, "enter",
                         "🔴 又弹了一次更新界面(action=%r reason=%r)。"
                         "第 1 轮只把周期从「每次」改成「每两次」,症状没根除" % (action, reason))

        # 第 4 步:再走一轮,确认它是收敛的,不是把周期拉长到 3
        ds_update_startup.prepare_update(
            self._info(), self.data_root, download=self._spy_download())
        self.assertEqual(self.downloads, [], "第二轮又下了一遍 —— 这条链没有收敛,只是周期更长")
        self.assertEqual(self._startup_action()[0], "enter", "第二轮又弹了一次更新界面")

    # === el9:资格闸装上之后,别把 46MB 永远晾在盘上 ========================

    def test_el9_an_ineligible_leftover_package_gets_cleaned_up(self):
        """**我自己审出来的,不是腿报的**(2026-09-20,写完 el1/el2 的实现之后)。

        资格闸装上以后,已试过那一版的链路变成:prepare 直接拒、startup 回 enter
        ⇒ **apply 再也不会被调用**。而清包的动作原本就挂在 apply 那一侧
        (`discard_ready`)。于是只要有一份 attempted 版本的 ready 备货没走完正常流程
        (discard 那一下失败、或状态文件是更早的版本写的),它就**三处都没人碰**:
        `_sweep_installed` 不清(它比当前版本新)、`_sweep_orphans` 不清(状态正指着它)、
        apply 不跑。业主盘上白占 46MB,永久。

        prepare 每次打开软件后 60 秒跑一趟(前端 `setTimeout` 单次,**不是**轮询),
        本来就是"打扫 + 备货"的地方,是这条链自然的收敛点。
        清掉它零风险:那个包**永远不会再被自动装**,而手动更新走的是真下载、不碰它(el6)。
        """
        path, _ = self._stock()
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._armed()

        got = ds_update_startup.prepare_update(
            self._info(), self.data_root, download=self._spy_download())

        self.assertEqual(self.downloads, [], "夹具没摆对:这一版不该被重下(el1)")
        self.assertFalse(
            self._package_exists(path),
            "🔴 这一版永远不会再自动装(prepare 拒、startup 回 enter、apply 不跑),"
            "那 46MB 却还躺在业主盘上,三处都没人清:%r" % (got,))
        state = ds_update_startup.read_state(ds_update_startup.state_path(self.data_root))
        self.assertNotEqual((state or {}).get("phase"), "ready",
                            "包清了状态还说 ready:%r" % (state,))

    # === el6:手动更新这条路一行不许变 ======================================

    def test_el6_manual_update_is_unaffected_by_the_auto_eligibility_gate(self):
        """资格判据管的是**自动**更新。业主自己点「更新」,试过多少次都得让他装。"""
        ok, err = ds_auto_update.record_attempt(self.data_root, LATEST)
        self.assertTrue(ok, err)
        self._stock()
        with self._serve() as port:            # 手动这条路本来就该联网,不装炸弹
            st, body = _post(port, "/api/update/apply", MANUAL)
        self.assertEqual(st, 200, body)
        self.assertEqual(self.order.count("apply"), 1,
                         "🔴 资格判据下沉时把手动更新一起挡了 —— 业主再也装不上这一版:%r" % (body,))

    # === el10~el13:完整资格(第 3 轮 subdeepseek F1,我跑探针核实成立)=========
    #
    # 🔴 第 2 轮我只把**账本**那一维(试过没试过)收成了单一判据,于是漏了另外几维。
    #    完整的「该不该自动装」住在 `ds_web._auto_update_status`,它有 7 种否决:
    #    no_update / asset / **no_shell** / **not_installed** / **path_unsupported** /
    #    attempted / **disabled**。加粗那几种**只在 apply 被问** —— 那时界面已经弹出来了。
    #    探针实测(第 3 轮派发后我自己跑的):
    #        [no_shell] STARTUP -> install ; APPLY -> auto_skipped/no_shell ; 包还在盘上
    #        [disabled] 同上
    #    ⇒ 界面闪一下、什么都不说、包留着、下次打开再来一遍,**永不收敛**。
    #    比 attempted 那条更糟(那条至少会清包收敛),而且 `disabled` 就是
    #    「关掉自动更新」那个开关 —— 关了照样弹界面、照样下 46MB。
    #
    # 🔴 **而且是我上午那条 el4 把它锁死的**:el4 要求临时条件不许删包(对的),
    #    但我漏了一句 —— 既然不该删,就更不该让它走到弹界面那一步。
    #
    # 这些题**全部走真端点**:纯函数问不出「端点有没有把完整资格接上去」。

    def _startup_and_apply(self, env):
        with mock.patch.dict(os.environ, env):
            with self._serve() as port:
                st, startup = _get(port, "/api/update/startup")
                st2, applied = _post(port, "/api/update/apply", AUTO)
        self.assertEqual((st, st2), (200, 200), (startup, applied))
        return startup, applied

    def test_el10_startup_does_not_offer_to_install_when_the_machine_cannot(self):
        """没外壳 / 开关关着 ⇒ 打开软件**不许**弹更新界面(apply 迟早也会拒,但那太晚了)。"""
        for label, env in (("no_shell", {"DS_SHELL_LOCK_PORT": ""}),
                           ("disabled", {AUTO_KNOB: "off"})):
            with self.subTest(why_not=label):
                self._stock()
                self._armed()
                startup, applied = self._startup_and_apply(env)
                self.assertEqual(
                    startup.get("action"), "enter",
                    "🔴 %s:启动说 install(reason=%r)⇒ 界面弹「正在更新到 X」,"
                    "而 apply 回 %r 在界面上是**静默**的。业主看到「闪一下,什么都没说」,"
                    "且包留着 ⇒ 每次打开重复一遍,永不收敛"
                    % (label, startup.get("reason"), applied.get("stage")))

    def test_el11_prepare_does_not_stock_when_the_machine_cannot(self):
        """没外壳 / 开关关着 ⇒ 后台**不许**去下那 46MB(下了也装不上)。

        `disabled` 尤其要紧:那是「关掉自动更新」的开关,关了还偷偷下载是说话不算话。
        """
        for label, env in (("no_shell", {"DS_SHELL_LOCK_PORT": ""}),
                           ("disabled", {AUTO_KNOB: "off"})):
            with self.subTest(why_not=label):
                self._armed()
                self.downloads = []
                with mock.patch.dict(os.environ, env):
                    with self._serve() as port:
                        st, body = _post(port, "/api/update/prepare", b"{}")
                        self.assertEqual(st, 200, body)
                        self._drain_prepare(port)
                self.assertEqual(
                    self.downloads, [],
                    "🔴 %s:机器现在根本装不上,后台还是把 46MB 下了(业主的流量和磁盘)" % label)

    def test_el12_a_capable_machine_still_prepares_and_installs(self):
        """反向题:该能装的时候一切照旧 —— 防"把功能关死"式假修(同 el3)。"""
        self._stock()
        self._armed()
        with self._serve() as port:
            st, startup = _get(port, "/api/update/startup")
        self.assertEqual(st, 200, startup)
        self.assertEqual(startup.get("action"), "install",
                         "🔴 条件全满足却不装了(reason=%r)—— 自动更新被关死了"
                         % (startup.get("reason"),))

    def test_el13_a_transient_blocker_going_away_restores_auto_update(self):
        """没外壳是**临时**状况(下次带着外壳起来就好了)⇒ 不许把这一版永久判死。

        与 el4 呼应:el4 说这种情况不许删包;这一条说条件恢复后它必须还能装。
        两条一起才是完整的"临时条件"语义。
        """
        path, _ = self._stock()
        self._armed()
        startup, _applied = self._startup_and_apply({"DS_SHELL_LOCK_PORT": ""})
        self.assertEqual(startup.get("action"), "enter", "夹具没摆对(见 el10)")
        self.assertTrue(self._package_exists(path), "临时状况不该删包(el4)")
        self.assertIsNone(ds_auto_update.attempted_at(self.data_root, LATEST),
                          "临时状况不该记账(那会把这一版永久判死)")

        with self._serve() as port:          # 外壳回来了(夹具默认有 DS_SHELL_LOCK_PORT)
            st, startup2 = _get(port, "/api/update/startup")
        self.assertEqual(st, 200, startup2)
        self.assertEqual(startup2.get("action"), "install",
                         "🔴 临时状况过去了却再也不装(reason=%r)—— 把临时当成了永久"
                         % (startup2.get("reason"),))

    def test_el14_a_permanent_blocker_does_not_hoard_46mb_forever(self):
        """第 3 轮 subdeepseek F4:`path_unsupported` 是**永久**条件,而收窄后的 discard
        只在 `attempted` 触发、el9 的清理只在账本那条路触发 ⇒ 那 46MB 没人删。
        `_sweep_installed` 又故意放过比当前版本新的包。同一类磁盘泄漏,换了个 reason code。
        """
        path, _ = self._stock()
        self._armed()
        bad = os.path.join(self.tmp, "live with %s percent")
        os.makedirs(bad, exist_ok=True)
        with mock.patch.object(ds_update_apply, "update_preflight_problem",
                               lambda paths: ("path_unsupported", "安装路径里有 %")):
            with self._serve() as port:
                st, body = _post(port, "/api/update/prepare", b"{}")
                self.assertEqual(st, 200, body)
                self._drain_prepare(port)
        self.assertFalse(
            self._package_exists(path),
            "🔴 path_unsupported 是永久条件,这一版**永远**装不上,那 46MB 却没人清")

    # === el7 / el8:第 2 轮两条 LOW ========================================

    def test_el7_a_throwing_prepare_does_not_wedge_the_endpoint_forever(self):
        """`_PREPARE_STATE["running"]` 置位之后若抛出,本会话之后所有备货永远回
        already_running ⇒ 自动更新整条**静默**死掉(第 2 轮 subdeepseek LOW)。"""
        self._armed()
        boom_calls = []
        real_paths_for_update = ds_update_apply.paths_for_update

        def boom(*a, **kw):
            boom_calls.append(1)
            raise RuntimeError("算数据根时炸了")

        with self._serve() as port:
            ds_update_apply.paths_for_update = boom
            try:
                st, body = _post(port, "/api/update/prepare", b"{}")
            finally:
                ds_update_apply.paths_for_update = real_paths_for_update
            self.assertEqual(st, 200, "备货端点不许把异常抛给界面:%r" % (body,))
            self.assertTrue(boom_calls, "夹具没摆对:那一炸没被触发")

            st2, body2 = _post(port, "/api/update/prepare", b"{}")
        self.assertEqual(st2, 200, body2)
        self.assertNotEqual((body2 or {}).get("reason"), "already_running",
                            "🔴 上一次抛出把闸永久卡死了 ⇒ 自动更新这一会话再也不工作,而且悄无声息")

    def test_el8_discard_never_raises_even_on_a_broken_state(self):
        """`_discard` 的 docstring 写着"自己也不许抛",实现只 catch OSError,
        而 `os.path.isfile(None)` 抛的是 TypeError(第 2 轮 subdeepseek 实测)。"""
        state_file = ds_update_startup.state_path(self.data_root)
        ds_update_startup.write_state(state_file, {
            "schema": 1, "phase": "ready", "version": LATEST,
            "asset": {"name": "x.exe", "size": 1, "sha256": "0" * 64, "url": "https://x/y"},
            "path": None, "updated_at": time.time()})
        try:
            ds_update_startup._discard(None, state_file)
        except Exception as exc:  # noqa: BLE001
            self.fail("_discard 说好了自己不抛,却抛了 %s: %s" % (type(exc).__name__, exc))


if __name__ == "__main__":
    unittest.main()
