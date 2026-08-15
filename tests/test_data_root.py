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
        # ⚠️ 默认是"要点确认"(MODE_ASK)⇒ set_workspace 只落一份 pending,
        #    `config/workspace.json` 根本不会被写。先切 ALLOW 才真的走到那个写口。
        #    (这是 b3 替我抓出来的:第一版 exercise_writes 从没碰过 workspace.json。)
        ds_consent.set_mode(self.ds_root, ds_consent.MODE_ALLOW)
        ds_tools.set_workspace(self.workdir(), ds_root=self.ds_root)
        ds_refs.add_style("侘寂", ds_root=self.ds_root)
        ds_consent.set_mode(self.ds_root, ds_consent.MODE_ASK)   # 位置参数,别写成 kwarg
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
        """双向验:上面那条不能靠"什么都没写"过关。

        ⚠️ 第一版只问"有没有一个 projects 文件" —— 攻题腿点破:
        `append_change` / `log_communication` / `set_stage` / `delete_project`
        全都返回 `{"ok": True}` 但不落盘,a2/a3/b3 照样绿,而**业主的变更记录静默全丢**。
        ⇒ 这条现在读内容,不只数文件。
        """
        self.exercise_writes()
        landed = tree_hash(self.data_root)
        self.assertTrue(any(k.startswith("projects") for k in landed),
                        f"数据根里没有档案,那 a2 的绿是假的:{sorted(landed)}")
        doc = open(os.path.join(self.data_root, "projects", "星河名邸-2302.md"),
                   encoding="utf-8").read()
        self.assertIn("客厅改推拉门", doc, "变更记录空转了(写口返回 ok 但没落盘)")
        self.assertIn("太太确认", doc, "沟通日志空转了")
        self.assertIn("方案深化", doc, "阶段没写进去")
        self.assertTrue(os.path.isdir(os.path.join(self.data_root, "projects", ".trash")),
                        "删除项目没走数据根下的回收站")


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

    def test_b3_without_env_the_whole_shape_is_unchanged(self):
        """🔴 我自攻 M7:b2 只看一个文件 —— 实现要是把落点统一成 `ds_root/data/…`,
        b2 照样绿,而 git-pull 那两台机器的档案**原地失踪**(它们的档案就在仓库工作树里)。
        这一条比的是**整棵树的形状**:每一样东西都必须还在它原来的相对位置。"""
        os.environ.pop(ENV_VAR, None)
        self.exercise_writes()
        must_exist = [
            os.path.join("projects", "星河名邸-2302.md"),
            os.path.join("clients", "王五.md"),
            os.path.join("config", "workspace.json"),
            os.path.join("config", "consent.json"),
            "refs-vocab.md",
        ]
        missing = [r for r in must_exist if not os.path.exists(os.path.join(self.ds_root, r))]
        self.assertEqual(missing, [], f"没设 env 时这些东西离开了原位(git-pull 那两台会失踪):{missing}")


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


    def test_c3_a_bogus_env_does_not_end_up_writing_into_the_install_dir(self):
        """🔴 我自攻 M5:c1/c2 只问 `data_root()` 自己抛不抛错 —— 调用方一句
        `except Exception: root = ds_root` 就把 fail closed 拆了,而那两条仍然绿。
        这一条问的是**端到端的事实**:env 坏掉时,业主的东西不许落进安装目录。"""
        bogus = os.path.join(self.tmp, "我是个文件3")
        with open(bogus, "w", encoding="utf-8") as fh:
            fh.write("x")
        os.environ[ENV_VAR] = bogus
        before = tree_hash(self.ds_root)
        try:
            ds_tools.create_project("坏env-项目", ds_root=self.ds_root)
        except Exception:
            pass                        # 炸掉是可以接受的结果;悄悄写进安装目录不是
        after = tree_hash(self.ds_root)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        self.assertEqual(changed, [], f"数据根坏掉时回退写进了安装目录:{changed}")


    def test_c4_env_pointing_inside_the_install_dir_is_refused(self):
        """攻题腿第 4 条:c1~c3 都拿**一个文件**当坏 env。若 `DS_DATA_ROOT` 被设成
        安装目录里的一个**合法目录**,按"是不是目录"的契约它照收 ⇒ 数据写回安装目录、卸载删。
        数据根的定义里就该有"必须在安装目录之外"。"""
        inside = os.path.join(self.ds_root, "data")
        os.makedirs(inside, exist_ok=True)
        os.environ[ENV_VAR] = inside
        with self.assertRaises(ds_common.DataRootError):
            ds_common.data_root(self.ds_root)

    def test_c6_in_a_real_install_the_whole_install_dir_is_off_limits(self):
        """c4 拦的是"数据根在 ds/ 里面"。真正的危险区比那大一圈:卸载删的是**整个
        $INSTDIR**(ds/ 只是它的一个子目录)⇒ `$INSTDIR\\Data` 这种同级位置也得拦。

        ⚠️ 但"上一级就是安装目录"只在**装出来的形态**下成立;开发仓 / 考卷台架里
        上一级是个无辜目录,拦它就是误报 —— 而误报会让两条真联跑考卷莫名其妙地红
        (2026-08-15 实测:第一版就是这么把 test_ds_shell_core 的 g1/g2 打红的)。
        ⇒ 认**装出来的标志**(启动器 exe 与包内 python 在 ds/ 的同级)。
        """
        with open(os.path.join(self.install, "OpenDesign.exe"), "w", encoding="utf-8") as fh:
            fh.write("MZ")                      # 装出来的形态才有这个
        sibling = os.path.join(self.install, "Data")
        os.makedirs(sibling, exist_ok=True)
        os.environ[ENV_VAR] = sibling
        with self.assertRaises(ds_common.DataRootError):
            ds_common.data_root(self.ds_root)

    def test_c7_a_dev_checkout_does_not_get_false_alarms(self):
        """双向验:没有"装出来的标志"时,ds_root 的同级目录是无辜的,不许拦。"""
        sibling = os.path.join(self.install, "Data")   # 此时 install 下没有 OpenDesign.exe
        os.makedirs(sibling, exist_ok=True)
        os.environ[ENV_VAR] = sibling
        self.assertEqual(os.path.realpath(ds_common.data_root(self.ds_root)),
                         os.path.realpath(sibling))

    def test_c5_an_empty_env_value_is_not_treated_as_unset(self):
        """攻题腿第 5 条 —— **"缺席被当成通过"家族的第四个**,我请它专门找的就是这个。

        `os.environ.get(K) or ds_root` 这种懒写法把空串当"没设",于是子进程静默
        退回写安装目录。空串是**设错了**,不是没设 ⇒ 必须 fail closed。
        """
        os.environ[ENV_VAR] = ""
        with self.assertRaises(ds_common.DataRootError):
            ds_common.data_root(self.ds_root)


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

    def test_f3_the_index_lands_next_to_the_images(self):
        """🔴 我自攻 M3:只把 `refs_base` 搬走就能让 f1 绿,而 `refs-index.md`
        仍写安装目录 ⇒ 卸载后**图还在、索引没了**,业主看到的是"图库全空"。"""
        refs = os.path.join(self.data_root, "refs")
        os.makedirs(refs, exist_ok=True)
        img = os.path.join(refs, "带索引的.png")
        with open(img, "wb") as fh:
            fh.write(b"PNG")
        ds_refs.add_style("侘寂", ds_root=self.ds_root)
        ds_refs.add_ref(img, "侘寂", "客厅", ds_root=self.ds_root)
        self.assertTrue(os.path.isfile(os.path.join(self.data_root, "refs-index.md")),
                        "图片搬走了,索引还留在安装目录")

    def test_f4_a_hand_edited_taxonomy_is_read_from_the_data_root(self):
        """攻题腿第 7 条:本文件开头点名了 `config/taxonomy.json` 是"只读的用户数据",
        F 组却只测了 refs。`ds_taxonomy.load_taxonomy` 若仍从安装目录读用户表,
        业主手工改的分类规则卸载即失。"""
        import ds_taxonomy
        cfg = os.path.join(self.data_root, "config")
        os.makedirs(cfg, exist_ok=True)
        overlay = {"categories": [{"id": "我自己加的类目", "scope": "workspace",
                                   "dir": "09-我的", "extensions": [".xyz"], "mode": "auto"}]}
        with open(os.path.join(cfg, "taxonomy.json"), "w", encoding="utf-8") as fh:
            json.dump(overlay, fh, ensure_ascii=False)
        got = json.dumps(ds_taxonomy.load_taxonomy(self.ds_root), ensure_ascii=False)
        self.assertIn("我自己加的类目", got, "业主手工放在数据根的分类表没被读到")

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
        """⚠️ 第一版只断言 `projects/老项目-1801.md` 一个文件 —— 攻题腿点破:
        实现只搬 projects 一种,`refs/老图.png`、`index.md` 全留在安装目录,
        g1/g2/g3 照样全绿而卸载把它们删光。**迁移的完整性必须逐条问。**"""
        ds_common.migrate_legacy_data(self.ds_root)
        for rel in (os.path.join("projects", "老项目-1801.md"),
                    os.path.join("refs", "老图.png"),
                    "index.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.data_root, rel)),
                            f"遗留数据没搬过来:{rel}(卸载会删掉它)")

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

    def test_g4_the_unknown_report_is_not_drowned_in_code(self):
        """🔴 闸③ 亲读实现时实测出来的:`unknown` 把**每一个代码文件**都报进去了
        (bin/*.py、web/dist/**、assets/、workspace/SOUL.md、版本号.txt……)。
        真安装包里那是几千条 ⇒ canary 淹在噪音里,等于"报了但没人看"
        (攻题腿点名的同一个形状)。**一份谁都不会读的报告不算报告。**"""
        for rel in ("bin/ds_web.py", "web/dist/index.html", "assets/图标.png",
                    "workspace/SOUL.md", "版本号.txt"):
            p = os.path.join(self.ds_root, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("x")
        canary = os.path.join(self.ds_root, "future-kind", "canary.bin")
        os.makedirs(os.path.dirname(canary), exist_ok=True)
        with open(canary, "wb") as fh:
            fh.write(b"canary")

        unknown = ds_common.migrate_legacy_data(self.ds_root).get("unknown", [])
        noise = [u for u in unknown
                 if u.split("/")[0] in {"bin", "web", "assets", "workspace"}
                 or u == "版本号.txt" or u.startswith("config/nanobot.config")]
        self.assertEqual(noise, [], f"代码文件被报成「没认识的数据」,canary 会被淹掉:{noise[:8]}")
        self.assertTrue(any("canary.bin" in u for u in unknown),
                        f"噪音清掉之后 canary 也没了:{unknown}")


class TestStaticGate(unittest.TestCase):
    """H 组:静态闸 —— 兜住"写口没跑到"那种漏网(骗法一)。

    实扫依据(2026-08-15):`bin/*.py` 里 `os.path.join(<…ds_root…>, …)` 共 47 处、
    11 个文件,**47 处全是数据**;`ds_root` 唯一的代码用途在 `ds_provision.py`。
    ⇒ 规则:数据一律走 `data_root(ds_root)`,`join(ds_root, …)` 一处都不该再有。

    🔴 **走 AST 不走正则**(我自攻 M2:第一版只认 `os.path.join(ds_root,` 这一种写法,
    而 `root = ds_root` 后再 join、`Path(ds_root) / "projects"`、`join(ds_root, *parts)`
    全能绕过 —— 而且这些都不是使坏,是自然写法)。
    """

    ALLOW = {"ds_provision.py"}   # 装机脚本读的是模板与 ds_merge_config.py,那是代码

    @staticmethod
    def _is_ds_root(node, aliases):
        """认得出"这个表达式就是安装目录"。

        攻题腿(subdeepseek)指出第一版只认 Name/Attribute,以下全漏:
        `os.sep.join([ds_root, …])`(第一个参数是 List)、`f"{ds_root}/projects"`、
        `open(f"{ds_root}/x.md","w")`。⇒ 这里认 List/Tuple 的元素和 f-string 的插值。
        """
        import ast
        if isinstance(node, ast.Name):
            return node.id == "ds_root" or node.id in aliases
        if isinstance(node, ast.Attribute):
            return node.attr == "ds_root"
        if isinstance(node, (ast.List, ast.Tuple)):
            return any(TestStaticGate._is_ds_root(e, aliases) for e in node.elts)
        if isinstance(node, ast.Starred):
            return TestStaticGate._is_ds_root(node.value, aliases)
        if isinstance(node, ast.JoinedStr):        # f"{ds_root}/projects"
            return any(TestStaticGate._is_ds_root(v.value, aliases)
                       for v in node.values if isinstance(v, ast.FormattedValue))
        return False

    def test_h1_no_module_builds_data_paths_on_ds_root(self):
        import ast
        offenders = []
        for fn in sorted(os.listdir(os.path.join(ROOT, "bin"))):
            if not fn.endswith(".py") or fn in self.ALLOW:
                continue
            path = os.path.join(ROOT, "bin", fn)
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src, filename=fn)

            # 别名:`root = ds_root` 之后 root 也算(M2);函数默认参数同理(攻题腿补的)
            aliases = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                        and isinstance(n.targets[0], ast.Name) \
                        and isinstance(n.value, ast.Name) and n.value.id == "ds_root":
                    aliases.add(n.targets[0].id)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = n.args
                    for a, d in zip(args.args[-len(args.defaults):] if args.defaults else [],
                                    args.defaults):
                        if isinstance(d, ast.Name) and d.id == "ds_root":
                            aliases.add(a.arg)

            for n in ast.walk(tree):
                # os.path.join(ds_root, …) / os.sep.join([ds_root, …]) / Path(ds_root)
                if isinstance(n, ast.Call):
                    f = n.func
                    joinish = (isinstance(f, ast.Attribute) and f.attr == "join") or \
                              (isinstance(f, ast.Name) and f.id == "Path")
                    if joinish and n.args and self._is_ds_root(n.args[0], aliases):
                        offenders.append(f"{fn}:{n.lineno}")
                    # open(f"{ds_root}/x.md", "w") —— 连 join 都不经过
                    if isinstance(f, ast.Name) and f.id == "open" and n.args \
                            and self._is_ds_root(n.args[0], aliases):
                        offenders.append(f"{fn}:{n.lineno}")
                # ds_root / "projects"
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) \
                        and self._is_ds_root(n.left, aliases):
                    offenders.append(f"{fn}:{n.lineno}")
                # f"{ds_root}/…" 直接当路径用(赋值右边就算)
                if isinstance(n, ast.JoinedStr) and self._is_ds_root(n, aliases):
                    offenders.append(f"{fn}:{n.lineno}")
        self.assertEqual(sorted(set(offenders)), [],
                         "这些地方还把业主的东西往安装目录里拼(应走 data_root):\n  "
                         + "\n  ".join(sorted(set(offenders))))

    def test_h2_migration_is_actually_called_not_just_mentioned(self):
        """🔴 我自攻 M1 + 攻题腿的第 1 条:G 组**直接调**迁移函数 ——
        实现只要把函数写出来就全绿,而真机上没有任何启动路径叫它。

        ⚠️ 第一版这条查的是**字符串出现**,攻题腿当场点破:在 `ds_shell.py` 里加一句
        注释 `# 记得调 migrate_legacy_data` 就能喂饱它 —— **把门槛从"函数存在"抬到
        "字符串出现",门还是没关上**。现在查 AST 里真的有一次 `Call`。
        """
        import ast
        callers = []
        for fn in ("ds_web.py", "ds_shell.py", "ds_shell_core.py", "ds_mcp.py"):
            path = os.path.join(ROOT, "bin", fn)
            if not os.path.isfile(path):
                continue
            for n in ast.walk(ast.parse(open(path, encoding="utf-8").read(), filename=fn)):
                if isinstance(n, ast.Call):
                    f = n.func
                    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                    if name == "migrate_legacy_data":
                        callers.append(f"{fn}:{n.lineno}")
        self.assertTrue(callers, "没有任何启动路径**真的调用** migrate_legacy_data —— "
                                 "迁移函数写了也白写,G 组那三条绿是假的")

    def test_h3_the_shell_migrates_before_it_starts_anything(self):
        """🔴 主 agent 自审 F1:迁移只挂在 `ds_web.main()` 上,而 `ds_shell.py` 里
        **网关先起、工作台(ds-web)后起**(`ds_shell.py` 的 Service 顺序)。

        ⇒ 装了旧数据的机器上,网关和它的三个 MCP 工具服务会**先**读到一个空数据根;
        业主那一刻问"我有哪些项目",助手回"一个都没有",甚至可能在新根里建一个重名的。
        迁移必须发生在**外壳起任何服务之前** —— 外壳才是装出来那一份的唯一入口。
        """
        import ast
        src = open(os.path.join(ROOT, "bin", "ds_shell.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        migrate_line = start_line = None
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name == "migrate_legacy_data" and migrate_line is None:
                    migrate_line = n.lineno
                if name == "start" and start_line is None:
                    start_line = n.lineno
        self.assertIsNotNone(migrate_line, "外壳自己没有调用 migrate_legacy_data —— "
                                           "网关会先于 ds-web 读到一个空数据根")
        if start_line is not None:
            self.assertLess(migrate_line, start_line,
                            "迁移写在起服务之后了:网关和三个 MCP 仍会先读到空数据根")


if __name__ == "__main__":
    unittest.main(verbosity=2)
