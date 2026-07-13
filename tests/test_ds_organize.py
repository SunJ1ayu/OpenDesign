#!/usr/bin/env python3
"""ds_organize 核心的 oracle 矩阵 — 对齐 track opendesign-file-organizer design.md。

跑法:  python3 tests/test_ds_organize.py
不需要 nanobot / mcp SDK / 网络 —— 只测纯 Python 核心(+ ds-approve CLI 冒烟)。

铁律:LLM 只能 scan/stage/apply;`.approved` 标记只能由人(ds-approve)创建;
MVP 原语只有 move/rename(delete 已被用户砍掉,必须被拒)。
"""
import json
import os
import subprocess
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # design-studio/
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_organize  # noqa: E402


def _write(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _tree(root):
    """整棵树的 (相对路径, 是否目录, 内容) 快照,用来断言"零改动"。"""
    snap = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            snap.add((os.path.relpath(os.path.join(dirpath, d), root), "dir", ""))
        for f in filenames:
            p = os.path.join(dirpath, f)
            with open(p, encoding="utf-8") as fh:
                snap.add((os.path.relpath(p, root), "file", fh.read()))
    return snap


class OrganizeOracle(unittest.TestCase):
    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsorg-ds-")      # ds_root:plans/audit 落这
        self.root = tempfile.mkdtemp(prefix="dsorg-root-")  # 被整理的根
        self.other = tempfile.mkdtemp(prefix="dsorg-out-")  # 白名单外
        self.allowed = [self.root]
        _write(os.path.join(self.root, "a.txt"), "AAA")
        _write(os.path.join(self.root, "b.txt"), "BBB")
        _write(os.path.join(self.root, "sub", "c.txt"), "CCC")

    def tearDown(self):
        for d in (self.ds, self.root, self.other):
            shutil.rmtree(d, ignore_errors=True)

    # ── helpers ──────────────────────────────────────────────────────────
    def _stage(self, ops, root=None):
        return ds_organize.stage_plan(root or self.root, ops,
                                      allowed_roots=self.allowed, ds_root=self.ds)

    def _apply(self, plan_id):
        return ds_organize.apply_plan(plan_id, allowed_roots=self.allowed,
                                      ds_root=self.ds)

    def _plans_dir_files(self):
        d = os.path.join(self.ds, "organize", "plans")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    # ① scan 正常 + 白名单
    def test_01_scan(self):
        r = ds_organize.scan_dir(self.root, allowed_roots=self.allowed)
        self.assertTrue(r["ok"])
        paths = {e["path"]: e["type"] for e in r["entries"]}
        self.assertEqual(paths.get("a.txt"), "file")
        self.assertEqual(paths.get("sub"), "dir")
        self.assertEqual(paths.get(os.path.join("sub", "c.txt")), "file")
        self.assertFalse(r["truncated"])

    def test_02_scan_root_not_allowed(self):
        r = ds_organize.scan_dir(self.other, allowed_roots=self.allowed)
        self.assertEqual(r.get("error"), "root_not_allowed")
        # root 里带 ../ 逃出白名单也不行
        r2 = ds_organize.scan_dir(os.path.join(self.root, ".."),
                                  allowed_roots=self.allowed)
        self.assertEqual(r2.get("error"), "root_not_allowed")
        # 白名单为空 = 默认关死
        r3 = ds_organize.scan_dir(self.root, allowed_roots=[])
        self.assertEqual(r3.get("error"), "root_not_allowed")

    # ② stage:src/dst 路径逃逸
    def test_03_stage_path_escape(self):
        before = _tree(self.root)
        for ops in (
            [{"op": "move", "src": "../escape.txt", "dst": "x.txt"}],
            [{"op": "move", "src": "a.txt", "dst": "../pwn.txt"}],
            [{"op": "move", "src": "a.txt", "dst": "/tmp/pwn.txt"}],
        ):
            r = self._stage(ops)
            self.assertEqual(r.get("error"), "path_escape", msg=str(ops))
        self.assertEqual(_tree(self.root), before)
        self.assertEqual(self._plans_dir_files(), [])  # 失败不留 plan 文件

    # ③ stage:不覆盖 + op 间冲突
    def test_04_stage_overwrite_and_conflicts(self):
        # dst 已存在
        r = self._stage([{"op": "move", "src": "a.txt", "dst": "b.txt"}])
        self.assertEqual(r.get("error"), "would_overwrite")
        # 两 op 同 dst
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": "x.txt"},
            {"op": "move", "src": "b.txt", "dst": "x.txt"},
        ])
        self.assertEqual(r.get("error"), "conflict")
        # 同一 src 动两次
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": "x.txt"},
            {"op": "move", "src": "a.txt", "dst": "y.txt"},
        ])
        self.assertEqual(r.get("error"), "conflict")
        # dst 撞另一 op 的 src(链式,与执行顺序相关 → 拒)
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": "b2.txt"},
            {"op": "move", "src": "b2.txt", "dst": "c2.txt"},
        ])
        self.assertEqual(r.get("error"), "conflict")

    # ④ delete / 未知 op 一律拒(MVP 用户拍板砍 delete)
    def test_05_op_not_allowed(self):
        before = _tree(self.root)
        for op in ("delete", "remove", "trash", "chmod", ""):
            r = self._stage([{"op": op, "src": "a.txt", "dst": "x.txt"}])
            self.assertEqual(r.get("error"), "op_not_allowed", msg=op)
        self.assertEqual(_tree(self.root), before)
        # 空 plan 也不行
        r = self._stage([])
        self.assertEqual(r.get("error"), "empty_plan")

    # ⑤ stage 成功 = 零文件系统改动 + plan 落盘带快照
    def test_06_stage_ok_zero_changes(self):
        before = _tree(self.root)
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": os.path.join("docs", "a.txt")},
            {"op": "rename", "src": "b.txt", "dst": "b-final.txt"},
        ])
        self.assertTrue(r.get("ok"), msg=str(r))
        self.assertIn("plan_id", r)
        self.assertIn("a.txt", r["summary"])   # 给人看的清单
        self.assertEqual(_tree(self.root), before)  # root 零改动
        plan_path = os.path.join(self.ds, "organize", "plans",
                                 f"plan_{r['plan_id']}.json")
        self.assertTrue(os.path.exists(plan_path))
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        for op in plan["operations"]:
            self.assertIn("size", op["snapshot"])
            self.assertIn("mtime_ns", op["snapshot"])

    # ⑥ 未批准 → 物理执行不了
    def test_07_apply_not_approved(self):
        r = self._stage([{"op": "move", "src": "a.txt", "dst": "x.txt"}])
        before = _tree(self.root)
        r2 = self._apply(r["plan_id"])
        self.assertEqual(r2.get("error"), "not_approved")
        self.assertEqual(_tree(self.root), before)

    # ⑦ 批准 → 精确执行 + 子目录自动建 + audit
    def test_08_approve_then_apply(self):
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": os.path.join("docs", "2026", "a.txt")},
            {"op": "rename", "src": "b.txt", "dst": "b-final.txt"},
        ])
        ra = ds_organize.approve_plan(r["plan_id"], ds_root=self.ds)
        self.assertTrue(ra.get("ok"), msg=str(ra))
        r2 = self._apply(r["plan_id"])
        self.assertTrue(r2.get("ok"), msg=str(r2))
        self.assertFalse(os.path.exists(os.path.join(self.root, "a.txt")))
        with open(os.path.join(self.root, "docs", "2026", "a.txt")) as fh:
            self.assertEqual(fh.read(), "AAA")
        self.assertTrue(os.path.exists(os.path.join(self.root, "b-final.txt")))
        audit = os.path.join(self.ds, "organize", "audit.log")
        self.assertTrue(os.path.exists(audit))
        with open(audit, encoding="utf-8") as fh:
            log = fh.read()
        self.assertIn(r["plan_id"], log)
        self.assertIn("a.txt", log)

    # ⑧ 漂移:stage 后 src 变了 → 整体中止零执行
    def test_09_drift_aborts_whole_plan(self):
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": "x.txt"},
            {"op": "move", "src": "b.txt", "dst": "y.txt"},
        ])
        ds_organize.approve_plan(r["plan_id"], ds_root=self.ds)
        _write(os.path.join(self.root, "b.txt"), "BBB-changed-longer")  # 只漂移 b
        before = _tree(self.root)
        r2 = self._apply(r["plan_id"])
        self.assertEqual(r2.get("error"), "plan_drift")
        self.assertEqual(_tree(self.root), before)  # a 也没动 → 零执行

    # ⑨ apply 时 src 没了 / dst 被占 → 整体中止
    def test_10_apply_revalidates(self):
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": "x.txt"},
            {"op": "move", "src": "b.txt", "dst": "y.txt"},
        ])
        ds_organize.approve_plan(r["plan_id"], ds_root=self.ds)
        os.remove(os.path.join(self.root, "a.txt"))
        before = _tree(self.root)
        r2 = self._apply(r["plan_id"])
        self.assertIn(r2.get("error"), ("src_missing", "plan_drift"))
        self.assertEqual(_tree(self.root), before)
        # dst 被占
        r3 = self._stage([{"op": "move", "src": "b.txt", "dst": "z.txt"}])
        ds_organize.approve_plan(r3["plan_id"], ds_root=self.ds)
        _write(os.path.join(self.root, "z.txt"), "squatter")
        before = _tree(self.root)
        r4 = self._apply(r3["plan_id"])
        self.assertEqual(r4.get("error"), "would_overwrite")
        self.assertEqual(_tree(self.root), before)

    # ⑩ 不可二次 apply
    def test_11_no_double_apply(self):
        r = self._stage([{"op": "move", "src": "a.txt", "dst": "x.txt"}])
        ds_organize.approve_plan(r["plan_id"], ds_root=self.ds)
        self.assertTrue(self._apply(r["plan_id"]).get("ok"))
        before = _tree(self.root)
        r2 = self._apply(r["plan_id"])
        self.assertEqual(r2.get("error"), "already_applied")
        self.assertEqual(_tree(self.root), before)

    # ⑪ 批准只对单个 plan 生效
    def test_12_approval_not_transferable(self):
        ra = self._stage([{"op": "move", "src": "a.txt", "dst": "xa.txt"}])
        rb = self._stage([{"op": "move", "src": "b.txt", "dst": "xb.txt"}])
        ds_organize.approve_plan(ra["plan_id"], ds_root=self.ds)
        r2 = self._apply(rb["plan_id"])
        self.assertEqual(r2.get("error"), "not_approved")
        self.assertTrue(self._apply(ra["plan_id"]).get("ok"))

    # ⑫ plan_id 本身不可用于路径逃逸
    def test_13_bad_plan_id(self):
        for pid in ("../../etc/passwd", "a/b", "x" * 200, "", "плн"):
            r = self._apply(pid)
            self.assertEqual(r.get("error"), "bad_plan_id", msg=pid)
            r2 = ds_organize.approve_plan(pid, ds_root=self.ds)
            self.assertEqual(r2.get("error"), "bad_plan_id", msg=pid)
        # 格式合法但不存在
        r3 = self._apply("20990101-000000-abcdef")
        self.assertEqual(r3.get("error"), "plan_not_found")

    # ⑬ ds-approve CLI 冒烟(人工闸的真实入口)
    def test_14_ds_approve_cli(self):
        r = self._stage([{"op": "move", "src": "a.txt", "dst": "x.txt"}])
        cli = os.path.join(ROOT, "bin", "ds-approve")
        env = dict(os.environ, DS_ROOT=self.ds)
        proc = subprocess.run([sys.executable, cli, r["plan_id"]],
                              capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("a.txt", proc.stdout)  # 打印工具渲染的清单,不经模型转述
        marker = os.path.join(self.ds, "organize", "plans",
                              f"plan_{r['plan_id']}.approved")
        self.assertTrue(os.path.exists(marker))
        self.assertTrue(self._apply(r["plan_id"]).get("ok"))

    # ⑮ 指向 root 外的符号链接当 src → 拒(realpath 逃逸);panel 补的缺口
    def test_16_symlink_out_rejected(self):
        outside = os.path.join(self.other, "secret.txt")
        _write(outside, "SECRET")
        os.symlink(outside, os.path.join(self.root, "link.txt"))
        r = self._stage([{"op": "move", "src": "link.txt", "dst": "x.txt"}])
        self.assertEqual(r.get("error"), "path_escape")

    # ⑯ dst 中间组件是文件 → stage 就拒(否则 apply 中途 makedirs 炸出部分执行);GLM 抓的
    def test_17_dst_parent_is_file(self):
        r = self._stage([{"op": "move", "src": "a.txt",
                          "dst": os.path.join("b.txt", "inner", "a.txt")}])
        self.assertEqual(r.get("error"), "dst_parent_not_dir")

    # ⑰ 重复 approve 幂等
    def test_18_approve_idempotent(self):
        r = self._stage([{"op": "move", "src": "a.txt", "dst": "x.txt"}])
        self.assertTrue(ds_organize.approve_plan(r["plan_id"], ds_root=self.ds).get("ok"))
        self.assertTrue(ds_organize.approve_plan(r["plan_id"], ds_root=self.ds).get("ok"))
        self.assertTrue(self._apply(r["plan_id"]).get("ok"))

    # ⑭ MCP 包装冒烟:恰好暴露 3 个工具,没有任何"批准"工具(venv 有 mcp 才跑)
    def test_15_mcp_surface(self):
        try:
            import asyncio
            server = ds_organize._build_server(self.ds, self.allowed)
        except ImportError:
            self.skipTest("mcp not installed")
        tools = asyncio.run(server.list_tools())
        names = {t.name for t in tools}
        self.assertEqual(len(names), 3)
        for n in names:
            self.assertNotIn("approve", n)


class HardeningOracle(unittest.TestCase):
    """2026-07-03 全库盲评 #4/#5/#18 后落的加固 oracle。"""

    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsorg-ds-")
        self.root = tempfile.mkdtemp(prefix="dsorg-root-")
        self.allowed = [self.root]
        _write(os.path.join(self.root, "a.txt"), "AAA")
        _write(os.path.join(self.root, "b.txt"), "BBB")

    def tearDown(self):
        for d in (self.ds, self.root):
            shutil.rmtree(d, ignore_errors=True)

    def _stage(self, ops, root=None, allowed=None):
        return ds_organize.stage_plan(root or self.root, ops,
                                      allowed_roots=allowed or self.allowed,
                                      ds_root=self.ds)

    # ㉑ 仅大小写不同的 dst 在 stage 即拒:大小写不敏感 FS 上那是执行中途才会
    #    撞破的碰撞(部分执行,违反"任一失败零执行")
    def test_21_case_collision_rejected_at_stage(self):
        r = self._stage([
            {"op": "move", "src": "a.txt", "dst": "docs/X.TXT"},
            {"op": "move", "src": "b.txt", "dst": "docs/x.txt"},
        ])
        self.assertEqual(r.get("error"), "conflict", msg=str(r))
        self.assertEqual(self._plans_files(), [])  # 零暂存

    def _plans_files(self):
        d = os.path.join(self.ds, "organize", "plans")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    # ㉒ apply 时白名单已收窄 → root_not_allowed,树零改动(代码在但此前没锁)
    def test_22_apply_rechecks_whitelist(self):
        r = self._stage([{"op": "move", "src": "a.txt", "dst": "sub/a.txt"}])
        self.assertTrue(r.get("ok"), msg=str(r))
        ds_organize.approve_plan(r["plan_id"], ds_root=self.ds)
        before = _tree(self.root)
        ra = ds_organize.apply_plan(r["plan_id"], allowed_roots=[],
                                    ds_root=self.ds)
        self.assertEqual(ra.get("error"), "root_not_allowed")
        self.assertEqual(_tree(self.root), before)

    # ㉔ R2-L5(07-13 盲评):apply 复验必须重跑嵌套检查。stage 有 nested_paths 闸,
    #    但 apply 复验漏了它 → 伪造一个嵌套 plan(直接写 plans/ + .approved)可部分执行:
    #    op1 把 D→E 落盘后,op2 的 src D/x 已不存在 → apply_failed 但 executed 带残留。
    #    docstring 自称"plan 文件不作免检信任",这条让它成真。
    def test_24_apply_rechecks_nested_paths(self):
        import json
        root_real = os.path.realpath(self.root)
        os.makedirs(os.path.join(root_real, "D"))
        _write(os.path.join(root_real, "D", "x.txt"), "X")
        ops = [
            {"op": "move", "src_rel": "D", "dst_rel": "E",
             "src": os.path.join(root_real, "D"), "dst": os.path.join(root_real, "E"),
             "snapshot": ds_organize._snapshot(os.path.join(root_real, "D"))},
            {"op": "move", "src_rel": "D/x.txt", "dst_rel": "y.txt",
             "src": os.path.join(root_real, "D", "x.txt"),
             "dst": os.path.join(root_real, "y.txt"),
             "snapshot": ds_organize._snapshot(os.path.join(root_real, "D", "x.txt"))},
        ]
        pid = "20260713-000000-abcdef"
        plans = os.path.join(self.ds, "organize", "plans")
        os.makedirs(plans, exist_ok=True)
        with open(os.path.join(plans, f"plan_{pid}.json"), "w", encoding="utf-8") as fh:
            json.dump({"plan_id": pid, "root": root_real, "created": "x",
                       "operations": ops, "summary": "s", "applied_at": None}, fh)
        with open(os.path.join(plans, f"plan_{pid}.approved"), "w") as fh:
            fh.write("x\n")
        before = _tree(self.root)
        r = ds_organize.apply_plan(pid, allowed_roots=self.allowed, ds_root=self.ds)
        self.assertEqual(r.get("error"), "conflict")
        self.assertEqual(r.get("detail"), "nested_paths")
        self.assertNotIn("executed", r)          # 零执行
        self.assertEqual(_tree(self.root), before)  # 树原封不动

    # ㉓ organize/ 子树(批准机关自身)硬排除:即使 ds_root 被圈进白名单,
    #    plans/.approved/audit.log 也不能成为整理对象
    def test_23_organize_area_protected(self):
        _write(os.path.join(self.ds, "organize", "plans", "老plan.json"), "{}")
        _write(os.path.join(self.ds, "散文件.txt"), "x")
        allowed = [self.ds]
        r = self._stage([{"op": "move", "src": "organize/plans/老plan.json",
                          "dst": "别处.json"}], root=self.ds, allowed=allowed)
        self.assertEqual(r.get("error"), "path_escape", msg=str(r))
        # 反向:把普通文件搬进 organize/ 也不行
        r2 = self._stage([{"op": "move", "src": "散文件.txt",
                           "dst": "organize/藏起来.txt"}], root=self.ds, allowed=allowed)
        self.assertEqual(r2.get("error"), "path_escape", msg=str(r2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
