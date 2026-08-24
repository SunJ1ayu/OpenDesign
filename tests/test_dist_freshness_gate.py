"""产物新鲜度闸的判据(track opendesign-dist-freshness-gate)。

这道闸答的问题只有一个:**`web/dist` 是不是当前 `web/src` build 出来的产物?**

它替换掉的旧闸(`tests/e2e/llm_key.e2e.mjs` 里)比的是 **mtime**,那个指标:
  - 会**误报**:改一行 CSS 注释 / 切分支 / 复制文件 —— 时间变了内容没变;
  - 更要命的是会**漏报**:src 真改了、dist 因某个无关动作 mtime 变新 ⇒ 闸绿而产物是旧的。
2026-08-24 实证:`c82dcbc` 改 app.css(纯注释)晚于 `d704df8` 那次 dist 重建 ⇒ 旧闸红,
而重新 build 的产物与 web/dist **逐字节相同** —— 报警指的事不要紧,但报警器本身也没问对问题。

判据全部**真调**闸,不看它的源码长什么样。

⚠️ **O4/O6 跑在真仓库上**(其余六条在临时副本里,node_modules 用符号链接)。
O6 会把 `web/dist/index.html` 短暂改脏再由 finally 还原;**若被 Ctrl+C 砍在中间**,
那一行 `<!-- judge-probe -->` 会留在工作树上 —— git status 当场看得见,不是无声损坏,
`git checkout -- web/dist/index.html` 一行就能收拾。
(2026-08-24 panel submimo 建议把这条写在文件头,采纳。)
"""

import os
import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "tests" / "e2e" / "check-dist-fresh.sh"
WEB = REPO / "web"

# 一次 build 实测约 2.5s(2026-08-24,本机)。留足余量,但不能大到把"卡死"也当成通过。
BUILD_TIMEOUT = 180


def _run_gate(web_dir, timeout=BUILD_TIMEOUT):
    """真调闸。返回 (rc, 合并后的 stdout+stderr)。"""
    proc = subprocess.run(
        [str(GATE), "--web-dir", str(web_dir)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _make_web_copy(dst):
    """造一份可 build 的 web/ 副本 —— node_modules 用符号链接(75M,不复制)。

    造副本而不是在真工作树上变异,是为了让判据**无论怎么崩都不会弄脏仓库**。
    """
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "package.json", "tsconfig.json", "vite.config.ts"):
        shutil.copy2(WEB / name, dst / name)
    shutil.copytree(WEB / "src", dst / "src")
    shutil.copytree(WEB / "dist", dst / "dist")
    os.symlink(WEB / "node_modules", dst / "node_modules")
    return dst


class DistFreshnessGate(unittest.TestCase):
    def setUp(self):
        self.assertTrue(GATE.exists(), f"闸不存在:{GATE}")
        self.assertTrue(os.access(GATE, os.X_OK), f"闸没有可执行位:{GATE}")

    # ── O2 先放前面:它是本单存在的理由 ────────────────────────────────
    def test_o2_comment_only_change_is_not_flagged(self):
        """O2 只改注释 ⇒ 产物不变 ⇒ 闸必须放行。

        这正是 2026-08-24 那次事故的原样形状。旧闸(比 mtime)和我一度提议的
        "比 src 内容哈希"方案,**在这一条上都会挂**。
        """
        with tempfile.TemporaryDirectory() as tmp:
            web = _make_web_copy(Path(tmp) / "web")
            css = web / "src" / "app.css"
            css.write_text(
                css.read_text(encoding="utf-8") + "\n/* 判据加的纯注释,不产生任何样式 */\n",
                encoding="utf-8",
            )
            rc, out = _run_gate(web)
            self.assertEqual(rc, 0, f"只改注释被误报成过期了。闸的输出:\n{out}")

    # ── O1 真过期必须咬住 ────────────────────────────────────────────
    def test_o1_real_source_change_is_caught(self):
        """O1 改了会进产物的源码却没 build ⇒ 闸必须红,并点名差异文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            web = _make_web_copy(Path(tmp) / "web")
            css = web / "src" / "app.css"
            css.write_text(
                css.read_text(encoding="utf-8") + "\n.judge-probe-xyz { color: rgb(1,2,3); }\n",
                encoding="utf-8",
            )
            rc, out = _run_gate(web)
            self.assertNotEqual(rc, 0, f"源码真改了没 build,闸却放行了。输出:\n{out}")
            self.assertIn("dist", out.lower(), f"闸红了但没说清是 dist 的问题:\n{out}")

    def test_o1b_index_html_change_is_caught(self):
        """O1b 变异落在 `index.html` 上 —— 它**不带内容哈希**。

        js/css 的文件名是内容哈希,所以"只比文件名"碰巧也能发现它们变了;
        而 index.html 改了内容**文件名不变**。这一条专门钉住"必须比内容,不能只比名字"。
        """
        with tempfile.TemporaryDirectory() as tmp:
            web = _make_web_copy(Path(tmp) / "web")
            html = web / "index.html"
            html.write_text(
                html.read_text(encoding="utf-8").replace(
                    "</head>", '<meta name="judge-probe" content="xyz" /></head>'
                ),
                encoding="utf-8",
            )
            rc, out = _run_gate(web)
            self.assertNotEqual(rc, 0, f"index.html 改了没 build,闸却放行了(只比了文件名?)。输出:\n{out}")

    # ── O3 build 失败不许静默放过 ────────────────────────────────────
    def test_o3_build_failure_blocks_loudly(self):
        """O3 build 挂了 ⇒ 必须红,而且要带得出 build 的报错原文。

        「返回成功≠事情发生了」在这个项目栽过三次。闸自己 build 失败却报绿,
        就是同一族里最坏的一种:它会让所有 e2e 在一个错误的前提上继续跑。
        """
        with tempfile.TemporaryDirectory() as tmp:
            web = _make_web_copy(Path(tmp) / "web")
            broken = web / "src" / "judge_broken.ts"
            broken.write_text("这不是合法的 TypeScript ((((\n", encoding="utf-8")
            # 让它真的进依赖图,否则 vite 不会碰它
            main = web / "src" / "main.tsx"
            if main.exists():
                main.write_text('import "./judge_broken";\n' + main.read_text(encoding="utf-8"),
                                encoding="utf-8")
            rc, out = _run_gate(web)
            self.assertNotEqual(rc, 0, f"build 失败了闸却报绿。输出:\n{out}")
            # 🔴 别断言"输出够长" —— 凑几十个字符太容易,闸多打两行套话就骗过去了,
            #    而查起来仍然只能靠猜。要问的是**报错可不可以溯源到具体文件**。
            self.assertIn(
                "judge_broken", out,
                f"闸红了,但没带出 build 报错里那个出问题的文件名,查不动:\n{out}",
            )

    # ── O4 不许污染工作树 ────────────────────────────────────────────
    def test_o4_does_not_touch_the_worktree(self):
        """O4 闸只报告、不修复 ⇒ 跑完 `web/dist` 逐字节不变、git 不新增脏项。

        「你欠一次 build」这个信号必须留在工作树上被看见,不能被工具悄悄抹平。
        """
        before = {p: p.read_bytes() for p in sorted(WEB.joinpath("dist").rglob("*")) if p.is_file()}
        self.assertGreater(len(before), 0, "web/dist 是空的,这条判据就没有意义了")
        status_before = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(REPO), capture_output=True, text=True
        ).stdout

        rc, out = _run_gate(WEB)

        after = {p: p.read_bytes() for p in sorted(WEB.joinpath("dist").rglob("*")) if p.is_file()}
        self.assertEqual(before.keys(), after.keys(), "闸改变了 web/dist 的文件集合")
        for p, data in before.items():
            self.assertEqual(data, after[p], f"闸改动了 {p}")
        status_after = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(REPO), capture_output=True, text=True
        ).stdout
        self.assertEqual(status_before, status_after, "闸跑完之后 git 状态变了")

    # ── O5 前提:build 必须是确定性的 ──────────────────────────────────
    def test_o5_build_is_deterministic(self):
        """O5 同样输入连续两次 build,产物必须逐字节相同。

        这是整道闸的**前提**:build 若不确定,闸就会随机红 ——
        那等于把报警器换成噪音源,比现状更坏。前提塌了要当场知道,不是等它偶发。
        """
        with tempfile.TemporaryDirectory() as tmp:
            web = _make_web_copy(Path(tmp) / "web")
            outs = []
            for i in ("a", "b"):
                d = Path(tmp) / f"out-{i}"
                proc = subprocess.run(
                    ["npx", "vite", "build", "--outDir", str(d), "--emptyOutDir"],
                    cwd=str(web), capture_output=True, text=True, timeout=BUILD_TIMEOUT,
                )
                self.assertEqual(proc.returncode, 0, f"build 失败:\n{proc.stdout}\n{proc.stderr}")
                files = {p.relative_to(d): p.read_bytes() for p in d.rglob("*") if p.is_file()}
                self.assertGreater(len(files), 0, "build 没产出任何文件")
                outs.append(files)
            self.assertEqual(outs[0].keys(), outs[1].keys(), "两次 build 的文件集合不同")
            for rel, data in outs[0].items():
                self.assertEqual(data, outs[1][rel], f"两次 build 的 {rel} 内容不同 ⇒ build 不确定")

    # ── O7 「两边都空」不许被读成一致 ─────────────────────────────────
    def test_o7_empty_build_output_is_not_treated_as_match(self):
        """O7 build 报成功却一个文件都没产出、而 dist 也是空的 ⇒ 闸必须红。

        这是恒绿的经典形状:比对函数把「两边文件集合都为空」读成一致,
        于是这道闸永远绿着、什么都不守,而收据上看起来一切正常。
        造法:副本里清空 dist,并让 vite `build.write=false`(build 成功但不落盘)。
        """
        with tempfile.TemporaryDirectory() as tmp:
            web = _make_web_copy(Path(tmp) / "web")
            shutil.rmtree(web / "dist")
            (web / "dist").mkdir()
            cfg = web / "vite.config.ts"
            cfg.write_text(
                cfg.read_text(encoding="utf-8").replace(
                    "plugins: [react()],", "plugins: [react()],\n  build: { write: false },"
                ),
                encoding="utf-8",
            )
            rc, out = _run_gate(web)
            self.assertNotEqual(
                rc, 0,
                f"build 没产出任何文件、dist 也是空的,闸却报绿 —— 这就是恒绿。输出:\n{out}",
            )

    # ── O6 rc 必须传得出去,而且是默认路径就跑 ─────────────────────────
    def test_o6_runall_wiring(self):
        """O6 `run-all.sh` 必须在**跑任何场景之前**过这道闸,且**闸红则整体红**。

        「管道/分号吃掉 rc 造出假绿收据」这个项目栽过五次,是最可能的失败形态,
        所以这里不只看静态形状,还要**真跑一次**。
        """
        runall = (REPO / "tests" / "e2e" / "run-all.sh").read_text(encoding="utf-8")
        self.assertIn("check-dist-fresh.sh", runall, "run-all.sh 根本没调这道闸")

        # 静态:调用不许被 `;` 接或塞进管道 —— 那两种写法都会吞掉 rc
        for line in runall.splitlines():
            if "check-dist-fresh.sh" in line and not line.strip().startswith("#"):
                self.assertNotIn("|", line, f"闸的调用进了管道,rc 会被吃掉:{line}")
                self.assertFalse(
                    line.rstrip().endswith(";"),
                    f"闸的调用以 `;` 收尾,rc 会被吃掉:{line}",
                )

        # 动态:把 dist 改脏(改产物,不改源码)⇒ 闸必须红 ⇒ run-all.sh 必须立刻整体红
        victim = WEB / "dist" / "index.html"
        original = victim.read_bytes()
        try:
            victim.write_bytes(original + b"\n<!-- judge-probe -->\n")
            # 闸若拦住了,run-all.sh 几秒内就该退出;90s 足够宽松,
            # 而它跑满全部场景要 2.5 分钟 —— 超时本身就是"没拦住"的证据。
            #
            # 🔴 必须 start_new_session + killpg:`subprocess.run(timeout=)` 只杀直接子进程,
            #    而 run-all.sh 底下是 node + 一整棵 chromium。2026-08-24 跑红检时当场 ps 到
            #    两个 ppid=1 的 crashpad handler —— **判据自己造遗孤**,和这个项目
            #    「断线遗孤占端口」是同一族。
            proc = subprocess.Popen(
                [str(REPO / "tests" / "e2e" / "run-all.sh")],
                cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, start_new_session=True,
            )
            try:
                combined = proc.communicate(timeout=90)[0]
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                combined = proc.communicate()[0] or ""
                self.fail("闸红了,run-all.sh 却没停 —— 90s 内还在跑场景(已杀掉整个进程组)")
            self.assertNotEqual(proc.returncode, 0, "dist 与源码不符,run-all.sh 却报绿")
            self.assertNotIn(
                "PASS", combined,
                f"闸红了却还continue跑了场景 —— 说明它没拦住:\n{combined[:2000]}",
            )
        finally:
            victim.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
