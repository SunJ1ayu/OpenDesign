#!/usr/bin/env python3
"""应用内更新「查更新」那一半的判据(track opendesign-in-app-update,第一刀)。

🔴 **这份考卷存在的第一理由是一条天生恒绿的坑,2026-09-07 开工前实测到的**:

    GET https://api.github.com/repos/SunJ1ayu/OpenDesign/releases/latest
    → http=404  {"message": "Not Found"}

原因不是仓库配错了,是 GitHub 那个接口**按设计跳过 prerelease**,
而本仓 **20 个 release 全是 prerelease**(同日录下的真实响应在
`tests/fixtures/update/github-releases-20260907.json`,自己数)。

⇒ 谁把挑版本的逻辑写成那个最直觉的接口,**这个功能会永远查不到新版本,
   而且一声不吭** —— 界面上永远显示"已是最新",业主永远收不到更新。
   这正是本项目反复栽的那种病:**一条永远绿的检查,比没有检查更坏**。

t1 从结果上钉它(预发布也必须挑得出来),t1b 从结构上钉它(源码里不许出现那个接口),
红检 m1 负责证明 t1 真咬得动。

另外三条问的是同一类"安静地错":版本号按字符串比(t2)、
本地比线上新时还提示更新(t3)、网络抽风时把异常甩到业主脸上(t7)。

**判据不许有外网出口**(2026-08-10 事故:一份考卷真去叫外部模型,一上午烧光额度),
所以这里一律喂录下来的夹具,`fetch` 一律注入。
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "update",
                       "github-releases-20260907.json")
MODULE_SRC = os.path.join(ROOT, "bin", "ds_update.py")

import ds_update  # noqa: E402  (故意在路径注入之后)


def _fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class PickLatest(unittest.TestCase):
    """t1:预发布也算数 —— 本单最要紧的一条。"""

    def test_t1a_fixture_is_all_prerelease(self):
        """先证明夹具确实是那个形状,否则 t1 问的是空气。"""
        rels = _fixture()
        self.assertGreaterEqual(len(rels), 10, "夹具太小,证明不了什么")
        self.assertTrue(
            all(r["prerelease"] for r in rels),
            "夹具里出现了非预发布 —— 那么 t1 就不再是在考"
            "「跳过 prerelease 会瞎掉」这件事了。要么换夹具,要么这条判据作废重写。")

    def test_t1_picks_the_newest_even_though_all_are_prerelease(self):
        """20 个全是预发布,必须挑出 0.98.3。"""
        got = ds_update.pick_latest(_fixture())
        self.assertIsNotNone(
            got, "一个都没挑出来 —— 这就是把 prerelease 过滤掉之后的样子:"
                 "功能永远查不到新版本,而且不报错。")
        self.assertEqual(ds_update.release_version(got), (0, 98, 3))

    def test_t1b_source_must_not_use_the_latest_endpoint(self):
        """结构闸:源码里不许出现 `/releases/latest`。

        t1 是从结果上问,这条是从结构上问。两条都在,是因为将来有人重写挑选逻辑时,
        很可能"顺手改回标准接口" —— 那一刻 t1 会红,而这一条会直接指出为什么。
        """
        src = open(MODULE_SRC, encoding="utf-8").read()
        self.assertNotIn(
            "releases/latest", src,
            "bin/ds_update.py 里出现了 `/releases/latest` —— 那个接口在本仓恒返回 404"
            "(本仓 20 个 release 全是 prerelease)。用 `/releases` 自己挑。")

    def test_t1c_release_without_installer_asset_is_not_a_candidate(self):
        """没有安装包资产的 release 不能被选中 —— 选中了就是"更新"到一个下不动的东西。"""
        rels = _fixture()
        newest = max(rels, key=lambda r: ds_update.release_version(r) or (0,))
        stripped = [dict(r, assets=[]) if r is newest else r for r in rels]
        got = ds_update.pick_latest(stripped)
        self.assertIsNotNone(got, "把最新那版的资产拿掉之后应当回退到上一版,而不是什么都不给")
        self.assertEqual(ds_update.release_version(got), (0, 98, 2))

    def test_t1d_draft_is_never_a_candidate(self):
        """草稿是没发出去的东西,业主下不到。"""
        rels = _fixture()
        faked = [dict(rels[0], tag_name="win-installer-9.9.9", draft=True)] + rels
        got = ds_update.pick_latest(faked)
        self.assertEqual(ds_update.release_version(got), (0, 98, 3),
                         "草稿被当成了可更新的版本")


class VersionCompare(unittest.TestCase):
    """t2:按数比,不按字符串。"""

    def test_t2a_numeric_not_lexicographic(self):
        """`"0.98.10" < "0.98.9"` 在字符串比较下成立 —— 这条就是钉它的。"""
        self.assertGreater(ds_update.parse_version("0.98.10"),
                           ds_update.parse_version("0.98.9"))

    def test_t2b_across_the_second_digit(self):
        self.assertGreater(ds_update.parse_version("0.99.0"),
                           ds_update.parse_version("0.98.3"))

    def test_t2c_one_point_oh(self):
        """1.0 由业主拍板才会出现,但版本比较不能等到那天才发现自己不认识它。"""
        self.assertGreater(ds_update.parse_version("1.0.0"),
                           ds_update.parse_version("0.99.9"))

    def test_t2d_tag_and_asset_forms_parse_the_same(self):
        """线上三种写法都指同一版:tag、资产名、纯版本号。"""
        self.assertEqual(ds_update.parse_version("win-installer-0.98.3"), (0, 98, 3))
        self.assertEqual(ds_update.parse_version("OpenDesign-Setup-0.98.3.exe"), (0, 98, 3))
        self.assertEqual(ds_update.parse_version("0.98.3"), (0, 98, 3))

    def test_t2e_garbage_returns_none_not_exception(self):
        for bad in ("", "  ", "latest", "v", "0.98.x", None):
            self.assertIsNone(ds_update.parse_version(bad), f"{bad!r} 应当解析失败而不是抛")


class DecideWhetherToOffer(unittest.TestCase):
    """t3:不比本地新就闭嘴。"""

    def test_t3a_same_version_no_offer(self):
        d = ds_update.decide("0.98.3", _fixture())
        self.assertFalse(d["update_available"], "版本一样还提示更新")

    def test_t3b_local_newer_no_offer(self):
        """开发机上本地永远比线上新 —— 那时提示"更新"是往回装。"""
        d = ds_update.decide("0.99.0", _fixture())
        self.assertFalse(d["update_available"], "本地比线上新,却提示更新(那是降级)")

    def test_t3c_local_older_offers_with_what_it_needs(self):
        d = ds_update.decide("0.98.1", _fixture())
        self.assertTrue(d["update_available"])
        self.assertEqual(d["latest"], "0.98.3")
        self.assertTrue(d["asset"]["url"].startswith("https://"),
                        "下载地址必须是 https —— 本单的信任根只有这一条")
        self.assertGreater(d["asset"]["size"], 0)

    def test_t3d_unparsable_local_version_never_offers(self):
        """读不出自己是哪一版时,宁可不提示,也不许瞎装。"""
        d = ds_update.decide("(未知)", _fixture())
        self.assertFalse(d["update_available"])


class NetworkMisbehaves(unittest.TestCase):
    """t7:网络抽风要安静,不许把栈甩到业主脸上。"""

    def _check(self, fetch):
        return ds_update.check("0.98.1", fetch=fetch)

    def test_t7a_timeout_is_quiet(self):
        def boom():
            raise TimeoutError("timed out")
        d = self._check(boom)
        self.assertFalse(d["update_available"])
        self.assertTrue(d["error"], "出错了却不说,日志里也查不到")

    def test_t7b_garbage_json_is_quiet(self):
        def junk():
            return "<html>502 Bad Gateway</html>"
        d = self._check(junk)
        self.assertFalse(d["update_available"])
        self.assertTrue(d["error"])

    def test_t7c_empty_list_is_quiet(self):
        d = self._check(lambda: [])
        self.assertFalse(d["update_available"])

    def test_t7d_never_raises_whatever_happens(self):
        """把能想到的坏形状都喂一遍:一条都不许抛。"""
        for bad in (lambda: (_ for _ in ()).throw(OSError("no route to host")),
                    lambda: None,
                    lambda: {"message": "Not Found"},
                    lambda: [{"tag_name": None, "assets": None}]):
            with self.subTest(bad=bad):
                try:
                    d = ds_update.check("0.98.1", fetch=bad)
                except Exception as exc:  # noqa: BLE001 —— 这里就是要抓住"抛了"
                    self.fail(f"check() 抛了 {exc!r} —— 业主会看到一坨栈")
                self.assertIn("update_available", d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
