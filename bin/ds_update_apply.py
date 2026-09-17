#!/usr/bin/env python3
"""应用内更新的第二刀:**真的去装**(track opendesign-in-app-update-install)。

`ds_update.py` 只查不装;这里管"业主点了更新之后"的段①。
判据在 `tests/test_ds_update_apply.py`,编号的权威表在该 track 的 design.md。

🔴 **这个文件存在的前提,是一件 Windows 上改不了的事实**:

    正在运行的 .exe / .pyd 被文件系统锁着,安装器覆盖不了。
    而外壳、python、ds\\bin\\*.py **全都住在 $INSTDIR 里**。

⇒ **软件不可能在自己活着的时候更新自己。** 所以这一单的形状是"装到旁边再换名":

    ① (这里) 下载 → 对 sha256 → 静默装进 OpenDesign.new → 查新树完整 → 写接力脚本
       **全程活树一个字节不碰**;任何一步失败 = 删掉 .new,当无事发生(t4/t5/t16)
    ② (接力脚本,住 %TEMP%) 收摊 → 两次改名 → 拉起 → 问 /api/health
    ③ 新版自报版本号 + nonce = 收口

**为什么不是"备份整棵树再就地覆盖"**:那是本单 09-08 重拍掉的方案。就地覆盖的危险
窗口是整个安装过程(数十秒),而 `OpenDesign.nsi:92` 那句注释说得很清楚 ——
程序还在跑时 `RMDir /r` 删不掉会**悄悄跳过**,装到一半 = 一半新一半旧、一声不吭。
换名的危险窗口是**两次改名之间(毫秒)**,回滚退化成改回名字。

⚠️ **段② 是 .cmd,Linux 上验不了。** 所以这里把判断尽量前移:段① 全部可单测,
段② 只做"等 / 装 / 起 / 问 / 换回"五个动作,而且它的**结构**由这里生成、由
t6/t17 机械地钉住(不是注释级契约);它的**行为**归 Windows CI 的 e3/e4。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import time
import urllib.request

# 哨兵与版本号文件 —— 与 installer/OpenDesign.nsi 的 SENTINEL 是同一处约定。
SENTINEL_REL = os.path.join("ds", "bin", "ds_shell.py")
VERSION_REL = os.path.join("ds", "版本号.txt")
# 安装器布局里活树根上的启动器(t40:活树得长得像装出来的,才许它更新自己)。
LAUNCHER_REL = "OpenDesign.exe"
# 接力脚本的就绪信号(t38):脚本旁边的 `<脚本>.ready`。
RELAY_READY_SUFFIX = ".ready"

# 🔴 死线(t13)。**具名,不许写成通配符** —— design 里那条:
#    "永远绿不了的判据,下一步一定会被我自己调松",所以豁免要窄到能说出名字。
DATA_ROOT_PROTECTED_DIRS = ("Data", "UserData")
DATA_ROOT_EXEMPT_DIRS = ("Logs",)

# 🔴 跨文件契约(t20):python 这边发这面旗子,installer/OpenDesign.nsi 那边认它,
#    认出来就**不跑 provisioning** —— 更新期一个字节都不碰数据根(死线 t13)。
#    两边任何一边悄悄改掉,死线就破了,而 t13 在 Linux 上照样全绿(它用的是替身安装器)。
INSTALL_UPDATE_FLAG = "/UPDATE"
UPDATE_MODE_VAR = "$UpdateMode"

_SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$", re.IGNORECASE)
_READ_CHUNK = 1024 * 1024


def parse_digest(text):
    """`"sha256:<64hex>"` → 小写 hex;**认不出来一律 None**(t15)。

    None 的下一步是"当作校验失败",**不是"没给就跳过校验"** —— 后者是一条
    "看起来在工作"的路径:资产被换过也照装不误,而信任根本来就只有这一条。
    """
    if not isinstance(text, str):
        return None
    m = _SHA256_RE.match(text.strip())
    return m.group(1).lower() if m else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_READ_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# --- 收口:问新版"你几版",而且要问得旧进程答不上来 -------------------------

def health_url(port, nonce):
    """收口探针的地址(t18)。

    `nonce` 不是装饰:换名之后旧进程可能还没死透,**它也会回一个 200 和一个版本号**。
    带一次性 nonce 才能分清"新版起来了"和"旧的还在答"。(双出抓到的第③条)
    """
    return "http://127.0.0.1:%d/api/health?nonce=%s" % (int(port), nonce)


def build_opener():
    """**绕开系统代理**(t18)。

    业主机器上挂着 VPN。问 127.0.0.1 却走系统代理,0.98.1 就栽在这;
    而 CI 上没有代理 ⇒ 这条自动判据永远照不出来,只能写死在实现里。
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def health_says(payload, expect_version, nonce):
    """这一份 `/api/health` 应答算不算"新版起来了"(t18)。

    三件事全对才算:回了我这次的 nonce、版本号是期望的那个、它自己说 ok。
    """
    if not isinstance(payload, dict):
        return False
    if payload.get("nonce") != nonce:
        return False
    if str(payload.get("version") or "") != str(expect_version):
        return False
    return bool(payload.get("ok", True))


# --- 段②:接力脚本 ----------------------------------------------------------
#
# 生成它的是这里,钉它的是 t6/t17。plan 是**声明式的**:先有有序的步骤表,
# 再渲染成 .cmd。这样"收摊闸在改名之前"这件事是**数据上的顺序**,
# 不是"我在 .cmd 里肉眼看着像在前面"。

def relay_plan(paths, port, nonce, expect_version):
    """接力脚本的步骤表(有序)。每步:kind / marker / cmd,失败分支写 on_fail。

    先有**有序的步骤表**、再渲染成 `.cmd`,这样「收摊闸在改名之前」是**数据上的顺序**,
    不是我在 .cmd 里肉眼看着像在前面(判据 t6a 因此问得出、变异 m12 因此咬得住)。
    """
    live, new, old = paths["live"], paths["new"], paths["old"]
    steps = [
        {
            "kind": "teardown_gate",
            # 🔴 这一步的锚点 09-08 搬过:安装现在发生在**收摊之前**,
            #    所以它问的不再是"不许进安装步",而是"不许进换名步"。
            "cmd": "call :wait_gone",
            "on_fail": ["delete_new", "abort"],
        },
        {"kind": "rename", "cmd": 'move /Y "%LIVE%" "%OLDT%"'},
        {"kind": "rename", "cmd": 'move /Y "%NEWT%" "%LIVE%"'},
        {"kind": "launch", "cmd": 'start "" "%LIVE%\\OpenDesign.exe"'},
        {"kind": "health", "cmd": "call :ask_health", "on_fail": ["rollback"]},
        {"kind": "cleanup", "cmd": 'rmdir /S /Q "%OLDT%"'},
        {
            "kind": "rollback",
            # 换名中断/新版起不来 ⇒ 改回名字就是回滚(t17)。
            # ⚠️ 它在脚本里是**只能跳进来的错误处理段**,不是顺序执行到的一步
            #    —— 成功路径必须在它之前就 exit(判据 t24d)。
            "cmd": ('move /Y "%s" "%s" & move /Y "%s" "%s"' % (live, new, old, live)),
        },
    ]
    for i, step in enumerate(steps):
        step.setdefault("on_fail", [])
        step["marker"] = ":: STEP-%02d-%s" % (i, step["kind"])
    return steps


def _win_path(*parts):
    """拼 Windows 路径。**不许用 os.path.join** —— 它在 Linux 上给的是 `/`,
    拼出来就是 `C:\\A\\B/Logs\\c.log` 这种混合分隔符(判据 t24e 钉着)。"""
    return "\\".join(str(p).rstrip("\\/") for p in parts)


def render_relay(plan, paths=None, port=8766, nonce="", expect_version=""):
    """把步骤表渲染成一份**真能跑的** `.cmd`。

    🔴 2026-09-08 重写。上一版渲染出来的是**一份带注释的清单,不是程序**:
    `call` 了不存在的标签、失败分支只是 `:: on_fail -> …` 注释、
    回滚段无条件执行(成功路径跑完会把新版又换回去)、每条路都 `exit /b 0`。
    **那样真跑起来会毁掉业主的安装,而判据 t6/t17 一片绿** ——
    它们问的是「计划里有没有这几件事」,没问「渲染出来的会不会照着计划执行」。
    判据 t24 现在钉着这件事。

    只依赖 System32:`cmd.exe` / `netstat` / `findstr` / `curl.exe` / `ping`。
    """
    paths = paths or {}
    live = paths.get("live", "")
    new = paths.get("new", "")
    old = paths.get("old", "")
    logf = _win_path(paths.get("data_root", ""), DATA_ROOT_EXEMPT_DIRS[0], "更新.log")
    sentinel = _win_path("%LIVE%", "ds", "bin", "ds_shell.py")
    by_kind = {}
    for step in plan:
        by_kind.setdefault(step["kind"], []).append(step)

    def marker(kind, n=0):
        return by_kind[kind][n]["marker"]

    out = [
        "@echo off",
        "setlocal enableextensions",
        ":: 🔴 先离开当前目录(t29):继承来的当前目录在活树里,站在里面就改不了它的名。",
        'cd /d "%~dp0"',
        ":: OpenDesign 更新接力脚本 —— 由 bin/ds_update_apply.py 生成,别手改。",
        ":: 它住 %TEMP%,只依赖 System32:活树在它手里被改名,所以它不能住在活树里。",
        "",
        'set "LIVE=%s"' % live,
        'set "NEWT=%s"' % new,
        'set "OLDT=%s"' % old,
        'set "LOGF=%s"' % logf,
        'set "PORT=%d"' % int(port),
        'set "NONCE=%s"' % nonce,
        'set "WANT=%s"' % expect_version,
        "",
        ":: 🔴 就绪信号(t38):走到这一行 = cmd 真的在执行这份脚本、变量已经设好。",
        ":: handoff 等到这个文件才请外壳关软件;等不到就把这个进程杀掉、更新取消,软件照常开着。",
        '>"%~f0' + RELAY_READY_SUFFIX + '" echo ready',
        'call :log "接力开始"',
        "",
        marker("teardown_gate"),
        "call :wait_gone",
        ":: 收不干净就绝不换名 —— 活树到这一刻为止一个字节没被动过",
        "if errorlevel 1 goto :teardown_failed",
        "",
        marker("rename", 0),
        ":: 🔴 有上限地重试(t28a)。收摊闸放行 ≠ 外壳已经退完:Windows 第三趟实测闸 40 毫秒放行,",
        ":: 而 pythonw.exe 还攥着活树 ⇒ 只试一次必失败。文件夹里还有程序在跑,改名就失败,活树不会被动。",
        "set /a _r=0",
        ":rename_live",
        'move /Y "%LIVE%" "%OLDT%" >nul 2>&1',
        "if not errorlevel 1 goto :rename_new",
        "set /a _r+=1",
        "if %_r% GEQ 60 goto :rename_failed",
        "ping -n 2 127.0.0.1 >nul 2>&1",
        "goto :rename_live",
        "",
        marker("rename", 1),
        ":rename_new",
        'move /Y "%NEWT%" "%LIVE%" >nul 2>&1',
        ":: 这一步失败 = 停在两次改名之间,活树叫 .old ⇒ 必须回滚",
        "if errorlevel 1 goto :rollback",
        "",
        marker("launch"),
        'start "" "%LIVE%\\OpenDesign.exe"',
        "",
        marker("health"),
        "call :ask_health",
        "if errorlevel 1 goto :rollback",
        "",
        marker("cleanup"),
        'rmdir /S /Q "%OLDT%" >nul 2>&1',
        'call :log "更新成功,已切到 %WANT%"',
        "exit /b 0",
        "",
        ":: 放弃的两条路都要把旧版打开(t28b):软件已经被收摊了,不打开 = 业主看到关了、没回来。",
        ":: 旧版要是其实还活着,单实例锁会让这次启动只把它叫到前台。",
        ":teardown_failed",
        'call :log "收摊没收干净,放弃更新(活树没动过)"',
        'rmdir /S /Q "%NEWT%" >nul 2>&1',
        'start "" "%LIVE%\\OpenDesign.exe"',
        "exit /b 2",
        "",
        ":rename_failed",
        'call :log "活树一直被占着改不了名,放弃更新(活树没动过)"',
        'rmdir /S /Q "%NEWT%" >nul 2>&1',
        'start "" "%LIVE%\\OpenDesign.exe"',
        "exit /b 3",
        "",
        marker("rollback"),
        ":rollback",
        'call :log "新版没能起来,换回旧版"',
        ":: 🔴 先停掉从活树里跑着的程序(t28c):新版要是起来了,它攥着活树,挪不动。",
        ":: 只按可执行文件路径停活树底下的进程 —— 本脚本自己的 cmd/curl/ping 都在 System32。",
        'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command '
        '"Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and '
        "$_.ExecutablePath.StartsWith('%LIVE%\\', 'OrdinalIgnoreCase') } | "
        'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" '
        '>nul 2>&1',
        'if exist "%LIVE%" call :move_retry "%LIVE%" "%NEWT%" 30',
        ":: 🔴 活树还在就绝不 move .old 进去(t28d):那会把旧树塞进活树里,两边都坏。",
        'if exist "%LIVE%" goto :rollback_stuck',
        'call :move_retry "%OLDT%" "%LIVE%" 30',
        "if errorlevel 1 goto :rollback_stuck",
        'start "" "%LIVE%\\OpenDesign.exe"',
        "exit /b 4",
        "",
        ":rollback_stuck",
        'call :log "换不回去:活树还被占着。旧版原封不动在 %OLDT%"',
        "exit /b 5",
        "",
        ":: ---- 子程序 ----",
        "",
        ":wait_gone",
        ":: 端口真的还回来了,而且哨兵文件没人锁着。两条都过才算收干净。",
        "set /a _t=0",
        ":wait_gone_loop",
        "set /a _t+=1",
        'netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1',
        "if not errorlevel 1 goto :wait_gone_busy",
        '2>nul (>>"%s" call ) || goto :wait_gone_busy' % sentinel,
        "exit /b 0",
        ":wait_gone_busy",
        "if %_t% GEQ 60 exit /b 1",
        "ping -n 2 127.0.0.1 >nul 2>&1",
        "goto :wait_gone_loop",
        "",
        ":ask_health",
        ":: 🔴 --noproxy:业主机器上挂着 VPN。问 127.0.0.1 却走系统代理,0.98.1 栽过。",
        ":: 🔴 认 nonce:换名之后旧进程可能还没死透,它也会回 200 和一个版本号。",
        "set /a _h=0",
        ":ask_health_loop",
        "set /a _h+=1",
        'curl.exe -s --noproxy "*" --max-time 5 '
        '"http://127.0.0.1:%PORT%/api/health?nonce=%NONCE%" > "%TEMP%\\od-health.txt" 2>nul',
        "if errorlevel 1 goto :ask_health_retry",
        'findstr /c:"%NONCE%" "%TEMP%\\od-health.txt" >nul 2>&1',
        "if errorlevel 1 goto :ask_health_retry",
        'findstr /c:"%WANT%" "%TEMP%\\od-health.txt" >nul 2>&1',
        "if errorlevel 1 goto :ask_health_retry",
        "exit /b 0",
        ":ask_health_retry",
        "if %_h% GEQ 60 exit /b 1",
        "ping -n 3 127.0.0.1 >nul 2>&1",
        "goto :ask_health_loop",
        "",
        ":move_retry",
        ":: %1 挪到 %2,最多试 %3 次(每次隔 ~1 秒)。成功退 0,试满退 1。",
        "set /a _m=0",
        ":move_retry_loop",
        "move /Y %1 %2 >nul 2>&1",
        "if not errorlevel 1 exit /b 0",
        "set /a _m+=1",
        "if %_m% GEQ %3 exit /b 1",
        "ping -n 2 127.0.0.1 >nul 2>&1",
        "goto :move_retry_loop",
        "",
        ":log",
        '>>"%LOGF%" echo [%date% %time%] %~1',
        "goto :eof",
    ]
    return "\n".join(out)


# --- 段①:下载 → 校验 → 装到旁边 → 查新树 → 写接力脚本 ---------------------

def _fail(stage, error):
    return {"ok": False, "stage": stage, "error": error, "relay": None}


RELAY_ENCODING = "gbk"
# 接力脚本里会被**再解释一遍**的字符(t36):
#   %  cmd 在双引号里照样展开变量;
#   '  回滚那行 PowerShell 把 %LIVE% 放在单引号串里,一个 ' 就拆坏 ⇒ 停不掉新版 ⇒ 挪不动;
#   ^  `call :move_retry "..."` 会把引号内的脱字符翻倍(cmd 的已知行为,未在真机上单独量过,拒绝是保守侧)。
RELAY_UNSAFE_CHARS = ("%", "'", "^")


def _oem_code_page():
    """控制台代码页 —— 接力脚本 `.cmd` 的字节是按它读的。非 Windows 返回 None(那里没有接力脚本)。"""
    if os.name != "nt":
        return None
    import ctypes
    return int(ctypes.windll.kernel32.GetOEMCP())


def relay_path_problem(paths):
    """接力脚本处理得了这些路径吗?处理不了返回一句人话,处理得了返回 None(t36)。

    处理不了的后果不是"更新失败"那么轻:路径一乱,放弃分支里那句 `start "%LIVE%\\OpenDesign.exe"`
    也指错地方 ⇒ 软件已经被收摊、又打不开 ⇒ **关了不回来**。所以在动任何东西之前拒绝。
    `paths["oem_cp"]` 可注入(判据用);不给就问 Windows。
    """
    oem_cp = paths["oem_cp"] if "oem_cp" in paths else _oem_code_page()
    for key in ("live", "new", "old", "data_root", "temp"):
        p = str(paths.get(key) or "")
        for ch in RELAY_UNSAFE_CHARS:
            if ch in p:
                return "安装路径里有 %s,自动更新处理不了:%s" % (ch, p)
        try:
            p.encode(RELAY_ENCODING)
        except UnicodeEncodeError:
            return "安装路径里有 GBK 表示不了的字符,自动更新处理不了:%s" % p
        if oem_cp is not None and oem_cp != 936 and not p.isascii():
            return "系统代码页是 %s,自动更新处理不了带中文等非英文字符的路径:%s" % (oem_cp, p)
    return None


def _note(paths, line):
    """往数据根里唯一允许写的那个具名目录记一笔(t13:`Logs\\` 豁免)。"""
    root = paths.get("data_root")
    if not root:
        return
    logs = os.path.join(root, DATA_ROOT_EXEMPT_DIRS[0])
    try:
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, "更新.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # 记日志失败不该把更新带崩


def update_preflight_problem(paths):
    """段① 前两道纯检查。自动倒计时也调用它,避免两边各自猜安装形状。"""
    live = str(paths.get("live") or "")
    if not (os.path.isfile(os.path.join(live, LAUNCHER_REL))
            and os.path.isfile(os.path.join(live, SENTINEL_REL))):
        return ("not_installed",
                "这份软件不是用安装包装的(%s),请到发布页手动下载" % live)
    bad_path = relay_path_problem(paths)
    if bad_path:
        return ("path_unsupported", bad_path)
    return (None, None)


def _default_download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "OpenDesign-updater"})
    # 🔴 **走系统代理**(t30)。这里原来复用了 build_opener() —— 那是 t18 给"问本机 health"用的、
    #    专门绕开代理的 opener。而查更新走默认 urllib、认代理 ⇒ 业主开 VPN 时查得到新版、
    #    下载却直接去连 github.com。去外网的请求一律走默认 opener,和查更新同一个口径。
    # 🔴 而且**当场现建**(t30b),不用 urlopen:urlopen 复用进程级缓存的 opener,代理在它第一次被建时
    #    读一次就定死 ⇒ 业主先开软件、后开 VPN,下载照样不走代理。build_opener() 不带参数 = 默认处理器
    #    (含按此刻系统代理建的 ProxyHandler);和上面那个传了空 ProxyHandler 的 build_opener 不是一回事。
    with urllib.request.build_opener().open(req, timeout=300) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    return dest


def _default_install(setup_path, target_dir):
    """静默装进**别的目录**:`/S` 静默、`/UPDATE` 不跑 provisioning、`/D=` 指目标。

    `/D=` 必须是最后一个参数且不加引号 —— 这是 NSIS 的规矩,不是我们的选择。
    本仓 `.github/scripts/windows-nonempty-probe.ps1:81` 已在真 Windows 上跑过这条路。
    ⚠️ `/UPDATE` 的意义:首装才需要 provisioning,更新时跑它就会写 `UserData\\`,
       而那是死线(t13)。**改实现,不改考卷。**

    🔴 所以命令行**自己拼**,不交列表(t33)。交列表 = subprocess 用 list2cmdline 拼,
       路径带空格就给 `/D=` 加引号 ⇒ NSIS 不认(`Main.c` 要求 `/D=` 前面紧挨空格)⇒
       安装目录退回注册表 = **正在运行的活树**。前面几个参数照常交给 list2cmdline 加引号;
       `/D=` 原样接在最后,NSIS 抄到行尾,空格不用引号。只在 Windows 上走得到这里。
    """
    import subprocess

    from ds_shell_core import spawn_kwargs  # 平台标志的**唯一来源**

    # 🔴 必须走 spawn_kwargs():漏掉那一位,Windows 上会冒一个黑窗口,
    #    而**业主关掉它就等于杀掉正在装的安装器** —— 更新装到一半被腰斩。
    #    (0.90.0 那一单立的闸 tests/test_no_console_window.py 当场咬住了我这一行。)
    cmd = subprocess.list2cmdline([setup_path, "/S", INSTALL_UPDATE_FLAG]) + " /D=%s" % target_dir
    return subprocess.call(cmd, **spawn_kwargs())


def verify_new_tree(new_dir, expect_version):
    """新树完整吗(t5):哨兵在,且版本号文件正是我们要的那一版。

    只查"目录还在"是不够的 —— 装了个旧的、装了半棵树,两种都能让目录存在。
    """
    sentinel = os.path.join(new_dir, SENTINEL_REL)
    if not os.path.isfile(sentinel):
        return "新树缺哨兵:%s" % SENTINEL_REL
    try:
        got = tree_version(new_dir)
    except OSError as exc:
        return "新树读不出版本号:%s" % (exc,)
    # 🔴 按**版本号**比,不按字面比(t37):decide() 把 `1.1` 补零成 `1.1.0`,新树里写的是构建时原样的 `1.1`。
    #    同一套解析(ds_update.parse_version)两边都过一遍,认不出的一律算不对。
    import ds_update
    want = ds_update.parse_version(str(expect_version))
    if want is None or ds_update.parse_version(got) != want:
        return "新树版本号是 %s,要的是 %s" % (got, expect_version)
    return None


def tree_version(tree_dir):
    """一棵树自己写着的版本号**原文** —— 也就是它起来之后 /api/health 会报的那个字符串。"""
    with open(os.path.join(tree_dir, VERSION_REL), encoding="utf-8") as fh:
        return fh.read().strip()


def apply_update(decision, paths, download=None, install=None):
    """段① 全程。**成功与失败都不许碰活树**(t16 / t4)。

    返回 `{"ok", "stage", "error", "relay"}`。`stage` 是失败停在哪一步 ——
    段② 死在半路时业主看到的是"软件关了没回来",而日志里得分得清
    "装错了"和"没装成"(design「这个 oracle 能被什么骗过」第 4 条)。
    """
    download = download or _default_download
    install = install or _default_install
    asset = (decision or {}).get("asset") or {}
    expect_version = decision.get("latest")

    # -2/-1. 活树形状与接力脚本路径都是纯检查;GET 的自动资格也复用同一处。
    problem, error = update_preflight_problem(paths)
    if problem == "not_installed":
        _note(paths, "%s 不像安装器装出来的目录,不做应用内更新" % str(paths.get("live") or ""))
        return _fail(problem, error)
    if problem == "path_unsupported":
        _note(paths, "路径接力脚本处理不了,放弃自动更新:%s" % error)
        return _fail(problem, error)

    # 0. 上次留下的 .old 先清掉(t32)。接力脚本第一次改名是 `move 活树 .old`,
    #    目标已存在时 move 会把活树**挪进去**;一旦走到回滚,换回来的就是那棵残缺的旧 .old。
    #    我们正从活树里跑着 ⇒ 活树在 ⇒ .old 一定是过期的。清不掉就不开始 —— 别先下 43MB。
    old_dir = paths.get("old")
    if old_dir and os.path.lexists(old_dir):
        if os.path.isdir(old_dir) and not os.path.islink(old_dir):
            shutil.rmtree(old_dir, ignore_errors=True)
        if os.path.lexists(old_dir):
            _note(paths, "上次更新留下的 %s 清不掉,放弃更新" % old_dir)
            return _fail("stale_old", "上次更新留下的 %s 清不掉,请手动删除后再试" % old_dir)

    # 1. digest 先于下载:没有可信的哈希就别开始下 43MB(t15)
    digest = parse_digest(asset.get("digest"))
    if digest is None:
        _note(paths, "digest 缺失或形状不对,放弃更新")
        return _fail("digest", "digest 缺失或格式不对,拒绝下载")

    url = asset.get("url")
    if not url:
        return _fail("digest", "没有下载地址")

    # 2. 下载。地址**逐字节照抄 GitHub 给的**,不许拿版本号拼(t14)
    dest = os.path.join(paths["temp"], asset.get("name") or "OpenDesign-Setup.exe")
    try:
        download(url, dest)
    except Exception as exc:  # noqa: BLE001 —— 下载失败是小事,甩栈是大事
        _note(paths, "下载失败:%r" % (exc,))
        return _fail("download", "下载失败:%r" % (exc,))

    # 3. 校验。对不上 = 下坏了 / 被换了 ⇒ 到此为止,活树一个字节没动过(t4)
    got = sha256_file(dest)
    if got != digest:
        _cleanup(dest, paths["new"])
        _note(paths, "校验不过:期望 %s 实得 %s" % (digest, got))
        return _fail("verify", "sha256 对不上:期望 %s,实得 %s" % (digest, got))

    # 4. 装到**旁边**。到这一步为止活树仍然一个字节没动过(t16)
    new_dir = paths["new"]
    if os.path.exists(new_dir):
        shutil.rmtree(new_dir, ignore_errors=True)
    try:
        rc = install(dest, new_dir)
    except Exception as exc:  # noqa: BLE001
        _cleanup(dest, new_dir)
        _note(paths, "安装器抛了:%r" % (exc,))
        return _fail("install", "安装器抛了:%r" % (exc,))
    if rc not in (0, None):
        _cleanup(dest, new_dir)
        _note(paths, "安装器 rc=%r" % (rc,))
        return _fail("install", "安装器 rc=%r" % (rc,))

    # 5. 查新树。不完整就删掉当无事发生(t5)
    bad = verify_new_tree(new_dir, expect_version)
    if bad:
        _cleanup(dest, new_dir)
        _note(paths, "新树不完整:%s" % bad)
        return _fail("newtree", bad)

    # 5b. 安装包用完了(t39):新树已经验过,接力脚本也不需要它。不删 = 每更新一次在 %TEMP% 留 43MB。
    _cleanup(dest, None)

    # 6. 写接力脚本。**交棒之后活树才会被动**,而那已经是段② 的事了
    port = int(paths.get("port") or 8766)
    nonce = paths.get("nonce") or hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    # 🔴 接力脚本要等的是新版 /api/health **真会报的**那个字符串 = 新树版本号原文(t37),
    #    不是 decide() 补过零的 latest —— `1.1` 的新版永远不会说自己是 `1.1.0`。
    expect_version = tree_version(new_dir)
    plan = relay_plan(paths, port=port, nonce=nonce, expect_version=expect_version)
    relay = os.path.join(paths["temp"], "opendesign-update-relay.cmd")
    with open(relay, "w", encoding=RELAY_ENCODING, errors="replace", newline="\r\n") as fh:
        # 🔴 四个参数一个都不能少(t25)。09-14 Windows 端到端第一趟:这里原来只传了 plan,
        #    盘上的脚本里 LIVE/NEWT/OLDT/NONCE/WANT 全是空的 ⇒ 每次点更新软件都关掉不回来,
        #    而判据 t24 调渲染器时参数给全了,本机一片绿。
        fh.write(render_relay(plan, paths=paths, port=port, nonce=nonce,
                              expect_version=expect_version))
    _note(paths, "新树就绪,接力脚本 %s" % relay)
    return {"ok": True, "stage": "relay", "error": None, "relay": relay}


def _cleanup(setup_path, new_dir):
    """失败即当无事发生:临时安装包和 `.new` 都别留下。"""
    try:
        if setup_path and os.path.isfile(setup_path):
            os.remove(setup_path)
    except OSError:
        pass
    if new_dir and os.path.exists(new_dir):
        shutil.rmtree(new_dir, ignore_errors=True)


# --- 交棒:把接力脚本脱离启动 -----------------------------------------------

def _default_launcher(argv, **kwargs):
    """起了就走。**这里不许出现任何等待** —— 接力脚本正在等我们死。

    我们要是等它结束,就是互相等死:软件永远关不掉、更新永远不发生,
    而界面上写着"正在更新"。判据 t21e 机械地钉着这件事(禁 call/run/wait/communicate)。
    """
    import subprocess

    # no-console-exempt: 平台标志由 handoff() 统一取自 spawn_kwargs() 再 **kwargs 传进来
    # (判据 t21c 逐项比对它们真的到了这一层)。这里**不许自己拼** —— 一拼就成了第二个来源,
    # 而黑窗口那道闸防的正是"各调用点自己拼"。闸看不到跨函数那一步,所以在这里说明。
    return subprocess.Popen(argv, **kwargs)


def relay_argv(relay_path):
    """怎么把那个 `.cmd` 起起来。抽出来是为了让 t21 问得到。"""
    return ["cmd.exe", "/c", relay_path]


def handoff(relay_path, launcher=None, ready_timeout=20.0):
    """把接力脚本脱离启动。**起不来一律返回 False,上层绝不许往下走。**

    🔴 这是整条路上最不能出错的一步:它之后 `ds_web` 就要请外壳把整套软件关掉。
    **脚本没起来却把软件关了 = 业主看到"软件关了,没再打开",而且没有任何东西
    会去回滚。** 所以这里对"起来了"的判断宁可保守:任何异常都算没起来。

    🔴 "起来了"= **接力脚本自己写下就绪标记**(t38),不是"启动器没抛异常":
       cmd.exe 起来了却没跑成脚本的路有好几条(路径里的 & 没被加引号、空格加括号时引号被 cmd 剥掉、
       杀软拦截)。限时等不到 ⇒ 把起的那个进程杀掉 ⇒ 真的没有接力在跑 ⇒ 报没交棒(上层放锁,t35b)。
       这里等的是一个文件,不是等进程结束 —— 接力脚本正在等我们死,等它结束就是互相等死(t21e 管启动器)。
    """
    launcher = launcher or _default_launcher
    if not relay_path or not os.path.isfile(relay_path):
        return False
    ready = relay_path + RELAY_READY_SUFFIX
    try:
        if os.path.lexists(ready):
            os.remove(ready)          # 上一次留下的不算数(t38c)
    except OSError:
        return False                  # 清不掉旧信号 = 分不清这次到底起没起来

    from ds_shell_core import spawn_kwargs  # 平台标志的唯一来源(同 _default_install)

    try:
        # leave_job=True(t27):接力脚本要活过外壳收摊。不脱离的话它在 ds-web 的 Job 里,
        # 外壳一关 Job 它就跟着死 —— 软件关了、没人换名、没人拉起(Windows 端到端第二趟实测)。
        # 某些环境外层 Job 不许脱离 ⇒ 这里抛 ⇒ 下面按"没交棒"处理,更新取消、软件照常能用。
        # cwd(t29):不给的话继承 ds-web 的当前目录 —— 启动器 SetOutPath 把它设成了活树,
        # **进程的当前目录在哪个文件夹里,那个文件夹就改不了名** ⇒ 接力脚本自己占住活树
        # (Windows 端到端第四趟:改名重试满 60 秒一次没成)。
        proc = launcher(relay_argv(relay_path), cwd=os.path.dirname(os.path.abspath(relay_path)),
                        **spawn_kwargs(leave_job=True))
    except Exception:  # noqa: BLE001 —— 起不来是"没交棒",不是"甩栈给业主"
        return False
    deadline = time.monotonic() + ready_timeout
    while time.monotonic() < deadline:
        if os.path.exists(ready):
            try:
                os.remove(ready)
            except OSError:
                pass
            return True
        time.sleep(0.05)
    kill = getattr(proc, "kill", None)
    if callable(kill):
        try:
            kill()
        except Exception:  # noqa: BLE001 —— 杀不掉也照样报没交棒;它等不到外壳退出,60 秒后自己放弃
            pass
    return False


def paths_for_update(ds_root, data_root=None, temp_dir=None, port=None, nonce=None):
    """从 ds-web 手上已有的 `ds_root` 推出段① 要的那几个路径(判据 t23)。

    - **安装根 = `ds_root` 的上一级**:`<安装根>\\ds` 是安装器写死的布局,
      `OpenDesign.nsi` 的哨兵 `ds\\bin\\ds_shell.py` 也是按它算的。
    - `.new` / `.old` 是安装根的**同级**。三个"不许"由 t23 机械钉着:
      不许放进安装根(安装器会一起覆盖掉)、不许放进数据根(整整一棵树写进去,
      死线 t13 当场破)、不许和活树同名。
    - `data_root` 指的是**装着 `Data\\` 和 `UserData\\` 的那一层**(不是它们自己)。
      段① 只往它底下的 `Logs\\` 写一行更新日志。
    """
    live = os.path.normpath(os.path.dirname(os.path.normpath(str(ds_root))))
    if data_root is None:
        # 与 ds_shell 的 _app_dir()、OpenDesign.nsi 的 DATA_ROOT 是同一处约定。
        data_root = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "OpenDesign")
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    return update_paths(live, data_root, temp_dir, port=port, nonce=nonce)


def update_paths(install_root, data_root, temp_dir, port=None, nonce=None):
    """段① 要用到的那几个路径。`.new` / `.old` 都是 `$INSTDIR` 的**同级**。

    不放数据根(会踩死线 t13)、不放 `$INSTDIR` 里(会被安装器一起覆盖)。
    """
    live = os.path.normpath(str(install_root))
    paths = {"live": live, "new": live + ".new", "old": live + ".old",
             "data_root": str(data_root), "temp": str(temp_dir)}
    if port is not None:
        paths["port"] = port
    if nonce is not None:
        paths["nonce"] = nonce
    return paths
