#!/usr/bin/env python3
"""档案写入不留空档案的判据(track opendesign-atomic-archive-write)。

编号的权威表在 `tracks/opendesign-atomic-archive-write/design.md` 的 `## Test strategy (oracle)`。
**这里不重抄语义,只标 id。** 前缀 `aw`:`tests/mutation-*.sh` 按名字选靶子,别和 t*/m*/u* 撞。

🔴 为什么要这份考卷(2026-09-15,应用内更新那一单的切片评审 GPT 腿 #3,我核实):
`ds_common.locked_rw` 是 open(r+) → 锁 → 读 → **truncate** → write。截断之后、写完之前进程被杀
(托盘退出 / 崩溃 / 断电 / 应用内更新收摊),业主的档案就只剩空文件或半截。

**这份考卷此刻应该有红** —— 实现还没改。判据先行单独一笔。

⚠️ 判不了的那一半别假装判得了:Linux 上 `os.replace` 永远成功,**"Windows 上目标被别人开着就换不掉"
本机结构上照不出** ⇒ aw12b 只在 Windows 上跑,由 `.github/workflows/windows-atomic-probe.yml` 真问。
"""
from __future__ import annotations

import errno
import glob
import os
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, BIN)

import ds_common  # noqa: E402
import ds_refs    # noqa: E402
import ds_tools   # noqa: E402

POSIX = os.name != "nt"
FOOTER = "== 档案页脚 END =="


def _child_env():
    env = dict(os.environ)
    env.pop(ds_common.DATA_ROOT_ENV, None)      # 数据根 = 传进去的 ds_root
    env["PYTHONDONTWRITEBYTECODE"] = "1"         # 限了文件大小的子进程里别去写 .pyc
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_child(code, timeout=60, **popen_kw):
    """在子进程里跑一段代码(sys.path 已含 bin/)。"""
    prelude = "import sys, os\nsys.path.insert(0, %r)\n" % BIN
    return subprocess.run([sys.executable, "-c", prelude + code], capture_output=True, text=True,
                          env=_child_env(), timeout=timeout, **popen_kw)


_FSIZE_PRELUDE = """
import errno, resource, signal
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)      # 超限时让 write 返回 EFBIG,而不是被信号杀掉
def limit(n):
    resource.setrlimit(resource.RLIMIT_FSIZE, (n, n))
def report(fn):
    try:
        fn()
    except OSError as exc:
        print("RAISED", exc.errno == errno.EFBIG)
        return
    print("NORAISE")
"""


def _archive_text(n_lines, tag):
    lines = ["# 项目档案 %s" % tag, "", "## 变更记录", ""]
    lines += ["- [已确认] C%d 2026-09-%02d 客户要求把主卧衣柜改成通顶,柜门换成哑光白 %s" % (i, 1 + i % 28, tag)
              for i in range(n_lines)]
    lines += ["", FOOTER]
    return "\n".join(lines)


# 大内容不能塞进 `python -c` 的参数(Argument list too long):先落到仓外临时文件,子进程自己读
_TOGGLE_LOADER = """
import ds_common
with open(%r, encoding="utf-8") as fh:
    A = fh.read().split("\\n")
with open(%r, encoding="utf-8") as fh:
    B = fh.read().split("\\n")
"""


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 与 locked_rw 写回时同一种打开方式(text 模式、utf-8、newline 默认),字节口径才对得上
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _text_bytes(text):
    """text 模式写出去的字节:Windows 上 \\n 会变 \\r\\n(原实现就是这样)。"""
    return text.replace("\n", os.linesep).encode("utf-8")


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.ds = tempfile.mkdtemp(prefix="dsaw-")
        self.addCleanup(shutil.rmtree, self.ds, ignore_errors=True)
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(ds_common.DATA_ROOT_ENV, None)
        self.proj = os.path.join(self.ds, "projects", "翡翠湾-1801.md")
        _write_text(self.proj, _archive_text(20, "旧"))

    def _content_file(self, name, text):
        path = os.path.join(self.ds, "fixture-%s.txt" % name)     # 不在 projects/ 里,不干扰被测目录
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return path

    def assertNoTmpLitter(self, directory):
        litter = [n for n in os.listdir(directory) if n.endswith(".tmp")]
        self.assertEqual(litter, [], "留下了临时文件残骸:%r" % litter)


@unittest.skipUnless(POSIX, "RLIMIT_FSIZE 只有 POSIX 有;Windows 那一半由 aw12 在 Windows 探针上问")
class AMidWriteFailureLeavesTheOldArchive(_Tmp):
    """aw1 / aw3 —— 写到一半出错(盘满 / 被杀在截断之后),原档案逐字节不变,且不留临时文件残骸。"""

    def _grow_in_child(self, path, limit_bytes):
        code = _FSIZE_PRELUDE + """
import ds_common
def go():
    with ds_common.locked_rw(%r) as box:
        box["lines"] = box["lines"][:-1] + ["- 追加的新变更 %%d 客户确认了厨房台面换成岩板" %% i for i in range(400)] + box["lines"][-1:]
limit(%d)
report(go)
""" % (path, limit_bytes)
        return _run_child(code)

    def test_aw1_a_write_that_dies_halfway_leaves_the_old_archive(self):
        before = _bytes(self.proj)
        mtime = os.stat(self.proj).st_mtime_ns
        size = len(before)
        r = self._grow_in_child(self.proj, size + 2048)      # 新内容远大于上限 ⇒ 必在写到一半时失败
        self.assertIn("RAISED True", r.stdout, "故障没注入成功(不是 EFBIG),这条问不到它要问的事:%r %r"
                      % (r.stdout, r.stderr[-500:]))
        after = _bytes(self.proj)
        self.assertEqual(len(after), size, "档案被截成了 %d 字节(原来 %d)" % (len(after), size))
        self.assertEqual(after, before, "写到一半出错之后,档案内容变了")
        self.assertEqual(os.stat(self.proj).st_mtime_ns, mtime, "写失败了,档案的 mtime 却被碰过")

    def test_aw3_no_tmp_litter_after_a_failed_or_a_successful_write(self):
        r = self._grow_in_child(self.proj, len(_bytes(self.proj)) + 2048)
        self.assertIn("RAISED True", r.stdout, r.stderr[-500:])
        self.assertNoTmpLitter(os.path.dirname(self.proj))
        _write_text(self.proj, _archive_text(20, "旧"))      # 档案被没被写坏归 aw1 问;这里只问残骸
        with ds_common.locked_rw(self.proj) as box:
            box["lines"].insert(4, "- 成功的这一次")
        self.assertNoTmpLitter(os.path.dirname(self.proj))


class AWriteThatIsNotWantedTouchesNothing(_Tmp):
    """aw4 —— box["write"] = False ⇒ 文件字节与 mtime 都不变(原语义)。"""

    def test_aw4_write_false_changes_nothing(self):
        before = _bytes(self.proj)
        mtime = os.stat(self.proj).st_mtime_ns
        time.sleep(0.01)
        with ds_common.locked_rw(self.proj) as box:
            box["lines"].append("不该写进去")
            box["write"] = False
        self.assertEqual(_bytes(self.proj), before)
        self.assertEqual(os.stat(self.proj).st_mtime_ns, mtime)


class ARealKillNeverLeavesAHalfArchive(_Tmp):
    """aw2 —— 真的杀进程:每一轮之后档案要么是完整旧内容、要么是完整新内容。

    概率性的回归护栏(对新实现恒绿;对旧实现不保证一定红),红检以 aw1 为准。
    """

    ROUNDS = 12

    def test_aw2_killing_the_writer_at_random_moments(self):
        a = _archive_text(6000, "A")
        b = _archive_text(6000, "B")
        _write_text(self.proj, a)
        want = {_text_bytes(a), _text_bytes(b)}
        code = _TOGGLE_LOADER % (self._content_file("A", a), self._content_file("B", b)) + """
print("ready", flush=True)
while True:
    with ds_common.locked_rw(%r) as box:
        box["lines"] = B if box["lines"][0] == A[0] else A
""" % self.proj
        rng = random.Random(20260915)
        prelude = "import sys, os\nsys.path.insert(0, %r)\n" % BIN
        for i in range(self.ROUNDS):
            p = subprocess.Popen([sys.executable, "-c", prelude + code], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, env=_child_env())
            try:
                self.assertEqual(p.stdout.readline().strip(), "ready")
                time.sleep(rng.uniform(0.005, 0.25))
            finally:
                p.kill()
                p.wait(30)
                p.stdout.close()
            got = _bytes(self.proj)
            self.assertTrue(got in want, "第 %d 轮杀掉写者之后,档案既不是完整旧内容也不是完整新内容(%d 字节)"
                            % (i + 1, len(got)))


class NoLostUpdatesAcrossProcesses(_Tmp):
    """aw5 —— 两个进程各做 N 次"读数字 +1 写回",终值 2N:锁换位置之后仍然互斥。"""

    N = 60

    def test_aw5_two_processes_never_lose_an_increment(self):
        counter = os.path.join(self.ds, "projects", "计数.md")
        _write_text(counter, "0\n" + FOOTER)
        code = """
import ds_common
for _ in range(%d):
    with ds_common.locked_rw(%r) as box:
        box["lines"][0] = str(int(box["lines"][0]) + 1)
""" % (self.N, counter)
        prelude = "import sys, os\nsys.path.insert(0, %r)\n" % BIN
        procs = [subprocess.Popen([sys.executable, "-c", prelude + code], env=_child_env(),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                 for _ in range(2)]
        for p in procs:
            _out, err = p.communicate(timeout=180)
            self.assertEqual(p.returncode, 0, err[-800:])
        with open(counter, encoding="utf-8") as fh:
            first = fh.read().split("\n")[0]
        self.assertEqual(first, str(2 * self.N), "丢了更新:两个进程各 +%d,终值却是 %s" % (self.N, first))


class ReadersAlwaysSeeAWholeArchive(_Tmp):
    """aw6 —— 写者反复改写时,并发的读者每次读到的都是完整文件(带页脚、是 A 或 B 之一)。概率性回归护栏。"""

    def test_aw6_concurrent_reader_never_sees_a_half_file(self):
        a = _archive_text(3000, "A")
        b = _archive_text(3000, "B")
        _write_text(self.proj, a)
        want = {_text_bytes(a), _text_bytes(b)}
        code = _TOGGLE_LOADER % (self._content_file("A", a), self._content_file("B", b)) + """
for _ in range(80):
    with ds_common.locked_rw(%r) as box:
        box["lines"] = B if box["lines"][0] == A[0] else A
""" % self.proj
        prelude = "import sys, os\nsys.path.insert(0, %r)\n" % BIN
        p = subprocess.Popen([sys.executable, "-c", prelude + code], env=_child_env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        bad, reads = [], 0
        try:
            while p.poll() is None:
                try:
                    got = _bytes(self.proj)
                except OSError:
                    continue          # Windows 上替换那一瞬可能打不开:读不到不算读到半截
                reads += 1
                if got not in want:
                    bad.append(len(got))
                # 读者之间留 2ms:真实的读者是偶尔读一次,不是死循环。Windows 上一个死循环开关文件的读者
                # 会让写者的替换一直等不到"没人开着"的空隙 —— 那测的是饥饿,不是这条要问的"读不到半截"。
                time.sleep(0.002)
        finally:
            _out, err = p.communicate(timeout=180)
        self.assertEqual(p.returncode, 0, err[-800:])
        self.assertGreater(reads, 0, "读者一次都没读到 —— 这条没问到东西")
        self.assertEqual(bad, [], "读者读到了 %d 次不完整的档案(字节数样本 %r)" % (len(bad), bad[:5]))


class BytesAndPermissionsStayTheSame(_Tmp):
    """aw7 —— 换行/编码与原实现逐字节一致;权限位原样保留(不被收紧、也不被放宽)。"""

    def test_aw7a_bytes_are_what_text_mode_would_have_written(self):
        with ds_common.locked_rw(self.proj) as box:
            box["lines"].insert(4, "- [待确认] C99 2026-09-15 新加的一条:餐厅吊灯换成三头")
            lines = list(box["lines"])
        got, want = _bytes(self.proj), _text_bytes("\n".join(lines))
        self.assertTrue(got == want, "字节口径变了(%d vs %d 字节)" % (len(got), len(want)))

    @unittest.skipUnless(POSIX, "权限位是 POSIX 语义")
    def test_aw7b_permission_bits_are_kept(self):
        for mode in (0o644, 0o640, 0o600):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.proj, mode)
                with ds_common.locked_rw(self.proj) as box:
                    box["lines"].insert(4, "- 改权限位 %o" % mode)
                self.assertEqual(stat.S_IMODE(os.stat(self.proj).st_mode), mode)


@unittest.skipUnless(POSIX, "Windows 建符号链接要特权")
class SymlinkedArchivesStayLinks(_Tmp):
    """aw8 —— 目标是符号链接 ⇒ 写进真实文件,链接仍是链接。"""

    def test_aw8_the_link_survives_and_the_real_file_changes(self):
        real = os.path.join(self.ds, "elsewhere", "真实档案.md")
        _write_text(real, _archive_text(5, "真"))
        link = os.path.join(self.ds, "projects", "链接档案.md")
        os.symlink(real, link)
        with ds_common.locked_rw(link) as box:
            box["lines"].insert(4, "- 通过链接写的")
        self.assertTrue(os.path.islink(link), "链接被替换成了普通文件")
        with open(real, encoding="utf-8") as fh:
            self.assertIn("- 通过链接写的", fh.read())


@unittest.skipUnless(POSIX, "RLIMIT_FSIZE 只有 POSIX 有")
class TheStyleVocabularyIsWrittenTheSameWay(_Tmp):
    """aw9 —— `ds_refs.add_style` 写到一半出错 ⇒ 风格词表原封不动。"""

    def test_aw9_add_style_dying_halfway_keeps_the_vocabulary(self):
        path = ds_refs._ensure_vocab(self.ds)
        with open(path, "a", encoding="utf-8") as fh:        # 词表做大一点,新写一行必然越过上限
            fh.write("".join("- 旧风格%d\n" % i for i in range(300)))
        before = _bytes(path)
        code = _FSIZE_PRELUDE + """
import ds_refs
limit(%d)
report(lambda: ds_refs.add_style("判据专用风格aw9", %r))
""" % (len(before) - 64, self.ds)
        r = _run_child(code)
        self.assertIn("RAISED True", r.stdout, "故障没注入成功:%r %r" % (r.stdout, r.stderr[-500:]))
        got = _bytes(path)
        self.assertTrue(got == before, "风格词表被写坏了(%d 字节,原来 %d)" % (len(got), len(before)))


@unittest.skipUnless(POSIX, "RLIMIT_FSIZE 只有 POSIX 有")
class RenameProjectRewritesAreAtomicToo(_Tmp):
    """aw10 —— 项目改名改写客户备忘 / index / 档案正文时写到一半出错 ⇒ 这三类文件都不出现空或半截。"""

    def test_aw10_rename_dying_halfway_leaves_every_file_whole(self):
        old, new = "翡翠湾-1801", "翡翠湾-1801改"
        filler = "".join("- 沟通记录 %d:客户在群里确认了瓷砖样板,下周二去现场看\n" % i for i in range(900))
        client = os.path.join(self.ds, "clients", "王先生.md")
        index = os.path.join(self.ds, "index.md")
        _write_text(client, "# 王先生\n\n负责项目 [[%s]]\n\n%s%s" % (old, filler, FOOTER))
        _write_text(index, "# 索引\n\n- [[%s]]\n\n%s%s" % (old, filler, FOOTER))
        originals = {p: _bytes(p) for p in (client, index, self.proj)}
        limit = min(len(b) for b in originals.values() if len(b) > 4096) - 1024
        code = _FSIZE_PRELUDE + """
import ds_tools
limit(%d)
report(lambda: ds_tools.rename_project(%r, %r, %r, today="2026-09-15"))
""" % (limit, old, new, self.ds)
        r = _run_child(code)
        self.assertIn("RAISED True", r.stdout, "故障没注入成功:%r %r" % (r.stdout, r.stderr[-500:]))
        for p in (client, index):
            with self.subTest(file=os.path.basename(p)):
                got = _bytes(p)
                done = originals[p].replace(("[[%s]]" % old).encode("utf-8"), ("[[%s]]" % new).encode("utf-8"))
                self.assertTrue(got in (originals[p], done), "%s 成了半截(%d 字节,原来 %d)"
                                % (os.path.basename(p), len(got), len(originals[p])))
        new_path = os.path.join(self.ds, "projects", new + ".md")
        survivors = [x for x in (self.proj, new_path) if os.path.exists(x)]
        self.assertEqual(len(survivors), 1, "档案本体不见了或出现了两份:%r" % survivors)
        self.assertGreater(len(_bytes(survivors[0])), len(originals[self.proj]) // 2, "档案本体成了半截")


class ListingsIgnoreTheLockDirectory(_Tmp):
    """aw11 —— 写过之后,项目列表里不出现锁目录之类的东西。"""

    def test_aw11_list_projects_is_unchanged_by_writes(self):
        before = ds_tools.list_projects(self.ds, today="2026-09-15")
        with ds_common.locked_rw(self.proj) as box:
            box["lines"].insert(4, "- 触发一次写")
        after = ds_tools.list_projects(self.ds, today="2026-09-15")
        key = lambda res: sorted(str(p.get("project") or p.get("key") or p.get("name")) for p in res.get("projects", []))
        self.assertEqual(key(after), key(before))
        self.assertEqual(after.get("errors") or [], before.get("errors") or [])
        for name in key(after):
            self.assertFalse(name.startswith("."), "列表里冒出了 %r" % name)


class WindowsReplaceSemantics(_Tmp):
    """aw12 —— 目标被另一个句柄开着时怎么办。Linux 上 replace 永远成功,a 在哪都跑,b 只在 Windows 上问。"""

    def _write_while_held(self, hold_seconds):
        result = {}

        def writer():
            try:
                with ds_common.locked_rw(self.proj) as box:
                    box["lines"].insert(4, "- 别人开着文件时写的")
                result["ok"] = True
            except OSError as exc:
                result["error"] = exc

        reader = open(self.proj, encoding="utf-8")
        try:
            t = threading.Thread(target=writer)
            t.start()
            time.sleep(hold_seconds)
        finally:
            reader.close()
        t.join(60)
        return result

    def test_aw12a_a_brief_reader_does_not_make_the_write_fail(self):
        result = self._write_while_held(0.2)
        self.assertTrue(result.get("ok"), "别人只开了 0.2 秒,写入却失败了:%r" % (result,))
        with open(self.proj, encoding="utf-8") as fh:
            self.assertIn("- 别人开着文件时写的", fh.read())

    @unittest.skipUnless(os.name == "nt", "只有 Windows 上\"开着的文件换不掉\"")
    def test_aw12b_a_long_reader_fails_the_write_but_keeps_the_archive(self):
        before = _bytes(self.proj)
        result = self._write_while_held(8.0)
        self.assertIn("error", result, "目标一直被开着,写入却报成功 —— 那它是怎么写进去的?%r" % (result,))
        self.assertEqual(_bytes(self.proj), before, "写入失败了,档案却被动过")
        self.assertNoTmpLitter(os.path.dirname(os.path.abspath(self.proj)))   # 与 aw3 那两行字面不同:死断言放行清单按内容认


class OneSourceForReplaceRetry(unittest.TestCase):
    """aw13 —— "Windows 上替换重试"只有一处定义(ds_common),别处引用它。"""

    def test_aw13_replace_with_retry_is_defined_once_in_ds_common(self):
        import re
        hits = []
        for path in sorted(glob.glob(os.path.join(BIN, "*.py"))):
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if re.match(r"\s*def _?replace_with_retry\(", line):
                        hits.append((os.path.basename(path), n))
        self.assertEqual([h[0] for h in hits], ["ds_common.py"], "定义在:%r" % hits)


class FlushedToDiskBeforeTheSwap(unittest.TestCase):
    """aw14 —— 断电那一半只能钉结构:`atomic_write_text` 里**替换之前**对临时文件 `os.fsync`。

    断电本机模拟不了;只改名不刷盘,断电后可能是"改名落了、数据块没落"的空文件 —— 正是这一单要防的事。
    钉的是调用顺序(AST 里 fsync 的调用出现在 replace_with_retry 之前),注释里写了 fsync 不算。
    """

    def test_aw14_fsync_happens_before_the_replace(self):
        import ast
        with open(os.path.join(BIN, "ds_common.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "atomic_write_text"), None)
        self.assertIsNotNone(fn, "ds_common 里没有 atomic_write_text")
        calls = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                calls.append((node.lineno, node.col_offset, name))
        calls.sort()
        names = [c[2] for c in calls]
        self.assertIn("fsync", names, "atomic_write_text 不刷盘:断电后可能是空文件")
        self.assertIn("replace_with_retry", names)
        self.assertLess(names.index("fsync"), names.index("replace_with_retry"), "刷盘发生在替换之后,来不及")


if __name__ == "__main__":
    unittest.main()
