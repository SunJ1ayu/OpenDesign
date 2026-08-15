#!/usr/bin/env python3
"""判据:业主的东西不许住在安装目录里(track opendesign-data-outside-install)。

    python3 tests/test_data_root.py

## 为什么这份判据存在

S1c 的安装器卸载时执行 `RMDir /r "$INSTDIR"` —— 整棵删。而业主的**共享参考图库
(真图片,含现场照片)**、项目档案、客户备忘、总索引、整理审计、工作区设置,
现在全在 `$INSTDIR\\ds\\` 底下。卸载确认页却写着「你的资料默认不会被删除」。
比卸载更常发生的是更新:S1d 的换整棵树设计会把同一批东西带走。

## 它问的是一条不变量,不是一份清单

**安装目录在运行时是只读的。** 之所以不写成"projects/ 要在数据根下"这种逐项断言:
清单会漏(我这次栽的正是"把位置做成了闸、没把清单做成闸"),而不变量不会 ——
将来谁再加一种数据文件,只要写进安装目录就当场红。

## 它问不出什么

- **只读的用户数据**(用户手工放进 `refs/` 的图片、`config/taxonomy.json`)——
  程序从不写它们,哈希闸永远不会为它们红。⇒ F 组专门不靠写口去问(规划双出 B 卷戳穿的)。
- Windows 上 `RMDir /r` 到底删了什么 —— 只有业主真机能答,已在真机清单里。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_common  # noqa: E402
import ds_consent  # noqa: E402
import ds_refs  # noqa: E402
import ds_tools  # noqa: E402

ENV_VAR = "DS_DATA_ROOT"

# 判据自己不许够得着这台机器的真家(2026-08-15 实证:红检把真机 gateway 口令换了)。
_JUDGE_HOME = None
_SAVED: dict[str, str | None] = {}


def setUpModule():
    global _JUDGE_HOME
    _JUDGE_HOME = tempfile.mkdtemp(prefix="ds-dataroot-判据假家-")
    for k in ("HOME", "USERPROFILE", ENV_VAR):
        _SAVED[k] = os.environ.get(k)
    os.environ["HOME"] = _JUDGE_HOME
    os.environ["USERPROFILE"] = _JUDGE_HOME
    os.environ.pop(ENV_VAR, None)


def tearDownModule():
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def tree_hash(root: str) -> dict[str, str]:
    """逐文件 sha256。忽略 __pycache__/*.pyc —— 那是解释器写的,不是业主的东西。"""
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if fn.endswith(".pyc"):
                continue
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, root)
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


class Rig(unittest.TestCase):
    """一棵仿真安装树:代码 + **已经存在的业主数据**(基线必须非空,否则"前后一致"没有意义)。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-dataroot-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.install = os.path.join(self.tmp, "Programs", "OpenDesign")
        self.ds_root = os.path.join(self.install, "ds")
        self.state_root = os.path.join(self.tmp, "OpenDesign")      # 应用状态根
        self.data_root = os.path.join(self.state_root, "Data")
        os.makedirs(os.path.join(self.ds_root, "config"), exist_ok=True)
        os.makedirs(self.data_root, exist_ok=True)

        # 代码那一份(装什么样就该一直是什么样)
        with open(os.path.join(self.ds_root, "config", "nanobot.config.windows.jsonc"),
                  "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        with open(os.path.join(self.ds_root, "版本号.txt"), "w", encoding="utf-8") as fh:
            fh.write("0.86.0\n")

        # 🔴 基线里必须有**数据形状**的文件(防"骗法二:哈希比的是空树"):
        # 实现要是写回安装目录,这些同名文件正好会被改到。
        for rel, body in (
            (os.path.join("projects", "老项目-1801.md"), "# 老项目-1801\n\n## 变更记录\n"),
            (os.path.join("refs", "老图.png"), "PNG-老图"),
            ("index.md", "# 索引\n"),
        ):
            p = os.path.join(self.ds_root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)

        os.environ[ENV_VAR] = self.data_root
        self.addCleanup(os.environ.pop, ENV_VAR, None)

    def workdir(self, name="业主的项目夹"):
        d = os.path.join(self.tmp, name)
        os.makedirs(d, exist_ok=True)
        return d

    def exercise_writes(self):
        """把写口跑一遍。清单**从代码机械抽**(bin/*.py 里 join(ds_root,…) 共 47 处),
        不是我凭记忆列的;总覆盖由 H 组的静态闸兜底。"""
        ds_tools.create_project("星河名邸-2302", client="李四", ds_root=self.ds_root)
        ds_tools.create_client("王五", ds_root=self.ds_root)
        ds_tools.append_change("星河名邸-2302", "客厅改推拉门", ds_root=self.ds_root)
        ds_tools.log_communication("星河名邸-2302", "微信:太太确认", ds_root=self.ds_root)
        ds_tools.set_stage("星河名邸-2302", "方案深化", ds_root=self.ds_root)
        ds_tools.set_workspace(self.workdir(), ds_root=self.ds_root)
        ds_refs.add_style("侘寂", ds_root=self.ds_root)
        ds_consent.set_mode(ds_consent.MODE_ASK, ds_root=self.ds_root)
        ds_consent.create_pending(self.ds_root, "set_workspace", {"root": self.workdir()})
        ds_tools.delete_project("老项目-1801", ds_root=self.ds_root)   # 走 projects/.trash


class TestInstallDirIsReadOnly(Rig):
    """A 组:**本文件最重的一条** —— 跑完所有写口,安装目录一个字节都不许变。"""

    def test_a1_baseline_is_not_empty(self):
        """防"骗法二":拿空树比哈希,前后一致毫无意义。"""
        before = tree_hash(self.ds_root)
        self.assertGreaterEqual(len(before), 5, f"基线太薄,这个闸问不出东西:{sorted(before)}")
        self.assertTrue(any(k.startswith("projects") for k in before), "基线里没有数据形状的文件")

    def test_a2_writes_do_not_touch_the_install_tree(self):
        before = tree_hash(self.ds_root)
        self.exercise_writes()
        after = tree_hash(self.ds_root)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        self.assertEqual(changed, [], f"业主的东西写进了安装目录(卸载会删掉它们):{changed}")

    def test_a3_the_writes_actually_landed_somewhere(self):
        """双向验:上面那条不能靠"什么都没写"过关。"""
        self.exercise_writes()
        landed = tree_hash(self.data_root)
        self.assertTrue(any(k.startswith("projects") for k in landed),
                        f"数据根里没有档案,那 a2 的绿是假的:{sorted(landed)}")


class TestDefaultUnchanged(Rig):
    """B 组:没设 env = 老行为。git-pull 那两台机器不许被这次改动碰到。"""

    def test_b1_without_env_data_root_is_ds_root(self):
        os.environ.pop(ENV_VAR, None)
        self.assertEqual(os.path.realpath(ds_common.data_root(self.ds_root)),
                         os.path.realpath(self.ds_root))

    def test_b2_without_env_writes_still_land_in_ds_root(self):
        os.environ.pop(ENV_VAR, None)
        ds_tools.create_project("翡翠湾-1801", ds_root=self.ds_root)
        self.assertTrue(os.path.isfile(os.path.join(self.ds_root, "projects", "翡翠湾-1801.md")))


class TestFailClosed(Rig):
    """C 组:设了但不可用 ⇒ **拒绝**,绝不静默回退安装目录(规划双出 B 卷)。

    静默回退是本单最危险的失败形态:一切看起来正常,而业主的东西正在往会被删的地方写。
    """

    # ⚠️ 这两条第一版写成 `assertRaises(Exception)` —— 而函数还不存在时抛的
    #    `AttributeError` 也是 Exception,于是判据在实现写出来之前就"绿"了。
    #    那是 08-14 记过的同一个坑的反面(红在 AttributeError 上 ≠ 红对了)。
    #    现在钉死到一个专门的异常类上,顺带把契约写进判据。
    def test_c1_env_pointing_at_a_file_is_refused(self):
        bogus = os.path.join(self.tmp, "我是个文件")
        with open(bogus, "w", encoding="utf-8") as fh:
            fh.write("x")
        os.environ[ENV_VAR] = bogus
        with self.assertRaises(ds_common.DataRootError):
            ds_common.data_root(self.ds_root)

    def test_c2_unusable_env_never_falls_back_to_install_dir(self):
        bogus = os.path.join(self.tmp, "我是个文件2")
        with open(bogus, "w", encoding="utf-8") as fh:
            fh.write("x")
        os.environ[ENV_VAR] = bogus
        try:
            got = ds_common.data_root(self.ds_root)
        except ds_common.DataRootError:
            return                      # 拒绝 = 正确
        self.assertNotEqual(os.path.realpath(got), os.path.realpath(self.ds_root),
                            "env 不可用时悄悄回退到了安装目录 —— 这正是最危险的那种绿")


class TestShellPassesTheEnv(Rig):
    """D 组:包里那条 env **真的**传到了子进程。

    这一组防的是本单最阴的失败:代码全改对了,而外壳忘了把 `DS_DATA_ROOT` 传下去 ⇒
    三个 MCP 与 ds-web 全都 fail closed 起不来(或者更糟:回退写安装目录)。
    **问的是 `ds_shell_core` 真的那个造环境函数**,不是我在判据里重写一遍期望
    (08-14「两张考卷对同一前提做了相反假设」那笔账)。
    """

    def test_d1_child_env_carries_the_data_root(self):
        import ds_shell_core as core
        env = core.child_env({"PATH": "/usr/bin"}, ds_root=self.ds_root,
                             user_home=os.path.join(self.state_root, "UserData"),
                             dsweb_port=18795, ws_port=8765)
        self.assertIn(ENV_VAR, env, "外壳没把数据根传给子进程")
        self.assertNotEqual(os.path.realpath(env[ENV_VAR]), os.path.realpath(self.ds_root),
                            "外壳把数据根指回了安装目录")

    def test_d2_the_data_root_sits_outside_the_install_dir(self):
        import ds_shell_core as core
        env = core.child_env({}, ds_root=self.ds_root,
                             user_home=os.path.join(self.state_root, "UserData"),
                             dsweb_port=18795, ws_port=8765)
        # ⚠️ 先问"在不在" —— 第一版写的是 `env.get(ENV_VAR, "")`,缺席时 realpath("")
        #    等于当前目录,当然不在安装目录里面 ⇒ **判据在功能还没做时就绿了**。
        #    今天这是我自己写出的第三条"缺席被当成通过"。
        self.assertIn(ENV_VAR, env, "外壳没把数据根传给子进程")
        got = os.path.realpath(env[ENV_VAR])
        self.assertFalse(ds_common.within(os.path.realpath(self.install), got),
                         f"数据根落在安装目录里面,卸载照样删:{got}")


class TestWorkspaceGuard(Rig):
    """E 组:业主的项目夹不许设在"删得掉的地方"。双向重叠都要拦(B 卷补的)。"""

    def _refused(self, root):
        r = ds_tools.set_workspace(root, ds_root=self.ds_root)
        self.assertIsInstance(r, dict)
        self.assertTrue(r.get("error"), f"这个位置应该被拒绝:{root} → {r}")
        return r

    def test_e1_refuses_the_install_dir_itself(self):
        self._refused(self.install)

    def test_e2_refuses_a_folder_inside_the_install_dir(self):
        d = os.path.join(self.ds_root, "我的项目")
        os.makedirs(d, exist_ok=True)
        self._refused(d)

    def test_e3_refuses_a_folder_inside_the_app_state_root(self):
        d = os.path.join(self.data_root, "我的项目")
        os.makedirs(d, exist_ok=True)
        self._refused(d)

    def test_e4_refuses_a_folder_that_contains_the_app_state_root(self):
        """把工作区设成 %LOCALAPPDATA% 就"包住"了应用状态根 —— 我 A 卷只想到"在里面"。"""
        self._refused(self.tmp)

    def test_e5_a_normal_folder_still_works(self):
        """双向验:别造一个"永远拒绝"的闸。"""
        r = ds_tools.set_workspace(self.workdir(), ds_root=self.ds_root)
        self.assertFalse(r.get("error"), f"正常目录被拦了:{r}")


class TestReadOnlyUserData(Rig):
    """F 组:**不靠写口**的一路(规划双出 B 卷戳穿我的盲区)。

    程序从不写 refs/ 里的图片 —— 用户手工放进去,`add_ref` 只往索引记一笔。
    ⇒ 哈希闸永远不会为它们红,但卸载照样删。这一组问的是"读口有没有也搬家"。
    """

    def test_f1_a_hand_placed_image_is_found_under_the_data_root(self):
        refs = os.path.join(self.data_root, "refs")
        os.makedirs(refs, exist_ok=True)
        img = os.path.join(refs, "业主自己放的.png")
        with open(img, "wb") as fh:
            fh.write(b"PNG")
        ds_refs.add_style("侘寂", ds_root=self.ds_root)
        r = ds_refs.add_ref(img, "侘寂", "客厅", ds_root=self.ds_root)
        self.assertFalse(r.get("error"), f"数据根下的图片没被认出来:{r}")

    def test_f2_an_image_left_in_the_install_dir_is_not_the_supported_home(self):
        """反面:安装目录里的图片不该被当成图库正主(它会被卸载删掉)。"""
        refs = os.path.join(self.ds_root, "refs")
        os.makedirs(refs, exist_ok=True)
        img = os.path.join(refs, "放错地方的.png")
        with open(img, "wb") as fh:
            fh.write(b"PNG")
        ds_refs.add_style("侘寂", ds_root=self.ds_root)
        r = ds_refs.add_ref(img, "侘寂", "客厅", ds_root=self.ds_root)
        self.assertTrue(r.get("error"), "安装目录里的图片被当成图库正主收下了")


class TestLegacyMigration(Rig):
    """G 组:已经产生过数据的机器,升级之后不许"看起来数据没了"。"""

    def test_g1_legacy_data_moves_into_the_data_root(self):
        ds_common.migrate_legacy_data(self.ds_root)
        self.assertTrue(os.path.isfile(os.path.join(self.data_root, "projects", "老项目-1801.md")),
                        "遗留档案没搬过来")

    def test_g2_never_overwrites_something_already_there(self):
        p = os.path.join(self.data_root, "projects", "老项目-1801.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("新的,别覆盖我\n")
        ds_common.migrate_legacy_data(self.ds_root)
        with open(p, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "新的,别覆盖我\n", "同名文件被覆盖了")

    def test_g3_an_unknown_kind_is_reported_not_silently_left_behind(self):
        """canary(B 卷):清单里没有的东西,不许被无声当成代码丢下。"""
        p = os.path.join(self.ds_root, "future-kind", "canary.bin")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b"canary")
        r = ds_common.migrate_legacy_data(self.ds_root)
        self.assertIn("future-kind/canary.bin",
                      json.dumps(r, ensure_ascii=False).replace("\\\\", "/"),
                      f"没认识的东西被无声吞了:{r}")


class TestStaticGate(unittest.TestCase):
    """H 组:静态闸 —— 兜住"写口没跑到"那种漏网(骗法一)。

    实扫依据(2026-08-15):`bin/*.py` 里 `os.path.join(<…ds_root…>, …)` 共 47 处、
    11 个文件,**47 处全是数据**;`ds_root` 唯一的代码用途在 `ds_provision.py`。
    ⇒ 规则:数据一律走 `data_root(ds_root)`,`join(ds_root, …)` 一处都不该再有。
    """

    ALLOW = {"ds_provision.py"}   # 装机脚本读的是模板与 ds_merge_config.py,那是代码

    def test_h1_no_module_joins_data_paths_onto_ds_root(self):
        import re
        pat = re.compile(r'os\.path\.join\(\s*(?:self\.server\.)?ds_root\s*,')
        offenders = []
        for fn in sorted(os.listdir(os.path.join(ROOT, "bin"))):
            if not fn.endswith(".py") or fn in self.ALLOW:
                continue
            path = os.path.join(ROOT, "bin", fn)
            with open(path, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if pat.search(line):
                        offenders.append(f"{fn}:{i}")
        self.assertEqual(offenders, [],
                         "这些地方还把业主的东西往安装目录里拼(应走 data_root):\n  "
                         + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
