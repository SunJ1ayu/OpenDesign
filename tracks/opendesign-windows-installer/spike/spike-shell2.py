"""S1b 外壳探路(第二张)—— 回答 S1a 那张**故意没问**的那些。

S1a 只问了"窗口和托盘这套东西在这台机器上跑不跑得起来",而且窗口里装的是它自己写死的
一段 HTML。那个取舍是对的:把"窗口起不起得来"和"后端行不行"混进一问,红了会分不清是谁的锅。
**代价是下面这些一条都没验过**,S1a 的收据不覆盖它们(tasks.md 里逐条记着账):

  1. 外壳 + **真实后端**的组合 —— 窗口里加载的是 ds-web,不是自带 HTML
  2. 关掉窗口**不退出**(收进托盘),托盘"退出"才真收摊
  3. 第二次双击不起第二份,而是把已经开着的那扇窗叫到前台
  4. 收摊之后两条后台腿**没有变成孤儿进程**
  5. 装坏了(配置缺失)时给的是**人话**,不是一堆英文栈

判卷规则(与 S0/S1a 同一套,别在同一个项目里换第二套习惯):
- **只读、不装、不改机器**:外壳本来要写 `%LOCALAPPDATA%\\OpenDesign`,这张考卷把
  `LOCALAPPDATA` 整个改指到**包内** `fakelocal\\`。删掉这个文件夹 = 完全消失。
  不写注册表、不进 PATH、不碰你已经装着的那套 OpenDesign。
- **机器能判的绝不让业主判**:下面七问里只有两问要你用眼睛答(窗口内容、托盘图标),
  其余五问全是脚本自己抓证据。你按提示做动作就行,不用判断对错。
- **每一问都要打印"凭什么"**,不许只打印 PASS。
- **绝不能挂住**:每一处等待都有超时,超时算 FAIL 并说明。

跑法:双击 `跑一下.bat`。全程大约 5~10 分钟(网关冷启动要连 3 个 MCP,S0 真机上见过接近 4 分钟)。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Windows 的 cmd 默认不是 UTF-8。不焊这一下,打印中文会 UnicodeEncodeError ⇒ **假红**。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "收据.txt"
PYEXE = HERE / "python" / "python.exe"
DSDIR = HERE / "ds"
SHELL = DSDIR / "bin" / "ds_shell.py"
FAKELOCAL = HERE / "fakelocal"                      # 冒充 %LOCALAPPDATA%
APPDIR = FAKELOCAL / "OpenDesign"
USERDATA = APPDIR / "UserData"
SHELLLOG = APPDIR / "Logs" / "外壳.log"


class _Tee:
    """屏幕和收据文件各写一份 —— 业主把 收据.txt 发回来即可,不用截图。"""

    def __init__(self, stream, fh):
        self._s, self._f = stream, fh

    def write(self, data):
        self._s.write(data)
        self._f.write(data)
        self._f.flush()
        return len(data)

    def flush(self):
        self._s.flush()
        self._f.flush()


_fh = open(RECEIPT, "w", encoding="utf-8")
_REAL_STDOUT = sys.stdout
sys.stdout = _Tee(sys.stdout, _fh)
PASS = FAIL = SKIP = 0


def head(t: str) -> None:
    print(f"\n{'=' * 64}\n{t}\n{'=' * 64}")


def ok(q: str, why: str) -> None:
    global PASS
    PASS += 1
    print(f"  [PASS] {q}\n         凭据: {why}")


def no(q: str, why: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {q}\n         凭据: {why}")


def skip(q: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {q}\n         原因: {why}")


def err_detail(e: BaseException) -> str:
    """把真实报错原样带出来 —— 「启动失败」这四个字对我毫无用处。"""
    return f"{type(e).__name__}: {e}"


def ask(prompt: str) -> str | None:
    """问业主一句。**EOF 不许炸** —— 从管道跑时 input() 会直接 EOFError。"""
    try:
        print()
        return input(f"  ❓ {prompt} ").strip().lower()
    except EOFError:
        return None


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def health(port: int, timeout: float = 3.0) -> dict | None:
    """ds-web 自报身份。拿不到就是 None,不抛。"""
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def web_port_from_log() -> int | None:
    """外壳自己在日志里写下它挑中的端口(ds_shell.py:「窗口打开:http://...」)。

    为什么不直接假定 8766:业主机器上**很可能已经装着 OpenDesign 并且开着**,
    那 8766 就被占了,外壳会自动往后挪 —— 这恰恰是它该干的事,不是故障。
    """
    try:
        m = re.findall(r"窗口打开:http://127\.0\.0\.1:(\d+)/", SHELLLOG.read_text("utf-8"))
        return int(m[-1]) if m else None
    except OSError:
        return None


def scan_web_port() -> int | None:
    """兜底:日志没写成的话,把首选段扫一遍找我们自己的 ds-web。"""
    for p in range(8766, 8766 + 21):
        h = health(p, timeout=0.6)
        if h and h.get("ok") is True and "version" in h:
            return p
    return None


def shell_env() -> dict:
    """跑外壳用的环境 —— **把 LOCALAPPDATA 劫持进包内**,保住"删掉即消失"。"""
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(FAKELOCAL)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# ═══════════════════════════════════════════════════════════ 0. 现场
head("0. 现场(先证明这是我以为的那个运行时)")

print(f"  python  : {sys.version.split()[0]}")
print(f"  可执行  : {sys.executable}")

exe = Path(sys.executable).resolve()
if str(exe).lower().startswith(str(HERE).lower()):
    ok("跑的是包内的免装 Python", f"{exe}")
else:
    no("跑的是包内的免装 Python",
       f"{exe} 不在包目录下 —— 这一跑的结论对成品无效,先弄清为什么")

for p, what in [(PYEXE, "包内 python.exe"), (SHELL, "外壳 ds_shell.py"),
                (DSDIR / "bin" / "ds_shell_core.py", "外壳内核"),
                (DSDIR / "bin" / "ds_web.py", "工作台")]:
    if not p.exists():
        no(f"{what} 在包里", f"找不到 {p} —— 包组坏了,后面的问都没意义")

VERSION_ANCHOR = ""
try:
    VERSION_ANCHOR = (DSDIR / "版本号.txt").read_text("utf-8").strip()
    print(f"  包里的 ds-web 版本锚: {VERSION_ANCHOR}")
except OSError:
    no("读得到版本号锚", "ds\\版本号.txt 缺失 —— 没法验运行中的后端是不是这个包里的代码")


# ═══════════════════════════════════════════════════════════ 准备
head("准备:造一份干净的配置(这是**安装器**将来要干的活,不计分)")

print("  注:这一步把 %LOCALAPPDATA% 改指到包内 fakelocal\\,")
print("      所以你已经装着的那套 OpenDesign 一根头发都不会被碰到。")

shutil.rmtree(FAKELOCAL, ignore_errors=True)
NANOBOT = USERDATA / ".nanobot"
NANOBOT.mkdir(parents=True, exist_ok=True)
CFG = NANOBOT / "config.json"
_prep_ok = True
try:
    # 与 S0 的 S4 同一条路子:nanobot 自己的默认配置 → 开 webui → 合并 Windows 模板。
    # 端口改写与 MCP 指向**故意不做** —— 那正是外壳要负责的事,这张考卷考的就是它。
    gen = subprocess.run(
        [str(PYEXE), "-c",
         "import json,sys;from nanobot.config.schema import Config;"
         "sys.stdout.write(json.dumps(Config().model_dump(mode='json',by_alias=True,"
         "exclude_none=True),ensure_ascii=False,indent=2))"],
        capture_output=True, text=True, encoding="utf-8", env=shell_env(), timeout=120)
    if gen.returncode != 0:
        raise RuntimeError(f"生成默认配置失败 rc={gen.returncode}: {gen.stderr[:400]}")
    CFG.write_text(gen.stdout, encoding="utf-8")

    for argv, what in [
        ([str(PYEXE), str(DSDIR / "bin" / "enable_webui.py"), "spike-passwd"], "enable_webui"),
        ([str(PYEXE), str(DSDIR / "bin" / "ds_merge_config.py"),
          str(DSDIR / "config" / "nanobot.config.windows.jsonc"), str(CFG)], "合并 Windows 模板"),
    ]:
        env = shell_env()
        env["USERPROFILE"] = str(USERDATA)
        env["HOME"] = str(USERDATA)
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           env=env, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(f"{what} rc={r.returncode}: {(r.stderr or r.stdout)[:400]}")
    print(f"  ✅ 配置就绪:{CFG}({CFG.stat().st_size} 字节)")
    print("  注:**没有放真 key** —— 这一跑不考聊天,聊天连不上大模型是预期的。")
except Exception as exc:
    _prep_ok = False
    print(f"  🔴 准备阶段就失败了:{err_detail(exc)}")
    print("     后面七问全部跳过 —— 在坏配置上跑出来的红没有任何信息量。")


# ═══════════════════════════════════════════════════════════ 1~6
proc: subprocess.Popen | None = None
WEB: int | None = None

if not _prep_ok:
    for q in ["外壳能把真实后端拉起来", "窗口里是 OpenDesign 工作台", "关掉窗口不退出",
              "托盘图标常驻", "第二次双击不起第二份", "托盘退出后收干净"]:
        skip(q, "准备阶段失败")
else:
    head("1. 外壳能不能把**真实后端**拉起来(S1a 那张考卷没问过这个)")
    print("  正在启动 OpenDesign 外壳…")
    print("  ⏳ 网关要连 3 个 MCP 子进程,冷启动最长可能要 4 分钟,请耐心等窗口出现。")
    try:
        proc = subprocess.Popen([str(PYEXE), str(SHELL)], env=shell_env(), cwd=str(HERE))
    except Exception as exc:
        proc = None
        no("外壳能把真实后端拉起来", f"外壳进程都没起来:{err_detail(exc)}")

    if proc is not None:
        # 外壳自己给的上限就是 网关 300s + 工作台 60s = 360s。等于它的话,慢一点点就会
        # **红在我的秒表上**,而不是红在真问题上 —— 而那种红要花业主又一趟真机才能澄清。
        # 留 60s 余量:超时仍然算 FAIL(不许无限等),但那时它是真的起不来。
        deadline = time.time() + 420
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            WEB = web_port_from_log()
            if WEB and health(WEB):
                break
            time.sleep(2.0)

        if proc.poll() is not None:
            no("外壳能把真实后端拉起来",
               f"外壳自己退出了,rc={proc.returncode}。它应该已经弹过一个说明原因的对话框;"
               f"日志:{SHELLLOG}")
        else:
            WEB = WEB or scan_web_port()
            h = health(WEB) if WEB else None
            if not h:
                no("外壳能把真实后端拉起来",
                   f"等了 6 分钟,ds-web 仍然不应答(日志里读到的端口={WEB});日志:{SHELLLOG}")
            else:
                got = str(h.get("version", "?"))
                why = f"127.0.0.1:{WEB}/api/health 自报 version={got}"
                if VERSION_ANCHOR and got != VERSION_ANCHOR:
                    no("外壳能把真实后端拉起来",
                       f"{why},但包里的锚是 {VERSION_ANCHOR} —— "
                       f"**跑起来的多半是你机器上另一套 OpenDesign,不是这个包**")
                else:
                    ok("外壳能把真实后端拉起来",
                       f"{why},与包内锚一致;两条腿由外壳自己的监管拉起")

    # 第 1 问的结论要传下去。**不传的后果台架上当场演过一遍**:外壳压根没起来,
    # 第 3 问照样问「关掉窗口了吗」并判「关窗把它带走了」—— 一条**理由是假的**的红。
    # 假报警和假绿一样坏:它会把我引去查一个根本没发生的现象。
    SHELL_UP = proc is not None and proc.poll() is None and bool(WEB and health(WEB))

    # ── 2. 只有眼睛能答的第一问 ──────────────────────────────────────
    head("2. 窗口里装的是**真界面**吗(这一问只有你能答)")
    if not SHELL_UP:
        skip("窗口里是 OpenDesign 工作台", "外壳没起来,没有窗口可看(见第 1 问)")
    else:
        print("  应该看到:一扇 OpenDesign 窗口,里面是工作台界面(项目/待办那套),")
        print("            而且**没有地址栏**(它是应用窗口,不是浏览器)。")
        print("  提示:聊天发不出去是正常的(这一跑没放 key)。")
        a = ask("看到工作台界面了吗?(y=看到 / n=没有或是白屏/报错,回车前请先看清) [y/n]:")
        if a is None:
            skip("窗口里是 OpenDesign 工作台", "没法交互(非终端环境)")
        elif a.startswith("y"):
            ok("窗口里是 OpenDesign 工作台", "业主目视确认:界面出来了,且没有地址栏")
        else:
            no("窗口里是 OpenDesign 工作台",
               "业主目视:没出来/白屏/报错 —— 请把窗口和 收据.txt 一起发回来")

    # ── 3. 关窗不退出(机器判) ──────────────────────────────────────
    head("3. 关掉窗口之后,它应该**收进托盘继续活着**(这一问机器自己判)")
    if not SHELL_UP:
        skip("关掉窗口不退出", "外壳没起来(见第 1 问)—— 没有窗口可关,这一问问不出东西")
    else:
        print("  请点窗口右上角的 × 关掉它,然后回来按回车。")
        ask("关好了就按回车:")
        time.sleep(3.0)
        if proc.poll() is not None:
            no("关掉窗口不退出",
               f"外壳进程跟着窗口一起没了(rc={proc.returncode})—— 关窗应该只是收进托盘")
        elif WEB and health(WEB):
            ok("关掉窗口不退出",
               f"外壳进程仍在(pid={proc.pid}),且后端 127.0.0.1:{WEB} 仍然应答")
        else:
            no("关掉窗口不退出",
               f"外壳进程还在(pid={proc.pid}),但后端不应答了 —— 关窗把后台带崩了")

    # ── 4. 托盘图标(眼睛) ─────────────────────────────────────────
    head("4. 托盘里有没有它(关窗不退出全靠这个)")
    if not SHELL_UP:
        skip("托盘图标常驻", "外壳没起来(见第 1 问)")
    else:
        print("  看右下角托盘区(可能要点那个 ∧ 展开隐藏图标)。")
        a = ask("看到 OpenDesign 的托盘图标了吗? [y/n]:")
        if a is None:
            skip("托盘图标常驻", "没法交互")
        elif a.startswith("y"):
            ok("托盘图标常驻", "业主目视确认")
        else:
            no("托盘图标常驻", "业主目视:没找到 —— 关窗之后就再也叫不出来了,这是硬伤")

    # ── 5. 第二次双击(机器判 + 眼睛) ───────────────────────────────
    head("5. 再打开一次,应该**把原来那扇窗叫回来**,而不是起第二份")
    if proc is None or proc.poll() is not None:
        skip("第二次双击不起第二份", "第一份外壳已经不在了")
    else:
        print("  脚本这就替你「再双击一次」(起第二个外壳进程)…")
        try:
            second = subprocess.Popen([str(PYEXE), str(SHELL)], env=shell_env(), cwd=str(HERE))
            try:
                rc2 = second.wait(timeout=60)
            except subprocess.TimeoutExpired:
                second.kill()
                rc2 = None
            if rc2 is None:
                no("第二次双击不起第二份",
                   "第二个外壳 60 秒都没退出 —— 它多半在起第二套后端,单实例锁没拦住")
            elif rc2 != 0:
                no("第二次双击不起第二份",
                   f"第二个外壳退出了但 rc={rc2}(应该是 0:让位是正常行为,不是错误)")
            elif proc.poll() is not None:
                no("第二次双击不起第二份", "第二份把第一份挤掉了 —— 锁抢反了")
            elif not (health(WEB) if WEB else None):
                no("第二次双击不起第二份", "第二份退出后,原来那份的后端不应答了")
            else:
                ok("第二次双击不起第二份",
                   f"第二个进程 rc=0 自行让位,第一份(pid={proc.pid})与其后端都还在")
        except Exception as exc:
            no("第二次双击不起第二份", err_detail(exc))

        a = ask("刚才那扇窗自己弹回到前台了吗?(这半只有你看得见) [y/n]:")
        if a is None:
            skip("第二次双击会把窗口叫回前台", "没法交互")
        elif a.startswith("y"):
            ok("第二次双击会把窗口叫回前台", "业主目视确认")
        else:
            no("第二次双击会把窗口叫回前台",
               "窗口没回来 —— 锁的监听线程调 UI 那条路在这台机器上不成立"
               "(ds_shell.py 里点名过这个假设)")

    # ── 6. 托盘退出要收干净(机器判) ───────────────────────────────
    head("6. 托盘「退出」之后,两条后台腿**不许变成孤儿**(机器自己判)")
    if proc is None or proc.poll() is not None:
        skip("托盘退出后收干净", "外壳已经不在了")
    else:
        print("  请右键托盘图标 → 点「退出」,然后回来按回车。")
        ask("点完「退出」就按回车:")
        gone_at = time.time() + 60
        while time.time() < gone_at and proc.poll() is None:
            time.sleep(1.0)
        if proc.poll() is None:
            no("托盘退出后收干净", "点了退出,60 秒后外壳进程还活着 —— 收摊卡住了")
            try:
                proc.kill()
            except Exception:
                pass
        else:
            time.sleep(3.0)
            leftovers = [p for p in ([WEB] if WEB else []) if listening(p)]
            if leftovers:
                no("托盘退出后收干净",
                   f"外壳退了(rc={proc.returncode}),但端口 {leftovers} 还有人听着 —— "
                   f"后台腿变成孤儿进程了")
            else:
                ok("托盘退出后收干净",
                   f"外壳 rc={proc.returncode},且 ds-web 端口 {WEB} 已经没人听了")


# ═══════════════════════════════════════════════════════════ 7. 装坏了要说人话
head("7. 装坏了的时候,给的是**人话**还是一堆英文栈")
print("  这一问故意把配置文件藏起来,看它怎么报错。")
print("  ⚠️ 会弹出一个错误对话框 —— **那是预期的**,看一眼上面写的是不是中文人话,再点确定。")
ask("准备好了按回车:")

BROKEN = HERE / "fakelocal-broken"
shutil.rmtree(BROKEN, ignore_errors=True)
(BROKEN / "OpenDesign" / "UserData").mkdir(parents=True, exist_ok=True)
try:
    env = shell_env()
    env["LOCALAPPDATA"] = str(BROKEN)
    r = subprocess.run([str(PYEXE), str(SHELL)], env=env, cwd=str(HERE),
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    blog = BROKEN / "OpenDesign" / "Logs" / "外壳.log"
    text = blog.read_text("utf-8") if blog.exists() else ""
    said_human = "还没装好" in text or "找不到配置文件" in text
    leaked_stack = "Traceback (most recent call last)" in (r.stderr or "")
    if r.returncode == 0:
        no("装坏了会说人话", "配置缺失竟然 rc=0 —— 它把一个坏状态当成正常启动了")
    elif said_human and not leaked_stack:
        ok("装坏了会说人话",
           f"rc={r.returncode},弹窗文案进了日志(「还没装好…」),终端没有裸栈")
    elif said_human:
        no("装坏了会说人话", f"人话有了,但 stderr 里还是漏了一段栈:{(r.stderr or '')[:200]}")
    else:
        no("装坏了会说人话",
           f"rc={r.returncode},但日志里找不到那句人话。日志内容:{text[:300] or '(空)'}")
except subprocess.TimeoutExpired:
    no("装坏了会说人话", "配置缺失时它挂住了 3 分钟不退出 —— 业主会以为电脑死了")
except Exception as exc:
    no("装坏了会说人话", err_detail(exc))
finally:
    shutil.rmtree(BROKEN, ignore_errors=True)


# ═══════════════════════════════════════════════════════════ 收据
head("收据")
print(f"  PASS {PASS}   FAIL {FAIL}   SKIP {SKIP}")
print()
print("  这一跑**没有**覆盖到的(别拿这张收据当它们的绿):")
print("   · WebView2 / .NET **缺失**时的表现 —— 你这台机器上它们都在,验不了。")
print("     安装器要带微软官方引导程序兜底,那是 S1c 的事。")
print("   · 聊天(没放 key)。ds-web 是只读的,不需要 key 就能看。")
print("   · 开机自启、卸载、开始菜单 —— 都还没做。")
print()
if FAIL == 0 and SKIP == 0:
    print("  ⇒ 外壳这一层成立:真后端拉得起来、关窗收托盘、单实例、退出收得干净。")
    print("    下一步是把它包进安装器(Inno Setup)。")
else:
    print("  ⇒ 有红或跳过的项。把 收据.txt 整个发回来就行,不用你判断是什么问题。")
    print(f"    外壳自己的日志在:{SHELLLOG}")
print()
print("  注:这一跑不写注册表、不改 PATH、不碰你已装的那套 OpenDesign。")
print("      所有产生的东西都在这个文件夹内(fakelocal\\),删掉文件夹即可清除。")
print(f"\n  内容已存成 {RECEIPT.name} —— 把那个文件整个发回来。")

# 收尾顺序有讲究,写错会**污染退出码**(S1a 那张考卷在这里栽过:先 close 再 exit,
# 解释器收尾去 flush 一个已经关掉的文件 ⇒ rc 变成 120,一次本该全绿的跑以报错收场)。
sys.stdout.flush()
_code = 1 if FAIL else 0
sys.stdout = _REAL_STDOUT
_fh.close()
sys.exit(_code)
