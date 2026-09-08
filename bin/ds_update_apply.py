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
import urllib.request

# 哨兵与版本号文件 —— 与 installer/OpenDesign.nsi 的 SENTINEL 是同一处约定。
SENTINEL_REL = os.path.join("ds", "bin", "ds_shell.py")
VERSION_REL = os.path.join("ds", "版本号.txt")

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
    """接力脚本的步骤表(有序)。每步:kind / marker / cmd,失败分支写 on_fail。"""
    live = paths["live"]
    new = paths["new"]
    old = paths["old"]
    logs = os.path.join(paths.get("data_root", ""), DATA_ROOT_EXEMPT_DIRS[0])
    steps = [
        {
            "kind": "teardown_gate",
            # 🔴 这一步的锚点 09-08 搬过:安装现在发生在**收摊之前**,
            #    所以它问的不再是"不许进安装步",而是"不许进换名步"。
            "cmd": ('call :wait_gone "%s" %d' % (live, int(port))),
            "on_fail": ["delete_new", "abort"],
        },
        {"kind": "rename", "cmd": 'move /Y "%s" "%s"' % (live, old)},
        {"kind": "rename", "cmd": 'move /Y "%s" "%s"' % (new, live)},
        {"kind": "launch", "cmd": 'start "" "%s\\OpenDesign.exe"' % live},
        {
            "kind": "health",
            "cmd": ('call :ask_health %d %s %s' % (int(port), nonce, expect_version)),
            "on_fail": ["rollback"],
        },
        {
            "kind": "rollback",
            # 换名中断/新版起不来 ⇒ 改回名字就是回滚(t17)。
            "cmd": ('move /Y "%s" "%s" & move /Y "%s" "%s" & start "" "%s\\OpenDesign.exe"'
                    % (live, new, old, live, live)),
        },
        {"kind": "cleanup", "cmd": 'rmdir /S /Q "%s"' % old},
        {"kind": "log", "cmd": 'echo done>>"%s\\更新.log"' % logs},
    ]
    for i, step in enumerate(steps):
        step.setdefault("on_fail", [])
        step["marker"] = ":: STEP-%02d-%s" % (i, step["kind"])
    return steps


def render_relay(plan):
    """把步骤表渲染成 `.cmd`。**每一步的 marker 必须原样出现,且顺序不变**(t6c)。"""
    out = [
        "@echo off",
        "setlocal enableextensions",
        ":: OpenDesign 更新接力脚本 —— 由 bin/ds_update_apply.py 生成,别手改。",
        ":: 它住 %TEMP%,只依赖 System32:活树在它手里被改名,所以它不能住在活树里。",
        "",
    ]
    for step in plan:
        out.append(step["marker"])
        out.append(step["cmd"])
        for branch in step["on_fail"]:
            out.append(":: on_fail -> %s" % branch)
        out.append("")
    out.append("exit /b 0")
    return "\n".join(out)


# --- 段①:下载 → 校验 → 装到旁边 → 查新树 → 写接力脚本 ---------------------

def _fail(stage, error):
    return {"ok": False, "stage": stage, "error": error, "relay": None}


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


def _default_download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "OpenDesign-updater"})
    with build_opener().open(req, timeout=300) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    return dest


def _default_install(setup_path, target_dir):
    """静默装进**别的目录**:`/S` 静默、`/UPDATE` 不跑 provisioning、`/D=` 指目标。

    `/D=` 必须是最后一个参数且不加引号 —— 这是 NSIS 的规矩,不是我们的选择。
    本仓 `.github/scripts/windows-nonempty-probe.ps1:81` 已在真 Windows 上跑过这条路。
    ⚠️ `/UPDATE` 的意义:首装才需要 provisioning,更新时跑它就会写 `UserData\\`,
       而那是死线(t13)。**改实现,不改考卷。**
    """
    import subprocess

    from ds_shell_core import spawn_kwargs  # 平台标志的**唯一来源**

    # 🔴 必须走 spawn_kwargs():漏掉那一位,Windows 上会冒一个黑窗口,
    #    而**业主关掉它就等于杀掉正在装的安装器** —— 更新装到一半被腰斩。
    #    (0.90.0 那一单立的闸 tests/test_no_console_window.py 当场咬住了我这一行。)
    cmd = [setup_path, "/S", INSTALL_UPDATE_FLAG, "/D=%s" % target_dir]
    return subprocess.call(cmd, **spawn_kwargs())


def verify_new_tree(new_dir, expect_version):
    """新树完整吗(t5):哨兵在,且版本号文件正是我们要的那一版。

    只查"目录还在"是不够的 —— 装了个旧的、装了半棵树,两种都能让目录存在。
    """
    sentinel = os.path.join(new_dir, SENTINEL_REL)
    if not os.path.isfile(sentinel):
        return "新树缺哨兵:%s" % SENTINEL_REL
    vpath = os.path.join(new_dir, VERSION_REL)
    try:
        with open(vpath, encoding="utf-8") as fh:
            got = fh.read().strip()
    except OSError as exc:
        return "新树读不出版本号:%s" % (exc,)
    if got != str(expect_version):
        return "新树版本号是 %s,要的是 %s" % (got, expect_version)
    return None


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

    # 6. 写接力脚本。**交棒之后活树才会被动**,而那已经是段② 的事了
    port = int(paths.get("port") or 8766)
    nonce = paths.get("nonce") or hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    plan = relay_plan(paths, port=port, nonce=nonce, expect_version=expect_version)
    relay = os.path.join(paths["temp"], "opendesign-update-relay.cmd")
    with open(relay, "w", encoding="gbk", errors="replace", newline="\r\n") as fh:
        fh.write(render_relay(plan))
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
    return subprocess.Popen(argv, **kwargs)


def relay_argv(relay_path):
    """怎么把那个 `.cmd` 起起来。抽出来是为了让 t21 问得到。"""
    return ["cmd.exe", "/c", relay_path]


def handoff(relay_path, launcher=None):
    """把接力脚本脱离启动。**起不来一律返回 False,上层绝不许往下走。**

    🔴 这是整条路上最不能出错的一步:它之后 `ds_web` 就要请外壳把整套软件关掉。
    **脚本没起来却把软件关了 = 业主看到"软件关了,没再打开",而且没有任何东西
    会去回滚。** 所以这里对"起来了"的判断宁可保守:任何异常都算没起来。
    """
    launcher = launcher or _default_launcher
    if not relay_path or not os.path.isfile(relay_path):
        return False

    from ds_shell_core import spawn_kwargs  # 平台标志的唯一来源(同 _default_install)

    try:
        launcher(relay_argv(relay_path), **spawn_kwargs())
    except Exception:  # noqa: BLE001 —— 起不来是"没交棒",不是"甩栈给业主"
        return False
    return True


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
