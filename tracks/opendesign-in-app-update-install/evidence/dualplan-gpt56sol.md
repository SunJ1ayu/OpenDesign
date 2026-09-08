# 规划双出:gpt-5.6-sol 独立方案

- 跑于: 2026-09-08 19:05:17
- 纪律: 明令不许读 tracks/;主 agent 的 design.md 已先行 commit f194983

---

Reading additional input from stdin...
OpenAI Codex v0.150.1
--------
workdir: /root/.openclaw/workspace/projects/design-studio
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: xhigh
reasoning summaries: none
session id: 01a080b1-9bb7-7431-917a-0eaabd7f92ce
--------
user
你在给一个真实的 Windows 桌面产品(OpenDesign,仓库就是当前目录)做**方案设计**,不写实现。

## 需求(原样给你,这是唯一的输入)

软件现在已经能"发现线上有新版并说一句话",但业主仍然要自己:打开浏览器 → 找到 GitHub
仓库 → 翻 releases → 下载 43MB 的安装包 → 双击重装。这一单要把这五步手工活去掉:
业主点一下「更新」→ 下载 → 校验 → 收摊 → 静默安装 → 重新起来 →
**新起来的进程自己在 /api/health 报出新版本号才算成功**。

硬性要求:
- 收口判据是最后那半句(新进程自报版本号),不是"安装器退出码 0"。
  盘上有新文件 ≠ 部署成功,这个项目为这条栽过两次。
- 更新前后,业主的数据必须一个字节都不能变。
- 不做增量/差分更新;不做自动静默更新(必须他点);没有代码签名证书。
- 失败必须能回到更新前的状态。

## 你要交的东西

一份方案(中文),包含:
1. **Approach**:你选的技术方向,以及它为什么解决得了"软件不能在自己活着的时候更新自己"这件事
2. **Key trade-offs / risks**:最可能出事的地方
3. **Alternatives considered**:你考虑过但没选的方向 + 为什么没选
4. **Test strategy**:怎么证明它对;并且专门回答一句:
   **"断言全绿但业主眼里仍然失败,会失败成什么样?"**

## 纪律

- 🔴 **不许读 `tracks/` 目录下的任何文件。** 那里有别人对同一个需求写的方案,
  读了这次双出就作废了。你要的是**独立的**一版。
- 该读的是实现和安装器本身:`bin/ds_update.py`、`bin/ds_web.py`、`bin/ds_shell.py`、
  `bin/ds_shell_core.py`、`installer/OpenDesign.nsi`、`installer/build-installer.sh`、
  `.github/workflows/`。
- 只读不写:**不要修改任何文件**,不要跑构建,不要联网。
- 说"因为"的时候请标明是**读到的**还是**推的** —— 这个项目吃过太多次"把推论写成事实"的亏。
warning: Codex could not find bubblewrap on PATH. Install bubblewrap with your OS package manager. See the sandbox prerequisites: https://developers.openai.com/codex/concepts/sandboxing#prerequisites. Codex will use the bundled bubblewrap in the meantime.
codex
我会只读你指定的实现、安装器和工作流，明确绕开 `tracks/`，不构建、不联网、不改文件。方案里会把依据逐条标成「读到」或「推论」，尤其把回滚边界、数据不变和 `/api/health` 的最终验收链路说清楚。
  → 读取指定实现、安装器和工作流（排除 tracks/）
  • 梳理现状约束、进程关系、版本来源与数据落点
  • 形成更新/验收/回滚方案及备选方向
  • 设计覆盖故障注入与业主视角的测试策略
exec
/bin/bash -lc 'git status --short' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
M  tests/test_update_ui.mjs
A  tracks/opendesign-in-app-update-install/evidence/20260908T110326Z-01-red-u23-u25-notes-setext.txt
AM tracks/opendesign-in-app-update-install/evidence/dualplan-gpt56sol.md
?? tracks/opendesign-in-app-update-install/observations/

exec
/bin/bash -lc 'wc -l bin/ds_update.py bin/ds_web.py bin/ds_shell.py bin/ds_shell_core.py installer/OpenDesign.nsi installer/build-installer.sh' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
   240 bin/ds_update.py
  2621 bin/ds_web.py
  1387 bin/ds_shell.py
  1256 bin/ds_shell_core.py
   295 installer/OpenDesign.nsi
   153 installer/build-installer.sh
  5952 total

exec
/bin/bash -lc 'rg --files .github/workflows' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
.github/workflows/windows-package-probe.yml
.github/workflows/windows-nonempty-probe.yml
.github/workflows/windows-gui-probe.yml

exec
/bin/bash -lc "sed -n '1,260p' bin/ds_update.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
#!/usr/bin/env python3
"""查更新:问一次 GitHub,答"线上有没有比我新的版本"(track opendesign-in-app-update)。

这个模块**只查不装**。装是第二刀的事,住在别处。

🔴 **写这个文件的人必须知道的一件事**(2026-09-07 实测,判据 t1/t1b 钉着):

    GET /repos/SunJ1ayu/OpenDesign/releases/latest  →  404 Not Found

那个接口**按 GitHub 的设计跳过 prerelease**,而本仓至今 **20 个 release 全是 prerelease**。
所以这里必须用 `/releases`(列表,含预发布)**自己挑**。改回那个"标准接口"的后果不是报错,
是**功能永远查不到新版本、界面永远显示"已是最新"** —— 一条恒绿路径,比没有更新功能更坏。

信任根就一条:**HTTPS 到 github.com**。资产的 sha256 由 GitHub 在 `digest` 字段里给
(实测与我们发版时记的那串一致),它挡得住"下坏了/下了半截/被中间人换了包",
**挡不住"GitHub 账号被盗后换了资产"** —— 我们没有代码签名证书,这是明账,不假装有。
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request

REPO = "SunJ1ayu/OpenDesign"
API_BASE = "https://api.github.com"
# 故意拼出来而不是写成一整串:t1b 那道结构闸扫的是本文件的源码。
RELEASES_PATH = "/repos/{repo}/releases"
# 版本号=**2~4 段数字**。单段不算(会撞上一堆随便的数字),形状必须整段吻合。
# 🔴 收两段是 S1 自审改的:原来只认三段,业主哪天宣布 1.0、tag 打成 `win-installer-1.0`,
#    那一版在更新检查里就**根本不存在,而且一声不吭** —— 和本单开头那个
#    /releases/latest 404 是同一种病。web/src/update.ts 的 releasePageUrl 与这里同口径。
_NUM = r"\d+(?:\.\d+){1,3}"
ASSET_RE = re.compile(rf"^OpenDesign-Setup-({_NUM})\.exe$")
TAG_RE = re.compile(rf"^win-installer-({_NUM})$")
BARE_RE = re.compile(rf"^({_NUM})$")
TIMEOUT_S = 10


def parse_version(text):
    """认三种写法:`0.98.3` / `win-installer-0.98.3` / `OpenDesign-Setup-0.98.3.exe`。

    整段吻合才算,**不做"从一串字里捞个版本号出来"** —— 那样 `0.98.x` 会被捞成 0.98,
    而它其实是个坏版本号。

    取不出来返回 None —— **绝不抛**。读不出版本号是"我不知道",不是"出事了":
    上层遇到 None 一律不提示更新(判据 t3d)。
    """
    if not isinstance(text, str):
        return None
    t = text.strip()
    for rx in (BARE_RE, TAG_RE, ASSET_RE):
        m = rx.match(t)
        if m:
            parts = [int(n) for n in m.group(1).split(".")]
            # 补零到三段:`0.98` 和 `0.98.0` 是同一版,不是前者更小(判据 t2g)。
            while len(parts) < 3:
                parts.append(0)
            return tuple(parts)
    return None


def _installer_asset(release):
    """挑出这个 release 里那个业主真正双击的安装包;没有就 None。

    没有安装包的 release 不是"可更新到的版本" —— 选中它等于把业主指向一个下不动的东西
    (判据 t1c)。
    """
    for asset in release.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if ASSET_RE.match(asset.get("name") or ""):
            return asset
    return None


def release_version(release):
    """一个 release 代表哪一版:先看 tag,tag 认不出再看安装包文件名。"""
    if not isinstance(release, dict):
        return None
    return (parse_version(release.get("tag_name"))
            or parse_version((_installer_asset(release) or {}).get("name")))


def pick_latest(releases):
    """从 `/releases` 的响应里挑出最新的**可安装**版本。

    **预发布算数**(见文件头);草稿不算(业主下不到,判据 t1d);
    没有安装包资产的不算(判据 t1c)。
    """
    best = None
    best_ver = None
    for rel in releases or []:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        if _installer_asset(rel) is None:
            continue
        ver = release_version(rel)
        if ver is None:
            continue
        if best_ver is None or ver > best_ver:
            best, best_ver = rel, ver
    return best


def decide(current, releases):
    """给定"我现在是哪一版"和线上列表,答"要不要提示业主更新"。

    只在**线上严格比本地新**时才提示:相等不提示,本地更新也不提示
    (开发机上本地永远比线上新,那时提示"更新"其实是往回装 —— 判据 t3b)。
    """
    out = {"current": current, "update_available": False, "latest": None,
           "asset": None, "notes": "", "error": None, "release_url": None}
    here = parse_version(current)
    if here is None:
        out["error"] = "读不出本机版本号,不提示更新"
        return out
    rel = pick_latest(releases)
    if rel is None:
        out["error"] = "线上没有可安装的版本"
        return out
    there = release_version(rel)
    out["latest"] = ".".join(str(n) for n in there)
    if there <= here:
        return out
    asset = _installer_asset(rel)
    out["update_available"] = True
    out["notes"] = rel.get("body") or ""
    # 🔴 F1(评审抓到、我复现确认):**地址由 GitHub 给,不许我们拿版本号拼**。
    #    我修 S1 时给版本号补了零(1.0 → 1.0.0),界面拿 latest 去拼就成了
    #    `win-installer-1.0.0` —— 而真实 tag 是 `win-installer-1.0`,点开 404。
    #    认出来了却给一个打不开的链接,又一条"看起来在工作"。
    out["release_url"] = rel.get("html_url")
    out["asset"] = {
        "name": asset.get("name"),
        "url": asset.get("browser_download_url"),
        "size": asset.get("size") or 0,
        # "sha256:<hex>" —— GitHub 自己给的,第二刀下载完拿它对。
        "digest": asset.get("digest"),
    }
    return out


def releases_url(repo=REPO):
    """要问的那个地址,**逐字节可断言**(判据 t11)。

    评审 F5 指出:t1b 那道 AST 闸只咬"一整条字符串里含 releases/latest",
    把 `/latest` 拆成另一个字面量拼上去,t1 和 t1b 都躲得过。
    ⇒ 与其扫源码,不如直接断言拼出来的结果是什么。
    """
    return API_BASE + RELEASES_PATH.format(repo=repo) + "?per_page=100"


def fetch_releases(repo=REPO, timeout=TIMEOUT_S):
    """唯一碰网络的函数。判据一律注入替身,不打真网(2026-08-10 那次事故立的规矩)。"""
    url = releases_url(repo)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenDesign-updater",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (常量 https)
        return json.loads(resp.read().decode("utf-8"))


def check_for_update(current, fetch=None):
    """查一次。**任何异常都不许漏出去** —— 查更新失败是小事,把一坨栈甩给业主是大事。

    ⚠️ 名字不叫 `check`:`tests/dead_assertions.py` 把**任何叫 `check(` 的调用**当成断言
    (测试里常见的自定义断言助手),撞名会让那道闸对我的判据发出误报。
    2026-09-07 实测撞过一次,改名比削弱那道闸便宜得多。

    `fetch=None` 时到**调用那一刻**才去取 `fetch_releases`。默认参数在 def 那一刻就固化了,
    那样判据里替换 `ds_update.fetch_releases` 根本不生效,离线判据会悄悄变成真去打网
    (判据 t9d 钉的就是这件事)。
    """
    try:
        releases = (fetch or fetch_releases)()
    except Exception as exc:  # noqa: BLE001 —— 故意兜底,判据 t7d 就是钉它
        return {"current": current, "update_available": False, "latest": None,
                "asset": None, "notes": "", "release_url": None,
                "error": f"查更新失败:{exc.__class__.__name__}: {exc}"}
    if isinstance(releases, str):
        try:
            releases = json.loads(releases)
        except Exception:  # noqa: BLE001
            return {"current": current, "update_available": False, "latest": None,
                    "asset": None, "notes": "", "release_url": None,
                    "error": "查更新失败:线上返回的不是 JSON"}
    if not isinstance(releases, list):
        return {"current": current, "update_available": False, "latest": None,
                "asset": None, "notes": "", "release_url": None,
                "error": "查更新失败:线上返回的不是版本列表"}
    try:
        return decide(current, releases)
    except Exception as exc:  # noqa: BLE001
        return {"current": current, "update_available": False, "latest": None,
                "asset": None, "notes": "", "release_url": None,
                "error": f"查更新失败:{exc.__class__.__name__}: {exc}"}


# ── 缓存 ────────────────────────────────────────────────────────────────────
# 未登录的 GitHub API 每小时 60 次。每开一次界面、每点一下都真去问,业主很快会被限流,
# 而限流的样子恰恰是"查不到新版本" —— 一条安静的错。
#
# 🔴 方向必须写死:**失败不许进缓存**(判据 t8d)。一次断网如果把"查不到"钉死 6 小时,
#    业主点「检查更新」也没反应,他看到的和"功能坏了"一模一样。
CACHE_TTL_S = 6 * 3600
_cache_lock = threading.Lock()
_cache = {}  # {缓存键: (时刻, 结果)}


def _cache_key(current):
    """按**本机版本号**分键:装完新版之后旧答案立刻作废(判据 t8e,变异 m12 咬这一行)。

    单独抽成一个函数不是为了好看 —— 是为了让"按什么分键"这件事**在一处可判**:
    读和写都走它,红检改这一行就能表达"不按版本分键了",不用改两处。
    """
    return current


def cache_clear():
    with _cache_lock:
        _cache.clear()


def check_cached(current, fetch=None, now=time.time, force=False, ttl=None):
    """带缓存地查一次。`force=True` 是业主亲手点了「检查更新」—— 那一下必须真去问。"""
    ttl = CACHE_TTL_S if ttl is None else ttl
    t = now()
    if not force:
        with _cache_lock:
            hit = _cache.get(_cache_key(current))
        if hit and t - hit[0] < ttl:
            return hit[1]
    result = check_for_update(current, fetch=fetch)
    if not result.get("error"):
        with _cache_lock:
            _cache[_cache_key(current)] = (t, result)
    return result

exec
/bin/bash -lc "sed -n '1,340p' installer/OpenDesign.nsi" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
; OpenDesign Windows 安装器(track opendesign-windows-installer,S1c)
;
; 业主要的:双击装完、开始菜单出图标、不装 Python、不装 Git、不开 PowerShell、不答向导。
; 这个文件就是那句话的全部实现。
;
; ## 三条贯穿全文的决定(理由在 design.md,别在这儿重新讨论)
;
;   1. **每用户安装**(`$LOCALAPPDATA\Programs`,`RequestExecutionLevel user`)。
;      装进 Program Files 的话,将来的"应用内一键更新"要写自己的目录 = 每次弹 UAC。
;   2. **数据在安装根之外**(`$LOCALAPPDATA\OpenDesign`)。卸载/更新的边界从"约定"
;      变成"路径" —— 清单会漏,目录边界不会。
;   3. **不经手任何凭据**。安装器只把配置铺到"起得起来"的程度,key 由业主自己放,
;      口令由程序自己生成自己管(见 bin/ds_provision.py)。
;
; ## 为什么这份脚本被一份静态闸盯着(installer/check-installer.py)
;
; 这东西在业主的机器上以他的身份跑,而**我一次也跑不了它**(makensis 在 Linux 上能编,
; 编出来的 PE 只有 Windows 能执行)。可验证性只有两处:那份静态闸 + 他真机装一趟。
; NSIS 的经典事故全都是静态可判的(卸载删数据、$INSTDIR 空串递归删、写 HKLM 要管理员),
; 所以它们逐条变成了 G1~G17。**改这个文件之后必须跑一遍那份闸。**

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define APP        "OpenDesign"
!ifndef APPVER
  !define APPVER   "0.0.0"
!endif
!ifndef PAYLOAD
  !define PAYLOAD  "payload"
!endif

; 数据根 —— 与 bin/ds_shell.py 的 user_home() / _log_path() 是同一处约定。
; 那边写的是 %LOCALAPPDATA%\OpenDesign\{UserData,Logs},这里只认它的父目录。
!define DATA_ROOT  "$LOCALAPPDATA\${APP}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"
!define RUN_KEY    "Software\Microsoft\Windows\CurrentVersion\Run"
; 哨兵:递归删安装目录之前先确认"这确实是我们装的地方"。
; NSIS 最出名的一次性事故就是 $INSTDIR 变成空串之后 RMDir /r 从当前目录往下删。
!define SENTINEL   "ds\bin\ds_shell.py"
; 微软官方的 WebView2 检测键(每机器装 / 每用户装两处)。
!define WV2_GUID   "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "${APP} ${APPVER}"
OutFile "${APP}-Setup-${APPVER}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "Software\${APP}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
; 300MB 的树铺开要一会儿,让业主看得见在动,免得他以为卡死了去点叉。
ShowInstDetails show
ShowUnInstDetails show

VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName"     "${APP}"
VIAddVersionKey "FileDescription" "${APP} 安装程序"
VIAddVersionKey "FileVersion"     "${APPVER}.0"
VIAddVersionKey "ProductVersion"  "${APPVER}"
VIAddVersionKey "LegalCopyright"  "OpenDesign"

!define MUI_ICON   "opendesign.ico"
!define MUI_UNICON "opendesign.ico"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "安装 ${APP} ${APPVER}"
; 这段话要替业主回答两个他一定会遇到的问题,不然他会来问我:
;   ① 没有代码签名 ⇒ Windows 会弹"未知发布者"(design 已记账,签名要花钱);
;   ② 覆盖安装时如果程序正在跑,文件是锁着的。
!define MUI_WELCOMEPAGE_TEXT "这个安装程序会把 ${APP} 装到你自己的用户目录里,\
不需要管理员权限,也不会改动系统。$\r$\n$\r$\n\
如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续安装。$\r$\n$\r$\n\
你的资料(备忘、对话、工作区设置)存在安装目录之外,\
更新和卸载都不会碰它。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
; 目录页要有人守:卸载时会把安装目录**整棵**删掉,所以不能让业主随手指到一个
; 本来就有东西的文件夹(见 CheckDirEmpty)。
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE CheckDirEmpty
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "现在就打开 ${APP}"
!define MUI_FINISHPAGE_TEXT "装好了。开始菜单里可以找到 ${APP}。$\r$\n$\r$\n\
第一次打开时,如果还没填过大模型的 API key,它会告诉你要把 key 放在哪个文件里。"
!insertmacro MUI_PAGE_FINISH

; 程序在跑的时候文件是锁着的,而 `RMDir /r` 删不掉会**悄悄**跳过 ——
; 卸载器会显示"完成",盘上却剩半棵树。所以先提醒。
; ⚠️ 这句话在 0.86.0 之前是**假的**:项目档案、客户备忘、共享参考图库、工作区设置
; 当时都住在 $INSTDIR\ds 里,普通卸载(RMDir /r $INSTDIR)照样删。
; track opendesign-data-outside-install 把它们搬到了 $LOCALAPPDATA\${APP}\Data 之后,
; 这句才成立。**改这句之前先确认实现真的搬完了**(判据 tests/test_data_root.py)。
!define MUI_UNCONFIRMPAGE_TEXT_TOP "如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续卸载。$\r$\n$\r$\n你的项目档案、参考图库、和助手的对话、工作区设置都放在别处,默认不会被删除。$\r$\n你自己的设计文件(CAD/SU/效果图)本来就在你自己的文件夹里,卸载完全不碰。"
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; ─────────────────────────────────────────────────────────────── 安装

Section "${APP} 主程序" SecMain
  SectionIn RO
  ; 每用户:$SMPROGRAMS / $DESKTOP 都要取当前用户的那一份,不是 All Users
  ; (取错的话装的时候不报错,卸载时删不掉 —— 因为那需要管理员)。
  SetShellVarContext current

  SetOutPath "$INSTDIR"
  ; 整棵树一次铺进去。**故意不逐个 File 点名**:点名清单会跟真实树漂移,
  ; 而"少铺了半棵树"这种事编译期不报错。谁保证它全:成品闸 P4/P5
  ; 逐个文件比对 makensis 自己打印的清单与 payload 树。
  File /r "${PAYLOAD}\*"

  WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\${APP}" "Version"    "${APPVER}"

  ; 卸载条目("设置 → 应用"里那一条)。
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayName"     "${APP}"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayVersion"  "${APPVER}"
  WriteRegStr   HKCU "${UNINST_KEY}" "Publisher"       "OpenDesign"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${APP}.exe"
  WriteRegStr   HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\卸载.exe"'
  WriteRegStr   HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\卸载.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\卸载.exe"

  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\${APP}.exe"
  CreateShortcut "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk" "$INSTDIR\卸载.exe"

  Call EnsureWebView2
  Call ProvisionConfig
SectionEnd

Section "在桌面上放一个图标" SecDesktop
  SetShellVarContext current
  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${APP}.exe"
SectionEnd

; `/o` = 默认不勾。业主拍板"开机自启做成选项";默认关还有第二个理由:
; 常驻 + 自启会把底座的 dream(每 2 小时回顾对话、会写 SOUL.md)放大到 24 小时,
; 那件事 design.md 记在 backlog 里、本单不动 —— 那就更不该默认替他打开。
Section /o "开机时自动启动" SecAutorun
  SetShellVarContext current
  WriteRegStr HKCU "${RUN_KEY}" "${APP}" '"$INSTDIR\${APP}.exe"'
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}    "${APP} 本体(必装)。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "在桌面上放一个 ${APP} 图标。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutorun} "开机后自动把 ${APP} 挂到右下角托盘里。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ─────────────────────────────────────────────────────────────── 装机时的三件事

Function CheckDirEmpty
  ; 🔴 卸载时会 `RMDir /r "$INSTDIR"` —— 整棵删。所以"装到哪儿"这件事,
  ; 一旦业主把路径改成一个本来就有东西的文件夹(`D:\文档` 这种),卸载就会把他的东西
  ; 一起删光。**G6 那个哨兵挡不住这一种**:装完之后哨兵文件就在那儿了,它会说"是我们的"。
  ;
  ; 所以在这里拦:目录存在、非空、又不是上一次装的 OpenDesign ⇒ 让他确认一次。
  ; 不直接禁止 —— 他可能真的想装回一个自己清理过的文件夹。
  ; NSIS 的 `IfFileExists 文件 有则跳 [无则跳]`;`0` = "不跳,往下走"(标准惯用法)。
  ; 把语义写在这儿是因为它属于"Linux 上验不了、写反了也没有闸看得出来"的那一类
  ; (四审 subdeepseek F6 点名的最后一处不可验控制流)。
  IfFileExists "$INSTDIR\${SENTINEL}" ok        ; 上一次装的就是这儿,覆盖安装,放行
  IfFileExists "$INSTDIR\*.*" 0 ok              ; 有 ⇒ 往下数内容;没有(新目录)⇒ 放行

  FindFirst $0 $1 "$INSTDIR\*.*"
  loop:
    StrCmp $1 "" done
    StrCmp $1 "." next
    StrCmp $1 ".." next
    ; 找到了第一个真实条目 ⇒ 非空
    FindClose $0
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
      "这个文件夹里已经有别的东西了:$\n$INSTDIR$\n$\n\
卸载 ${APP} 的时候会把整个文件夹删掉,里面原有的东西也会一起没。$\n$\n\
建议换一个空文件夹(比如默认的那个)。一定要用这里的话,点“确定”。" \
      /SD IDCANCEL IDOK ok
    Abort
  next:
    FindNext $0 $1
    Goto loop
  done:
  FindClose $0
  ok:
FunctionEnd

Function EnsureWebView2
  ; S1a 的账:两台机器上 WebView2 都在,但那只证明了**那两台**。缺了的话窗口根本开不出来,
  ; 而业主看到的会是一串 CLR 英文栈。⇒ 检测 + 带微软官方引导程序补装,不许赌。
  ; 读 HKLM 是允许的(闸 G7 只禁止**写**);安装器是 32 位进程,读 HKLM\SOFTWARE
  ; 会被自动重定向到 WOW6432Node —— 正好是 Edge 在 64 位系统上写的那一处。
  ClearErrors
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${EndIf}
  ${If} $0 != ""
  ${AndIf} $0 != "0.0.0.0"
    DetailPrint "WebView2 运行时已在(版本 $0),不用补装。"
    Return
  ${EndIf}

  DetailPrint "这台电脑上没有 WebView2 运行时,正在装微软官方的那一份(要联网)…"
  ; ⚠️ 这条路径**在业主的两台机器上都不会被走到**(WebView2 都在),所以它没有真机证据。
  ;    另:微软的引导程序装的是"每机器"运行时 ⇒ **这一步会弹 UAC**,
  ;    "全程不要管理员"那句承诺在缺 WebView2 的机器上不成立。已写进真机清单。
  ClearErrors
  ExecWait '"$INSTDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install' $1
  ; 起都没起来(被杀软秒删、文件损坏)时 ExecWait 置 error flag,而 $1 此时不可信 ——
  ; 不查的话会错印"装好了"(四审 subkimi F4)。
  IfErrors 0 +2
    StrCpy $1 "启动失败"
  ${If} $1 != 0
    ; 装不上不拦住整个安装:业主可能只是暂时没网。第一次打开时外壳会再说一次人话。
    MessageBox MB_ICONEXCLAMATION "没能装上微软的 WebView2 运行时(错误码 $1)。$\n$\n\
${APP} 仍然装好了,但第一次打开可能会报错。$\n\
联网之后重新运行一次这个安装程序就行。" /SD IDOK
  ${Else}
    DetailPrint "WebView2 运行时装好了。"
  ${EndIf}
FunctionEnd

Function ProvisionConfig
  ; 把配置铺到"后台起得起来"的程度。**不问业主任何东西** —— 这一步是非交互的,
  ; 而且幂等(已经装过一次的机器,他自己的设置原样留着)。细节全在
  ; bin/ds_provision.py,那边有 15 条判据 + 12 条红检盯着。
  DetailPrint "正在准备配置…"
  ; **一行写完,不用续行**:NSIS 的续行拼出来到底是什么样,我在 Linux 上验不了,
  ; 而"命令拼歪了"的表现是装机时静默失败 —— 少一个验不了的机制比省几个字重要。
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\ds\bin\ds_provision.py" --home "${DATA_ROOT}\UserData" --ds-root "$INSTDIR\ds"'
  Pop $0
  ${If} $0 != 0
    ; 不 Abort:文件已经铺好了,而外壳自己会把"到底缺什么"说得比这里清楚
    ; (那段话在业主真机上验过)。这里只负责别让它悄悄过去。
    MessageBox MB_ICONEXCLAMATION "配置初始化没有成功(错误码 $0)。$\n$\n\
${APP} 的文件已经装好了。第一次打开时它会告诉你还缺什么。" /SD IDOK
  ${EndIf}
FunctionEnd

; ─────────────────────────────────────────────────────────────── 卸载

Section "un.${APP}" SecUnMain
  SectionIn RO
  SetShellVarContext current

  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"
  DeleteRegKey   HKCU "${UNINST_KEY}"
  DeleteRegKey   HKCU "Software\${APP}"

  Delete "$DESKTOP\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk"
  RMDir  "$SMPROGRAMS\${APP}"

  ; 🔴 递归删之前先认门。$INSTDIR 可能因为注册表被人动过而变成空串或别的目录,
  ; 那时候 `RMDir /r` 会从那里往下把东西删光。哨兵是这份闸(G6)要求的形状。
  IfFileExists "$INSTDIR\${SENTINEL}" 0 not_ours
    RMDir /r "$INSTDIR"
    Goto done
  not_ours:
    MessageBox MB_ICONEXCLAMATION "这个目录看起来不是 ${APP} 装的地方,为安全起见没有删:$\n$INSTDIR" /SD IDOK
  done:
SectionEnd

; `/o` = 默认不勾。业主两年的档案在这底下 —— 删掉不可恢复,必须是他主动勾的。
Section /o "un.连我的资料一起删掉(不可恢复)" SecUnData
  SetShellVarContext current
  IfFileExists "${DATA_ROOT}\*.*" 0 no_data
    RMDir /r "${DATA_ROOT}"
    DetailPrint "资料目录已删除:${DATA_ROOT}"
    Goto after
  no_data:
    DetailPrint "没有找到资料目录:${DATA_ROOT}"
  after:
SectionEnd

!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnMain} "卸载 ${APP} 程序本体(你的资料不会被删)。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnData} "连同项目档案、参考图库、对话记录、工作区设置一起删掉。删了就找不回来了。(你自己的设计文件不在这儿,不受影响。)"
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END

exec
/bin/bash -lc "sed -n '1,220p' installer/build-installer.sh" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
#!/usr/bin/env bash
#
# 🔴 **产物名字被应用内更新依赖,别随手改**(2026-09-07,track opendesign-in-app-update)。
#    `bin/ds_update.py` 的 ASSET_RE 严格匹配 `OpenDesign-Setup-<版本>.exe`
#    (大小写、空格都算)。哪天这里的产物名变成 `...EXE` 或带了后缀,
#    那一版会在业主的"检查更新"里**被静默跳过** —— 他不会看到新版,也不会看到任何错误。
#    要改名就同时改 ASSET_RE 和 tests/test_ds_update.py 的 t1c2。
# 造 OpenDesign 的 Windows 安装器 —— 从零到一个可以发给业主的 .exe。
#
# 用法:installer/build-installer.sh <输出目录>
# 产出:<输出目录>/OpenDesign-Setup-<版本>.exe
#
# ## 为什么这条流水线长这样
#
# **在 Linux 上编 Windows 安装器**:`makensis` 是原生 Linux 程序,把 Ubuntu 的两个
# .deb 解到构建缓存里就能用,**零系统改动**。(Inno Setup 的 ISCC.exe 只有 Windows 版,
# 要靠 wine,而本机 wine 建不起 prefix —— 换工具的完整理由在 design.md。)
#
# **每一步都 fail closed**。这一单我一次也跑不了成品(编出来的 PE 只有 Windows 能执行),
# 可验证性只有"闸 + 业主真机一趟"。所以任何一道闸红了就停,不许"打印一行让人自己看见"：
#   闸 A/C  组包时的依赖闸(build-package.sh 自带,曾经真响过)
#   闸 B    成品结构(check-package.sh --app)
#   闸 静态  .nsi 与启动器的 23 条(check-installer.py static)
#   闸 成品  编出来的 exe:清单逐个文件对字节数(check-installer.py product)

set -euo pipefail

OUT="${1:?用法: build-installer.sh <输出目录>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SPIKE_DIR="$REPO/tracks/opendesign-windows-installer/spike"

# NSIS 的版本要**锁死**:同一份 .nsi 在不同版本的 makensis 上编出来的东西可以不一样,
# 而我没有第二台机器去发现这件事。(依赖不锁版本的代价本单已经付过一次:
# lark_oapi 1.5.5 vs 1.7.2 装完起不来。)
NSIS_VER="3.09-4ubuntu1"
NSIS_DEBS=("nsis_${NSIS_VER}_amd64.deb" "nsis-common_${NSIS_VER}_all.deb")
# 微软官方的 WebView2 引导程序(缺 WebView2 的机器上补装用;1.7MB,不含运行时本体)
WV2_URL="https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WV2_EXE="MicrosoftEdgeWebview2Setup.exe"

CACHE="$OUT/cache"
PKG="$OUT/pkg"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n🔴 %s\n' "$*" >&2; exit 1; }

mkdir -p "$CACHE"

# ---------------------------------------------------------------- 0. 版本号
# **唯一来源是 bin/ds_web.py 的 VERSION**。这里只读,不许手写 —— 名字里印错版本,
# 业主装完自报的版本就和我以为发出去的不是一回事。
APPVER="$(grep -oP '^VERSION = "\K[^"]+' "$REPO/bin/ds_web.py")"
[ -n "$APPVER" ] || die "从 bin/ds_web.py 读不出 VERSION"
# NSIS 的 VIProductVersion 只收四段数字。将来版本号带上 -beta 之类的后缀,
# `${APPVER}.0` 会让编译当场报错 —— 与其那时候现查,不如现在就说清楚(四审 submimo)。
case "$APPVER" in
  *[!0-9.]*|*..*) die "版本号 '$APPVER' 不是 X.Y.Z 形式,NSIS 的 VIProductVersion 收不了" ;;
esac
say "0/6 版本 $APPVER"

# ---------------------------------------------------------------- 1. makensis
say "1/6 准备 NSIS $NSIS_VER(解到构建缓存,不动系统)"
NSIS_ROOT="$CACHE/nsis"
MAKENSIS="$NSIS_ROOT/usr/bin/makensis"
if [ ! -x "$MAKENSIS" ]; then
  mkdir -p "$CACHE/deb" "$NSIS_ROOT"
  ( cd "$CACHE/deb" && apt-get download nsis nsis-common >/dev/null 2>&1 ) \
    || die "下不动 nsis 的 deb(要能连 apt 源)"
  for d in "${NSIS_DEBS[@]}"; do
    [ -f "$CACHE/deb/$d" ] || die "拿到的不是锁定的版本:缺 $d"
    dpkg-deb -x "$CACHE/deb/$d" "$NSIS_ROOT"
  done
fi
[ -x "$MAKENSIS" ] || die "makensis 没解出来"
export NSISDIR="$NSIS_ROOT/usr/share/nsis"
# 🔴 这里原来是 `[ ... ] || echo`:期望串算错了(拼出 v3.09-1,实际 v3.09-4),
# 于是那行"提示"每次都打印,而构建**永远不会因此失败** —— 正是"看着像检查项、
# 其实问不出东西"的那一类(四审 subdeepseek F4 / subkimi 同时点名)。
# 现在写死期望串并 fail closed;顺带堵掉缓存里躺着旧 makensis 的情形
# (bump NSIS_VER 时 `-x` 短路会静默沿用旧编译器)。
NSIS_VER_STRING="v3.09-4"
GOT_VER="$("$MAKENSIS" -VERSION)"
echo "  makensis $GOT_VER"
[ "$GOT_VER" = "$NSIS_VER_STRING" ] \
  || die "makensis 版本不对:期望 $NSIS_VER_STRING,实际 $GOT_VER(缓存里可能是旧的,删掉 $NSIS_ROOT 重来)"

# ---------------------------------------------------------------- 2. 图标
say "2/6 图标(托盘 png + 程序 ico,同一份形状)"
python3 "$HERE/make-icon.py" "$REPO"

# ---------------------------------------------------------------- 3. payload
say "3/6 组包(出货形态:带外壳、不带考卷)"
bash "$SPIKE_DIR/build-package.sh" "$OUT" --app
[ -d "$PKG/python" ] || die "组包没产出 $PKG"

# ---------------------------------------------------------------- 4. 两个根文件
say "4/6 启动器 + WebView2 引导程序"
# 启动器:业主每天双击的那个 exe。编进 payload 根,跟着安装器一起铺下去。
# cwd 必须是 installer/ —— NSIS 的相对路径(`Icon "opendesign.ico"`)是按**当前目录**
# 解析的,不是按脚本所在目录。
# 输出路径**不用 `-X` 覆盖**:实测那条命令行会被脚本里的 OutFile 盖掉(编出来的东西
# 仍落在 installer/),而"编成功了但没落到该在的地方"是最容易被当成成功的一种失败。
# 老老实实编在原地再搬走 —— 少一个不确定的机制。
( cd "$HERE" && "$MAKENSIS" -NOCONFIG -INPUTCHARSET UTF8 -DAPPVER="$APPVER" launcher.nsi ) \
  > "$OUT/launcher-build.log" 2>&1 \
  || { tail -20 "$OUT/launcher-build.log"; die "启动器编不出来"; }
[ -f "$HERE/OpenDesign.exe" ] || die "启动器没编出来(installer/OpenDesign.exe 不在)"
mv "$HERE/OpenDesign.exe" "$PKG/OpenDesign.exe"
[ -f "$PKG/OpenDesign.exe" ] || die "启动器没落到 $PKG"
echo "  启动器 $(stat -c%s "$PKG/OpenDesign.exe") 字节"

# S1a 的账:两台机器上 WebView2 都在,但那只证明了那两台。不许赌。
if [ ! -f "$CACHE/$WV2_EXE" ]; then
  curl -fsSL -o "$CACHE/$WV2_EXE" "$WV2_URL" || die "下不动 WebView2 引导程序"
fi
# 微软会不定期更新这个文件 ⇒ **不锁哈希**(锁了每次都断),但把哈希记进构建日志,
# 出事时至少答得出"业主装的是哪一份"。
head -c2 "$CACHE/$WV2_EXE" | grep -q MZ || die "下回来的 WebView2 引导程序不是 PE"
cp "$CACHE/$WV2_EXE" "$PKG/$WV2_EXE"
echo "  WebView2 引导程序 $(stat -c%s "$PKG/$WV2_EXE") 字节  sha256=$(sha256sum "$PKG/$WV2_EXE" | cut -c1-16)…"

# ---------------------------------------------------------------- 5. 三道闸
say "5/6 闸:成品结构 + .nsi 静态"
bash "$SPIKE_DIR/check-package.sh" "$PKG" --app || die "闸 B:成品结构不合格"
# 包根上的三件:启动器、WebView2 引导程序、pythonw。闸 B 查的是 ds/ 那棵树,
# 这三个谁都没查过 —— 少了任何一个都是"装得上、打不开"或"老机器上窗口开不出来",
# 而且全都装完才发现(四审 subdeepseek F1)。
for f in OpenDesign.exe "$WV2_EXE" python/pythonw.exe; do
  [ -f "$PKG/$f" ] || die "出货包里缺 $f"
done
echo "  出货三件齐:启动器 / WebView2 引导程序 / pythonw.exe"
python3 "$HERE/check-installer.py" static "$HERE/OpenDesign.nsi" --launcher "$HERE/launcher.nsi" \
  || die "静态闸:.nsi 不合格"

# ---------------------------------------------------------------- 6. 编安装器
say "6/6 编安装器"
# **cwd 必须是 payload 的父目录**:makensis -V4 打印的清单是相对路径,成品闸靠它
# 逐个文件对字节数。给绝对路径的话清单变成绝对路径,那条闸就对不上了。
cp "$HERE/OpenDesign.nsi" "$HERE/opendesign.ico" "$OUT/"
BUILDLOG="$OUT/makensis.log"
( cd "$OUT" && "$MAKENSIS" -NOCONFIG -INPUTCHARSET UTF8 -V4 \
    -DAPPVER="$APPVER" -DPAYLOAD="pkg" OpenDesign.nsi ) > "$BUILDLOG" 2>&1 \
  || { tail -30 "$BUILDLOG"; die "安装器编不出来"; }

EXE="$OUT/OpenDesign-Setup-${APPVER}.exe"
[ -f "$EXE" ] || die "编完没找到 $EXE"

python3 "$HERE/check-installer.py" product --exe "$EXE" --log "$BUILDLOG" \
  --payload "$PKG" --version "$APPVER" || die "成品闸:编出来的 exe 与 payload 对不上"

say "成了:$EXE($(stat -c%s "$EXE" | awk '{printf "%.1f MB", $1/1048576}'))"
echo "构建日志:$BUILDLOG"

exec
/bin/bash -lc "for f in .github/workflows/*.yml; do sed -n '1,260p' \""'$f"; done' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
# 一次性可行性探针:GitHub 托管的 windows runner 能不能替我们"看一眼界面"。
#
# 为什么有这个文件:这个仓库一年来 **一个 workflow 都没有**,而唯一的验证路径是
# "打包 43MB 发给业主,让他装上肉眼看"。烧掉真机验收的三件事里有两件
# (0.90 窗口栏整块没画出来 / 0.93 界面全白)是一张截图就能看出来的。
#
# 🔴 它**不是**回归判据,别把它当门槛:绿只代表探针跑完了,四问的答案在
#    日志的 VERDICT 段 + 构件里的三张图上,由主 agent 亲眼看图之后下结论。
#
# 跑法:推到 ci-probe/** 分支自动跑,或在 Actions 页面手点(workflow_dispatch)。

name: windows-gui-probe

on:
  push:
    branches: ['ci-probe/**']
  workflow_dispatch:

permissions:
  contents: read

jobs:
  probe:
    runs-on: windows-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: 这台机器是什么
        shell: pwsh
        run: |
          (Get-CimInstance Win32_OperatingSystem).Caption
          "session name = $env:SESSIONNAME"
          "user         = $env:USERNAME"

      - name: 四问探针(截图 + 像素核对)
        shell: pwsh
        run: .\.github\scripts\windows-gui-probe.ps1 -OutDir probe-out

      - name: 把图交出来
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: windows-gui-probe
          path: probe-out/*.png
          if-no-files-found: warn
# 一次性探针:静默安装(/S)装进一个**非空**目录会怎样,以及卸载会不会把业主
# 本来就放在那儿的东西一起删掉。
#
# 为什么单独一支:两条评审腿在「CheckDirEmpty 在 /S 下可不可达」上给了相反答案,
# 而三方(两条腿 + 我)全是读文档/读源码**推**出来的,没有一方量过。
# 这支探针去量它 —— 结论写在 track opendesign-fresh-install-fix 的 verify.md。
#
# 🔴 只报告不判卷:绿只代表探针跑完了。判读规则写死在脚本头部。

name: windows-nonempty-probe

on:
  workflow_dispatch:
    inputs:
      tag:
        description: '发布 tag'
        default: 'win-installer-0.98.0'
      asset:
        description: '安装包文件名'
        default: 'OpenDesign-Setup-0.98.0.exe'

permissions:
  contents: read

jobs:
  nonempty:
    runs-on: windows-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - name: 装进非空目录 → 看有没有被拦 → 卸载 → 看业主的文件还在不在
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          .\.github\scripts\windows-nonempty-probe.ps1 `
            -Tag "${{ github.event.inputs.tag || 'win-installer-0.98.0' }}" `
            -Asset "${{ github.event.inputs.asset || 'OpenDesign-Setup-0.98.0.exe' }}" `
            -OutDir probe-out
# 真安装包探针:把业主真正双击的那个 45MB 包搬上云 Windows 机器走一遍。
#
# 上一支探针(windows-gui-probe)只答"这台机器有没有屏幕、画不画得出窗口";
# 这一支答的才是那句要紧的:**我们的软件在上面装得上、打得开、界面在不在。**
#
# 🔴 一次性探路,**不是回归判据**:绿只代表探针跑完了。
#    八相的结果在日志 VERDICT 段 + 构件里的截图和 外壳.log 上,由主 agent 看图下结论。

name: windows-package-probe

on:
  push:
    branches: ['ci-probe/**']
  # 🔴 默认值 = **push 到 ci-probe/** 分支时用的那个**(那条路没有 inputs)。
  #    **它天生会过期**:GitHub Actions 的 `default:` 只吃字面量,读不到仓库里的
  #    VERSION,所以这里必然是第二份版本号。**发新版时必须顺手改这里。**
  #    发生过两次:2026-08-30 深夜发现它还停在 0.97.0(当时已发到 0.98.2)⇒
  #    改探针后推分支验证,跑的其实是三个版本前的安装包;
  #    2026-09-02 发 0.98.3 时它还停在 0.98.2,**已随本次发版同步**。
  #    (别在这句话里再写"当前发布是 X" —— 那正是让它过期的写法。
  #     当前发布看 releases 页,不看这里。)
  workflow_dispatch:
    inputs:
      tag:
        description: '发布 tag'
        default: 'win-installer-0.98.3'
      asset:
        description: '安装包文件名'
        default: 'OpenDesign-Setup-0.98.3.exe'

permissions:
  contents: read

jobs:
  package:
    runs-on: windows-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - name: 下载 → 静默装 → 启动 → 截图 → 收日志
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          .\.github\scripts\windows-package-probe.ps1 `
            -Tag "${{ github.event.inputs.tag || 'win-installer-0.98.3' }}" `
            -Asset "${{ github.event.inputs.asset || 'OpenDesign-Setup-0.98.3.exe' }}" `
            -OutDir probe-out

      # 🔴 **退出闸的第二条路,故意住在这个文件里**(2026-08-31,第六轮 panel)。
      #    探针末尾那道闸读的是它自己进程内的 $phases。外部评审实测:在闸前面补一行
      #    `$phases = @{}`、或者在 Get-Verdict 的 return 里多一个 `-replace "FAIL",""`,
      #    任何事故都整趟绿,而 50 条本机判据全绿。**一条路的闸,改一处就没了。**
      #    这一步读的是判定器写下的**退出码**收据,和上面那步不在同一个文件、
      #    不在同一种判断上 —— 绕过去要同时改两处。
      #    `if: always()` 不能省:探针被绕过时的样子恰恰是 exit 0,而它真红时这一步
      #    也得跑完把收据打出来。
      - name: 裁决收据独立复核
        if: always()
        shell: pwsh
        # 🔴 这一步打出来的话**只许 ASCII**(2026-08-31)。实测它在 runner 上把中文
        #    全打成了问号:`?? ?????? probe-out/verdicts.tsv ? ??????????,??????`
        #    —— 闸红了却说不清为什么红,和没红一样坏(本项目栽编码的第 N 次;
        #    上一次是第 9 相打印中文即炸、rc=1 泄漏出来染红整趟)。
        #    中文说明留在注释里:注释不进输出。
        #    第一行那个 OutputEncoding 治的是另一半 —— 收据**内容**里的相名是中文。
        run: |
          [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
          $f = 'probe-out/verdicts.tsv'
          if (-not (Test-Path $f)) {
              "RED: no verdict receipt at $f -- the probe never reached the bookkeeping step, this run does not pass"
              exit 1
          }
          $lines = @(Get-Content $f)
          "verdict receipt, $($lines.Count) line(s):"
          $lines | ForEach-Object { "  $_" }
          $bad = @($lines | Where-Object { $_ -like "1`t*" })
          if ($bad.Count) {
              "RED: $($bad.Count) FAIL verdict(s) in the receipt, this run does not pass"
              exit 1
          }
          "no FAIL verdict in the receipt"

      - name: 把图和日志交出来
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: windows-package-probe
          path: |
            probe-out/*.png
            probe-out/*.log
            probe-out/*.zip
            probe-out/*.tsv
          if-no-files-found: warn

codex
先确认到两条关键现状：安装器是每用户 NSIS、程序文件在 `%LOCALAPPDATA%\Programs\OpenDesign`，数据根明确在安装目录外；当前更新模块只负责“查”，并已把 GitHub 资产的 `digest` 带到上层。下一步我在定位进程退出/拉起、端口和 health 的真实实现，避免凭印象设计交接协议。
exec
/bin/bash -lc "sed -n '1,180p' installer/OpenDesign.nsi" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
; OpenDesign Windows 安装器(track opendesign-windows-installer,S1c)
;
; 业主要的:双击装完、开始菜单出图标、不装 Python、不装 Git、不开 PowerShell、不答向导。
; 这个文件就是那句话的全部实现。
;
; ## 三条贯穿全文的决定(理由在 design.md,别在这儿重新讨论)
;
;   1. **每用户安装**(`$LOCALAPPDATA\Programs`,`RequestExecutionLevel user`)。
;      装进 Program Files 的话,将来的"应用内一键更新"要写自己的目录 = 每次弹 UAC。
;   2. **数据在安装根之外**(`$LOCALAPPDATA\OpenDesign`)。卸载/更新的边界从"约定"
;      变成"路径" —— 清单会漏,目录边界不会。
;   3. **不经手任何凭据**。安装器只把配置铺到"起得起来"的程度,key 由业主自己放,
;      口令由程序自己生成自己管(见 bin/ds_provision.py)。
;
; ## 为什么这份脚本被一份静态闸盯着(installer/check-installer.py)
;
; 这东西在业主的机器上以他的身份跑,而**我一次也跑不了它**(makensis 在 Linux 上能编,
; 编出来的 PE 只有 Windows 能执行)。可验证性只有两处:那份静态闸 + 他真机装一趟。
; NSIS 的经典事故全都是静态可判的(卸载删数据、$INSTDIR 空串递归删、写 HKLM 要管理员),
; 所以它们逐条变成了 G1~G17。**改这个文件之后必须跑一遍那份闸。**

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define APP        "OpenDesign"
!ifndef APPVER
  !define APPVER   "0.0.0"
!endif
!ifndef PAYLOAD
  !define PAYLOAD  "payload"
!endif

; 数据根 —— 与 bin/ds_shell.py 的 user_home() / _log_path() 是同一处约定。
; 那边写的是 %LOCALAPPDATA%\OpenDesign\{UserData,Logs},这里只认它的父目录。
!define DATA_ROOT  "$LOCALAPPDATA\${APP}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"
!define RUN_KEY    "Software\Microsoft\Windows\CurrentVersion\Run"
; 哨兵:递归删安装目录之前先确认"这确实是我们装的地方"。
; NSIS 最出名的一次性事故就是 $INSTDIR 变成空串之后 RMDir /r 从当前目录往下删。
!define SENTINEL   "ds\bin\ds_shell.py"
; 微软官方的 WebView2 检测键(每机器装 / 每用户装两处)。
!define WV2_GUID   "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "${APP} ${APPVER}"
OutFile "${APP}-Setup-${APPVER}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "Software\${APP}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
; 300MB 的树铺开要一会儿,让业主看得见在动,免得他以为卡死了去点叉。
ShowInstDetails show
ShowUnInstDetails show

VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName"     "${APP}"
VIAddVersionKey "FileDescription" "${APP} 安装程序"
VIAddVersionKey "FileVersion"     "${APPVER}.0"
VIAddVersionKey "ProductVersion"  "${APPVER}"
VIAddVersionKey "LegalCopyright"  "OpenDesign"

!define MUI_ICON   "opendesign.ico"
!define MUI_UNICON "opendesign.ico"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "安装 ${APP} ${APPVER}"
; 这段话要替业主回答两个他一定会遇到的问题,不然他会来问我:
;   ① 没有代码签名 ⇒ Windows 会弹"未知发布者"(design 已记账,签名要花钱);
;   ② 覆盖安装时如果程序正在跑,文件是锁着的。
!define MUI_WELCOMEPAGE_TEXT "这个安装程序会把 ${APP} 装到你自己的用户目录里,\
不需要管理员权限,也不会改动系统。$\r$\n$\r$\n\
如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续安装。$\r$\n$\r$\n\
你的资料(备忘、对话、工作区设置)存在安装目录之外,\
更新和卸载都不会碰它。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
; 目录页要有人守:卸载时会把安装目录**整棵**删掉,所以不能让业主随手指到一个
; 本来就有东西的文件夹(见 CheckDirEmpty)。
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE CheckDirEmpty
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "现在就打开 ${APP}"
!define MUI_FINISHPAGE_TEXT "装好了。开始菜单里可以找到 ${APP}。$\r$\n$\r$\n\
第一次打开时,如果还没填过大模型的 API key,它会告诉你要把 key 放在哪个文件里。"
!insertmacro MUI_PAGE_FINISH

; 程序在跑的时候文件是锁着的,而 `RMDir /r` 删不掉会**悄悄**跳过 ——
; 卸载器会显示"完成",盘上却剩半棵树。所以先提醒。
; ⚠️ 这句话在 0.86.0 之前是**假的**:项目档案、客户备忘、共享参考图库、工作区设置
; 当时都住在 $INSTDIR\ds 里,普通卸载(RMDir /r $INSTDIR)照样删。
; track opendesign-data-outside-install 把它们搬到了 $LOCALAPPDATA\${APP}\Data 之后,
; 这句才成立。**改这句之前先确认实现真的搬完了**(判据 tests/test_data_root.py)。
!define MUI_UNCONFIRMPAGE_TEXT_TOP "如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续卸载。$\r$\n$\r$\n你的项目档案、参考图库、和助手的对话、工作区设置都放在别处,默认不会被删除。$\r$\n你自己的设计文件(CAD/SU/效果图)本来就在你自己的文件夹里,卸载完全不碰。"
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; ─────────────────────────────────────────────────────────────── 安装

Section "${APP} 主程序" SecMain
  SectionIn RO
  ; 每用户:$SMPROGRAMS / $DESKTOP 都要取当前用户的那一份,不是 All Users
  ; (取错的话装的时候不报错,卸载时删不掉 —— 因为那需要管理员)。
  SetShellVarContext current

  SetOutPath "$INSTDIR"
  ; 整棵树一次铺进去。**故意不逐个 File 点名**:点名清单会跟真实树漂移,
  ; 而"少铺了半棵树"这种事编译期不报错。谁保证它全:成品闸 P4/P5
  ; 逐个文件比对 makensis 自己打印的清单与 payload 树。
  File /r "${PAYLOAD}\*"

  WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\${APP}" "Version"    "${APPVER}"

  ; 卸载条目("设置 → 应用"里那一条)。
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayName"     "${APP}"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayVersion"  "${APPVER}"
  WriteRegStr   HKCU "${UNINST_KEY}" "Publisher"       "OpenDesign"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${APP}.exe"
  WriteRegStr   HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\卸载.exe"'
  WriteRegStr   HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\卸载.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\卸载.exe"

  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\${APP}.exe"
  CreateShortcut "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk" "$INSTDIR\卸载.exe"

  Call EnsureWebView2
  Call ProvisionConfig
SectionEnd

Section "在桌面上放一个图标" SecDesktop
  SetShellVarContext current
  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${APP}.exe"
SectionEnd

; `/o` = 默认不勾。业主拍板"开机自启做成选项";默认关还有第二个理由:
; 常驻 + 自启会把底座的 dream(每 2 小时回顾对话、会写 SOUL.md)放大到 24 小时,
; 那件事 design.md 记在 backlog 里、本单不动 —— 那就更不该默认替他打开。
Section /o "开机时自动启动" SecAutorun
  SetShellVarContext current
  WriteRegStr HKCU "${RUN_KEY}" "${APP}" '"$INSTDIR\${APP}.exe"'
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}    "${APP} 本体(必装)。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "在桌面上放一个 ${APP} 图标。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutorun} "开机后自动把 ${APP} 挂到右下角托盘里。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ─────────────────────────────────────────────────────────────── 装机时的三件事

Function CheckDirEmpty
  ; 🔴 卸载时会 `RMDir /r "$INSTDIR"` —— 整棵删。所以"装到哪儿"这件事,
  ; 一旦业主把路径改成一个本来就有东西的文件夹(`D:\文档` 这种),卸载就会把他的东西
  ; 一起删光。**G6 那个哨兵挡不住这一种**:装完之后哨兵文件就在那儿了,它会说"是我们的"。
  ;
  ; 所以在这里拦:目录存在、非空、又不是上一次装的 OpenDesign ⇒ 让他确认一次。
  ; 不直接禁止 —— 他可能真的想装回一个自己清理过的文件夹。
  ; NSIS 的 `IfFileExists 文件 有则跳 [无则跳]`;`0` = "不跳,往下走"(标准惯用法)。
  ; 把语义写在这儿是因为它属于"Linux 上验不了、写反了也没有闸看得出来"的那一类
  ; (四审 subdeepseek F6 点名的最后一处不可验控制流)。
  IfFileExists "$INSTDIR\${SENTINEL}" ok        ; 上一次装的就是这儿,覆盖安装,放行
  IfFileExists "$INSTDIR\*.*" 0 ok              ; 有 ⇒ 往下数内容;没有(新目录)⇒ 放行

  FindFirst $0 $1 "$INSTDIR\*.*"

exec
/bin/bash -lc "sed -n '181,360p' installer/OpenDesign.nsi" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
  loop:
    StrCmp $1 "" done
    StrCmp $1 "." next
    StrCmp $1 ".." next
    ; 找到了第一个真实条目 ⇒ 非空
    FindClose $0
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
      "这个文件夹里已经有别的东西了:$\n$INSTDIR$\n$\n\
卸载 ${APP} 的时候会把整个文件夹删掉,里面原有的东西也会一起没。$\n$\n\
建议换一个空文件夹(比如默认的那个)。一定要用这里的话,点“确定”。" \
      /SD IDCANCEL IDOK ok
    Abort
  next:
    FindNext $0 $1
    Goto loop
  done:
  FindClose $0
  ok:
FunctionEnd

Function EnsureWebView2
  ; S1a 的账:两台机器上 WebView2 都在,但那只证明了**那两台**。缺了的话窗口根本开不出来,
  ; 而业主看到的会是一串 CLR 英文栈。⇒ 检测 + 带微软官方引导程序补装,不许赌。
  ; 读 HKLM 是允许的(闸 G7 只禁止**写**);安装器是 32 位进程,读 HKLM\SOFTWARE
  ; 会被自动重定向到 WOW6432Node —— 正好是 Edge 在 64 位系统上写的那一处。
  ClearErrors
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${EndIf}
  ${If} $0 != ""
  ${AndIf} $0 != "0.0.0.0"
    DetailPrint "WebView2 运行时已在(版本 $0),不用补装。"
    Return
  ${EndIf}

  DetailPrint "这台电脑上没有 WebView2 运行时,正在装微软官方的那一份(要联网)…"
  ; ⚠️ 这条路径**在业主的两台机器上都不会被走到**(WebView2 都在),所以它没有真机证据。
  ;    另:微软的引导程序装的是"每机器"运行时 ⇒ **这一步会弹 UAC**,
  ;    "全程不要管理员"那句承诺在缺 WebView2 的机器上不成立。已写进真机清单。
  ClearErrors
  ExecWait '"$INSTDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install' $1
  ; 起都没起来(被杀软秒删、文件损坏)时 ExecWait 置 error flag,而 $1 此时不可信 ——
  ; 不查的话会错印"装好了"(四审 subkimi F4)。
  IfErrors 0 +2
    StrCpy $1 "启动失败"
  ${If} $1 != 0
    ; 装不上不拦住整个安装:业主可能只是暂时没网。第一次打开时外壳会再说一次人话。
    MessageBox MB_ICONEXCLAMATION "没能装上微软的 WebView2 运行时(错误码 $1)。$\n$\n\
${APP} 仍然装好了,但第一次打开可能会报错。$\n\
联网之后重新运行一次这个安装程序就行。" /SD IDOK
  ${Else}
    DetailPrint "WebView2 运行时装好了。"
  ${EndIf}
FunctionEnd

Function ProvisionConfig
  ; 把配置铺到"后台起得起来"的程度。**不问业主任何东西** —— 这一步是非交互的,
  ; 而且幂等(已经装过一次的机器,他自己的设置原样留着)。细节全在
  ; bin/ds_provision.py,那边有 15 条判据 + 12 条红检盯着。
  DetailPrint "正在准备配置…"
  ; **一行写完,不用续行**:NSIS 的续行拼出来到底是什么样,我在 Linux 上验不了,
  ; 而"命令拼歪了"的表现是装机时静默失败 —— 少一个验不了的机制比省几个字重要。
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\ds\bin\ds_provision.py" --home "${DATA_ROOT}\UserData" --ds-root "$INSTDIR\ds"'
  Pop $0
  ${If} $0 != 0
    ; 不 Abort:文件已经铺好了,而外壳自己会把"到底缺什么"说得比这里清楚
    ; (那段话在业主真机上验过)。这里只负责别让它悄悄过去。
    MessageBox MB_ICONEXCLAMATION "配置初始化没有成功(错误码 $0)。$\n$\n\
${APP} 的文件已经装好了。第一次打开时它会告诉你还缺什么。" /SD IDOK
  ${EndIf}
FunctionEnd

; ─────────────────────────────────────────────────────────────── 卸载

Section "un.${APP}" SecUnMain
  SectionIn RO
  SetShellVarContext current

  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"
  DeleteRegKey   HKCU "${UNINST_KEY}"
  DeleteRegKey   HKCU "Software\${APP}"

  Delete "$DESKTOP\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk"
  RMDir  "$SMPROGRAMS\${APP}"

  ; 🔴 递归删之前先认门。$INSTDIR 可能因为注册表被人动过而变成空串或别的目录,
  ; 那时候 `RMDir /r` 会从那里往下把东西删光。哨兵是这份闸(G6)要求的形状。
  IfFileExists "$INSTDIR\${SENTINEL}" 0 not_ours
    RMDir /r "$INSTDIR"
    Goto done
  not_ours:
    MessageBox MB_ICONEXCLAMATION "这个目录看起来不是 ${APP} 装的地方,为安全起见没有删:$\n$INSTDIR" /SD IDOK
  done:
SectionEnd

; `/o` = 默认不勾。业主两年的档案在这底下 —— 删掉不可恢复,必须是他主动勾的。
Section /o "un.连我的资料一起删掉(不可恢复)" SecUnData
  SetShellVarContext current
  IfFileExists "${DATA_ROOT}\*.*" 0 no_data
    RMDir /r "${DATA_ROOT}"
    DetailPrint "资料目录已删除:${DATA_ROOT}"
    Goto after
  no_data:
    DetailPrint "没有找到资料目录:${DATA_ROOT}"
  after:
SectionEnd

!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnMain} "卸载 ${APP} 程序本体(你的资料不会被删)。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnData} "连同项目档案、参考图库、对话记录、工作区设置一起删掉。删了就找不回来了。(你自己的设计文件不在这儿,不受影响。)"
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END

exec
/bin/bash -lc "rg -n -i \"VERSION|/api/health|health|update|shutdown|quit|exit|server|port|pid|localhost|127\\.0\\.0\\.1|DATA_ROOT|LOCALAPPDATA|UserData|subprocess|Popen|terminate|kill|restart|relaunch|lock\" bin/ds_web.py bin/ds_shell.py bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
bin/ds_web.py:6:  GET /api/health  存活探针(version + ds_root)
bin/ds_web.py:8:  GET /api/chat/bootstrap             → 127.0.0.1:<nanobot>/webui/bootstrap
bin/ds_web.py:50:  POST /api/refs/update            {"ref_id","style","space","note"} 针孔⑪:薄壳直调
bin/ds_web.py:51:    ds_refs.update_ref(词表校验/分段重写/锁/页脚 bump 全在核心,只重写头段与备注段,
bin/ds_web.py:55:约束(design.md D2):只绑 127.0.0.1;端口 DS_WEB_PORT(默认 8766),被占明确报错
bin/ds_web.py:59:环境变量:DS_ROOT / DS_WEB_PORT / DS_WEB_DIST(测试注入用)/ DS_NANOBOT_PORT。
bin/ds_web.py:61:import http.client
bin/ds_web.py:62:import base64
bin/ds_web.py:63:import binascii
bin/ds_web.py:64:import hashlib
bin/ds_web.py:65:import json
bin/ds_web.py:66:import os
bin/ds_web.py:67:import re
bin/ds_web.py:68:import socket
bin/ds_web.py:69:import sys
bin/ds_web.py:70:import time
bin/ds_web.py:71:import traceback
bin/ds_web.py:72:import uuid
bin/ds_web.py:73:from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
bin/ds_web.py:74:from urllib.parse import parse_qs, unquote, urlsplit
bin/ds_web.py:76:import ds_common
bin/ds_web.py:77:import ds_consent
bin/ds_web.py:78:import ds_credential  # 大模型 key(track opendesign-key-onboarding)
bin/ds_web.py:79:import ds_intake    # 收件箱清单/建议(track opendesign-intake)
bin/ds_web.py:80:import ds_model
bin/ds_web.py:81:import ds_openfolder
bin/ds_web.py:82:import ds_organize  # 针孔④ approve+apply 直调核心(锁/复验/审计全在核心)
bin/ds_web.py:83:import ds_refs
bin/ds_web.py:84:import ds_shell_core     # 只取锁通道的协议常量与读行:帧格式两处各抄一份迟早对不上
bin/ds_web.py:85:import ds_taxonomy
bin/ds_web.py:86:import ds_update    # 查更新(track opendesign-in-app-update):只查不装
bin/ds_web.py:87:import ds_todo
bin/ds_web.py:88:import ds_tools
bin/ds_web.py:89:import ds_workspace
bin/ds_web.py:94:VERSION = "0.98.4"  # 应用内更新第一刀:软件自己发现新版并说一句(只查不装)
bin/ds_web.py:95:                    # (track opendesign-in-app-update)
bin/ds_web.py:100:                    # 我给"后端就绪"加的探针走了系统代理(urlopen 对 127.0.0.1 不绕代理),
bin/ds_web.py:102:                    # 怎么发现的:**四审孤腿 BLOCK,然后我自己造探针复现**——
bin/ds_web.py:128:                    # %LOCALAPPDATA%\OpenDesign\关掉窗口动画.on。
bin/ds_web.py:162:                    # ds_web.py 两版之间只改了 VERSION 注释 ⇒ 从"看得见"到"全白"
bin/ds_web.py:172:                    #   (%LOCALAPPDATA%\OpenDesign\实验-窗口动画.on),
bin/ds_web.py:226:                    # 现在它们在 %LOCALAPPDATA%\OpenDesign\Data 下,卸载和更新都碰不到;
bin/ds_web.py:231:                    # /api/health 都取这个号,而 08-14 那个安装器和这个若同叫 0.85.0,
bin/ds_web.py:241:                    # 装机脚本要装 firecrawl-anydoc==0.1.6;/api/health 的
bin/ds_web.py:250:DEFAULT_NANOBOT_PORT = 8765
bin/ds_web.py:307:def _restart_verdict(reply: bytes) -> str:
bin/ds_web.py:314:    return "requested" if reply == ds_shell_core.LOCK_OK_RESTART.strip() else "manual"
bin/ds_web.py:317:def ds_shell_bridge_restart() -> str:
bin/ds_web.py:321:    外壳把锁端口写在 `DS_SHELL_LOCK_PORT` 里交给我们(ds_shell_core.child_env)。
bin/ds_web.py:329:    raw = (os.environ.get("DS_SHELL_LOCK_PORT") or "").strip()
bin/ds_web.py:333:        with socket.create_connection(("127.0.0.1", int(raw)), timeout=3) as s:
bin/ds_web.py:334:            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_RESTART)
bin/ds_web.py:339:    return _restart_verdict(reply)
bin/ds_web.py:374:        import importlib.metadata as _md
bin/ds_web.py:375:        return {"available": True, "converter": _md.version("firecrawl-anydoc")}
bin/ds_web.py:414:REFS_UPDATE_PATH = "/api/refs/update"  # do_POST 写针孔⑪(同上 track §8),精确匹配
bin/ds_web.py:549:_REFS_UPDATE_ALLOWED_KEYS = {"ref_id", "style", "space", "note"}
bin/ds_web.py:550:# update_ref error code → HTTP status(校验类 400,资源不存在 404,状态冲突 409)
bin/ds_web.py:551:_REFS_UPDATE_ERR_STATUS = {
bin/ds_web.py:760:        with open(os.path.join(ds_common.data_root(ds_root), ds_workspace.CONFIG_REL),
bin/ds_web.py:788:def _workspace_health_state(ds_root: str) -> dict:
bin/ds_web.py:789:    """GET /api/workspace/health 的领域数据;不写盘、不自动修配置。"""
bin/ds_web.py:840:DEFAULT_PORT = 8766
bin/ds_web.py:856:    server_version = f"ds-web/{VERSION}"
bin/ds_web.py:896:        rebinding 下 TCP 连的是 127.0.0.1 但浏览器带的 Host 是恶意域名——绑 loopback
bin/ds_web.py:901:        port = self.server.server_address[1]
bin/ds_web.py:902:        return host in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}",
bin/ds_web.py:903:                        "127.0.0.1", "localhost", "[::1]"}
bin/ds_web.py:916:        if path == "/api/health":
bin/ds_web.py:917:            self._json(200, {"ok": True, "version": VERSION,
bin/ds_web.py:918:                             "ds_root": self.server.ds_root,
bin/ds_web.py:920:                             # 文档转换器装没装:业主刷一下 /api/health 就看得见,
bin/ds_web.py:923:        elif path == "/api/update/check":
bin/ds_web.py:924:            self._update_check()
bin/ds_web.py:945:        elif path == "/api/workspace/health":
bin/ds_web.py:946:            self._workspace_health()
bin/ds_web.py:1007:        elif path == REFS_UPDATE_PATH:
bin/ds_web.py:1008:            self._refs_update()
bin/ds_web.py:1024:    def _update_check(self):
bin/ds_web.py:1025:        """查更新:线上有没有比本机新的版本(track opendesign-in-app-update,第一刀)。
bin/ds_web.py:1032:        本机版本号只有一个来源(VERSION),不另写一份 —— 抄第二份迟早对不上。
bin/ds_web.py:1039:        self._json(200, ds_update.check_cached(VERSION, force=force))
bin/ds_web.py:1043:            data = ds_todo.collect(self.server.ds_root)
bin/ds_web.py:1059:            ds_common.data_root(self.server.ds_root), "projects"))
bin/ds_web.py:1067:            root = self.server.ds_root
bin/ds_web.py:1071:            proj_dir = os.path.realpath(os.path.join(ds_common.data_root(root), "projects"))
bin/ds_web.py:1101:                    "last_update": dates[-1] if dates else None,
bin/ds_web.py:1142:                        "last_update": None, "unregistered": True,
bin/ds_web.py:1156:                ds_workspace.load_config(self.server.ds_root))
bin/ds_web.py:1162:    def _workspace_health(self):
bin/ds_web.py:1163:        """GET /api/workspace/health:工作区体检卡当前事实 + 本轮 reviewId。
bin/ds_web.py:1170:        ③ 而代价在 Windows 上是实的:`ds_lock` 是重试式锁,约 10 次重试后
bin/ds_web.py:1175:            data = _workspace_health_state(self.server.ds_root)
bin/ds_web.py:1219:            refs = ds_refs.list_project_refs(key, self.server.ds_root)
bin/ds_web.py:1232:        vocab = {"style": ds_refs._load_styles(self.server.ds_root),
bin/ds_web.py:1245:            ds_common.data_root(self.server.ds_root), "refs"))
bin/ds_web.py:1276:        cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:1370:            cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:1374:            taxonomy = ds_taxonomy.load_taxonomy(self.server.ds_root)
bin/ds_web.py:1443:        blocked_by_automations 原样透传给前端提示。查询串按 _proxy 契约原样
bin/ds_web.py:1471:            r = ds_intake.list_inbox(self.server.ds_root)
bin/ds_web.py:1472:            cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:1479:                    tax = ds_taxonomy.load_taxonomy(self.server.ds_root)
bin/ds_web.py:1505:        plans_dir = os.path.join(ds_common.data_root(self.server.ds_root),
bin/ds_web.py:1539:            self._json(200, {"mode": ds_consent.load_mode(self.server.ds_root),
bin/ds_web.py:1540:                             "pending": ds_consent.list_pending(self.server.ds_root)})
bin/ds_web.py:1577:            self._json(200, ds_consent.set_mode(self.server.ds_root, mode))
bin/ds_web.py:1597:            # 里记的参数执行)。ds_consent 自己不 import ds_tools —— 那是循环依赖。
bin/ds_web.py:1598:            r = ds_consent.resolve_pending(self.server.ds_root, pending_id, approve,
bin/ds_web.py:1654:            cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:1658:            plan_path = os.path.join(ds_common.data_root(self.server.ds_root),
bin/ds_web.py:1675:            r = ds_organize.approve_plan(plan_id, ds_root=self.server.ds_root)
bin/ds_web.py:1681:                                       ds_root=self.server.ds_root)
bin/ds_web.py:1720:            cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:1724:            r = ds_intake.stage_inbox_auto([cfg["root"]], self.server.ds_root)
bin/ds_web.py:1763:            cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:1767:            plan_path = os.path.join(ds_common.data_root(self.server.ds_root),
bin/ds_web.py:1781:                                     self.server.ds_root)
bin/ds_web.py:1834:            new_text=new_text, note=note, ds_root=self.server.ds_root)
bin/ds_web.py:1876:            project, content or "", space=space or "", ds_root=self.server.ds_root)
bin/ds_web.py:1923:            ds_root=self.server.ds_root)
bin/ds_web.py:1995:        cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:2002:        taxonomy = ds_taxonomy.load_taxonomy(self.server.ds_root)
bin/ds_web.py:2053:        # 不是新的泄漏类:/api/health 早就回 ds_root,且这是 localhost 单机工具、
bin/ds_web.py:2100:        cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:2104:        taxonomy = ds_taxonomy.load_taxonomy(self.server.ds_root)
bin/ds_web.py:2177:        # ① ds_web 只绑 127.0.0.1;② Host 白名单挡 DNS rebinding;
bin/ds_web.py:2186:        r = ds_tools._apply_bind_project(project, folder, ds_root=self.server.ds_root)
bin/ds_web.py:2201:        locked_workspace_json 内进行,且只改 raw["structuralDirs"] 一个键。
bin/ds_web.py:2242:            with ds_tools.locked_workspace_json(self.server.ds_root) as box:
bin/ds_web.py:2245:                cfg = ds_workspace.load_config(self.server.ds_root)
bin/ds_web.py:2262:            _workspace_config_bytes(self.server.ds_root), top_dirs)
bin/ds_web.py:2314:        r = ds_tools.set_stage(project, stage, since=since, ds_root=self.server.ds_root)
bin/ds_web.py:2321:    def _refs_update(self):
bin/ds_web.py:2326:        (缺省=不动,原样交核心区分)→ ds_refs.update_ref(词表/分段重写/锁/页脚 bump
bin/ds_web.py:2344:        if not isinstance(body, dict) or set(body) - _REFS_UPDATE_ALLOWED_KEYS:
bin/ds_web.py:2355:        r = ds_refs.update_ref(
bin/ds_web.py:2360:            ds_root=self.server.ds_root)
bin/ds_web.py:2367:        self._json(_REFS_UPDATE_ERR_STATUS.get(err, 400), {"error": err})
bin/ds_web.py:2403:        r = ds_tools.set_due_date(project, body.get("cnum"), due, ds_root=self.server.ds_root)
bin/ds_web.py:2442:        r = ds_tools.delete_change(project, body.get("cnum"), ds_root=self.server.ds_root)
bin/ds_web.py:2471:                "127.0.0.1", self.server.nanobot_port, timeout=30)
bin/ds_web.py:2499:        port = self.server.server_address[1]
bin/ds_web.py:2500:        return origin.lower() in {f"http://127.0.0.1:{port}", f"http://localhost:{port}",
bin/ds_web.py:2501:                                  f"http://[::1]:{port}"}
bin/ds_web.py:2547:        out["restart"] = ds_shell_bridge_restart()
bin/ds_web.py:2556:        dist = self.server.dist  # 已 realpath(make_server 保证)
bin/ds_web.py:2576:def make_server(ds_root: str, dist: str, host: str = "127.0.0.1",
bin/ds_web.py:2577:                port: int = DEFAULT_PORT,
bin/ds_web.py:2578:                nanobot_port: int = DEFAULT_NANOBOT_PORT) -> ThreadingHTTPServer:
bin/ds_web.py:2579:    httpd = ThreadingHTTPServer((host, port), Handler)  # allow_reuse_address 已内建
bin/ds_web.py:2582:    httpd.nanobot_port = nanobot_port  # 代理上游恒 127.0.0.1,仅端口可配
bin/ds_web.py:2589:    port = int(os.environ.get("DS_WEB_PORT", str(DEFAULT_PORT)))
bin/ds_web.py:2590:    nanobot_port = int(os.environ.get("DS_NANOBOT_PORT", str(DEFAULT_NANOBOT_PORT)))
bin/ds_web.py:2604:        httpd = make_server(ds_root, dist, port=port, nanobot_port=nanobot_port)
bin/ds_web.py:2606:        print(f"ds-web: 端口 {port} 起不来({e});被占用请设 DS_WEB_PORT 换端口",
bin/ds_web.py:2609:    print(f"ds-web {VERSION}: http://127.0.0.1:{port}/  "
bin/ds_web.py:2610:          f"(DS_DATA_ROOT={ds_common.data_root(ds_root)})")
bin/ds_web.py:2616:        httpd.server_close()
bin/ds_web.py:2621:    sys.exit(main())
bin/ds_shell_core.py:4:from __future__ import annotations
bin/ds_shell_core.py:6:import concurrent.futures
bin/ds_shell_core.py:7:import functools
bin/ds_shell_core.py:8:import json
bin/ds_shell_core.py:9:import os
bin/ds_shell_core.py:10:import re
bin/ds_shell_core.py:11:import signal
bin/ds_shell_core.py:12:import socket
bin/ds_shell_core.py:13:import subprocess
bin/ds_shell_core.py:14:import sys
bin/ds_shell_core.py:15:import tempfile
bin/ds_shell_core.py:16:import threading
bin/ds_shell_core.py:17:import time
bin/ds_shell_core.py:18:from dataclasses import dataclass
bin/ds_shell_core.py:19:from pathlib import Path
bin/ds_shell_core.py:21:import ds_common
bin/ds_shell_core.py:22:from typing import Any
bin/ds_shell_core.py:32:# 🔴 数值写死,不用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)`:
bin/ds_shell_core.py:33:#    Linux 的 subprocess **没有**这两个常量,getattr 会退化成 0,
bin/ds_shell_core.py:41:    """起子进程时要额外传给 `subprocess` 的平台参数 —— **唯一来源**。
bin/ds_shell_core.py:56:class PortBusy(RuntimeError):
bin/ds_shell_core.py:68:def port_free(port: int, host: str = "127.0.0.1") -> bool:
bin/ds_shell_core.py:72:        s.bind((host, int(port)))
bin/ds_shell_core.py:80:def port_listening(port: int, host: str = "127.0.0.1") -> bool:
bin/ds_shell_core.py:83:        with socket.create_connection((host, int(port)), timeout=0.25):
bin/ds_shell_core.py:89:def pick_port(preferred: int, *, span: int = 20) -> int:
bin/ds_shell_core.py:91:    for port in range(start, start + int(span) + 1):
bin/ds_shell_core.py:92:        if port_free(port):
bin/ds_shell_core.py:93:            return port
bin/ds_shell_core.py:94:    raise PortBusy(f"端口段 {start}..{start + int(span)} 全部被占")
bin/ds_shell_core.py:97:def pick_ports(preferred: list[int], *, span: int = 20) -> list[int]:
bin/ds_shell_core.py:102:        for port in range(start, start + int(span) + 1):
bin/ds_shell_core.py:103:            if port not in used and port_free(port):
bin/ds_shell_core.py:104:                chosen.append(port)
bin/ds_shell_core.py:105:                used.add(port)
bin/ds_shell_core.py:108:            raise PortBusy(f"端口段 {start}..{start + int(span)} 没有可用端口")
bin/ds_shell_core.py:112:def lock_sockopts(platform: str) -> list[tuple[str, int]]:
bin/ds_shell_core.py:124:def lock_timeouts() -> dict[str, float]:
bin/ds_shell_core.py:125:    """握手的两个期限。纯数据 —— 和 `lock_sockopts` 一个用意:好让考卷问得出来。
bin/ds_shell_core.py:131:    (2026-09-01,三条评审腿里两条 BLOCK,加我自己共四次独立复现):
bin/ds_shell_core.py:134:        tracks/opendesign-slow-lock-scan/probes/connect_latency.py:
bin/ds_shell_core.py:141:    同一个 data_root(评审腿查过:`pick_ports(span=20)` 会让第二份换端口照跑,
bin/ds_shell_core.py:154:    6 个锁位;他那台机器上每个锁位都耗满 ⇒ `manifest.done` 到 `lock.acquired`
bin/ds_shell_core.py:160:    见 tracks/opendesign-slow-lock-scan/proposal.md 的"还不知道的"。)
bin/ds_shell_core.py:169:# 两处各抄一份的代价我付过(见 ports_for 那段注释),这里只留一个真相源。
bin/ds_shell_core.py:170:LOCK_HELLO = b"OpenDesign.ds_shell_core.lock.v1\n"
bin/ds_shell_core.py:171:LOCK_SHOW = b"SHOW\n"
bin/ds_shell_core.py:172:LOCK_RESTART = b"RESTART-BACKEND\n"     # 业主填完 key ⇒ 网关得重来一次才认新 env
bin/ds_shell_core.py:173:LOCK_OK = b"OK\n"
bin/ds_shell_core.py:174:# 🔴 应答**点名动词**:老外壳认不出 RESTART 也会回裸 OK,ds-web 就会把
bin/ds_shell_core.py:178:LOCK_OK_RESTART = b"OK RESTART-BACKEND\n"
bin/ds_shell_core.py:202:class InstanceLock:
bin/ds_shell_core.py:203:    _HELLO = LOCK_HELLO
bin/ds_shell_core.py:204:    _SHOW = LOCK_SHOW
bin/ds_shell_core.py:205:    _RESTART = LOCK_RESTART
bin/ds_shell_core.py:206:    _OK = LOCK_OK
bin/ds_shell_core.py:207:    _OK_RESTART = LOCK_OK_RESTART
bin/ds_shell_core.py:209:    port: int | None
bin/ds_shell_core.py:212:    def __init__(self, base_port: int, span: int = 5, on_show=None, on_restart=None):
bin/ds_shell_core.py:213:        self.base_port = int(base_port)
bin/ds_shell_core.py:216:        self.on_restart = on_restart
bin/ds_shell_core.py:217:        self.port = None
bin/ds_shell_core.py:237:        hit = self._scan(self._ports())
bin/ds_shell_core.py:239:            self.port = hit
bin/ds_shell_core.py:242:        for port in self._ports():
bin/ds_shell_core.py:245:                for name, value in lock_sockopts(sys.platform):
bin/ds_shell_core.py:249:                sock.bind(("127.0.0.1", port))
bin/ds_shell_core.py:255:            self.port = port
bin/ds_shell_core.py:256:            self._thread = threading.Thread(target=self._serve, name="ds-shell-lock", daemon=True)
bin/ds_shell_core.py:265:            if self._someone_ahead_of(port):
bin/ds_shell_core.py:267:                self.port = port
bin/ds_shell_core.py:271:        raise PortBusy(f"单实例锁端口段 {self.base_port}..{self.base_port + self.span} 全部被占")
bin/ds_shell_core.py:288:        补了探针 `tracks/opendesign-slow-lock-scan/probes/yield_race.py`,量的是一笔
bin/ds_shell_core.py:327:        `opendesign-lock-seniority-field` 的第一件事(那一单的题面已按这份收据改过)。
bin/ds_shell_core.py:348:        return self._scan((p for p in self._ports() if p < mine), patient=True) is not None
bin/ds_shell_core.py:350:    def _scan(self, ports, patient: bool = False) -> int | None:
bin/ds_shell_core.py:364:        ports = list(ports)
bin/ds_shell_core.py:369:        self.scanned += len(ports)
bin/ds_shell_core.py:370:        if not ports:
bin/ds_shell_core.py:374:                max_workers=len(ports), thread_name_prefix="ds-shell-lock-scan") as pool:
bin/ds_shell_core.py:375:            answered = list(pool.map(probe, ports))
bin/ds_shell_core.py:376:        for port, ok in zip(ports, answered):
bin/ds_shell_core.py:378:                return port
bin/ds_shell_core.py:389:        叫醒的办法:先 shutdown() 断开监听,再自连一次把可能仍阻塞的 accept 顶出来。
bin/ds_shell_core.py:393:        port = self.port
bin/ds_shell_core.py:395:        self.port = None
bin/ds_shell_core.py:399:            sock.shutdown(socket.SHUT_RDWR)
bin/ds_shell_core.py:401:            pass          # 监听 socket 上 shutdown 在有的平台直接报错,不影响下一步
bin/ds_shell_core.py:402:        if port:
bin/ds_shell_core.py:404:                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
bin/ds_shell_core.py:416:    def _ports(self):
bin/ds_shell_core.py:417:        return range(self.base_port, self.base_port + self.span + 1)
bin/ds_shell_core.py:419:    def _send_show(self, port: int, patient: bool = False) -> bool:
bin/ds_shell_core.py:425:        t = lock_timeouts()
bin/ds_shell_core.py:430:            with socket.create_connection(("127.0.0.1", port), timeout=connect_deadline) as s:
bin/ds_shell_core.py:459:                             name="ds-shell-lock-conn", daemon=True).start()
bin/ds_shell_core.py:503:                is_restart = verb.strip() == self._RESTART.strip()
bin/ds_shell_core.py:504:                conn.sendall(self._OK_RESTART if is_restart else self._OK)
bin/ds_shell_core.py:509:        cb = self.on_restart if is_restart else self.on_show
bin/ds_shell_core.py:519:    ready_port: int
bin/ds_shell_core.py:522:    # 可选的身份探针:收到 ready_port 后再问一句"听这个端口的真是你吗"。
bin/ds_shell_core.py:524:    # ds-web 用 /api/health 自报版本;不给探针就退化成只看端口。
bin/ds_shell_core.py:531:    proc: subprocess.Popen
bin/ds_shell_core.py:540:        self._shutdown_lock = threading.Lock()
bin/ds_shell_core.py:543:        ports = [int(s.ready_port) for s in services]
bin/ds_shell_core.py:544:        if len(set(ports)) != len(ports):
bin/ds_shell_core.py:545:            raise StartupFailed(f"服务端口重复: {ports}")
bin/ds_shell_core.py:547:            if not port_free(int(svc.ready_port)):
bin/ds_shell_core.py:548:                raise StartupFailed(f"{svc.name} 的端口 {svc.ready_port} 已被占用")
bin/ds_shell_core.py:565:            self.shutdown()
bin/ds_shell_core.py:568:    def restart(self, services: list[Service]) -> None:
bin/ds_shell_core.py:579:        🔴 **不持 `_shutdown_lock` 是有意的取舍**(08-17 四审两腿都提):
bin/ds_shell_core.py:580:        托盘"退出"和这里交错时,新起的网关可能落在 `shutdown()` 的名册快照之后
bin/ds_shell_core.py:581:        ⇒ 理论上留一个孤儿。没加锁是因为 `shutdown()` 持的是同一把,重启途中
bin/ds_shell_core.py:583:        Windows 上外壳退出时 Job 的 KILL_ON_JOB_CLOSE 会兜底,窗口只有毫秒宽。
bin/ds_shell_core.py:584:        **下一个想加锁的人:先把 shutdown 那侧的等待改成可中断的,再动这里。**
bin/ds_shell_core.py:594:            self._terminate_tree(child)
bin/ds_shell_core.py:600:        # 🔴 收尸要走**和 shutdown 同一套**(判据 c18)。少了这一步,Windows 上
bin/ds_shell_core.py:601:        # `_terminate_tree` 只 terminate 了 nanobot 本尊,它带的 3 个 MCP 工具服务
bin/ds_shell_core.py:602:        # 留在 Job 里没人收 —— 关 Job(KILL_ON_JOB_CLOSE)才是那边收整棵树的机制。
bin/ds_shell_core.py:603:        # Linux 看不出来:那边 `_terminate_tree` 打的是整个进程组,孙子跟着一起走。
bin/ds_shell_core.py:606:            self._kill_tree(child)
bin/ds_shell_core.py:616:            port_deadline = time.monotonic() + 5.0
bin/ds_shell_core.py:617:            while not port_free(int(svc.ready_port)):
bin/ds_shell_core.py:618:                if time.monotonic() > port_deadline:
bin/ds_shell_core.py:620:                        f"{svc.name} 的端口 {svc.ready_port} 一直没释放,没能重启")
bin/ds_shell_core.py:629:                # 完全同一套**。这里原来只有 `_terminate_tree` —— Windows 上那等于
bin/ds_shell_core.py:631:                # (KILL_ON_JOB_CLOSE 不触发),外壳里每失败一次还漏一个日志句柄。
bin/ds_shell_core.py:633:                self._kill_tree(child)
bin/ds_shell_core.py:642:    def shutdown(self) -> None:
bin/ds_shell_core.py:643:        with self._shutdown_lock:
bin/ds_shell_core.py:649:                self._terminate_tree(child)
bin/ds_shell_core.py:658:                # posix 上即使父进程已经死了也要再 KILL 一遍进程组:
bin/ds_shell_core.py:661:                    self._kill_tree(child)
bin/ds_shell_core.py:668:                except subprocess.TimeoutExpired:
bin/ds_shell_core.py:691:        看门狗以前分两眼看 —— 先 `poll_dead()` 问"谁死了",再 `dead_reports()`
bin/ds_shell_core.py:697:        修法不是加锁:`shutdown()` 持的是 `_shutdown_lock`,重启途中再互等
bin/ds_shell_core.py:699:        `list(...)` 是同一件事的另一半:遍历途中被 restart 改名册不许抛。
bin/ds_shell_core.py:713:    def dead_reports(self) -> list[str]:
bin/ds_shell_core.py:738:            os.killpg(child.pgid, 0)
bin/ds_shell_core.py:757:            "stderr": subprocess.STDOUT,
bin/ds_shell_core.py:760:        kwargs.update(spawn_kwargs())
bin/ds_shell_core.py:762:            proc = subprocess.Popen([str(x) for x in svc.argv], **kwargs)
bin/ds_shell_core.py:773:            # 那时候 os.getpgid(pid) 已经问不到,进程组就永远没人收。
bin/ds_shell_core.py:775:                child.pgid = os.getpgid(proc.pid)
bin/ds_shell_core.py:777:                child.pgid = proc.pid
bin/ds_shell_core.py:793:            if port_listening(int(svc.ready_port)) and self._probe_ok(svc):
bin/ds_shell_core.py:805:            return bool(svc.ready_probe(int(svc.ready_port)))
bin/ds_shell_core.py:834:    def _terminate_tree(self, child: _Managed) -> None:
bin/ds_shell_core.py:838:                    os.killpg(child.pgid, signal.SIGTERM)
bin/ds_shell_core.py:844:                child.proc.terminate()
bin/ds_shell_core.py:848:    def _kill_tree(self, child: _Managed) -> None:
bin/ds_shell_core.py:852:                    os.killpg(child.pgid, signal.SIGKILL)
bin/ds_shell_core.py:856:        # Windows:关掉 Job 就等于收掉整棵树(KILL_ON_JOB_CLOSE)——
bin/ds_shell_core.py:864:            # 没挂上 Job 时的退路:taskkill /T 连子孙一起杀。
bin/ds_shell_core.py:866:            subprocess.run(
bin/ds_shell_core.py:867:                ["taskkill", "/T", "/F", "/PID", str(child.proc.pid)],
bin/ds_shell_core.py:868:                stdout=subprocess.DEVNULL,
bin/ds_shell_core.py:869:                stderr=subprocess.DEVNULL,
bin/ds_shell_core.py:878:            child.proc.kill()
bin/ds_shell_core.py:882:    def _assign_windows_job(self, proc: subprocess.Popen):
bin/ds_shell_core.py:886:            import ctypes
bin/ds_shell_core.py:887:            from ctypes import wintypes
bin/ds_shell_core.py:942:            info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
bin/ds_shell_core.py:960:            import ctypes
bin/ds_shell_core.py:961:            from ctypes import wintypes
bin/ds_shell_core.py:964:            # 而 KILL_ON_JOB_CLOSE 那条命就白挂了(这一处是第二个现场,别只修一个)。
bin/ds_shell_core.py:980:def patch_config(path, *, gateway_port: int, ws_port: int, python_exe: str,
bin/ds_shell_core.py:981:                 data_root: str | None = None) -> None:
bin/ds_shell_core.py:1002:    servers = cfg.get("tools", {}).get("mcpServers")
bin/ds_shell_core.py:1003:    if not isinstance(servers, dict):
bin/ds_shell_core.py:1004:        raise ConfigUnusable("配置里没有工具服务(mcpServers),这份配置是残的")
bin/ds_shell_core.py:1005:    missing = [n for n in OUR_MCP if not isinstance(servers.get(n), dict)]
bin/ds_shell_core.py:1009:    cfg.setdefault("gateway", {})["port"] = int(gateway_port)
bin/ds_shell_core.py:1010:    ws["port"] = int(ws_port)
bin/ds_shell_core.py:1012:        servers[name]["command"] = str(python_exe)
bin/ds_shell_core.py:1014:        # stdio 客户端只继承一份固定白名单,DS_DATA_ROOT 不在里面。不写进来的话:
bin/ds_shell_core.py:1017:        # 四审 subkimi 抓的 BLOCK;判据 d4 咬着。写绝对路径,不用 ${VAR}:
bin/ds_shell_core.py:1019:        if data_root:
bin/ds_shell_core.py:1020:            servers[name].setdefault("env", {})[ds_common.DATA_ROOT_ENV] = str(data_root)
bin/ds_shell_core.py:1124:def data_root_for(user_home: str) -> str:
bin/ds_shell_core.py:1125:    """装出来那一份的数据根:`<应用状态根>\\Data`(user_home 是它下面的 UserData)。
bin/ds_shell_core.py:1133:def prepare_data_root(user_home: str, ds_root: str) -> dict:
bin/ds_shell_core.py:1139:    os.environ[ds_common.DATA_ROOT_ENV] = data_root_for(user_home)
bin/ds_shell_core.py:1148:    dsweb_port: int,
bin/ds_shell_core.py:1149:    ws_port: int,
bin/ds_shell_core.py:1152:    lock_port: int | None = None,
bin/ds_shell_core.py:1162:    env.update(
bin/ds_shell_core.py:1165:            "DS_DATA_ROOT": data_root_for(str(user_home)),
bin/ds_shell_core.py:1166:            "DS_WEB_PORT": str(dsweb_port),
bin/ds_shell_core.py:1167:            "DS_NANOBOT_PORT": str(ws_port),
bin/ds_shell_core.py:1173:    if lock_port:
bin/ds_shell_core.py:1176:        env["DS_SHELL_LOCK_PORT"] = str(lock_port)
bin/ds_shell_core.py:1192:    dsweb_port: int,
bin/ds_shell_core.py:1193:    ws_port: int,
bin/ds_shell_core.py:1196:    lock_port: int | None = None,
bin/ds_shell_core.py:1200:    🔴 为什么必须分开(2026-08-16 四审 BLOCK,两条评审腿各自独立命中):
bin/ds_shell_core.py:1212:    common = dict(ds_root=ds_root, user_home=user_home, dsweb_port=dsweb_port,
bin/ds_shell_core.py:1213:                  ws_port=ws_port, lock_port=lock_port)
bin/ds_shell_core.py:1222:    exiting: bool
bin/ds_shell_core.py:1228:        self.exiting = False
bin/ds_shell_core.py:1230:        # 没有这把锁,"检查 exiting 再置位"是两步 —— 两个线程能一起穿过去,
bin/ds_shell_core.py:1232:        self._lock = threading.RLock()
bin/ds_shell_core.py:1235:        with self._lock:
bin/ds_shell_core.py:1236:            if self.exiting:
bin/ds_shell_core.py:1243:        with self._lock:
bin/ds_shell_core.py:1244:            if self.exiting:
bin/ds_shell_core.py:1249:    def on_quit(self) -> None:
bin/ds_shell_core.py:1250:        with self._lock:
bin/ds_shell_core.py:1251:            if self.exiting:
bin/ds_shell_core.py:1253:            self.exiting = True
bin/ds_shell.py:19:from __future__ import annotations
bin/ds_shell.py:21:import ctypes
bin/ds_shell.py:22:import json
bin/ds_shell.py:23:import os
bin/ds_shell.py:24:import sys
bin/ds_shell.py:25:import threading
bin/ds_shell.py:26:import time
bin/ds_shell.py:27:import traceback
bin/ds_shell.py:28:from pathlib import Path
bin/ds_shell.py:32:import ds_common  # noqa: E402
bin/ds_shell.py:33:import ds_credential  # noqa: E402  变量名从配置的 apiKey 引用里读,不许写死
bin/ds_shell.py:34:import ds_diag  # noqa: E402  启动可观测性:run_id / 分阶段耗时 / 诊断包
bin/ds_shell.py:35:import ds_shell_core as core  # noqa: E402
bin/ds_shell.py:48:def window_url(port: int) -> str:
bin/ds_shell.py:55:    return f"http://127.0.0.1:{port}/?{SHELL_MARK}"
bin/ds_shell.py:59:LOCK_PORT = 18788
bin/ds_shell.py:67:    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP
bin/ds_shell.py:93:    不想要就在 `%LOCALAPPDATA%\\OpenDesign\\` 里新建一个空文件,
bin/ds_shell.py:130:def web_ready_probe(port: int) -> bool:
bin/ds_shell.py:131:    """工作台"就绪"的真正含义:`/api/health` 应答得了。
bin/ds_shell.py:136:    🔴 **绝不能走系统代理**(判据 s13;2026-08-30 四审孤腿 BLOCK 抓到、我实测坐实)。
bin/ds_shell.py:137:    `urllib.request.urlopen` 对 127.0.0.1 **不绕过**代理:`proxy_bypass('127.0.0.1')`
bin/ds_shell.py:145:    import urllib.request
bin/ds_shell.py:149:                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:
bin/ds_shell.py:156:# 进程真正的起点(import 本身也可能慢,那段时间也该被量到)。
bin/ds_shell.py:172:    sys.exit(1)
bin/ds_shell.py:187:    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "UserData"
bin/ds_shell.py:215:    from PIL import Image, ImageDraw
bin/ds_shell.py:234:def start_backend(home: Path, lock_port: int | None = None):
bin/ds_shell.py:235:    """挑端口 → 改配置 → 按计划拉起后台。返回 (supervisor, web_port, restart_gateway)。
bin/ds_shell.py:239:    填完之后 ds-web 通过锁通道回来叫 `restart_gateway`。
bin/ds_shell.py:247:        gw, ws, web = core.pick_ports(
bin/ds_shell.py:249:    except core.PortBusy as e:
bin/ds_shell.py:253:        core.patch_config(cfg, gateway_port=gw, ws_port=ws, python_exe=str(python_exe()),
bin/ds_shell.py:254:                          data_root=core.data_root_for(str(home)))
bin/ds_shell.py:274:        #    从没设过的变量。(2026-08-16 四审 BLOCK,判据 J 组钉住。)
bin/ds_shell.py:277:            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)
bin/ds_shell.py:312:        migration = core.prepare_data_root(user_home=str(home),
bin/ds_shell.py:320:    logs = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"
bin/ds_shell.py:324:                            env=e, ready_port=ws, log_path=logs / "网关.log",
bin/ds_shell.py:331:                            env=e, ready_port=web, log_path=logs / "工作台.log",
bin/ds_shell.py:348:        sup.shutdown()
bin/ds_shell.py:351:    def restart_gateway():
bin/ds_shell.py:362:            sup.restart([gateway_service(fresh["网关"])])
bin/ds_shell.py:369:    return sup, web, restart_gateway
bin/ds_shell.py:477:            from System import Action        # pythonnet(pywebview 的 Windows 依赖)
bin/ds_shell.py:492:        from ctypes import wintypes            # Windows 才有(core 那边同一写法)
bin/ds_shell.py:513:        from System.Windows.Forms import Screen
bin/ds_shell.py:529:            from System.Windows.Forms import FormWindowState
bin/ds_shell.py:576:        from ctypes import wintypes            # Windows 才有(同 _hit 的写法)
bin/ds_shell.py:724:        from ctypes import wintypes            # Windows 才有(同 _hit 的写法)
bin/ds_shell.py:727:        # 否则这个文件在 Linux 上连 import 都过不去(判据都是静态读源码的)。
bin/ds_shell.py:779:            from ctypes import wintypes
bin/ds_shell.py:841:        from ctypes import wintypes
bin/ds_shell.py:884:            from ctypes import wintypes
bin/ds_shell.py:975:            from ctypes import wintypes
bin/ds_shell.py:1001:                f"        请退出软件、在 %LOCALAPPDATA%\\OpenDesign 里建一个"
bin/ds_shell.py:1012:            17:54:47 窗口打开:http://127.0.0.1:8766/?shell=1
bin/ds_shell.py:1040:            from System.Windows.Forms import FormWindowState
bin/ds_shell.py:1066:                from System.Windows.Forms import FormWindowState
bin/ds_shell.py:1073:            from System.Drawing import Rectangle
bin/ds_shell.py:1092:    def report_startup(self, event: str, detail: str = ""):
bin/ds_shell.py:1095:        白名单 / 限长 / 去重全在 `ds_diag.report_from_ui` 里(判据 s7),
bin/ds_shell.py:1101:        accepted = DIAG.report_from_ui(str(event), str(detail))
bin/ds_shell.py:1110:    def __init__(self, sup, web_port: int, lock: core.InstanceLock):
bin/ds_shell.py:1112:        self.web_port = web_port
bin/ds_shell.py:1113:        self.lock = lock
bin/ds_shell.py:1139:            from System.Windows.Forms import FormWindowState
bin/ds_shell.py:1178:            self.sup.shutdown()
bin/ds_shell.py:1180:            self.lock.release()
bin/ds_shell.py:1195:        """🔴 **只上一次膛**(判据 s14;四审孤腿 BLOCK 抓到)。
bin/ds_shell.py:1198:        再上一次膛的话:页面不会再报首帧(只在加载时报一次),而且 `report_from_ui`
bin/ds_shell.py:1225:            import urllib.request
bin/ds_shell.py:1228:                    f"http://127.0.0.1:{self.web_port}/api/health", timeout=3) as r:
bin/ds_shell.py:1229:                log(f"[启动]   /api/health 通,HTTP {r.status}"
bin/ds_shell.py:1232:            log(f"[启动]   /api/health 不通:{exc!r} ⇒ 问题可能在后端")
bin/ds_shell.py:1235:    def export_diagnostics(self):
bin/ds_shell.py:1239:            DIAG.export_bundle(out, app_dir=_app_dir())
bin/ds_shell.py:1243:            import ds_openfolder
bin/ds_shell.py:1250:        import pystray
bin/ds_shell.py:1255:            pystray.MenuItem("导出本次启动诊断", lambda *_: self.export_diagnostics()),
bin/ds_shell.py:1256:            pystray.MenuItem("退出", lambda *_: self.state.on_quit()),
bin/ds_shell.py:1267:            while not self.state.exiting:
bin/ds_shell.py:1274:                # 拿名字、再问 `dead_reports()` 拿原因,两问之间业主若正好存了 key
bin/ds_shell.py:1279:                    for _, report in found:
bin/ds_shell.py:1280:                        log(f"[后台退出] {report}")
bin/ds_shell.py:1295:    # manifest() 里会 import ds_web 拿版本号(唯一来源)。它是**我自己塞进这段窗口的
bin/ds_shell.py:1303:    restart_holder: list = []
bin/ds_shell.py:1304:    lock = core.InstanceLock(
bin/ds_shell.py:1305:        base_port=LOCK_PORT, span=5,
bin/ds_shell.py:1307:        on_restart=lambda: restart_holder and restart_holder[0]())
bin/ds_shell.py:1309:        if not lock.acquire():
bin/ds_shell.py:1312:    except core.PortBusy as e:
bin/ds_shell.py:1317:    DIAG.mark("lock.acquired",
bin/ds_shell.py:1318:              f"port={lock.port} 扫了{lock.scanned}格 用时{lock.scan_ms:.0f}ms")
bin/ds_shell.py:1322:        sup, web, restart_gateway = start_backend(home, lock_port=lock.port)
bin/ds_shell.py:1324:        restart_holder.append(restart_gateway)
bin/ds_shell.py:1325:        shell = Shell(sup, web, lock)
bin/ds_shell.py:1328:        import webview
bin/ds_shell.py:1363:        shell.state.on_quit()    # 走正常关闭时也要把后台收干净
bin/ds_shell.py:1365:    except ImportError as e:
bin/ds_shell.py:1376:        lock.release()
bin/ds_shell.py:1380:# 🔴 模块体走完 = 所有 import 都办完了。这一条把"进程起来 → 拿到锁"那个
bin/ds_shell.py:1382:#    整条 import 链只要 130ms —— 差 70 倍,差的是 I/O 不是算力。
bin/ds_shell.py:1383:#    切开之后才知道到底是 import 慢、还是锁那一步慢。
bin/ds_shell.py:1384:DIAG.mark("shell.imports_done")
bin/ds_shell.py:1387:    sys.exit(main())

exec
/bin/bash -lc 'for f in .github/workflows/*.yml; do wc -l "$f"; done' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
46 .github/workflows/windows-gui-probe.yml
40 .github/workflows/windows-nonempty-probe.yml
95 .github/workflows/windows-package-probe.yml

exec
/bin/bash -lc "sed -n '1,210p' bin/ds_web.py; sed -n '285,350p' bin/ds_web.py; sed -n '820,980p' bin/ds_web.py; sed -n '2280,2460p' bin/ds_web.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
#!/usr/bin/env python3
"""ds_web — OpenDesign 工作台本地服务(纯 stdlib,track opendesign-workbench)。

静态服务 web/dist(Vite 构建产物) + 只读 API:
  GET /api/todos   ds_todo.collect() 结构化 JSON(每请求现读 PKB,零缓存)
  GET /api/health  存活探针(version + ds_root)
聊天代理(P1,docs/nanobot-ws-protocol.md;8765 零 CORS → 同源转发,纯管道零秘密):
  GET /api/chat/bootstrap             → 127.0.0.1:<nanobot>/webui/bootstrap
  GET /api/chat/sessions              → …/api/sessions
  GET /api/chat/sessions/<key>/thread → …/api/sessions/<key>/webui-thread
  白名单仅此三条;<key> 先验 [A-Za-z0-9_:.-]{1,128} 且拒 './..'(不 unquote,
  %xx 直接非法 → 转发段永远改不了上游路径结构);查询串原样透传;请求头只
  透传 Authorization / X-Nanobot-Auth;上游状态码原样回传(401 不吞,前端
  靠它透明重签);上游连不上 → 502。
文件工作区只读视图(P5,ds_workspace + config/workspace.json):
  GET /api/files/overview/<key>    类目计数+最近文件(未配置/未映射诚实降级)
  GET /api/files/images/<key>      项目图片清单
  GET /api/files/file/<key>/<rel>  项目图片静态服务(三闸同 refs 先例)
  POST /api/open-folder            {"key","sub"?} → 本机资源管理器打开项目夹;
    或 {"key","rel"?}(track p3-polish §I4)→ 用系统默认程序打开单个文件。
    这是"只读铁律"的首个受控例外(P5 design §3,用户拍板):不写任何数据,
    sub 分支仅在 key 映射 + sub 白名单 + realpath within + isdir 全过后执行
    OPEN_LAUNCHER;rel 分支仅在 key 映射 + relpath_ok + realpath within +
    扩展名白名单(_OPEN_EXTS)+ isfile 全过后执行;rel/sub 同给 → 400。
    launcher 可注入(测试/e2e 永不真开)。
  POST /api/chat/sessions/<key>/delete  → …/api/sessions/<key>/delete(p7 第二针孔):
    删除历史对话 = 代理 nanobot 原生删除(上游自带"绑定自动化先拒"保护);上游
    不查方法,本服务只以 POST 暴露(GET 面保持纯只读);真正鉴权在上游 Bearer
    token,CT json 闸是 CSRF 纵深。本服务仍零 PKB 写面。
收件箱认领(track opendesign-intake,聊天驱动+面板确认):
  GET /api/intake                  收件箱清单+确定性建议+待确认 plans(只读,
                                   未配置降级 configured:false)
  POST /api/intake/approve         {"plan_id"} 针孔④:卡片「确认执行」= 人工批准
    本体(替代终端 ds-approve,仅限 root 在工作区根内的 intake plan;工作区外
    plan 维持 CLI 批准)→ approve+apply 一气,apply 整体快照复验兜 TOCTOU。
  POST /api/intake/amend           {"plan_id","drop"} 针孔⑧(track opendesign-
    frontend-p1):卡片单条「跳过」纠偏 → ds_intake.amend_plan(剩余行经
    stage_plan 全套复验重新暂存;旧 plan 标 superseded_at,不删文件)。
其余方法/其余 POST 路径一律 405 —— 写操作必须过 ds_tools 核心,本服务不直改 PKB。
项目列表(p7):/api/projects = PKB projects/*.md ∪ 工作区项目夹自动发现
(ds_workspace.project_folders,未被映射/绑定消费的文件夹以 unregistered:true 追加;
只读联合,不自动建档)。
  POST /api/projects/bind          {"project","folder"} 针孔⑨(同上 track):
    项目↔工作区文件夹关联薄壳,直调 ds_tools.bind_project(名字闸/两级匹配/
    原子写全在核心)。
切阶段/参考图标签就地改/变更历史(track opendesign-stage-history,P2 队列 #7#8#9):
  POST /api/projects/stage         {"project","stage"} 针孔⑩:薄壳直调
    ds_tools.set_stage(词表精确匹配/名字闸/锁/页脚 bump 全在核心);GET /api/projects
    顶层加 stages 词表(单一真相源)。
  POST /api/refs/update            {"ref_id","style","space","note"} 针孔⑪:薄壳直调
    ds_refs.update_ref(词表校验/分段重写/锁/页脚 bump 全在核心,只重写头段与备注段,
    来源/文件/用于逐字节不变);GET /api/projects/<key>/refs 加 vocab 词表。
  #9 纯前端:/api/projects/<key>/changes 早就返回 history/note,UI 侧渲染。

约束(design.md D2):只绑 127.0.0.1;端口 DS_WEB_PORT(默认 8766),被占明确报错
退出不静默换口;JSON ensure_ascii=False + charset=utf-8;读期 OSError(Windows
msvcrt 强制锁窗口内并发读会瞬时报错)归入 500 路径,刷新自愈;静态路径
unquote → realpath → ds_common.within 防逃逸。
环境变量:DS_ROOT / DS_WEB_PORT / DS_WEB_DIST(测试注入用)/ DS_NANOBOT_PORT。
"""
import http.client
import base64
import binascii
import hashlib
import json
import os
import re
import socket
import sys
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

import ds_common
import ds_consent
import ds_credential  # 大模型 key(track opendesign-key-onboarding)
import ds_intake    # 收件箱清单/建议(track opendesign-intake)
import ds_model
import ds_openfolder
import ds_organize  # 针孔④ approve+apply 直调核心(锁/复验/审计全在核心)
import ds_refs
import ds_shell_core     # 只取锁通道的协议常量与读行:帧格式两处各抄一份迟早对不上
import ds_taxonomy
import ds_update    # 查更新(track opendesign-in-app-update):只查不装
import ds_todo
import ds_tools
import ds_workspace

# 版本号约定(2026-08-25 业主亲口定):**从 0.98 起只往第三位加** —— 0.98.1、
# 0.98.2、0.98.3……**中途不许跳到 0.99 或 1.x**。`1.0.0` 留给业主说"就它了"
# 的那一版(他的原话:"我希望最后发行版是 1.0")。
VERSION = "0.98.4"  # 应用内更新第一刀:软件自己发现新版并说一句(只查不装)
                    # (track opendesign-in-app-update)
                    # 业主装上去**感觉不到变化**,只多一个托盘菜单「导出本次启动诊断」;
                    # 换来的是:每次启动有编号、有分阶段耗时、有网页内核版本,
                    # 白屏时能把现场打包发回来 —— 08-25 那晚我们手上一条线索都没有。
                    # 🔴 这一版还捎带修了一个**会让软件根本打不开**的新回归:
                    # 我给"后端就绪"加的探针走了系统代理(urlopen 对 127.0.0.1 不绕代理),
                    # 配了公司代理 / Clash 类 VPN 的机器上会死等 60s 然后判启动失败。
                    # 怎么发现的:**四审孤腿 BLOCK,然后我自己造探针复现**——
                    # 两条判 PASS 的腿都没看见(而且它们在读我的自审)。
                    # 链条:ds_merge_config 把配置写好了 → 最后一句「已合并 4 段进…」
                    # 在 cp1252 的 stdout 上 UnicodeEncodeError → rc≠0 →
                    # provision 判「合并失败」→ finally 删掉临时配置(顺序本身是对的)
                    # → config.json 从没出现 → 安装器弹「配置初始化没有成功(错误码 2)」
                    # → **NSIS 的 MessageBox 在 /S 下照弹** → 没人点 → 安装器假死。
                    # 修两处:① 这条链上的 Python 输出与控制台编码脱钩(输出通道有权
                    # 难看、没权杀进程)② 4 个 MessageBox 补 /SD(与①无关,①好了下一个
                    # 错误照样卡死)。业主两台是中文 Windows(cp936),**他从没撞上过**。
                    # ⚠️ 端到端要等这一版发出去、云机器再装一遍才算数。
                    # 0.97.0  pywebview 5.4 → 6.2.1(track opendesign-pywebview-upgrade)
                    # 业主指令「先升级吧」。我们原来锁在 2025-01 的 5.4,落后两个大版本;
                    # 0.96 的动画是在旧后端上绕出来的,不是上游认可的路。
                    # 前提核查:6.0 的三条 BREAKING 一条都不沾我们(只用了 8 个 API);
                    # 而动画依赖的 WinForms 后端按 frameless|FormBorderStyle|WndProc|
                    # CreateParams 过滤,5.4→6.2.1 **一行都没改**。
                    # ⚠️ 但"接口面没变"不等于"行为没变":6.x 新增了深色模式的
                    # DwmSetWindowAttribute,和我们的非客户区接管是同一片地 ——
                    # 那一层 Linux 验不了,**动画要在真机上重验一次**。
                    # 回退:pin 改回 5.4 重打包,代码零改动;业主重装 0.96 即可。
                    # 0.96.0  动画默认开着了,而且找到了一处真正可疑的偏离:
                    # 业主:「你为什么不直接给我做好动画的,要默认关闭动画」——
                    # 对的。0.95 装了"不对自动退回"的保险却又不敢依赖它,自相矛盾;
                    # 而且 0.95 起开窗口时不碰边框 ⇒ 最坏情况已从"一起来就是砖"
                    # 降到"重开一下就好"。所以默认打开,逃生门是
                    # %LOCALAPPDATA%\OpenDesign\关掉窗口动画.on。
                    #
                    # 🔴 更要紧的是业主追问「别人做成了为什么我们做不成」逼出来的:
                    # 我去扒了 WinFormedge(WinForms+WebView2,和我们同一套壳)的源码
                    # FormBase.cs:390 —— 它在 WM_NCCALCSIZE 的 wParam==0 那条上
                    # **是 break 到 base.WndProc,从不短路**;
                    # 而 0.93 我照评审腿建议改成了"两种 wParam 都 return 0",
                    # 还在注释里编了一句"WinFormedge 也为这条路打过补丁"。
                    # 时间线:那一笔是 c09ad55,就在 bump 0.93.0 前面 ——
                    # **业主唯一跑过、然后白屏的那一版,带着这个偏离**;
                    # 改之前(58b397e)本来和参考实现一致,但那版从没到过他机器上。
                    # 机制说得通:短路掉 wParam==0,WinForms 那层维护不了客户区记账,
                    # 而 WebView2 是挂在它下面的子窗口,布局和绘制正靠这套记账。
                    # ⚠️ 最可疑的线索,**不是已证实的根因**,只有真机能定案。
                    # 0.95.0  安装包小一半 + 窗口动画换个时机再试一次:
                    # ① 安装包瘦身(track opendesign-installer-slim):业主说装和卸都慢。
                    #    实测整包 22,118 个文件,而 OpenDesign 自己只占 42 个 ——
                    #    慢在 Windows 挨个写/删这两万多个小文件、每个还过一遍杀毒。
                    #    去掉他一个都没用的三族可选连接器(飞书 SDK / 亚马逊云 / Telegram):
                    #    **12,438 个文件、42 MB**,整包 22,118 → 9,680(砍掉 56%)。
                    #    可逆:删除清单是 build-package.sh 里的 SLIM_DROP 数组,
                    #    要加回来就删掉那一行重新打包,nanobot 的代码一个字节没动。
                    # ② 窗口动画(track opendesign-native-frame):方案 B 挪到"用的时候"才装。
                    #    真机日志显示 0.93 是在**窗口打开后一秒之内**动的边框,
                    #    正撞 WebView2 初始化;业主答"打开就白"。0.92 同样早却没事 ——
                    #    它贴的三个位不改变非客户区。⇒ 假设:时机撞车(**未证实**)。
                    #    这一版:shown 只贴安全位,方案 B 挪到第一次点缩小/最大化;
                    #    装完当场量子窗口,量出来明显坏了就**自动退回去** ——
                    #    最坏情况从"白屏"降级成"没有动画"。
                    #    仍在实验开关后面(默认关)。
                    # 0.94.0  窗口重新打得开(业主真机红:0.93 打开全是白的):
                    # 0.93.0 装到业主机器上「打开全是白的什么都没有了」。
                    # 本地核实:他装的确实是 0.93.0(发布物 digest 与本地 exe 逐字节
                    # 一致);包里前端产物完好、且与 0.92 的包**逐字节相同**;
                    # ds_web.py 两版之间只改了 VERSION 注释 ⇒ 从"看得见"到"全白"
                    # 唯一的功能性差量就是 ds_shell.py 的方案 B(接管窗口边框计算),
                    # 而它挂在 shown 上、开窗口就跑,与"打开就白"时间点吻合。
                    # 方案 B 的 ctypes 类型声明、常量对表、WM_NCCALCSIZE 两条 wParam
                    # 路都逐条读过,**没有笔误** —— 病在它与 WebView2 的运行时交互,
                    # 那一层 Linux 上一行都跑不到。0.92/0.93 连着两版都死在
                    # "把推论当结论发出去",这一版不再赌:
                    #   默认路径退回 0.92 那套真机验过能用的窗口行为(只贴三个
                    #   不参与绘制的样式位 + 假最大化);
                    #   方案 B 整套收进默认关闭的实验开关 frame_experiment_on()
                    #   (%LOCALAPPDATA%\OpenDesign\实验-窗口动画.on),
                    #   打开时额外写窗口/客户区/子窗口几何的诊断日志 ——
                    #   0.93 那趟我手上一个数字都没有,只能再要一趟。
                    # 代价说清楚:默认路径**没有缩小/放大动画**(业主本来也没有)。
                    # 0.93.0  缩小/放大都有系统动画了,靠把窗口框架接回来:
                    # 业主 08-23 验收 0.92 之后:「缩小和放大的动画还是没有」。
                    # **0.92 的规格问错了问题**:它贴的三个位管的是系统菜单和
                    # Win+方向键(那些确实修好了),而动画归 WS_CAPTION/WS_THICKFRAME
                    # 那一族 —— 恰恰是 0.92 特意排除的两个。真机 STYLE=0x360B0000 逐位对上,
                    # 业主机器上 5 个有动画的窗口 CAPTION+THICKFRAME 全都同时有。
                    # 这一版把那两个位加回来,再用 ctypes 装一个窗口过程接管 WM_NCCALCSIZE
                    # 把标题栏那块地方吃掉 —— 系统眼里框还在(所以有动画、有贴边分屏),
                    # 外观上一个像素不变。顺带拆掉"假最大化"换成真的(放大动画那一半)。
                    # pythonnet 覆写 WndProc 那条路真机探针实测走不通(回调 0 次),
                    # 走的是 ctypes SetWindowLongPtrW(GWLP_WNDPROC)。
                    # 0.92.0  缩小按钮重新有"向下收进任务栏"的动画(track opendesign-minimize-animation):
                    # 业主 08-23:「缩小按钮在页面上是直接消失,不会像成熟的产品一样有
                    # 向下缩小的动画,这个很重要,可以引导用户知道页面在底部」。
                    # 根因不是动画是**身份**:frameless ⇒ FormBorderStyle=None ⇒
                    # WinForms 的 CreateParams 把 WS_SYSMENU/WS_MINIMIZEBOX/WS_MAXIMIZEBOX
                    # 那批位一个都不发,而 Windows 的窗口待遇全按这些位发。贴回三个
                    # 不影响绘制的位就够(Electron 2014 年 #751 同一个坑、同一个结论)。
                    # 顺带修掉一条更狠的:缩小之后点托盘图标叫不回窗口 —— pywebview 的
                    # show() 是 Show()+Activate(),对最小化的窗口不还原(#1749 列过,
                    # 我们从没验过)。现在先 restore 再 show。
                    # ⚠️ 拖边缘分屏 / Win11 分屏布局 / 那个"假最大化"**本版没修**,
                    #    它们要动窗口非客户区,是方案 B,单独一单。
                    # 0.91.0  右上角那三个按钮和拖动带真的画出来了(track opendesign-shell-chrome):
                    # 无边框窗口把系统标题栏拿掉了,三个按钮 + 30px 拖动带 + 八个把手
                    # 改由前端自己画 —— 而它们在业主机器上**一样都没出现**
                    # (「拖不动 / 右上角还是没有缩小放大和退出」,0.89、0.90 两版都是)。
                    # 病根:分界问的是 window.pywebview 注没注进来,而 pywebview 在
                    # on_navigation_completed 之后才注入(页面脚本早跑完了)⇒ 首帧永远答 false。
                    # 改成外壳打开页面时在地址里报身份(?shell=1),第一帧就定;
                    # 顺带把"这条栏会不会被画出来"变成 Linux 上考得了的题(新 e2e shell_chrome)。
                    # 0.90.0  打开软件不再冒黑窗口(track opendesign-console-windows):
                    # 外壳是无控制台的 pythonw,却用 python.exe 起腿 ⇒ Windows 给每条腿
                    # 新开一个控制台窗口,而业主关掉它就等于杀掉那条腿(他亲手复现过)。
                    # 子进程的平台参数收进唯一来源 spawn_kwargs(),调用点不许自己拼;
    except FileExistsError:
        # 竞态输了或名字刚被占:复查一次再判,别把"别人先建好了"说成"被文件占了"
        if os.path.islink(target):
            return None, "inbox_outside_root"
        if os.path.isdir(target):
            return "already_exists", None
        return None, "name_taken"
    return "created", None


def _read_model():
    """当前大脑,解析规则与 nanobot 一致(schema.py:AgentDefaults):modelPreset 设了
    就以它指向的预设为准,悬空/未设才回落 agents.defaults.model —— 只读 model 字段会
    在 preset 布局(install.ps1 合并模板后的真机形态)回显假值(07-13 的雷)。
    只读、每请求现读(零缓存,与 /api/todos 同哲学);任何读取失败 → None,
    健康探针本体不受牵连。解析规则抽到 ds_model(与 set_model.py 同一真相源,L1)。"""
    try:
        cfg = os.environ.get("DS_NANOBOT_CONFIG", DEFAULT_NANOBOT_CONFIG)
        with open(cfg, encoding="utf-8") as fh:
            return ds_model.resolve_model(json.load(fh))
    except Exception:
        return None
def _restart_verdict(reply: bytes) -> str:
    """把外壳的应答翻译成给业主看的那句话。**只有点名了动词的应答才算数。**

    裸 `OK` 是老外壳的应答 —— 它收下了帧,但它做的是"把窗口叫到前台",不是重启。
    把那种情况报成 `requested`,界面就会说「已经自动应用新配置」而网关一动没动。
    ⇒ 宁可让业主多点一下(`manual`),也不要一句会撒谎的"已生效"。
    """
    return "requested" if reply == ds_shell_core.LOCK_OK_RESTART.strip() else "manual"


def ds_shell_bridge_restart() -> str:
    """请外壳重启网关(网关只在启动时读一次 env,不重来就认不到新 key)。

    走**外壳单实例锁那条已有的通道**:不新开端口、不新造 IPC(design 第三节)。
    外壳把锁端口写在 `DS_SHELL_LOCK_PORT` 里交给我们(ds_shell_core.child_env)。

    🔴 这个函数的全部难点是**不许撒谎**:回 "requested" 就意味着帧真的送到了外壳
    并且它认了。任何一步不确定 —— 没有外壳、端口上没人、占着那个号的是别的程序、
    它不吭声 —— 一律回 "manual",前端就说「配置好了,请重启一下程序」。
    宁可让他多点一下,也不要一句会撒谎的"已生效"。
    (git-pull 那两台本来就没有外壳,走的正是 manual 这条路。)
    """
    raw = (os.environ.get("DS_SHELL_LOCK_PORT") or "").strip()
    if not raw.isdigit():
        return "manual"
    try:
        with socket.create_connection(("127.0.0.1", int(raw)), timeout=3) as s:
            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_RESTART)
            reply = ds_shell_core.recv_line(s, deadline=time.monotonic() + 3)
    except (OSError, ValueError):
        return "manual"
    # 只有对上暗号才算数:端口是全机器共用的,占着那个号的完全可能是别的程序。
    return _restart_verdict(reply)


def _gateway_password() -> str | None:
    """网关 websocket 通道的口令(**只往上游发,永不回给浏览器**)。

    track opendesign-key-onboarding:业主不该被要求记一个我们自己生成的口令 ——
    ds-web 从配置里读出来替前端签。**每请求现读**,与 `_read_model` 同哲学:
    业主改了口令不用重启 ds-web。
    """
    try:
        cfg = os.environ.get("DS_NANOBOT_CONFIG", DEFAULT_NANOBOT_CONFIG)
                reason = "default"
            folders.append({
                "name": name,
                "reason": reason,
                "currentlyHidden": reason in ("declared", "guessed"),
                "preselect": reason == "declared",
                "missing": name not in current,
            })
    return {
        "configured": True,
        "applicable": applicable,
        "declared": declared,
        "root": root_real,
        "projectsRoot": projects_real,
        "projectCount": len(ds_workspace.project_folders(cfg)),
        "folders": folders,
        "reviewId": _workspace_review_id(config_bytes, top_dirs),
    }
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_DIST = os.path.join(DEFAULT_DS_ROOT, "web", "dist")
DEFAULT_PORT = 8766

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"ds-web/{VERSION}"

    # ---- helpers ----
    def _send(self, status: int, ctype: str, body: bytes, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        # 浏览器别自作主张嗅探类型:声明 image/png 就当图,不会被当 HTML 跑。
        # (上传口开放后,盘上可能出现"名叫 .png、内容不是图"的文件;读出面按扩展名
        #  发类型,加这一行把嗅探那半条路也焊死。)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    # 连接级超时(track opendesign-image-upload):上传口的体积上限抬到 14MB 后,
    # "Content-Length 说 14MB 却只发 1 字节"的连接会把一个工作线程挂死。
    timeout = 30

    def log_message(self, fmt, *args):  # 请求日志走 stdout(design D2 运维面)
        # 🔴 2026-08-30(判据 s2):补时间戳并**立刻 flush**。
        #    这份日志原来一个时间都没有 —— 于是"JS 是什么时候被请求的"
        #    "健康检查什么时候通的"在白屏事后一个都答不了,而那正是分流表里
        #    最要紧的几个分叉(08-25 白屏,我们手上一条线索都没有)。
        #    不 flush 的话崩溃时缓冲区里那几行会一起丢掉 —— 恰恰是最后几行最值钱。
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        sys.stdout.write("%s %s - %s\n" % (stamp, self.address_string(), fmt % args))
        try:
            sys.stdout.flush()
        except Exception:
            pass

    def _host_ok(self) -> bool:
        """H2(07-13 盲评):Host 白名单,拒 DNS rebinding。

        rebinding 下 TCP 连的是 127.0.0.1 但浏览器带的 Host 是恶意域名——绑 loopback
        与 CORS 都不挡它,Host 头是唯一可辨信号。只认本机形态(带不带端口都认:
        非标准端口浏览器必带,留裸形态兜 80 端口边缘);比较不区分大小写。
        """
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}",
                        "127.0.0.1", "localhost", "[::1]"}

    # ---- routes ----
    def do_GET(self):
        if not self._host_ok():
            self._json(403, {"error": "bad host"})
            return
        # track opendesign-key-onboarding:前端不再手输口令之后补的纵深。
        # 它挡"能被跨站触发的带副作用请求";浏览器同源策略与 _host_ok 各守另一面。
        if not self._same_site_ok():
            self._json(403, {"error": "cross-site"})
            return
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "version": VERSION,
                             "ds_root": self.server.ds_root,
                             "model": _read_model(),
                             # 文档转换器装没装:业主刷一下 /api/health 就看得见,
                             # 不用开命令行(部署规矩:盘上有 ≠ 跑起来有)。
                             "doc_reader": _doc_reader_status()})
        elif path == "/api/update/check":
            self._update_check()
        elif path == "/api/todos":
            self._todos()
        elif path == "/api/llm/credential":
            self._llm_credential_get()
        elif path == "/api/chat/bootstrap":
            self._proxy("/webui/bootstrap")
        elif path == "/api/chat/sessions":
            self._proxy("/api/sessions")
        elif (m := _THREAD_RE.match(path)):
            key = m.group(1)  # 原样段,不 unquote(见模块头契约)
            if _KEY_RE.match(key) and key not in (".", ".."):
                self._proxy(f"/api/sessions/{key}/webui-thread")
            else:
                self._json(404, {"error": "bad key"})
        elif path == "/api/intake":
            self._intake()
        elif path == "/api/consent":
            self._consent()
        elif path == "/api/projects":
            self._projects()
        elif path == "/api/workspace/health":
            self._workspace_health()
        elif (m := _CHANGES_RE.match(path)):
            self._changes(unquote(m.group(1)))
        elif (m := _PROJ_REFS_RE.match(path)):
            self._project_refs(unquote(m.group(1)))
        elif (m := _REFS_FILE_RE.match(path)):
            self._refs_file(unquote(m.group(1)))
        elif (m := _FILES_OVERVIEW_RE.match(path)):
            self._files_meta(unquote(m.group(1)), "overview")
        elif (m := _FILES_IMAGES_RE.match(path)):
            self._files_meta(unquote(m.group(1)), "images")
        elif (m := _FILES_FILE_RE.match(path)):
            self._files_file(unquote(m.group(1)), unquote(m.group(2)))
        elif path.startswith("/api/"):
            self._json(404, {"error": "unknown api"})
        else:
            self._static(path)

    def _method_not_allowed(self):  # P0 只读:写方法焊死 405(oracle #5)
        body = json.dumps({"error": "read-only"}, ensure_ascii=False).encode("utf-8")
        self._send(405, "application/json; charset=utf-8", body,
                   {"Allow": "GET"})  # RFC 7231 §6.5.5:405 必带 Allow

    def do_POST(self):
        if not self._host_ok():  # H2:针孔与 405 之前先验 Host(同 do_GET)
            self._json(403, {"error": "bad host"})
            return
        # track opendesign-key-onboarding:前端不再手输口令之后补的纵深。
        # 它挡"能被跨站触发的带副作用请求";浏览器同源策略与 _host_ok 各守另一面。
        if not self._same_site_ok():
            self._json(403, {"error": "cross-site"})
            return
        # 只读铁律的受控针孔白名单(精确匹配,其余 POST 维持 405,oracle 锁死):
        # ① open-folder(P5)② 会话删除代理(p7,真正鉴权在上游 Bearer token)
        path = urlsplit(self.path).path
        名字闸/词表精确匹配/锁/页脚 bump 全在核心)。响应体不回显词表(词表走
        GET /api/projects 的 stages,写口少一条外泄面)。Host 闸由 do_POST 入口继承。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _STAGE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        stage = body.get("stage")
        since = body.get("since")
        if (not isinstance(project, str) or not project
                or not isinstance(stage, str) or not stage):
            self._json(400, {"error": "bad request"})
            return
        if since is not None and not isinstance(since, str):
            self._json(400, {"error": "bad request"})
            return
        if since == "":
            self._json(400, {"error": "invalid_since"})
            return
        r = ds_tools.set_stage(project, stage, since=since, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_STAGE_ERR_STATUS.get(err, 400), {"error": err})

    def _refs_update(self):
        """POST 写针孔⑪(track opendesign-stage-history §8):参考图标签/备注就地改。
        薄壳,posture 同 ⑩:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {ref_id, style, space, note}(多余键即拒,防夹带
        file/source/used 走私)→ ref_id 必须 str → style/space/note 给了必须是 str
        (缺省=不动,原样交核心区分)→ ds_refs.update_ref(词表/分段重写/锁/页脚 bump
        全在核心)。Host 闸由 do_POST 入口继承。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _REFS_UPDATE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        ref_id = body.get("ref_id")
        if not isinstance(ref_id, str):
            self._json(400, {"error": "bad request"})
            return
        if any(k in body and not isinstance(body[k], str)
               for k in ("style", "space", "note")):
            self._json(400, {"error": "bad request"})
            return
        r = ds_refs.update_ref(
            ref_id,
            style=body.get("style") if "style" in body else None,
            space=body.get("space") if "space" in body else None,
            note=body.get("note") if "note" in body else None,
            ds_root=self.server.ds_root)
        if r.get("ok"):
            # 只回 {ok, ref_id}:核心的 r["line"] 是整行,含读口刻意不外泄的
            # `来源:`/`用于:`(见 _project_refs 注释)。同一份数据两个口径必须一致。
            self._json(200, {"ok": True, "ref_id": r.get("ref_id")})
            return
        err = r.get("error", "internal")
        self._json(_REFS_UPDATE_ERR_STATUS.get(err, 400), {"error": err})

    def _set_due_date(self):
        """POST 写针孔⑫(track opendesign-todo-duedate design.md):设/清一条变更的截止日。
        posture 逐条照抄 _edit_change:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {project, cnum, due}(多余键即拒,防夹带 ds_root/today 走私)→
        类型闸(due 可为 null/字符串)→ ds_tools.set_due_date(格式校验/定位/锁/页脚 bump
        全在核心)。Host 闸由 do_POST 入口继承。精确匹配(非前缀)防路径走私。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _DUE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        if not isinstance(project, str) or not project:
            self._json(400, {"error": "bad request"})
            return
        due = body.get("due")
        if due is not None and not isinstance(due, str):
            self._json(400, {"error": "bad request"})
            return
        # cnum 原样交核心:缺失/非数 → set_due_date 判 change_not_found(同 edit_change 口径)
        r = ds_tools.set_due_date(project, body.get("cnum"), due, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_DUE_ERR_STATUS.get(err, 400), {"error": err})

    def _delete_change(self):
        """POST 写针孔⑮(track opendesign-owner-review-0808):待办「删除」按钮。
        posture 逐条照抄 _set_due_date:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {project, cnum}(多余键即拒,防夹带 ds_root/today 走私)→
        ds_tools.delete_change(定位/校验/锁/页脚 bump 全在核心;写的是字面量"已删除",
        不经 STATUSES 词表)。前端二次确认(确定/取消弹窗)在浏览器那一侧,这里不重复
        问一遍——已经收到这个请求就等于用户点了"确定"。Host 闸由 do_POST 入口继承。
        精确匹配(非前缀)防路径走私。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _DELETE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        if not isinstance(project, str) or not project:
            self._json(400, {"error": "bad request"})
            return
        # cnum 原样交核心:缺失/非数 → delete_change 判 change_not_found(同 set_due_date 口径)
        r = ds_tools.delete_change(project, body.get("cnum"), ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_DELETE_ERR_STATUS.get(err, 400), {"error": err})

    def _proxy(self, up_path: str):
        """白名单转发到本机 nanobot gateway。纯管道:不读不存任何秘密。
        上游方法恒为 GET(nanobot ws_http 路由不查方法;delete 针孔也走这条,
        POST 语义只存在于本服务的暴露面)——将来若有上游要求真 POST 的端点,
        这里要加 method 参数,别隐式复用。"""
        q = urlsplit(self.path).query
        if q:
            up_path += "?" + q
        hdrs = {}
        for h in ("Authorization", "X-Nanobot-Auth"):  # 请求头白名单,其余剥离
            v = self.headers.get(h)
            if v is not None:

exec
/bin/bash -lc "sed -n '1,190p' bin/ds_shell_core.py; sed -n '190,540p' bin/ds_shell_core.py; sed -n '519,890p' bin/ds_shell_core.py; sed -n '1110,1265p' bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
exec
/bin/bash -lc "sed -n '1,390p' bin/ds_shell.py; sed -n '1080,1390p' bin/ds_shell.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
#!/usr/bin/env python3
"""OpenDesign 桌面外壳的平台无关内核。"""

from __future__ import annotations

import concurrent.futures
import functools
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import ds_common
from typing import Any


# ── 子进程创建的平台参数:唯一来源 ──────────────────────────────────────
#
# 业主 2026-08-17 装完 0.89.0:「为什么打开这个软件还会跳出命令行呢」——
# 两个黑窗口(网关一个、工作台一个),而且**关掉一个就等于杀掉一条腿**。
# 外壳自己是没有控制台的 `pythonw.exe`,却用 `python.exe`(控制台程序)起腿:
# **没有控制台的进程去起控制台程序,Windows 会为它新开一个控制台窗口。**
#
# 🔴 数值写死,不用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)`:
#    Linux 的 subprocess **没有**这两个常量,getattr 会退化成 0,
#    而 0 和"没设"一模一样 ⇒ 本机判据永远问不出东西(假绿)。
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
WINDOWS_SPAWN_FLAGS = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW


def spawn_kwargs(os_name: str = "") -> dict[str, Any]:
    """起子进程时要额外传给 `subprocess` 的平台参数 —— **唯一来源**。

    调用点不许自己拼:漏一位的代价是真机上冒一个业主关得掉的黑窗口,
    而本机一条判据都不会红(那一位只在 Windows 上有意义)。
    `tests/test_no_console_window.py` 机械地查"每个创建点是不是走了这儿"。
    """
    name = os_name or os.name
    if name == "posix":
        # 自成会话 ⇒ 收尸时按进程组收,孙进程跑不掉(c1/c2/c13 咬的就是它)
        return {"start_new_session": True}
    if name == "nt":
        return {"creationflags": WINDOWS_SPAWN_FLAGS}
    return {}


class PortBusy(RuntimeError):
    """端口段全被占。"""


class StartupFailed(RuntimeError):
    """子进程启动失败。"""


class ConfigUnusable(RuntimeError):
    """配置本身无法安全使用。"""


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否可以被当前进程绑定。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    """端口上是否有 TCP 服务正在接受连接。"""
    try:
        with socket.create_connection((host, int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def pick_port(preferred: int, *, span: int = 20) -> int:
    start = int(preferred)
    for port in range(start, start + int(span) + 1):
        if port_free(port):
            return port
    raise PortBusy(f"端口段 {start}..{start + int(span)} 全部被占")


def pick_ports(preferred: list[int], *, span: int = 20) -> list[int]:
    chosen: list[int] = []
    used: set[int] = set()
    for wanted in preferred:
        start = int(wanted)
        for port in range(start, start + int(span) + 1):
            if port not in used and port_free(port):
                chosen.append(port)
                used.add(port)
                break
        else:
            raise PortBusy(f"端口段 {start}..{start + int(span)} 没有可用端口")
    return chosen


def lock_sockopts(platform: str) -> list[tuple[str, int]]:
    """这个平台上,单实例锁的 socket 该设哪些选项。纯数据 —— 好让考卷问得出来。

    ⚠️ 兜底值必须是 Windows 上的真值 `-5`(= ~SO_REUSEADDR),**不能随手写 4**:
    4 在 Linux 上正好是 SO_REUSEADDR —— 恰恰是这把锁一辈子都不许设的那一个
    (Windows 上它允许后来者抢走监听端口 ⇒ 锁会被偷)。兜底写错方向 = 埋雷。
    """
    if platform.startswith("win"):
        return [("SO_EXCLUSIVEADDRUSE", int(getattr(socket, "SO_EXCLUSIVEADDRUSE", -5)))]
    return []


def lock_timeouts() -> dict[str, float]:
    """握手的两个期限。纯数据 —— 和 `lock_sockopts` 一个用意:好让考卷问得出来。

    **两个都是 1.5s,而且都不许再往下调。** 考卷 l2 钉着这条下限。

    🔴 这里曾经写着相反的话("connect 可以很短,因为对面活着时握手由内核在 backlog
    里完成"),并据此把 connect 缩到 0.25s。**那半句是错的,而且错法是可量的**
    (2026-09-01,三条评审腿里两条 BLOCK,加我自己共四次独立复现):

        本机 200 次回环 connect(对面**正常 accept**),见
        tracks/opendesign-slow-lock-scan/probes/connect_latency.py:
            中位 0.056ms   p99 1022.975ms   max 1023.173ms

    内核确实在 backlog 里完成握手 —— 但 backlog 一瞬间满掉就会丢 SYN,
    TCP 要等约 1 秒才重传。所以"对面活着 ⇒ connect 一定快"只在中位数上成立,
    **尾巴上不成立**。1.5s 罩得住整条实测尾巴,0.25s 罩不住 ⇒ 每次触发条件成立时
    约 1~3% 的概率把**活着的**第一份看成不存在 ⇒ 业主开出两份、两个后台对着
    同一个 data_root(评审腿查过:`pick_ports(span=20)` 会让第二份换端口照跑,
    没有第二层保护)。

    **那 9 秒是靠并发省下来的,不是靠缩这个期限:**
        串行 1.5s            9001.6ms   ← 探针模型,对上业主真机 9047ms
        并发 + connect=1.5   1502.5ms   快 6.0 倍,省 7.5s
        并发 + connect=0.25   251.2ms   只多省 1.25s
    (三个数各有收据:前两个在 probes-after-connect-1500,第三个在
     blackhole-with-connect-025-the-1250ms-question —— 2026-09-02 补,
     此前 "252ms" 是手抄的、仓库里没有出处,评审腿第三轮 LOW 第 4 条点名。)
    为那 1.25s 把数据面赌进去不划算,所以这一单**只要并发那一份收益**。

    由来:2026-09-01 业主真机第一份启动诊断。此前两个期限都是 1.5s,而且**串行**扫
    6 个锁位;他那台机器上每个锁位都耗满 ⇒ `manifest.done` 到 `lock.acquired`
    干等 **9047ms**,占整趟启动 11031ms 的 82%。他的原话是"直接没反应了十几秒"。
    (同样的扫描在本机 Linux 上是**毫秒级**:20 次扫 6 个空锁位,中位 0.9ms、max 4.0ms,
     收据 evidence/20260902T010857Z-01-empty-range-baseline-and-blackhole.txt;
     单遍会跳,另一遍是 1.1 / 4.6 —— 别引用具体值,量级才是结论。
     空端口瞬间被拒;Windows 上为什么耗满,
    见 tracks/opendesign-slow-lock-scan/proposal.md 的"还不知道的"。)

    ⚠️ 想把 connect 调回去,先在**那台 Windows** 上量一遍 connect_latency ——
    上面这组数来自 Linux,而那台机器的回环行为已经被证明和 Linux 不一样。
    """
    return {"connect": 1.5, "read": 1.5}


# 锁通道的线上协议。**公开常量,因为 ds_web 也要发这个帧** ——
# 两处各抄一份的代价我付过(见 ports_for 那段注释),这里只留一个真相源。
LOCK_HELLO = b"OpenDesign.ds_shell_core.lock.v1\n"
LOCK_SHOW = b"SHOW\n"
LOCK_RESTART = b"RESTART-BACKEND\n"     # 业主填完 key ⇒ 网关得重来一次才认新 env
LOCK_OK = b"OK\n"
# 🔴 应答**点名动词**:老外壳认不出 RESTART 也会回裸 OK,ds-web 就会把
#    "什么都没重启"报成 requested,界面对业主说「已自动应用新配置」——
#    正面违反「不许撒谎的重启」。带上动词,新 ds-web 碰上老外壳时才能
#    **正确降级**成"请手动重启"。(老 ds-web 碰上新外壳无碍:它比对的是前缀。)
LOCK_OK_RESTART = b"OK RESTART-BACKEND\n"


def recv_line(sock: socket.socket, deadline: float, limit: int = 4096) -> bytes:
    """读到第一个换行为止(不含换行);超时或对端关闭就返回已经读到的。

    模块级是因为 ds_web 那侧发完重启帧也要读这一行应答 —— 收发行的规矩只留一份。
    """
    buf = b""
    while b"\n" not in buf and len(buf) < limit:
        remain = deadline - time.monotonic()
        if remain <= 0:
            break
            break
        sock.settimeout(remain)
        try:
            chunk = sock.recv(limit)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0]


class InstanceLock:
    _HELLO = LOCK_HELLO
    _SHOW = LOCK_SHOW
    _RESTART = LOCK_RESTART
    _OK = LOCK_OK
    _OK_RESTART = LOCK_OK_RESTART

    port: int | None
    _sock: socket.socket | None

    def __init__(self, base_port: int, span: int = 5, on_show=None, on_restart=None):
        self.base_port = int(base_port)
        self.span = int(span)
        self.on_show = on_show
        self.on_restart = on_restart
        self.port = None
        self._sock = None
        self._thread: threading.Thread | None = None
        self._released = threading.Event()
        # 这把锁自己花了多少 —— 下一趟真机不该再靠人拿两个时间戳相减、再除以锁位数。
        # `scanned` 是**握手总次数**(两轮就是两轮之和),好让 `scan_ms / scanned`
        # 真的等于每格代价;`scan_ms` 是整个 `acquire()` 的墙钟。
        self.scan_ms: float = 0.0
        self.scanned: int = 0

    def acquire(self) -> bool:
        """True = 我是唯一实例(并已开始监听);False = 已有实例(SHOW 已送到)。"""
        t0 = time.monotonic()
        try:
            return self._acquire()
        finally:
            self.scan_ms = (time.monotonic() - t0) * 1000.0

    def _acquire(self) -> bool:
        # 第一份可能落在备用锁位上,所以先扫完整段握手,再尝试占新锁。
        hit = self._scan(self._ports())
        if hit is not None:
            self.port = hit
            return False

        for port in self._ports():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                for name, value in lock_sockopts(sys.platform):
                    opt = getattr(socket, name, None)
                    if opt is not None:
                        sock.setsockopt(socket.SOL_SOCKET, opt, value)
                sock.bind(("127.0.0.1", port))
                sock.listen(8)
            except OSError:
                sock.close()
                continue
            self._sock = sock
            self.port = port
            self._thread = threading.Thread(target=self._serve, name="ds-shell-lock", daemon=True)
            self._thread.start()

            # 🔴 并发裁决(业主快速双击两下走的就是这里)。
            # 上面那轮扫描解决不了同时启动:两份都会扫到"没人",然后一个绑 base、
            # 一个绑 base+1,**两份都以为自己是唯一的**。
            # 绑完再回头扫一次比自己**更靠前**的锁位:能应答的说明有人比我先站住了,
            # 我让位。因为"最靠前的那一格"只可能被一个人占住,所以恰好活下来一个,
            # 也不会两边互相让(让位只朝一个方向)。
            if self._someone_ahead_of(port):
                self.release()
                self.port = port
                return False
            return True

        raise PortBusy(f"单实例锁端口段 {self.base_port}..{self.base_port + self.span} 全部被占")

    def _someone_ahead_of(self, mine: int) -> bool:
        """我前面还有人吗 —— 并发启动时的**让位仲裁**。

        🔴 **它不是"快扫漏判"的兜底,别再这么用了**(2026-09-01 评审推翻的第二句话)。
        我曾在这里写"它是快扫漏判时的唯一兜底",三条评审腿里两条独立指出这是错的,
        而且拓扑摆在那儿:这一问只看 `p < mine`,所以**先起的那份落在比我更高的锁位时,
        这里一个口都不会问**。漏判最脆的那条路正好长这样 ——
        陌生程序占着 base ⇒ 第一份落到 base+1 ⇒ 陌生程序退出 ⇒
        第二份漏判、绑上 base ⇒ 走到这里前面没有锁位 ⇒ 放行 ⇒ **两份并存**。

        改成"整段都问"会引入**双向让位**:我问你、你问我,两边都让,业主双击后
        一个窗口都不开。(让位方向必须唯一,这正是"只问更靠前的"存在的理由。)

        🔴 这个数以前是"3 轮里有 1 轮",而**仓库里复现不出来** —— 2026-09-02 第二轮
        评审的两条腿各自独立指出:它是驳回这条修法的全部依据,却只活在这句注释里。
        补了探针 `tracks/opendesign-slow-lock-scan/probes/yield_race.py`,量的是一笔
        **取舍**(盲区堵不堵得住 × 同时启动活下来几份),三组实现:

            A 只问 p < mine(树上这个) 盲区**放行**   任何错开档上 0 存活都是 0
            B 绑完问整段(评审建议的)  盲区堵住      0 存活只出现在 ≲2ms 的对齐窗口内
            C 只让 base 上那份回头问   盲区堵住      同上(B/C 谁更窄写不得,见下)

        🔴 **我先前在这里写的"结构性做不到两全"是错的,是我的量具造出来的**
        (2026-09-02 第三轮:降级成瞎审的 subglm 与我自审 D2 各自独立指出
        "只量过 Barrier 对齐这一种情态")。补量错开启动后:两份的 acquire 只要错开
        **2ms 以上**,B 和 C 的 0 存活在五遍(30/40/40/20/20 轮)里**一次都没再出现**
        (五遍指"≥2ms 的档"都跑过;**2.0ms 那一格本身只在四遍里**,第一遍走的是
         0/10/50/200/500);
        1ms 那一档两组都掉到噪声底:带 1ms 档的四遍分别是
        B=1/40 C=0/40 / B=1/40 C=0/40 / B=0/20 C=1/20 / B=1/20 C=0/20
        —— 每一格不是 0 次就是 1 次,**这个样本量(20~40 轮)根本判不出
        两组有没有差别** ⇒ **不许写 B/C 谁的窗口更窄**。
        (2026-09-02 第五轮 submimo 打在这句话上:原先写的"方向不稳/翻面"
         是把噪声读成了方向 —— "量不到方向"和"方向在变"是两件事。)
        (2026-09-02 第四轮 subkimi 指出:我 09:50 在这里写下"C 已经是 0",
         70 秒后自己跑出的那份收据就把方向写反了,而它和下面那条 ⚠️
         "别引用其中任何一个比例" 在同一段注释里 —— 违反的是我六行后自己立的规矩。)
        收据:`evidence/*yield-race-stagger-sweep-30*`、`*stagger-fine-40*`(含 repeat)、
        `*acquire-duration-explains-the-window*`。
        ⇒ 真实结论是:**双向让位的危险窗口只有 1~2ms 量级,不是结构性的**。
        这个宽度**有机制解释、不是巧合**:空段上单份 acquire 实测中位 1.021ms、
        p90 1.211ms、max 2.722ms(收据 `*acquire-duration-explains-the-window*`),
        而双向让位要求两份都在对方扫描之前绑好 ⇒ 窗口量级 = 这个耗时的量级。
        ⚠️ **但这条对应只在 Linux、扫描很快时量到过**:业主那台机器上快扫会大面积超时
        (本刀量到的 9047ms → 1502ms),那里 acquire 慢得多。窗口会不会跟着变宽,
        取决于"绑完到真正发出 connect"之间有多久 —— **我没量过,这是推断不是测量**,
        已写进下一单的第 0 步。
        所以"这条修法行不通"不成立;成立的只有一句更小的话 ——
        它把一个**极窄的 0 存活窗口**换来盲区被堵住,是一笔**取舍**,不是一个错误。

        本刀仍然不改让位方向,理由只有两条(都不是"它行不通"):
          1. 那条盲区是**既有**的,不是本刀引入的回归(本刀只动扫描代价与期限);
          2. 换方向要重开判据与评审轮次,而这一刀的存在理由是"双击后别干等十几秒"。
        评估 C 是不是够、还是真要加先来后到字段,是 track
        `opendesign-lock-seniority-field` 的第一件事(那一单的题面已按这份收据改过)。

        ⚠️ **别引用其中任何一个比例**:错开启动那五遍(30/40/40/20/20 轮)在 0ms
        那一档给出过 3/20、4/20、5/20、5/20、6/30、10/30、12/40、13/40、14/40、21/40,
        方差很大 —— 跨度 3/20(0.15)到 21/40(0.525)。
        (另有一个 18/30 来自**错开启动补量之前**那一版,不在这五遍里;我 2026-09-02
         上午正是拿它写成"实测 60%、比原话严重一倍",下一遍就 30%。)
        **每一遍都成立的只有定性那几条**:A 任何档上都没出现过 0 存活;
        B/C 只在对齐窗口内出现;存活 2 份在所有组、所有档、所有遍里都是 0。
        探针还是同进程两线程 + Linux 回环,业主那台 Windows 上两个进程的对齐窗口
        宽度不一样,所以这些数更不能当成他那台机器上的概率。

        **所以现在防线在前面:快扫的 connect 期限必须罩得住实测尾巴(l2 钉着下限)**,
        让"漏判"这个前提本身够不着。`patient` 保留:它在 connect 被调短时自动重新
        生效(l5 靠注入 connect=0 钉着它),今天两个期限一样宽,它是空操作。

        代价只落在**罕见**分支上:绑到首选锁位时这里一个口都不用问(前面没有锁位),
        业主每次启动付的仍然只有一轮快扫。
        """
        # 这是**第二轮**整段扫描 —— 串行时代业主为一次启动付的是两轮超时
        # (考卷 l1 量到 15.0s,正是 5 个哑巴锁位 × 1.5s × 两轮)。
        return self._scan((p for p in self._ports() if p < mine), patient=True) is not None

    def _scan(self, ports, patient: bool = False) -> int | None:
        """并发对一段锁位握手,返回**最靠前**那个应答 OK 的锁位(没有就 None)。

        为什么必须并发:每个锁位在最坏情况下都要耗满超时,而**串行会把它们加起来**。
        业主真机上 6 个锁位一个都不肯快速失败 ⇒ 9047ms,他看到的就是"双击了没反应"。
        并发之后整段的代价 = **一个**超时,不再随锁位数量增长。

        顺序语义保持不变:`pool.map` 按入参顺序返回,所以仍然是"最靠前的那个赢" ——
        并发裁决(绑完回头看有没有人比我更靠前)靠的就是这个方向唯一。

        ⚠️ 与串行的唯一行为差异:串行遇到第一个应答就不再往下问,并发是整段都问一遍
        ⇒ 万一真有两份在跑(那本身是 bug),两份都会被叫到前台。已知且可接受:
        单实例世界里最多只有一份,而"多叫醒一个窗口"不伤数据。
        """
        ports = list(ports)
        # 🔴 **累加,不是取最大**:第二轮(`_someone_ahead_of`)扫的永远是第一轮的子集,
        #    取 max 会让这个字段恒等于 span+1、把兜底那一轮整个吞掉 —— 而 `scan_ms`
        #    是含两轮的墙钟 ⇒ 业主拿它一除,每格代价放大 1.5 倍。判据 l6 钉住
        #    "字段 == 握手函数真被调用的次数"(2026-09-01 接手复核)。
        self.scanned += len(ports)
        if not ports:
            return None
        probe = functools.partial(self._send_show, patient=patient)
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(ports), thread_name_prefix="ds-shell-lock-scan") as pool:
            answered = list(pool.map(probe, ports))
        for port, ok in zip(ports, answered):
            if ok:
                return port
        return None

    def release(self) -> None:
        """放开锁,并且**立刻**不再应答握手。

        只 close() 是不够的:服务线程这时正阻塞在旧 socket 的 accept() 里,而关掉一个
        正被 accept 阻塞的 socket 并不保证把它叫醒(Linux 实测不醒,Windows 同样不保证)。
        于是下一次握手连进来时 accept 才返回、线程照样回了个 OK ⇒ **锁已经放开了,
        新实例却被告知"已有一份在跑"**,业主看到的是双击图标没反应。

        叫醒的办法:先 shutdown() 断开监听,再自连一次把可能仍阻塞的 accept 顶出来。
        """
        self._released.set()
        sock = self._sock
        port = self.port
        self._sock = None
        self.port = None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass          # 监听 socket 上 shutdown 在有的平台直接报错,不影响下一步
        if port:
            try:          # 自连一次:把仍卡在 accept 里的线程顶出来(它一醒就看见 _released)
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    pass
            except OSError:
                pass
        try:
            sock.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _ports(self):
        return range(self.base_port, self.base_port + self.span + 1)

    def _send_show(self, port: int, patient: bool = False) -> bool:
        """连上去握一次手。对上了 = 那边是另一份 OpenDesign(SHOW 已送到)。

        收发都**循环读到整行**:TCP 没有消息边界,一次 recv 恰好等于整帧只是回环上的
        运气;分片就把真实例认成陌生人 ⇒ 开出第二份。
        """
        t = lock_timeouts()
        # patient=True:连接也用回话那个宽期限。只有 `_someone_ahead_of` 走这条 ——
        # 那一刻我们已经知道"锁位被占而快扫没问出来",短期限不该再被信任。
        connect_deadline = t["read"] if patient else t["connect"]
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=connect_deadline) as s:
                s.settimeout(t["read"])
                s.sendall(self._HELLO + self._SHOW)
                return self._recv_line(
                    s, deadline=time.monotonic() + t["read"]) == self._OK.strip()
        except OSError:
            return False

    _recv_line = staticmethod(recv_line)

    def _serve(self) -> None:
        # 捞一份本地引用:release() 会把 self._sock 置 None,再用 self._sock 就是 AttributeError。
        sock = self._sock
        if sock is None:
            return
        while not self._released.is_set():
            try:
                conn, _ = sock.accept()
            except OSError:
                break
            # 醒来之后**再问一次**:release() 的自连就是来顶醒我的,
            # 而这一刻锁已经放开了 —— 这时候还回 OK,就等于替一把不存在的锁挡人。
            if self._released.is_set():
                conn.close()
                break
            # 每条连接单独一个线程处理。**不许在主循环里同步处理**:
            # 端口扫描器(或任何连上就不说话的东西)会把这个循环堵住,而这段时间里
            # 第二个实例握手会超时、把真实例当成陌生人 ⇒ 开出第二份 OpenDesign。
            threading.Thread(target=self._handle, args=(conn,),
                             name="ds-shell-lock-conn", daemon=True).start()

    @classmethod
    def _recv_frame(cls, sock: socket.socket, deadline: float,
                    settle: float = 0.35, limit: int = 4096) -> tuple[bytes, bytes]:
        """读一整帧:第一行 HELLO,第二行动词(**可能没有**)。

        🔴 为什么不能连着调两次 `_recv_line`:那个函数每次都从 socket 重新读,
        **把同一个包里多出来的部分丢掉**。而 HELLO 和动词几乎总在同一个包里到达
        ⇒ 分两次读会把动词连缓冲一起扔了,然后干等第二行到超时。

        只发了 HELLO 的老实例(以及升级瞬间还在跑的那份)必须照常工作:
        第一行到手后只再宽限 `settle`,拿不到动词就按"没有动词"处理。
        """
        buf = b""
        grace: float | None = None
        while len(buf) < limit and buf.count(b"\n") < 2:
            now = time.monotonic()
            if buf.count(b"\n") >= 1 and grace is None:
                grace = now + settle
            remain = (min(deadline, grace) if grace is not None else deadline) - now
            if remain <= 0:
                break
            sock.settimeout(remain)
            try:
                chunk = sock.recv(limit)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
        parts = buf.split(b"\n")
        return parts[0], (parts[1] if len(parts) > 1 else b"")

    def _handle(self, conn: socket.socket) -> None:
        verb = b""
        with conn:
            try:
                head, verb = self._recv_frame(conn, deadline=time.monotonic() + 2.0)
                if not head.startswith(self._HELLO.strip()):
                    return
                if self._released.is_set():
                    return
                # 先认动词再决定回什么 —— 回裸 OK 就等于说"我收到了"而不说"我认了什么"
                is_restart = verb.strip() == self._RESTART.strip()
                conn.sendall(self._OK_RESTART if is_restart else self._OK)
            except OSError:
                return
        # 动词分派。**认不出的一律退回 SHOW**:重启会掐断他正在进行的对话,
        # 而把窗口叫到前台最多是打扰一下 ⇒ 拿不准时选那个不伤人的。
        cb = self.on_restart if is_restart else self.on_show
        if cb is not None:
            cb()


@dataclass
class Service:
    name: str
    argv: list[str]
    env: dict
    ready_port: int
    log_path: Path
    ready_timeout: float = 60.0
    # 可选的身份探针:收到 ready_port 后再问一句"听这个端口的真是你吗"。
    # "端口有人听"只说明有人听 —— 陌生进程抢在中间那一瞬占了端口,一样是绿的。
    # ds-web 用 /api/health 自报版本;不给探针就退化成只看端口。
    ready_probe: Any = None


@dataclass
class _Managed:
    service: Service
    proc: subprocess.Popen
    log_file: Any
    job_handle: Any = None
    pgid: int | None = None      # POSIX:开跑时记下进程组,别等父进程死了才去问


class Supervisor:
    def __init__(self):
        self._children: list[_Managed] = []
        self._shutdown_lock = threading.Lock()
    ready_port: int
    log_path: Path
    ready_timeout: float = 60.0
    # 可选的身份探针:收到 ready_port 后再问一句"听这个端口的真是你吗"。
    # "端口有人听"只说明有人听 —— 陌生进程抢在中间那一瞬占了端口,一样是绿的。
    # ds-web 用 /api/health 自报版本;不给探针就退化成只看端口。
    ready_probe: Any = None


@dataclass
class _Managed:
    service: Service
    proc: subprocess.Popen
    log_file: Any
    job_handle: Any = None
    pgid: int | None = None      # POSIX:开跑时记下进程组,别等父进程死了才去问


class Supervisor:
    def __init__(self):
        self._children: list[_Managed] = []
        self._shutdown_lock = threading.Lock()

    def start(self, services: list[Service]) -> None:
        ports = [int(s.ready_port) for s in services]
        if len(set(ports)) != len(ports):
            raise StartupFailed(f"服务端口重复: {ports}")
        for svc in services:
            if not port_free(int(svc.ready_port)):
                raise StartupFailed(f"{svc.name} 的端口 {svc.ready_port} 已被占用")

        try:
            for svc in services:
                child = self._spawn(svc)
                self._children.append(child)
                self._wait_ready(child)
            # 全部就绪之后再点一次名:等后面那条腿的这段时间里,前面的可能已经崩了。
            # 少了这一下,业主看到的是"窗口正常打开、聊天永远连不上、而且没有任何报错"。
            dead = self.poll_dead()
            if dead:
                raise StartupFailed(self._failure_message(
                    self._by_name(dead[0]).service, "起来之后又退出了",
                    self._by_name(dead[0]).proc.poll()))
        except BaseException:
            # 不只接 StartupFailed:建日志目录失败之类会抛 OSError,
            # 接不住就把已经起好的腿丢在那儿变成孤儿(业主下次打开撞端口,还查不出是谁)。
            self.shutdown()
            raise

    def restart(self, services: list[Service]) -> None:
        """把点名的几条腿换成新的(通常只是换了 env),**其余腿一动不动**。

        业主填完 key 之后要走的就是这条路:网关只在启动时读一次环境变量,
        不换一个新进程就永远认不到新 key。而 ds-web **不能**跟着换 ——
        他正看着的那个页面就是 ds-web 发的。

        与 `start()` 的差别是故意的,别照抄那边:start 半路失败会把已起的全停掉
        (半拉子启动没有意义);这里失败**不许连坐** —— 界面没有理由陪葬,
        而且他得看得见"重启失败"这句话。
        
        🔴 **不持 `_shutdown_lock` 是有意的取舍**(08-17 四审两腿都提):
        托盘"退出"和这里交错时,新起的网关可能落在 `shutdown()` 的名册快照之后
        ⇒ 理论上留一个孤儿。没加锁是因为 `shutdown()` 持的是同一把,重启途中
        点退出会让业主干等到 300s 超时 —— 这个仓库有过"重入即永久挂死"的先例。
        Windows 上外壳退出时 Job 的 KILL_ON_JOB_CLOSE 会兜底,窗口只有毫秒宽。
        **下一个想加锁的人:先把 shutdown 那侧的等待改成可中断的,再动这里。**
        """
        names = {s.name for s in services}
        old = [c for c in self._children if c.service.name in names]
        # 🔴 **先除名,再动手**(判据 c19)。反过来写会留下一个窗口:旧腿已经被杀、
        # 却还挂在名册上 —— 看门狗每 3 秒问一次 `poll_dead()`,问在这个窗口里就会
        # 弹「网关意外退出了,请退出后重新打开」,而那一刻其实是**正常重启**,
        # 而且那句指令(退出后重开)恰好会打断正在进行的重启。
        self._children = [c for c in self._children if c not in old]
        for child in old:
            self._terminate_tree(child)
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if all(c.proc.poll() is not None for c in old):
                break
            time.sleep(0.05)
        # 🔴 收尸要走**和 shutdown 同一套**(判据 c18)。少了这一步,Windows 上
        # `_terminate_tree` 只 terminate 了 nanobot 本尊,它带的 3 个 MCP 工具服务
        # 留在 Job 里没人收 —— 关 Job(KILL_ON_JOB_CLOSE)才是那边收整棵树的机制。
        # Linux 看不出来:那边 `_terminate_tree` 打的是整个进程组,孙子跟着一起走。
        # 业主每按一次"保存 key",机器上就多 3 个孤儿。
        for child in old:
            self._kill_tree(child)
            self._close_job(child)
            try:
                child.log_file.close()
            except Exception:
                pass

        for svc in services:
            # 端口得**真的还回来**再起新的。少这一步,新进程 bind 失败,
            # 而业主看到的症状是"点了保存,什么也没发生"。
            port_deadline = time.monotonic() + 5.0
            while not port_free(int(svc.ready_port)):
                if time.monotonic() > port_deadline:
                    raise StartupFailed(
                        f"{svc.name} 的端口 {svc.ready_port} 一直没释放,没能重启")
                time.sleep(0.05)
            child = self._spawn(svc)
            self._children.append(child)
            try:
                self._wait_ready(child)
            except BaseException:
                # 只收自己这一条,别动别人(上面那段 docstring 的"不连坐"就在这儿落地)。
                # 🔴 08-17(四审 subkimi F-2,判据 c22):收尸要走**和上面收旧腿
                # 完全同一套**。这里原来只有 `_terminate_tree` —— Windows 上那等于
                # 只杀了 nanobot 本尊,它带的 3 个 MCP 留在 Job 里没人收
                # (KILL_ON_JOB_CLOSE 不触发),外壳里每失败一次还漏一个日志句柄。
                # 同一个函数里两条路不一致,c18 只钉住了旧腿那一半。
                self._kill_tree(child)
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
                self._children = [c for c in self._children if c is not child]
                raise

    def shutdown(self) -> None:
        with self._shutdown_lock:
            children = list(self._children)
            if not children:
                return

            for child in children:
                self._terminate_tree(child)

            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                if all(child.proc.poll() is not None for child in children):
                    break
                time.sleep(0.05)

            for child in children:
                # posix 上即使父进程已经死了也要再 KILL 一遍进程组:
                # 活着的可能只剩孙进程,而 poll() 问的只是父进程。
                if child.proc.poll() is None or child.pgid or child.job_handle:
                    self._kill_tree(child)

            final_deadline = time.monotonic() + 4.0
            for child in children:
                remaining = max(0.0, final_deadline - time.monotonic())
                try:
                    child.proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    pass

            # 直接子进程死了 ≠ 收干净了:孙进程(nanobot 的 3 个 MCP)还要一会儿才落地,
            # 而它们手里攥着端口。这里等**整个进程组**真的空掉再返回 ——
            # 否则业主点完"退出"马上再双击,新的一份会撞在还没放开的端口上。
            group_deadline = time.monotonic() + 3.0
            while time.monotonic() < group_deadline:
                if all(self._group_gone(c) for c in children):
                    break
                time.sleep(0.05)

            for child in children:
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
            self._children.clear()

    def take_dead(self) -> list[tuple[str, str]]:
        """死掉的腿:**名字和死因一次拿全**(判据 c21)。

        看门狗以前分两眼看 —— 先 `poll_dead()` 问"谁死了",再 `dead_reports()`
        问"为什么"。两眼之间名册会变(业主恰好在这一刻存了 key、触发重启),
        于是第一眼有名字、第二眼没了原因 ⇒ 弹窗照弹「网关意外退出了」,
        日志里一个原因都没有 —— **c20 刚消灭掉的那种没线索的弹窗,换个入口又长回来。**
        (08-17 四审 subdeepseek F5。)

        修法不是加锁:`shutdown()` 持的是 `_shutdown_lock`,重启途中再互等
        风险更大。一次遍历、一份快照就够 —— 名册的**那一瞬**是自洽的。
        `list(...)` 是同一件事的另一半:遍历途中被 restart 改名册不许抛。
        """
        out = []
        for child in list(self._children):
            code = child.proc.poll()
            if code is None:
                continue
            out.append((child.service.name,
                        self._failure_message(child.service, "", code, what="意外退出了")))
        return out

    def poll_dead(self) -> list[str]:
        return [name for name, _ in self.take_dead()]

    def dead_reports(self) -> list[str]:
        """死掉的腿**为什么**死 —— 每条一段人话:退出码 + 那条腿日志的尾巴。

        🔴 2026-08-16 业主真机欠的就是这个。当时外壳只说了一句
        「网关 意外退出了。请退出后重新打开」,而网关自己的日志最后一句是
        `Agent loop started`,之后什么都没有。两份日志摆在面前,我也答不了
        「它是被杀的还是自己崩的」—— 因为**退出码从来没被打印过**。
        退出码分得清这两件事(被杀 vs 自己退),日志尾巴给的是崩在哪。

        看门狗现在走 `take_dead()`(名字和原因同一眼);这个留给只要原因的调用方。
        """
        out = []
        for _, said in self.take_dead():
            out.append(said)
        return out

    @staticmethod
    def _group_gone(child: _Managed) -> bool:
        """这条腿的进程组是不是真的空了(信号 0 = 只探不杀)。

        Windows 没有便宜的等价问法(Job 关掉就算数),那边只看直接子进程。
        """
        if os.name != "posix" or not child.pgid:
            return child.proc.poll() is not None
        try:
            os.killpg(child.pgid, 0)
            return False
        except OSError:
            return True

    def _by_name(self, name: str) -> _Managed:
        return next(c for c in self._children if c.service.name == name)

    def _spawn(self, svc: Service) -> _Managed:
        log_path = Path(svc.log_path)
        try:
            # 开日志也会失败(路径被占、没权限)。包成 StartupFailed,
            # 免得调用方只接 StartupFailed 时漏掉这条路,把兄弟腿丢成孤儿。
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("ab")
        except OSError as exc:
            raise StartupFailed(f"{svc.name} 起不来:日志写不了({log_path}):{exc}") from exc
        kwargs: dict[str, Any] = {
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "env": {str(k): str(v) for k, v in svc.env.items()},
        }
        kwargs.update(spawn_kwargs())
        try:
            proc = subprocess.Popen([str(x) for x in svc.argv], **kwargs)
        except Exception as exc:
            try:
                log_file.close()
            except Exception:
                pass
            raise StartupFailed(f"{svc.name} 启动失败: {exc}") from exc
        child = _Managed(service=svc, proc=proc, log_file=log_file)
        if os.name == "posix":
            # 开跑时就把进程组记下来。等到收摊时才去问就晚了:
            # 组长(nanobot 父进程)可能已经死了,而它的 3 个 MCP 孙进程还活着 ——
            # 那时候 os.getpgid(pid) 已经问不到,进程组就永远没人收。
            try:
                child.pgid = os.getpgid(proc.pid)
            except OSError:
                child.pgid = proc.pid
        elif os.name == "nt":
            child.job_handle = self._assign_windows_job(proc)
        return child

    def _wait_ready(self, child: _Managed) -> None:
        svc = child.service
        deadline = time.monotonic() + float(svc.ready_timeout)
        while True:
            # 盯的是**所有**已起的腿,不只当前这条:前面那条先就绪、随后崩掉的话,
            # 只盯当前这条会让 start() 一路绿到底(攻题二轮 HIGH#3)。
            for other in self._children:
                code = other.proc.poll()
                if code is not None:
                    raise StartupFailed(self._failure_message(
                        other.service, f"退出码 {code}", code))
            if port_listening(int(svc.ready_port)) and self._probe_ok(svc):
                return
            now = time.monotonic()
            if now >= deadline:
                raise StartupFailed(self._failure_message(svc, "启动超时", None))
            time.sleep(min(0.1, max(0.0, deadline - now)))

    @staticmethod
    def _probe_ok(svc: Service) -> bool:
        if svc.ready_probe is None:
            return True
        try:
            return bool(svc.ready_probe(int(svc.ready_port)))
        except Exception:
            return False      # 探针自己炸了 = 还没就绪,不是就绪

    def _failure_message(self, svc: Service, reason: str, code: int | None,
                         what: str = "启动失败") -> str:
        tail = self._log_tail(Path(svc.log_path))
        parts = [f"{svc.name} {what}: {reason}" if reason else f"{svc.name} {what}"]
        if code is not None:
            parts.append(f"退出码: {code}")
        parts.append(f"日志尾巴:\n{tail}")
        return "\n".join(parts)

    def _log_tail(self, path: Path, limit: int = 4000) -> str:
        try:
            with path.open("rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - limit))
                data = f.read()
            text = data.decode("utf-8", errors="replace").strip()
            return text or "(日志为空)"
        except OSError:
            return "(读不到日志)"

    # 🔴 下面两个**不许**因为 "poll() 非 None 就直接 return"。
    # 父进程先死、孙进程还活着,是 nanobot 最真实的一种残局(它自己拉起 3 个 MCP):
    # 那时候整个进程组还在,而"父进程已经死了"恰恰让收割整段被跳过 ⇒
    # 业主机器上留下几个占着端口的孤儿,看不出是谁,下次打开就撞端口。
    def _terminate_tree(self, child: _Managed) -> None:
        if os.name == "posix":
            if child.pgid:
                try:
                    os.killpg(child.pgid, signal.SIGTERM)
                except OSError:
                    pass          # 组已经空了:正常
            return
        if child.proc.poll() is None:
            try:
                child.proc.terminate()
            except Exception:
                pass

    def _kill_tree(self, child: _Managed) -> None:
        if os.name == "posix":
            if child.pgid:
                try:
                    os.killpg(child.pgid, signal.SIGKILL)
                except OSError:
                    pass
            return
        # Windows:关掉 Job 就等于收掉整棵树(KILL_ON_JOB_CLOSE)——
        # 父进程已经死了也照关,道理同上(孙进程还在这个 Job 里)。
        if child.job_handle:
            self._close_job(child)
            return
        if child.proc.poll() is not None:
            return
        try:
            # 没挂上 Job 时的退路:taskkill /T 连子孙一起杀。
            # 它也是控制台程序 ⇒ 平台参数走同一个来源,否则每收一次尸闪一个黑窗口。
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(child.proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                **spawn_kwargs("nt"),
            )
            return
        except Exception:
            pass
        try:
            child.proc.kill()
        except Exception:
            pass

    def _assign_windows_job(self, proc: subprocess.Popen):
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # ⚠️ 必须显式声明 HANDLE 的类型。ctypes 默认把返回值当 c_int(32 位),

def startup_plan(has_key: bool) -> dict:
    """起哪几条腿。

    🔴 规划双出 B 卷抓到的:上一版是"缺 key 就整个 `die()`",而那发生在**开窗口之前**
    ⇒ 业主永远看不到填 key 的引导页,只看到一个弹窗然后程序没了。
    正确形状:**界面(ds-web)无条件起**,网关**有 key 才起** ——
    网关缺 `${VAR}` 会自己拒绝启动,让它带着缺失去起本来就只会换来一句英文。
    """
    if has_key:
        return {"start": ["ds-web", "网关"], "wait": []}
    return {"start": ["ds-web"], "wait": ["网关"]}


def data_root_for(user_home: str) -> str:
    """装出来那一份的数据根:`<应用状态根>\\Data`(user_home 是它下面的 UserData)。

    **单一来源** —— child_env 与外壳自己都从这里取。分成两处算的代价我付过:
    外壳只给子进程设了 env、自己没设,于是它那次迁移空转了(判据 d3)。
    """
    return os.path.join(os.path.dirname(os.path.realpath(user_home)), "Data")


def prepare_data_root(user_home: str, ds_root: str) -> dict:
    """起任何服务之前:把数据根**给本进程也设上**,然后把遗留数据搬过去。

    为什么在 core 里而不在 ds_shell.py:那一层在 Linux 上一条判据都跑不了
    (pywebview/pystray/WebView2 全是 Windows 独有),而这段逻辑是可判定的。
    """
    os.environ[ds_common.DATA_ROOT_ENV] = data_root_for(user_home)
    return ds_common.migrate_legacy_data(ds_root)


def child_env(
    base_env: dict,
    *,
    ds_root: str,
    user_home: str,
    dsweb_port: int,
    ws_port: int,
    key: str | None = None,
    key_var: str | None = None,
    lock_port: int | None = None,
) -> dict:
    env: dict[str, str] = {}
    for k, v in base_env.items():
        name = str(k)
        upper = name.upper()
        if upper in {"PYTHONPATH", "PYTHONHOME"} or upper.startswith("DS_"):
            continue
        env[name] = str(v)

    env.update(
        {
            "DS_ROOT": str(ds_root),
            "DS_DATA_ROOT": data_root_for(str(user_home)),
            "DS_WEB_PORT": str(dsweb_port),
            "DS_NANOBOT_PORT": str(ws_port),
            "HOME": str(user_home),
            "USERPROFILE": str(user_home),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if lock_port:
        # ds-web 拿它去请外壳重启网关(业主填完 key 那一下)。没有锁就**什么都不留** ——
        # 留个假号的话 ds-web 会拿它去连别人。
        env["DS_SHELL_LOCK_PORT"] = str(lock_port)
    if key:
        # 变量名从配置的 apiKey 引用里读(ds_credential.env_var_name),**不许写死**:
        # Linux 那份引用的就是 ${MIMO_TP_KEY}。忘了传就抛 —— 悄悄退回一个默认名的话,
        # 症状是"填了 key 还是不能聊天",最难往这儿查。
        if not key_var:
            raise ValueError("有 key 却没说该设哪个环境变量(从配置的 apiKey 引用里读)")
        env[str(key_var)] = str(key)
    return env


def service_envs(
    base_env: dict,
    *,
    ds_root: str,
    user_home: str,
    dsweb_port: int,
    ws_port: int,
    key: str | None = None,
    key_var: str | None = None,
    lock_port: int | None = None,
) -> dict[str, dict]:
    """两条腿各自的环境:**key 只进网关,不进 ds-web。**

    🔴 为什么必须分开(2026-08-16 四审 BLOCK,两条评审腿各自独立命中):
    ds-web **不消费**这把 key —— 只有网关按配置里的 `${VAR}` 解析它。可上一版把
    同一份 env 给了两条腿,于是 ds-web 自己的 `os.environ` 里也有了它,而
    `ds_credential.status()` 分不出**外壳自注入**和**业主真设过**,判成
    `source="env" / writable=False` ⇒ 装好的应用第一次重启后,设置里那张改 key 的
    卡片**永久只读**,还让业主去清一个他从没设过的变量。
    「改 key / 换厂商」是 in-scope 功能,那条路在主形状上直接死了。

    拿掉之后,H1 的只读态回到它该有的语义:**只有业主自己真设过的环境变量**才让
    那一格变灰。(在装好的形状里那几乎不会发生 —— `child_env` 剥掉继承的 `DS_*`
    —— 但在 git-pull 那两台、以及业主手工设过变量的机器上仍然成立。)
    """
    common = dict(ds_root=ds_root, user_home=user_home, dsweb_port=dsweb_port,
                  ws_port=ws_port, lock_port=lock_port)
    return {
        "网关": child_env(base_env, key=key, key_var=key_var, **common),
        "ds-web": child_env(base_env, key=None, key_var=None, **common),
    }


class ShellState:
    visible: bool
    exiting: bool

    def __init__(self, ui, on_stop):
        self.ui = ui
        self.on_stop = on_stop
        self.visible = True
        self.exiting = False
        # 事件从三个方向来:锁的监听线程(第二次双击)、托盘线程、UI 线程。
        # 没有这把锁,"检查 exiting 再置位"是两步 —— 两个线程能一起穿过去,
        # 后台被收两遍、窗口被销毁两遍。锁只护**状态判定**,不护 UI 调用本身。
        self._lock = threading.RLock()

    def on_close_requested(self) -> bool:
        with self._lock:
            if self.exiting:
                return True
            self.visible = False
        self.ui.hide_window()
        return False

    def on_show(self) -> None:
        with self._lock:
            if self.exiting:
                return
            self.visible = True
        self.ui.show_window()

    def on_quit(self) -> None:
        with self._lock:
            if self.exiting:
                return
            self.exiting = True
            self.visible = False
        self.on_stop()
        self.ui.destroy()

 succeeded in 0ms:
#!/usr/bin/env python3
"""OpenDesign 桌面外壳 —— Windows 胶水层(S1b)。

双击 OpenDesign.exe 走到的就是这里。它负责的事:
  拿单实例锁 → 挑端口 → 改写配置 → 拉起网关和 ds-web → 开一个桌面窗口装 ds-web
  → 关窗口收进托盘 → 托盘"退出"才真的收摊。

**这一层没有任何自动考卷验得了**(pywebview / pystray / WebView2 / .NET 全是 Windows 独有,
而且要有桌面会话)。所以它的所有**可判定逻辑**都被推到了 `ds_shell_core.py` 里,
那一层有 `tests/test_ds_shell_core.py` 逐条锁着。留在这个文件里的只剩"接线"。

接线接错了照样是坏的,所以这个文件的规矩是:
  ① 每一步失败都要变成**业主看得懂的一句话**,而且是**弹窗**——
     业主是双击图标进来的,没有终端可看,往 stderr 打等于没打。
  ② 弹窗用 ctypes 直接叫 MessageBoxW,**不依赖 pywebview/.NET**:
     偏偏最需要报错的时候(WebView2 缺失、.NET 挂不上)那些东西正好是坏的。
  ③ 每一处"我在 Linux 上验不了"的假设,都在注释里点名,并进 Windows 真机考卷。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ds_common  # noqa: E402
import ds_credential  # noqa: E402  变量名从配置的 apiKey 引用里读,不许写死
import ds_diag  # noqa: E402  启动可观测性:run_id / 分阶段耗时 / 诊断包
import ds_shell_core as core  # noqa: E402

APP = "OpenDesign"
# 外壳打开页面时在地址里报的身份。前端靠它决定要不要画那条窗口栏
# (无边框之后三个按钮 + 拖动带 + 八个把手全是我们自己画的)。
# **唯一来源是 web/src/shellWindow.ts 的同名常量**,两边一字不差
# (tests/test_shell_window_contract.py x10 对表)。
# 为什么不用"pywebview 有没有把 api 注进页面"来判:它在 on_navigation_completed
# 之后才注入(页面脚本早跑完了)⇒ 前端首帧问它永远答 false,窗口栏整块不画。
# 0.89/0.90 两版就是这么发出去的(业主:「拖不动 / 右上角还是没有」)。
SHELL_MARK = "shell=1"


def window_url(port: int) -> str:
    """外壳打开的那个地址。**唯一来源** —— 开窗口和写日志都叫它。

    分开写两遍的代价已经付过一次:日志里印的地址少了标记,而那份
    `外壳.log` 正是业主报"没按钮"时我唯一的现场。
    (判据 x10 直接调它,不是去源码里 grep 字面量。)
    """
    return f"http://127.0.0.1:{port}/?{SHELL_MARK}"


# 锁位挑在一段不常用的高位端口上。它只是锁 + 唤醒通道,不承载数据。
LOCK_PORT = 18788
# 首选端口沿用现有部署(docs/install-windows.md / start.ps1),被占了会自动往后挪。
PREFERRED = {"gateway": 18790, "ws": 8765, "web": 8766}


# ---------------------------------------------------------------- 报错与日志
def _app_dir() -> Path:
    """这个软件在业主机器上自己的目录。日志和实验开关都住这儿。"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP


def _log_path() -> Path:
    d = _app_dir() / "Logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "外壳.log"


# ── 窗口动画开关(0.96.0 起**默认开**)──────────────────────────────
# 0.94/0.95 这里默认是**关**的,业主一句话点破了那个决定的自相矛盾:
#   「你为什么不直接给我做好动画的,要默认关闭动画」
# —— 我给 0.95 装了"不对就自动退回去"的保险,却又不敢依赖它。
#   要么保险可信、就该默认开;要么不可信、就不该把它当卖点。
#   我选了对自己最安全、对业主最麻烦的那一半:风险我躲了,力气他出。
#
# 而且 0.95 之后**「打开就白」在结构上已经没了**:开窗口时一个边框动作都不做,
# 方案 B 要等业主点缩小才装 ⇒ 就算真把画面搞坏,**重开软件就是好的**,
# 不像 0.93 那样一起来就是砖。既然最坏情况已经从"砖"降到"重开一下",
# 就没有理由再让业主自己去建文件。
DISABLE_FLAG = "关掉窗口动画.on"


def frame_animation_on() -> bool:
    """要不要接系统窗口框架(缩小/放大的动画靠它)。**默认开。**

    不想要就在 `%LOCALAPPDATA%\\OpenDesign\\` 里新建一个空文件,
    名字叫 `关掉窗口动画.on`,重开软件即可。删掉它就回到默认。

    🔴 **读不到环境时倒向"关"**(判据 f4 守着 except 必须 `return False`)。
    方向仍然是有讲究的,只是理由换了:这个逃生门是给"已经发现它坏了"的人用的。
    读不出文件系统时,把"可能已经关过"当成"关过"——
    让一个本来没事的人少一段动画(小),好过让一个已经被坑过的人再被坑一次(大)。
    """
    try:
        return not (_app_dir() / DISABLE_FLAG).is_file()
    except Exception:
        return False


def log(msg: str) -> None:
    """带时间戳写一行。

    🔴 时间戳是 08-14 那次真机红补上的:那份日志没有时间,于是「一起来就崩」和
    「等满 300s 超时」在事后长得一模一样,只能回头问业主等了多久。
    证据要自带能对账的东西 —— 一个 strftime 换的是一趟真机。

    🔴 2026-08-30(判据 s1):**补上日期** —— 上面那笔账只还了一半。
    业主 08-25 晚白屏、08-30 才回话,中间那几行属于哪一天,只有时分秒的日志答不了。
    续行缩进由 stamp 长度算出来,不写死数字(写死的那种迟早和格式对不上)。
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    pad = " " * (len(stamp) + 1)
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            for i, line in enumerate(msg.rstrip().splitlines() or [""]):
                # 多行文案(弹窗那种)只给第一行盖戳,其余缩进对齐 —— 免得每行都盖,
                # 反而看不出哪里是一条记录的开头。
                f.write(f"{stamp} {line}\n" if i == 0 else f"{pad}{line}\n")
    except OSError:
        pass


def web_ready_probe(port: int) -> bool:
    """工作台"就绪"的真正含义:`/api/health` 应答得了。

    🔴 **fail-closed**:任何异常都当成"还没就绪"。反过来写(拿不到就当好了)
    正是这个项目栽过的 fail-open 形状 —— 那样探针活着也等于没有。

    🔴 **绝不能走系统代理**(判据 s13;2026-08-30 四审孤腿 BLOCK 抓到、我实测坐实)。
    `urllib.request.urlopen` 对 127.0.0.1 **不绕过**代理:`proxy_bypass('127.0.0.1')`
    就是 False,而 Windows 上 `ProxyOverride` 里的 `<local>` 只匹配无点主机名。
    于是凡是配了系统代理的机器(公司代理、**以及 Clash 那类会设系统代理的 VPN 客户端**)
    上,这个探针对**健康**的工作台一律返回 False ⇒ `_wait_ready` 死等到 60s 超时
    ⇒ `StartupFailed` ⇒ **软件根本打不开**。
    观测层绝不能成为新的故障源 —— 这条红线是本单自己写的,第一版亲手违反了它。
    ⇒ 显式装一个空 `ProxyHandler`,任何环境里都直连。
    """
    import urllib.request
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


# 这一次启动的证据链。**在模块导入时就建**,不是在 main() 里 —— 那样 t0 才贴着
# 进程真正的起点(import 本身也可能慢,那段时间也该被量到)。
# 白屏和"打开好慢"都靠它留下的东西查(track opendesign-startup-observability)。
DIAG = ds_diag.StartupLog(emit=log)


def alert(msg: str, title: str = APP) -> None:
    """弹一个系统对话框。业主没有终端,这是唯一能被看见的出口。"""
    log(f"[提示] {msg}")
    try:
        ctypes.windll.user32.MessageBoxW(None, msg, title, 0x10)  # MB_ICONERROR
    except Exception:
        print(msg, file=sys.stderr)


def die(msg: str) -> None:
    alert(msg)
    sys.exit(1)


# ---------------------------------------------------------------- 路径
def install_root() -> Path:
    """包根:里面有 python\\ 和 ds\\。本文件在 <root>\\ds\\bin\\ 下。"""
    return HERE.parent.parent


def user_home() -> Path:
    """业主数据目录 —— **安装目录之外**(design:卸载/回滚不许碰数据)。

    这里同时是子进程眼里的 HOME/USERPROFILE,所以 nanobot 读的是
    <user_home>\\.nanobot\\config.json,而不是业主机器上原来那份。
    """
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "UserData"
    d.mkdir(parents=True, exist_ok=True)
    return d


def python_exe() -> Path:
    return install_root() / "python" / "python.exe"


def key_file(home: Path) -> Path:
    """机主自备的 LLM key 放在哪儿(deploy-security D1:部署者不发 key)。

    路径与现有部署一致(ds-nanobot.ps1:20),只是 USERPROFILE 换成了应用自己的数据目录。
    **报错文案要把这个路径原样念给业主听**,所以它得是个能被引用的单一来源。
    """
    return home / ".openDesign" / "key.txt"


def read_key(home: Path) -> str | None:
    try:
        return key_file(home).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


# ---------------------------------------------------------------- 托盘图标
def tray_image():
    """托盘图标。装机时安装器会放一份 图标.png 进来;没有就画一个,不为图标崩掉。"""
    from PIL import Image, ImageDraw

    # 安装器铺的是 ds\assets\图标.png(仓库里的 assets/图标.png,由 installer/make-icon.py
    # 与程序图标 opendesign.ico **同一份形状**生成)。路径挑在 assets\ 下是因为包里的 ds\
    # 是仓库根的镜像 —— 组包时那道"ds/ 里每个文件都必须是仓库里的"闸按这个对应关系查。
    png = install_root() / "ds" / "assets" / "图标.png"
    if png.exists():
        try:
            return Image.open(png)
        except Exception:
            pass
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(38, 70, 83, 255))
    d.rounded_rectangle((18, 18, 46, 46), radius=6, fill=(233, 196, 106, 255))
    return img


# ---------------------------------------------------------------- 主流程
def start_backend(home: Path, lock_port: int | None = None):
    """挑端口 → 改配置 → 按计划拉起后台。返回 (supervisor, web_port, restart_gateway)。

    **缺 key 不再是死路**(track opendesign-key-onboarding):界面无条件起,
    网关等着 —— 业主要在界面里填 key,而那个界面正是 ds-web 发的。
    填完之后 ds-web 通过锁通道回来叫 `restart_gateway`。
    这一层只剩接线,"起哪几条"由 core.startup_plan 判(判据 d1/d2 咬着)。
    """
    cfg = home / ".nanobot" / "config.json"
    if not cfg.exists():
        die(f"还没装好:找不到配置文件\n{cfg}\n\n请重新运行安装程序。")

    try:
        gw, ws, web = core.pick_ports(
            [PREFERRED["gateway"], PREFERRED["ws"], PREFERRED["web"]], span=20)
    except core.PortBusy as e:
        die(f"找不到可用的端口:{e}\n\n多半是有别的程序占着这几段端口,重启电脑再试一次。")

    try:
        core.patch_config(cfg, gateway_port=gw, ws_port=ws, python_exe=str(python_exe()),
                          data_root=core.data_root_for(str(home)))
    except core.ConfigUnusable as e:
        die(f"配置没法用:{e}\n\n请重新运行安装程序。")
    except OSError as e:
        die(f"写配置失败:{e}")

    def build_env():
        """每次都**现读** key 和配置:重启网关那一下走的就是这里,
        读到的必须是业主刚填进去的那份,不是启动时缓存的。"""
        key = read_key(home)
        key_var = None
        if key:
            try:
                with cfg.open("r", encoding="utf-8") as f:
                    key_var = ds_credential.env_var_name(json.load(f))
            except (OSError, ValueError, ds_credential.CredentialError) as e:
                die(f"配置里没写清楚 key 该放进哪个变量({e})。\n\n请重新运行安装程序。")
        # 🔴 **key 只进网关那条腿**(core.service_envs)。上一版把同一份 env 给了
        #    两条腿,ds-web 也拿到 key ⇒ status() 把外壳自注入误判成"外部遮蔽" ⇒
        #    装好的应用重启后,设置里改 key 的卡片永久只读,还让业主去清一个他
        #    从没设过的变量。(2026-08-16 四审 BLOCK,判据 J 组钉住。)
        return key, core.service_envs(
            dict(os.environ), ds_root=str(install_root() / "ds"), user_home=str(home),
            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)

    key, envs = build_env()

    # 🔴 08-14 业主真机红出来的那一条,别再写回去:
    # 上一版这里只 log 一句「没找到 key.txt,聊天会连不上大模型」就继续往下走,理由是
    # 「业主可能只是想看看待办,ds-web 是只读的、不需要 key」。**那句话是假的** ——
    # 配置里 "apiKey": "${DS_LLM_KEY}",nanobot 解析到没设的 ${VAR} 就整个拒绝启动,
    # 于是业主等来的是网关的一句英文 `Environment variable … is not set`。
    # (tests/test_ds_shell_core.py H5 真起了一次网关把这件事钉死,别再靠注释。)
    # 所以现在:起任何后台之前先扫一遍配置,缺什么当场说清楚、说该往哪儿放。
    plan = core.startup_plan(has_key=bool(key))

    # 缺 key **不再是错误**,是"该去填了" ⇒ 只有真要起网关时才拦缺变量。
    # (没有这个 if,业主永远走不到引导页:网关会死在缺变量上,而这一层直接 die。)
    if "网关" in plan["start"]:
        try:
            with cfg.open("r", encoding="utf-8") as f:
                # 拿**网关那条腿**的 env 去比,不是别的:key 只进它(service_envs),
                # 拿 ds-web 那份去比会说"DS_LLM_KEY 没设",而它本来就不该有。
                # (08-16 业主真机:这里写的是已经不存在的 `env` —— 有 key 的机器
                #  每次开机 NameError。判据 tests/test_shipped_names.py 咬着。)
                missing = core.missing_env_refs(json.load(f), envs["网关"])
        except (OSError, ValueError) as e:
            die(f"配置读不出来:{e}\n\n请重新运行安装程序。")
        # 说什么话在 core 里(判据 H6~H9 咬着);这一层只剩"有就弹"。
        trouble = core.missing_env_message(missing, app=APP, key_path=str(key_file(home)))
        if trouble:
            die(trouble)

    # 🔴 迁移必须在**起任何服务之前**(判据 h3)。网关是第一个起来的,它带着三个 MCP
    # 工具服务;老版本装过的机器上,档案还躺在安装目录里,而新的数据根是空的 ——
    # 那一刻业主问"我有哪些项目",助手会回"一个都没有",甚至在新根里建一个重名的。
    # ds_web 自己也会迁移一次(幂等),但它是**第二个**起来的,来不及。
    try:
        migration = core.prepare_data_root(user_home=str(home),
                                           ds_root=str(install_root() / "ds"))
    except ds_common.DataRootError as exc:
        die(f"数据目录不可用({exc})。\n\n请重新运行安装程序。")
    if migration["failed"]:
        die(f"你的资料从旧位置搬过来时出错了,先没有继续启动:\n{migration['failed']}\n\n"
            f"把这段发给我看看 —— 东西还在原处,没有丢。")

    logs = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"

    def gateway_service(e):
        return core.Service(name="网关", argv=[str(python_exe()), "-m", "nanobot", "gateway"],
                            env=e, ready_port=ws, log_path=logs / "网关.log",
                            # 冷启动要连 3 个 MCP 子进程,S0 真机上见过接近 4 分钟
                            ready_timeout=300)

    def web_service(e):
        return core.Service(name="工作台", argv=[str(python_exe()),
                                                 str(install_root() / "ds" / "bin" / "ds_web.py")],
                            env=e, ready_port=web, log_path=logs / "工作台.log",
                            # 🔴 2026-08-30(判据 s11):就绪 = **它真的应答了**,
                            #    不是"端口有人监听"。`ready_probe` 这个机制一直都在,
                            #    只是工作台从没接上 ⇒ 时间线里的"后端就绪"是半真话,
                            #    而整条启动耗时都建在这句话上面。
                            ready_probe=web_ready_probe,
                            ready_timeout=60)

    # plan 里那两个名字是 core 的说法("ds-web"/"网关");Service 名是业主看得见的
    # 中文名("工作台"),watchdog 和报错都用它。别把两套名字混着用。
    services = (([gateway_service(envs["网关"])] if "网关" in plan["start"] else [])
                + [web_service(envs["ds-web"])])

    sup = core.Supervisor()
    try:
        sup.start(services)
    except core.StartupFailed as e:
        sup.shutdown()
        die(f"{APP} 没能启动。\n\n{e}\n\n详细日志:{logs}")

    def restart_gateway():
        """业主在界面里填完 key ⇒ ds-web 通过锁通道叫到这里。

        **现读**一遍 key 和配置(build_env 就是干这个的),把网关换成新进程;
        界面那条腿一动不动 —— 他正看着的页面就是它发的。
        """
        k, fresh = build_env()      # fresh 是两条腿各自的 env,重启只换网关那条
        if not k:
            log("[重启网关] 收到请求,但 key.txt 还是空的 —— 不动")
            return
        try:
            sup.restart([gateway_service(fresh["网关"])])
            log("[重启网关] 完成")
        except Exception as exc:      # 回调跑在锁的线程里:炸出去会把那条线程带走
            log(f"[重启网关] 失败:{exc}")
            alert(f"key 已经存好了,但后台没能自己重启:\n{exc}\n\n"
                  f"请退出 {APP} 再打开一次。")

    return sup, web, restart_gateway


# ── winuser.h 的几个常量 ──────────────────────────────────────────────
# 🔴 值抄错一位**不会报错**,只会安静地设成别的位 ⇒ 判据 s1 逐个对表 winuser.h。
#    GWL_STYLE 是负数,别写成 0x10。
GWL_STYLE = -16
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

# ── 方案 B(track opendesign-native-frame)新增 ─────────────────────
# 0.92.0 只贴了上面那三个不参与绘制的位,真机证明**动画不归它们管** ——
# 归下面这两个。代价是它们会真的改变非客户区尺寸,所以必须同时接管
# WM_NCCALCSIZE 把那块地方吃掉。两件事同生共死(判据 n3)。
GWLP_WNDPROC = -4
WM_NCCALCSIZE = 0x0083
            area = self._work_area(form)
            form.Bounds = Rectangle(area.X, area.Y, area.Width, area.Height)
            return True
        return {"maximized": bool(self._on_ui(go))}

    def window_state(self):
        return {"maximized": bool(self._on_ui(self._is_max))}

    def close_window(self):
        """关 = 收进托盘,和以前点系统那个 × 一模一样(不是退出程序)。"""
        self._shell.state.on_close_requested()

    def report_startup(self, event: str, detail: str = ""):
        """前端报"我走到哪一步了"。**这是网页能写进日志的口子** ⇒ 当不可信输入处理。

        白名单 / 限长 / 去重全在 `ds_diag.report_from_ui` 里(判据 s7),
        这一层只负责把"首帧到了"这件事告诉看门狗、别让它误报。

        🔴 `frontend.frame_submitted` 只说明**浏览器提交了一帧**,不等于业主眼睛看见了
        —— 真实像素只有 Windows 那边的截图作得了准(双出那轮 GPT 把这条钉死的)。
        """
        accepted = DIAG.report_from_ui(str(event), str(detail))
        if event == "frontend.frame_submitted":
            self._shell.note_first_frame()
        return {"accepted": bool(accepted)}


class Shell:
    """把 core 的状态机接到 pywebview / pystray 上。"""

    def __init__(self, sup, web_port: int, lock: core.InstanceLock):
        self.sup = sup
        self.web_port = web_port
        self.lock = lock
        self.window = None
        self.icon = None
        # 窗口按钮走它,`shown` 那条线也要再叫它一次(贴系统样式位)⇒ 存一份,
        # 别在 main 里往实例上动态挂一个属性。
        self.window_api = WindowApi(self)
        self.state = core.ShellState(ui=self, on_stop=self.stop_backend)
        self._frame_watch = None

    # --- core.ShellState 要求的 UI 三件 -------------------------------
    # ⚠️ 这三个方法可能被**锁的监听线程**调到(第二次双击时)。pywebview 的
    # EdgeChromium 后端内部会把调用转到 UI 线程,但这一点我在 Linux 上验不了 ⇒
    # 已进 Windows 真机考卷(「开着的时候再双击一次图标」那一问)。
    def show_window(self):
        if not self.window:
            return
        # 🔴 先从最小化里捞出来,再 Show。pywebview 的 `show()` 是
        #    `Form.Show() + Activate()`,而 Activate 走的 `SetForegroundWindow`
        #    **对最小化的窗口不还原** ⇒ 业主点托盘图标、或再双击一次桌面图标,
        #    窗口都回不来(pywebview issue #1749 列的第三条,我们从没验过)。
        #    ⚠️ 2026-08-23(track opendesign-native-frame):这里原来写着
        #    「我们的最大化 WindowState 一直是 Normal ⇒ restore 幂等」——
        #    **D3 之后那句话不成立了**,最大化是真的,无条件 restore() 会把
        #    最大化的窗口打回小窗。所以先问一句它是不是真的最小化了。
        minimized = True
        try:
            from System.Windows.Forms import FormWindowState

            form = getattr(self.window, "native", None)
            if form is not None:
                minimized = (form.WindowState == FormWindowState.Minimized)
        except Exception as exc:
            # 读不到状态时**按最小化处理**:多还原一次顶多丢掉最大化状态,
            # 而漏还原会让窗口彻底回不来 —— 那才是 0.92 修掉的那个 bug。
            log(f"[窗口] 读不到窗口状态,按最小化处理:{exc.__class__.__name__}")
        if minimized:
            try:
                self.window.restore()
            except Exception as exc:
                log(f"[窗口] 从最小化还原失败,仍然试着 Show:{exc.__class__.__name__}")
        self.window.show()

    def hide_window(self):
        if self.window:
            self.window.hide()

    def destroy(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        if self.window:
            # 🔴 先把窗口过程还回去,再销毁窗口 —— 顺序反了的话,
            #    销毁过程中那几条消息会走进一个即将消失的 Python 回调。
            self.window_api.uninstall_wndproc()
            try:
                self.window.destroy()
            except Exception:
                pass

    # --- 收摊 ---------------------------------------------------------
    def stop_backend(self):
        log("收摊:停两条腿")
        try:
            self.sup.shutdown()
        finally:
            self.lock.release()

    # --- 托盘 ---------------------------------------------------------
    # --- 首帧看门 + 诊断导出 ------------------------------------------
    # 白屏那晚(0.98,08-25)我们手上一条线索都没有。这两件补的就是那笔账。

    FIRST_FRAME_TIMEOUT = 90.0
    """多少秒没等到前端画出第一帧,就写一次诊断快照。

    🔴 **这个数字不承重**(判据 s9):超时路径不弹框,定错了最多多写一段日志。
    取 90 是刻意取宽的 —— 已知唯一硬数据是云端冷启虚机 20~40 秒(08-25 分时段截图),
    **业主自己机器上要几秒,至今没有任何人量过**。等他发回第一份诊断包再谈收紧。
    """

    def start_first_frame_watch(self):
        """🔴 **只上一次膛**(判据 s14;四审孤腿 BLOCK 抓到)。

        它挂在 `events.shown` 上,而**托盘还原(hide → show)会再发一次 Shown**。
        再上一次膛的话:页面不会再报首帧(只在加载时报一次),而且 `report_from_ui`
        按进程去重、连重报都会被丢 ⇒ 新看门**必然超时** ⇒ 业主每次从托盘还原
        都换来一段假诊断。那就是"每次开机被骚扰"的原形,只是从弹框降级成了假日志。
        """
        if self._frame_watch is not None:
            return
        self._frame_watch = ds_diag.FirstFrameWatch(
            timeout=self.FIRST_FRAME_TIMEOUT, on_timeout=self._first_frame_missing, emit=log)
        self._frame_watch.start()

    def note_first_frame(self):
        if self._frame_watch is not None:
            self._frame_watch.seen()

    def _first_frame_missing(self):
        """到点了前端还没报"我画出来了" ⇒ 把现场记下来。**不弹框。**

        🔴 不许在这里叫 `sup.poll_dead()` —— 它内部走 `take_dead()`,是**破坏性**的,
        问一次就把死因从名册里取走了,看门狗那边的弹窗就变成"原因是空的"
        (08-17 判据 c21 治的正是这个形状)。这里只看不碰。
        """
        log("[启动] 🔴 到点还没等到界面画出来 —— 下面是现场,不是报错弹窗。")
        for name, ms in DIAG.milestones():
            log(f"[启动]   已到达 +{ms:.0f}ms {name}")
        try:
            # 同样绕开系统代理(见 web_ready_probe 的注释)—— 这条是诊断路径,
            # 走了代理只会让现场少一条信息,但没有理由留着同一个病的另一半。
            import urllib.request
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(
                    f"http://127.0.0.1:{self.web_port}/api/health", timeout=3) as r:
                log(f"[启动]   /api/health 通,HTTP {r.status}"
                    f" ⇒ 后端是活的,问题在网页那一层")
        except Exception as exc:
            log(f"[启动]   /api/health 不通:{exc!r} ⇒ 问题可能在后端")
        log(f"[启动]   右下角托盘 → 「导出本次启动诊断」可以把这些打包发出来。")

    def export_diagnostics(self):
        """托盘那一项。白屏时窗口是废的,**托盘还活着** —— 这是唯一还能操作的地方。"""
        try:
            out = _app_dir() / f"OpenDesign-诊断-{DIAG.run_id}.zip"
            DIAG.export_bundle(out, app_dir=_app_dir())
            log(f"[启动] 已导出诊断:{out}")
            # 复用既有的平台实现,别在这儿造第四种"打开文件夹"
            # (这个项目为同一个动作有过三种写法,已经统一到 ds_openfolder)。
            import ds_openfolder
            ds_openfolder._default_open_launcher(str(out.parent))
        except Exception as exc:
            log(f"[启动] 导出诊断失败:{exc!r}")
            alert(f"导出诊断没成功:{exc}\n\n日志在:\n{_log_path().parent}")

    def run_tray(self):
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("打开 OpenDesign", lambda *_: self.state.on_show(), default=True),
            # 白屏时业主唯一还点得动的地方 —— 一下打包,不用去文件夹里翻日志。
            pystray.MenuItem("导出本次启动诊断", lambda *_: self.export_diagnostics()),
            pystray.MenuItem("退出", lambda *_: self.state.on_quit()),
        )
        self.icon = pystray.Icon(APP, tray_image(), APP, menu)
        # run_detached 在没有主循环可挂靠时会失败 ⇒ 用自己的线程跑 run()
        threading.Thread(target=self.icon.run, name="ds-shell-tray", daemon=True).start()

    # --- 看门狗:哪条腿死了要说话,不能让界面一直转圈 -------------------
    def run_watchdog(self):
        self._stop_watch = threading.Event()

        def loop():
            while not self.state.exiting:
                # 🔴 2026-08-16:这里原来只打了一句 `[后台退出] ['网关']`。
                # 业主那晚网关死了,两份日志摆在我面前也答不了「是被杀的还是自己崩的」
                # —— 因为**退出码从来没被打印过**。现在每条腿都把退出码和它自己
                # 日志的尾巴写进外壳日志(判据 c20);弹窗仍然只说人话。
                #
                # 🔴 08-17(F5,判据 c21/w7):**只看一眼**。原来先问 `poll_dead()`
                # 拿名字、再问 `dead_reports()` 拿原因,两问之间业主若正好存了 key
                # 触发重启,名册就变了 ⇒ 弹窗照弹、原因是空的。
                found = self.sup.take_dead()
                if found:
                    dead = [name for name, _ in found]
                    for _, report in found:
                        log(f"[后台退出] {report}")
                    alert(f"{'、'.join(dead)} 意外退出了。\n\n"
                          f"请退出后重新打开 {APP};日志在:\n{_log_path().parent}\n\n"
                          f"（把 外壳.log 发给我,里面有它的退出码和最后几句话。）")
                    return
                self._stop_watch.wait(3.0)
        threading.Thread(target=loop, name="ds-shell-watchdog", daemon=True).start()


def main() -> int:
    DIAG.mark("main.entered")
    log(f"==== {APP} 外壳启动 ====")
    # 版本清单先写 —— 万一后面炸了,至少知道是哪一版、哪个内核上炸的。
    # (08-25 白屏那晚我们连内核版本都得靠业主去翻文件夹。)
    log(DIAG.manifest())
    # manifest() 里会 import ds_web 拿版本号(唯一来源)。它是**我自己塞进这段窗口的
    # 成本**,所以必须单独计一笔 —— 免得将来查慢的时候查到自己头上还不知道。
    DIAG.mark("manifest.done")
    shell_holder: list[Shell] = []

    # ① 单实例。第二次双击走到这里就退出了,窗口由第一份自己叫到前台。
    #    这把锁同时是 ds-web 回来找我们的**唯一通道**(填完 key 请求重启网关)——
    #    所以它必须在起后台之前就位:锁端口要随 env 交给 ds-web。
    restart_holder: list = []
    lock = core.InstanceLock(
        base_port=LOCK_PORT, span=5,
        on_show=lambda: shell_holder and shell_holder[0].state.on_show(),
        on_restart=lambda: restart_holder and restart_holder[0]())
    try:
        if not lock.acquire():
            log("已有一份在跑,把它叫到前台,自己退出")
            return 0
    except core.PortBusy as e:
        die(f"启动失败:{e}")
    # 花在哪、占了哪一格,由这把锁自己说 —— 2026-09-01 那一趟真机,业主的诊断里
    # 只有一个 +9094ms,是我拿它减前一条、再除以锁位数,才知道 6 次握手全部耗满。
    # 下一趟不该再靠人做除法。
    DIAG.mark("lock.acquired",
              f"port={lock.port} 扫了{lock.scanned}格 用时{lock.scan_ms:.0f}ms")

    try:
        home = user_home()
        sup, web, restart_gateway = start_backend(home, lock_port=lock.port)
        DIAG.mark("backend.ready")
        restart_holder.append(restart_gateway)
        shell = Shell(sup, web, lock)
        shell_holder.append(shell)

        import webview

        shell.window = webview.create_window(
            # 地址带 SHELL_MARK = 外壳自报身份,前端第一帧就知道要画窗口栏
            # (window_url 是唯一来源,日志里印的也是它)。
            APP, window_url(web),
            width=1280, height=860, min_size=(960, 640),
            # 🔴 2026-08-16 业主:系统标题栏那个 "OpenDesign" 和我们前端自己的标题
            #    撞了 ⇒ 不要那个框,窗口按钮我们自己画在右上角(WindowChrome.tsx)。
            #    代价说清楚:frameless 之后 Windows 把"拖边缘改大小"也一起收走了,
            #    由 WindowApi 用原生窗口消息接回来。
            #    `easy_drag=False` 是关键:开着的话**整个页面**按哪儿都能拖窗口 ——
            #    选不了字、拖不动滚动条。拖动只认我们那条栏。
            frameless=True, easy_drag=False, js_api=shell.window_api,
        )
        # 关窗口 = 收进托盘。pywebview 的 closing 回调返回 False 表示"别关"。
        shell.window.events.closing += lambda: shell.state.on_close_requested()
        # 窗口一出来就把 frameless 拿走的那几个样式位贴回去(见
        # WindowApi._apply_native_styles)。挂 `shown` 而不是在这儿直接叫:
        # 这一刻窗口还没建出来,没有 Handle 可用。
        shell.window.events.shown += shell.window_api.ensure_native_styles
        # 🔴 2026-08-30(判据 s6):「窗口打开」这行原来写在 `webview.start()` **之前** ——
        #    它报的是"我要开了",不是"开了"。白屏那晚这行照样出现在日志里,
        #    于是它把"窗口真开了"这件根本没发生的事说成了既成事实。搬到 shown 里。
        shell.window.events.shown += lambda: DIAG.mark("window.shown")
        # 首帧看门:到点还没等到前端报"我画出来了",就写一次诊断快照。
        # **不弹框**(判据 s9)—— 阈值不承重,定错了最多多写一段日志。
        shell.window.events.shown += lambda: shell.start_first_frame_watch()

        shell.run_tray()
        shell.run_watchdog()
        DIAG.mark("window.create_returned", window_url(web))
        log(f"准备进入图形循环:{window_url(web)}")
        DIAG.mark("webview.loop_entered")
        webview.start()          # 阻塞,直到窗口 destroy
        shell.state.on_quit()    # 走正常关闭时也要把后台收干净
        return 0
    except ImportError as e:
        # 少了 pywebview / pythonnet / PIL —— 包被装坏了
        die(f"{APP} 少了运行所需的组件:{e}\n\n请重新运行安装程序。")
    except Exception as e:
        # .NET 挂不上、WebView2 缺失都会落到这里。**不许只抛 CLR 栈**:
        # 业主看到一堆英文栈只会来问我。原始栈进日志,弹窗给人话。
        log(traceback.format_exc())
        die(f"{APP} 启动时出错:{e}\n\n"
            f"如果是第一次在这台电脑上打开,多半是缺少微软的 WebView2 运行时,\n"
            f"请重新运行安装程序(它会自动补装)。\n\n详细日志:{_log_path()}")
    finally:
        lock.release()
    return 1


# 🔴 模块体走完 = 所有 import 都办完了。这一条把"进程起来 → 拿到锁"那个
#    9.4 秒的黑块切开(判据 s17):云机器上它是全程最大的一块,而在 Linux 上
#    整条 import 链只要 130ms —— 差 70 倍,差的是 I/O 不是算力。
#    切开之后才知道到底是 import 慢、还是锁那一步慢。
DIAG.mark("shell.imports_done")

if __name__ == "__main__":
    sys.exit(main())

exec
/bin/bash -lc 'rg -n "ds_update|update_available|/api/update|api/health|VERSION|release_url|check_cached" bin/ds_web.py' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
6:  GET /api/health  存活探针(version + ds_root)
86:import ds_update    # 查更新(track opendesign-in-app-update):只查不装
94:VERSION = "0.98.4"  # 应用内更新第一刀:软件自己发现新版并说一句(只查不装)
162:                    # ds_web.py 两版之间只改了 VERSION 注释 ⇒ 从"看得见"到"全白"
231:                    # /api/health 都取这个号,而 08-14 那个安装器和这个若同叫 0.85.0,
241:                    # 装机脚本要装 firecrawl-anydoc==0.1.6;/api/health 的
856:    server_version = f"ds-web/{VERSION}"
916:        if path == "/api/health":
917:            self._json(200, {"ok": True, "version": VERSION,
920:                             # 文档转换器装没装:业主刷一下 /api/health 就看得见,
923:        elif path == "/api/update/check":
1032:        本机版本号只有一个来源(VERSION),不另写一份 —— 抄第二份迟早对不上。
1039:        self._json(200, ds_update.check_cached(VERSION, force=force))
2053:        # 不是新的泄漏类:/api/health 早就回 ds_root,且这是 localhost 单机工具、
2609:    print(f"ds-web {VERSION}: http://127.0.0.1:{port}/  "

exec
/bin/bash -lc "sed -n '840,930p' bin/ds_web.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 1ms:
exec
/bin/bash -lc "sed -n '2180,2320p' bin/ds_web.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
        #    —— 否则被注入的助手一句话就能在业主浏览器里同源 fetch 打这个口。
        #    现状由另一套机制撑着:markdown 禁 raw HTML(`web/src/chat/markdown.ts`,
        #    `test_chat_transcript.mjs` 的 XSS 闸钉着)+ 写口一律 application/json
        #    ⇒ 跨源要 preflight ⇒ 本服务没有 OPTIONS 面 ⇒ 浏览器自己拦下。
        #    哪天有人给 markdown 加 rehype-raw、或新增一个 text/plain 写口,这条就塌了。
        # ⇒ 模型够不到这个 HTTP 口。**这四条哪条塌了,这一行就得回来重想。**
        r = ds_tools._apply_bind_project(project, folder, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        out = {"error": err}
        if "folders" in r:  # folder_not_found/folder_ambiguous 候选名单透传
            out["folders"] = r["folders"]
        self._json(_BIND_ERR_STATUS.get(err, 400), out)

    def _folder_visibility(self):
        """POST /api/workspace/folder-visibility:一次存整份「不显示」清单。

        posture 照抄写针孔⑨:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {review_id, hidden} → 类型/值域闸。写盘只在
        locked_workspace_json 内进行,且只改 raw["structuralDirs"] 一个键。
        """
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= _FOLDER_VISIBILITY_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _FOLDER_VISIBILITY_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})
            return
        review_id = body.get("review_id")
        hidden = body.get("hidden")
        if not isinstance(review_id, str) or not review_id:
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(hidden, list) or len(hidden) > _FOLDER_VISIBILITY_MAX_NAMES:
            self._json(400, {"error": "bad request"})
            return
        seen = set()
        for name in hidden:
            if (not isinstance(name, str) or not name
                    or not ds_workspace._SEG_RE.match(name) or name in seen):
                self._json(400, {"error": "bad request"})
                return
            seen.add(name)

        # 锁内**只算出**要回什么,出锁再发 —— 响应虽小,但在锁内写 socket 等于
        # 让一个慢客户端占住 workspace.json 的排他锁,而该锁在 Windows 上争用
        # 会抛 OSError 而非排队(阶段一四审记录)。
        try:
            with ds_tools.locked_workspace_json(self.server.ds_root) as box:
                box["write"] = False
                raw = box["raw"]
                cfg = ds_workspace.load_config(self.server.ds_root)
                if raw is None or cfg is None:
                    reply = (409, {"error": "workspace_not_configured"})
                else:
                    reply = self._folder_visibility_apply(box, cfg, review_id, hidden)
        except Exception:
            traceback.print_exc()
            reply = (500, {"error": "internal"})
        self._json(*reply)

    def _folder_visibility_apply(self, box, cfg, review_id, hidden):
        """在已持锁的前提下复核快照并落盘;→ (status, payload),不自己发响应。"""
        proot = ds_workspace.projects_root(cfg)
        if not proot or os.path.realpath(cfg["root"]) != os.path.realpath(proot):
            return 409, {"error": "not_applicable"}
        top_dirs = _workspace_top_dirs(os.path.realpath(cfg["root"]))
        current_rid = _workspace_review_id(
            _workspace_config_bytes(self.server.ds_root), top_dirs)
        if review_id != current_rid:
            return 409, {"error": "stale_review"}
        declared = (cfg.get("structuralDirs")
                    if isinstance(cfg.get("structuralDirs"), list) else [])
        issued = set(top_dirs) | set(declared)
        if any(name not in issued for name in hidden):
            return 400, {"error": "bad request"}
        box["raw"]["structuralDirs"] = list(hidden)
        box["write"] = True
        return 200, {"ok": True}

    def _set_stage(self):
        """POST 写针孔⑩(track opendesign-stage-history §7):切阶段。
        薄壳,posture 逐条照抄 _edit_change:CT application/json →
        body 0<n≤OPEN_BODY_MAX → JSON dict → 键白名单 {project, stage, since}(多余键即拒,
        防夹带 ds_root/today 走私)→ project/stage 必须非空 str;since 可缺省或 null,
        给了就必须是 str(空串即拒)→ ds_tools.set_stage(
        名字闸/词表精确匹配/锁/页脚 bump 全在核心)。响应体不回显词表(词表走
        GET /api/projects 的 stages,写口少一条外泄面)。Host 闸由 do_POST 入口继承。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _STAGE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        stage = body.get("stage")
        since = body.get("since")
        if (not isinstance(project, str) or not project
                or not isinstance(stage, str) or not stage):
            self._json(400, {"error": "bad request"})
            return
        if since is not None and not isinstance(since, str):
            self._json(400, {"error": "bad request"})
            return
        if since == "":
            self._json(400, {"error": "invalid_since"})
            return
        r = ds_tools.set_stage(project, stage, since=since, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_STAGE_ERR_STATUS.get(err, 400), {"error": err})


exec
/bin/bash -lc "sed -n '1220,1390p' bin/ds_web.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        # 只回 UI 需要的字段(id/style/space/file/note),source/used 不外泄。
        # M2 不变量:列出=可服务——file 必须是 refs/ 下、剩余段过 Gate A 的路径,
        # 否则前端渲染即裂图(索引里手写了服务端认不出的字符)。跳过不列。
        out = [{"id": r["id"], "style": r["style"], "space": r["space"],
                "file": r["file"], "note": r["note"]}
               for r in refs if _servable_ref_file(r["file"])]
        # 词表(track opendesign-stage-history §8):单一真相源 = ds_refs._load_styles /
        # ds_refs.SPACES,前端 lightbox 编辑区不许硬编码副本。
        vocab = {"style": ds_refs._load_styles(self.server.ds_root),
                 "space": list(ds_refs.SPACES)}
        self._json(200, {"key": key, "refs": out, "vocab": vocab})

    def _refs_file(self, rel: str):
        """参考图静态服务 —— 本 track 唯一新增文件读出面。三闸串联,每闸独立可验红:
        Gate A 段黑名单 → Gate B realpath 前缀(逃逸/symlink 权威闸)→ Gate C 扩展白名单。
        404 一律不回显路径;Content-Type 按扩展映射;禁目录列表(只 isfile)。"""
        # Gate A —— relpath_ok:拒 % 残留 / 控制字符 / 反斜杠 / 空段 / . .. 段
        if not ds_workspace.relpath_ok(rel):
            self._json(404, {"error": "not found"})
            return
        base = os.path.realpath(os.path.join(
            ds_common.data_root(self.server.ds_root), "refs"))
        target = os.path.realpath(os.path.join(base, rel))
        # Gate B —— realpath 前缀:裸 ../ 与 symlink 逃逸展开后必须仍落在 refs/ 内
        if not ds_common.within(base, target):
            self._json(404, {"error": "not found"})
            return
        # Gate C —— 扩展名白名单:只有图片类型可读出
        ctype = _IMG_CTYPES.get(os.path.splitext(target)[1].lower())
        if ctype is None:
            self._json(404, {"error": "not found"})
            return
        if not os.path.isfile(target):  # 禁目录列表 + 不存在
            self._json(404, {"error": "not found"})
            return
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body,
                   {"Cache-Control": "public, max-age=86400"})

    # ── P5 文件工作区 ────────────────────────────────────────────────────────

    def _ws_proj(self, key: str):
        """(状态, 项目夹, 扫描深度) —— 状态 ∈ badkey/unconfigured/unmapped/ok。
        配置每请求现读(零缓存,与 /api/todos 同哲学,改 json 即生效)。"""
        if not _valid_proj_key(key):
            return "badkey", None, ds_workspace.DEFAULT_MAX_DEPTH
        cfg = ds_workspace.load_config(self.server.ds_root)
        if cfg is None:
            return "unconfigured", None, ds_workspace.DEFAULT_MAX_DEPTH
        pd = ds_workspace.project_dir(cfg, key)
        if pd is None:
            return "unmapped", None, cfg["galleryDepth"]
        return "ok", pd, cfg["galleryDepth"]

    def _files_meta(self, key: str, kind: str):
        """overview / images 共用外壳:降级态诚实回 JSON,不 404 糊弄前端。"""
        status, pd, depth = self._ws_proj(key)
        if status == "badkey":
            self._json(404, {"error": "not found"})
            return
        if status == "unconfigured":
            self._json(200, {"configured": False})
            return
        if status == "unmapped":
            self._json(200, {"configured": True, "mapped": False})
            return
        try:
            if kind == "overview":
                data = ds_workspace.overview(pd, max_depth=depth)
            else:
                data = {"images": ds_workspace.images(pd, max_depth=depth)}
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._json(200, {"configured": True, "mapped": True, **data})

    def _files_file(self, key: str, rel: str):
        """项目图片静态服务。三闸同 _refs_file 先例(Gate A relpath_ok → Gate B realpath
        within(项目夹) → Gate C 图片扩展白名单),外加 key 必须已映射;404 不回显路径。"""
        status, pd, depth = self._ws_proj(key)
        if status != "ok" or not ds_workspace.relpath_ok(rel):
            self._json(404, {"error": "not found"})
            return
        target = os.path.realpath(os.path.join(pd, rel))
        if not ds_common.within(pd, target):
            self._json(404, {"error": "not found"})
            return
        ctype = _IMG_CTYPES.get(os.path.splitext(target)[1].lower())
        if ctype is None or not os.path.isfile(target):
            self._json(404, {"error": "not found"})
            return
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body, {"Cache-Control": "public, max-age=3600"})

    def _open_folder(self):
        """唯一非 GET 端点(P5 design §3;track p3-polish §I4 拓宽为可选 rel)。
        闸序:body 尺寸/JSON → key 白名单+映射(_ws_proj)→ 分流:
          - 无 rel(老行为,不回归):sub 单段白名单+realpath within+isdir
            (ds_workspace.resolve_sub)
          - 有 rel(新增,开单个文件):Gate A ds_workspace.relpath_ok(rel) →
            Gate B realpath+ds_common.within(项目夹)→ Gate D os.path.isfile
            (目录/不存在 → 404,开目录走 sub 不走 rel)→ Gate C 扩展名 ∈
            _OPEN_EXTS 白名单(只有真文件才谈得上"扩展名被拒" 415)
        rel 与 sub 同给(body 同时含两个键)→ 400,不猜意图。
        全过才调 OPEN_LAUNCHER;任何拒绝路径零执行(oracle 断言)。
        CSRF 硬化:强制 Content-Type application/json——跨站 fetch 带该类型必触发
        preflight,本服务无 OPTIONS 面 → 浏览器拦;text/plain 类 simple request 在此 400。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict):
            self._json(400, {"error": "bad request"})
            return
        # inbox 分支(track opendesign-chat-image-p2 D2):「打开收件箱」。
        # **路径由服务端 _find_inbox 解析,调用方给不了路径** —— 否则这条口就成了
        # "网页能让 Windows 打开任意目录"。与 key/sub/rel 互斥,同给即 400(不猜意图)。
        if "inbox" in body:
            if body.get("inbox") is not True or set(body) != {"inbox"}:
                self._json(400, {"error": "bad request"})
                return
            cfg = ds_workspace.load_config(self.server.ds_root)
            if not cfg or not cfg.get("root"):
                self._json(404, {"error": "not found"})
                return
            taxonomy = ds_taxonomy.load_taxonomy(self.server.ds_root)
            found = ds_intake._find_inbox(cfg, taxonomy) if taxonomy else None
            if not found:
                self._json(404, {"error": "not found"})
                return
            try:
                OPEN_LAUNCHER(found[1])
            except OSError:
                traceback.print_exc()
                self._json(500, {"error": "internal"})
                return
            self._json(200, {"ok": True})
            return
        key = body.get("key")
        if not isinstance(key, str) or not key:
            self._json(400, {"error": "bad request"})
            return

exec
/bin/bash -lc "sed -n '1000,1050p' bin/ds_web.py; sed -n '2570,2630p' bin/ds_web.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
            self._inbox_create()
        elif path == BIND_PROJECT_PATH:
            self._bind_project()
        elif path == FOLDER_VISIBILITY_PATH:
            self._folder_visibility()
        elif path == STAGE_PATH:
            self._set_stage()
        elif path == REFS_UPDATE_PATH:
            self._refs_update()
        elif path == DUE_DATE_PATH:
            self._set_due_date()
        elif path == DELETE_CHANGE_PATH:
            self._delete_change()
        elif path == CONSENT_MODE_PATH:
            self._consent_mode()
        elif path == CONSENT_RESOLVE_PATH:
            self._consent_resolve()
        elif (m := _SESSION_DELETE_RE.match(path)):
            self._delete_session(m.group(1))
        else:
            self._method_not_allowed()

    do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    def _update_check(self):
        """查更新:线上有没有比本机新的版本(track opendesign-in-app-update,第一刀)。

        🔴 **任何失败都以 200 + error 字段回**(判据 t9b)。查更新失败是小事,
        而一个 500 会让前端的通用错误路径弹东西给业主 —— 他什么都没干、只是打开了软件,
        却看见"出错了"。**功能失败和软件坏了,在界面上不该长得一样。**

        `?force=1` 是业主亲手点了「检查更新」:那一下不给缓存,真去问一次。
        本机版本号只有一个来源(VERSION),不另写一份 —— 抄第二份迟早对不上。
        """
        # 🔴 第三轮评审 F6:原来判的是"非空且非 0" ⇒ `?force=false` 也会强制刷新。
        #    没有危害(只多打一次 GitHub),但一个**反着读**的参数迟早会骗到下一个人。
        #    只认明确的"开"(判据 t9e)。
        raw_force = parse_qs(urlsplit(self.path).query).get("force", [""])[0]
        force = raw_force.strip().lower() in ("1", "true", "yes", "on")
        self._json(200, ds_update.check_cached(VERSION, force=force))

    def _todos(self):
        try:
            data = ds_todo.collect(self.server.ds_root)
        except Exception:
            # M1 后:坏编码文件(F2)/读期 OSError(F3,Windows 写锁窗口)已在 collect
            # 内逐文件隔离进 errors 字段;这层降为兜底(projects 目录本身不可列等意外),
            # 仍 500 但不再被单个坏文件触发。trace 进日志不进响应体。
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body, {"Cache-Control": cache})


def make_server(ds_root: str, dist: str, host: str = "127.0.0.1",
                port: int = DEFAULT_PORT,
                nanobot_port: int = DEFAULT_NANOBOT_PORT) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)  # allow_reuse_address 已内建
    httpd.ds_root = ds_root
    httpd.dist = os.path.realpath(dist)
    httpd.nanobot_port = nanobot_port  # 代理上游恒 127.0.0.1,仅端口可配
    return httpd


def main() -> int:
    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    dist = os.environ.get("DS_WEB_DIST", DEFAULT_DIST)
    port = int(os.environ.get("DS_WEB_PORT", str(DEFAULT_PORT)))
    nanobot_port = int(os.environ.get("DS_NANOBOT_PORT", str(DEFAULT_NANOBOT_PORT)))
    if not os.path.isfile(os.path.join(dist, "index.html")):
        print(f"ds-web: 前端产物缺失 {dist}/index.html —— 先在开发机构建"
              f"(cd web && npm run build)或 git pull 取最新", file=sys.stderr)
        return 2
    try:
        migration = ds_common.migrate_legacy_data(ds_root)
    except ds_common.DataRootError as exc:
        print(f"ds-web: 数据目录不可用({exc})", file=sys.stderr)
        return 2
    if migration["failed"]:
        print(f"ds-web: 遗留数据搬运失败: {migration['failed']}", file=sys.stderr)
        return 2
    try:
        httpd = make_server(ds_root, dist, port=port, nanobot_port=nanobot_port)
    except OSError as e:
        print(f"ds-web: 端口 {port} 起不来({e});被占用请设 DS_WEB_PORT 换端口",
              file=sys.stderr)
        return 2
    print(f"ds-web {VERSION}: http://127.0.0.1:{port}/  "
          f"(DS_DATA_ROOT={ds_common.data_root(ds_root)})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

exec
/bin/bash -lc "sed -n '1080,1210p' bin/ds_shell.py; sed -n '1210,1390p' bin/ds_shell.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
            area = self._work_area(form)
            form.Bounds = Rectangle(area.X, area.Y, area.Width, area.Height)
            return True
        return {"maximized": bool(self._on_ui(go))}

    def window_state(self):
        return {"maximized": bool(self._on_ui(self._is_max))}

    def close_window(self):
        """关 = 收进托盘,和以前点系统那个 × 一模一样(不是退出程序)。"""
        self._shell.state.on_close_requested()

    def report_startup(self, event: str, detail: str = ""):
        """前端报"我走到哪一步了"。**这是网页能写进日志的口子** ⇒ 当不可信输入处理。

        白名单 / 限长 / 去重全在 `ds_diag.report_from_ui` 里(判据 s7),
        这一层只负责把"首帧到了"这件事告诉看门狗、别让它误报。

        🔴 `frontend.frame_submitted` 只说明**浏览器提交了一帧**,不等于业主眼睛看见了
        —— 真实像素只有 Windows 那边的截图作得了准(双出那轮 GPT 把这条钉死的)。
        """
        accepted = DIAG.report_from_ui(str(event), str(detail))
        if event == "frontend.frame_submitted":
            self._shell.note_first_frame()
        return {"accepted": bool(accepted)}


class Shell:
    """把 core 的状态机接到 pywebview / pystray 上。"""

    def __init__(self, sup, web_port: int, lock: core.InstanceLock):
        self.sup = sup
        self.web_port = web_port
        self.lock = lock
        self.window = None
        self.icon = None
        # 窗口按钮走它,`shown` 那条线也要再叫它一次(贴系统样式位)⇒ 存一份,
        # 别在 main 里往实例上动态挂一个属性。
        self.window_api = WindowApi(self)
        self.state = core.ShellState(ui=self, on_stop=self.stop_backend)
        self._frame_watch = None

    # --- core.ShellState 要求的 UI 三件 -------------------------------
    # ⚠️ 这三个方法可能被**锁的监听线程**调到(第二次双击时)。pywebview 的
    # EdgeChromium 后端内部会把调用转到 UI 线程,但这一点我在 Linux 上验不了 ⇒
    # 已进 Windows 真机考卷(「开着的时候再双击一次图标」那一问)。
    def show_window(self):
        if not self.window:
            return
        # 🔴 先从最小化里捞出来,再 Show。pywebview 的 `show()` 是
        #    `Form.Show() + Activate()`,而 Activate 走的 `SetForegroundWindow`
        #    **对最小化的窗口不还原** ⇒ 业主点托盘图标、或再双击一次桌面图标,
        #    窗口都回不来(pywebview issue #1749 列的第三条,我们从没验过)。
        #    ⚠️ 2026-08-23(track opendesign-native-frame):这里原来写着
        #    「我们的最大化 WindowState 一直是 Normal ⇒ restore 幂等」——
        #    **D3 之后那句话不成立了**,最大化是真的,无条件 restore() 会把
        #    最大化的窗口打回小窗。所以先问一句它是不是真的最小化了。
        minimized = True
        try:
            from System.Windows.Forms import FormWindowState

            form = getattr(self.window, "native", None)
            if form is not None:
                minimized = (form.WindowState == FormWindowState.Minimized)
        except Exception as exc:
            # 读不到状态时**按最小化处理**:多还原一次顶多丢掉最大化状态,
            # 而漏还原会让窗口彻底回不来 —— 那才是 0.92 修掉的那个 bug。
            log(f"[窗口] 读不到窗口状态,按最小化处理:{exc.__class__.__name__}")
        if minimized:
            try:
                self.window.restore()
            except Exception as exc:
                log(f"[窗口] 从最小化还原失败,仍然试着 Show:{exc.__class__.__name__}")
        self.window.show()

    def hide_window(self):
        if self.window:
            self.window.hide()

    def destroy(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        if self.window:
            # 🔴 先把窗口过程还回去,再销毁窗口 —— 顺序反了的话,
            #    销毁过程中那几条消息会走进一个即将消失的 Python 回调。
            self.window_api.uninstall_wndproc()
            try:
                self.window.destroy()
            except Exception:
                pass

    # --- 收摊 ---------------------------------------------------------
    def stop_backend(self):
        log("收摊:停两条腿")
        try:
            self.sup.shutdown()
        finally:
            self.lock.release()

    # --- 托盘 ---------------------------------------------------------
    # --- 首帧看门 + 诊断导出 ------------------------------------------
    # 白屏那晚(0.98,08-25)我们手上一条线索都没有。这两件补的就是那笔账。

    FIRST_FRAME_TIMEOUT = 90.0
    """多少秒没等到前端画出第一帧,就写一次诊断快照。

    🔴 **这个数字不承重**(判据 s9):超时路径不弹框,定错了最多多写一段日志。
    取 90 是刻意取宽的 —— 已知唯一硬数据是云端冷启虚机 20~40 秒(08-25 分时段截图),
    **业主自己机器上要几秒,至今没有任何人量过**。等他发回第一份诊断包再谈收紧。
    """

    def start_first_frame_watch(self):
        """🔴 **只上一次膛**(判据 s14;四审孤腿 BLOCK 抓到)。

        它挂在 `events.shown` 上,而**托盘还原(hide → show)会再发一次 Shown**。
        再上一次膛的话:页面不会再报首帧(只在加载时报一次),而且 `report_from_ui`
        按进程去重、连重报都会被丢 ⇒ 新看门**必然超时** ⇒ 业主每次从托盘还原
        都换来一段假诊断。那就是"每次开机被骚扰"的原形,只是从弹框降级成了假日志。
        """
        if self._frame_watch is not None:
            return
        self._frame_watch = ds_diag.FirstFrameWatch(
            timeout=self.FIRST_FRAME_TIMEOUT, on_timeout=self._first_frame_missing, emit=log)
        self._frame_watch.start()

    def note_first_frame(self):
        if self._frame_watch is not None:
            self._frame_watch.seen()
            self._frame_watch.seen()

    def _first_frame_missing(self):
        """到点了前端还没报"我画出来了" ⇒ 把现场记下来。**不弹框。**

        🔴 不许在这里叫 `sup.poll_dead()` —— 它内部走 `take_dead()`,是**破坏性**的,
        问一次就把死因从名册里取走了,看门狗那边的弹窗就变成"原因是空的"
        (08-17 判据 c21 治的正是这个形状)。这里只看不碰。
        """
        log("[启动] 🔴 到点还没等到界面画出来 —— 下面是现场,不是报错弹窗。")
        for name, ms in DIAG.milestones():
            log(f"[启动]   已到达 +{ms:.0f}ms {name}")
        try:
            # 同样绕开系统代理(见 web_ready_probe 的注释)—— 这条是诊断路径,
            # 走了代理只会让现场少一条信息,但没有理由留着同一个病的另一半。
            import urllib.request
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(
                    f"http://127.0.0.1:{self.web_port}/api/health", timeout=3) as r:
                log(f"[启动]   /api/health 通,HTTP {r.status}"
                    f" ⇒ 后端是活的,问题在网页那一层")
        except Exception as exc:
            log(f"[启动]   /api/health 不通:{exc!r} ⇒ 问题可能在后端")
        log(f"[启动]   右下角托盘 → 「导出本次启动诊断」可以把这些打包发出来。")

    def export_diagnostics(self):
        """托盘那一项。白屏时窗口是废的,**托盘还活着** —— 这是唯一还能操作的地方。"""
        try:
            out = _app_dir() / f"OpenDesign-诊断-{DIAG.run_id}.zip"
            DIAG.export_bundle(out, app_dir=_app_dir())
            log(f"[启动] 已导出诊断:{out}")
            # 复用既有的平台实现,别在这儿造第四种"打开文件夹"
            # (这个项目为同一个动作有过三种写法,已经统一到 ds_openfolder)。
            import ds_openfolder
            ds_openfolder._default_open_launcher(str(out.parent))
        except Exception as exc:
            log(f"[启动] 导出诊断失败:{exc!r}")
            alert(f"导出诊断没成功:{exc}\n\n日志在:\n{_log_path().parent}")

    def run_tray(self):
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("打开 OpenDesign", lambda *_: self.state.on_show(), default=True),
            # 白屏时业主唯一还点得动的地方 —— 一下打包,不用去文件夹里翻日志。
            pystray.MenuItem("导出本次启动诊断", lambda *_: self.export_diagnostics()),
            pystray.MenuItem("退出", lambda *_: self.state.on_quit()),
        )
        self.icon = pystray.Icon(APP, tray_image(), APP, menu)
        # run_detached 在没有主循环可挂靠时会失败 ⇒ 用自己的线程跑 run()
        threading.Thread(target=self.icon.run, name="ds-shell-tray", daemon=True).start()

    # --- 看门狗:哪条腿死了要说话,不能让界面一直转圈 -------------------
    def run_watchdog(self):
        self._stop_watch = threading.Event()

        def loop():
            while not self.state.exiting:
                # 🔴 2026-08-16:这里原来只打了一句 `[后台退出] ['网关']`。
                # 业主那晚网关死了,两份日志摆在我面前也答不了「是被杀的还是自己崩的」
                # —— 因为**退出码从来没被打印过**。现在每条腿都把退出码和它自己
                # 日志的尾巴写进外壳日志(判据 c20);弹窗仍然只说人话。
                #
                # 🔴 08-17(F5,判据 c21/w7):**只看一眼**。原来先问 `poll_dead()`
                # 拿名字、再问 `dead_reports()` 拿原因,两问之间业主若正好存了 key
                # 触发重启,名册就变了 ⇒ 弹窗照弹、原因是空的。
                found = self.sup.take_dead()
                if found:
                    dead = [name for name, _ in found]
                    for _, report in found:
                        log(f"[后台退出] {report}")
                    alert(f"{'、'.join(dead)} 意外退出了。\n\n"
                          f"请退出后重新打开 {APP};日志在:\n{_log_path().parent}\n\n"
                          f"（把 外壳.log 发给我,里面有它的退出码和最后几句话。）")
                    return
                self._stop_watch.wait(3.0)
        threading.Thread(target=loop, name="ds-shell-watchdog", daemon=True).start()


def main() -> int:
    DIAG.mark("main.entered")
    log(f"==== {APP} 外壳启动 ====")
    # 版本清单先写 —— 万一后面炸了,至少知道是哪一版、哪个内核上炸的。
    # (08-25 白屏那晚我们连内核版本都得靠业主去翻文件夹。)
    log(DIAG.manifest())
    # manifest() 里会 import ds_web 拿版本号(唯一来源)。它是**我自己塞进这段窗口的
    # 成本**,所以必须单独计一笔 —— 免得将来查慢的时候查到自己头上还不知道。
    DIAG.mark("manifest.done")
    shell_holder: list[Shell] = []

    # ① 单实例。第二次双击走到这里就退出了,窗口由第一份自己叫到前台。
    #    这把锁同时是 ds-web 回来找我们的**唯一通道**(填完 key 请求重启网关)——
    #    所以它必须在起后台之前就位:锁端口要随 env 交给 ds-web。
    restart_holder: list = []
    lock = core.InstanceLock(
        base_port=LOCK_PORT, span=5,
        on_show=lambda: shell_holder and shell_holder[0].state.on_show(),
        on_restart=lambda: restart_holder and restart_holder[0]())
    try:
        if not lock.acquire():
            log("已有一份在跑,把它叫到前台,自己退出")
            return 0
    except core.PortBusy as e:
        die(f"启动失败:{e}")
    # 花在哪、占了哪一格,由这把锁自己说 —— 2026-09-01 那一趟真机,业主的诊断里
    # 只有一个 +9094ms,是我拿它减前一条、再除以锁位数,才知道 6 次握手全部耗满。
    # 下一趟不该再靠人做除法。
    DIAG.mark("lock.acquired",
              f"port={lock.port} 扫了{lock.scanned}格 用时{lock.scan_ms:.0f}ms")

    try:
        home = user_home()
        sup, web, restart_gateway = start_backend(home, lock_port=lock.port)
        DIAG.mark("backend.ready")
        restart_holder.append(restart_gateway)
        shell = Shell(sup, web, lock)
        shell_holder.append(shell)

        import webview

        shell.window = webview.create_window(
            # 地址带 SHELL_MARK = 外壳自报身份,前端第一帧就知道要画窗口栏
            # (window_url 是唯一来源,日志里印的也是它)。
            APP, window_url(web),
            width=1280, height=860, min_size=(960, 640),
            # 🔴 2026-08-16 业主:系统标题栏那个 "OpenDesign" 和我们前端自己的标题
            #    撞了 ⇒ 不要那个框,窗口按钮我们自己画在右上角(WindowChrome.tsx)。
            #    代价说清楚:frameless 之后 Windows 把"拖边缘改大小"也一起收走了,
            #    由 WindowApi 用原生窗口消息接回来。
            #    `easy_drag=False` 是关键:开着的话**整个页面**按哪儿都能拖窗口 ——
            #    选不了字、拖不动滚动条。拖动只认我们那条栏。
            frameless=True, easy_drag=False, js_api=shell.window_api,
        )
        # 关窗口 = 收进托盘。pywebview 的 closing 回调返回 False 表示"别关"。
        shell.window.events.closing += lambda: shell.state.on_close_requested()
        # 窗口一出来就把 frameless 拿走的那几个样式位贴回去(见
        # WindowApi._apply_native_styles)。挂 `shown` 而不是在这儿直接叫:
        # 这一刻窗口还没建出来,没有 Handle 可用。
        shell.window.events.shown += shell.window_api.ensure_native_styles
        # 🔴 2026-08-30(判据 s6):「窗口打开」这行原来写在 `webview.start()` **之前** ——
        #    它报的是"我要开了",不是"开了"。白屏那晚这行照样出现在日志里,
        #    于是它把"窗口真开了"这件根本没发生的事说成了既成事实。搬到 shown 里。
        shell.window.events.shown += lambda: DIAG.mark("window.shown")
        # 首帧看门:到点还没等到前端报"我画出来了",就写一次诊断快照。
        # **不弹框**(判据 s9)—— 阈值不承重,定错了最多多写一段日志。
        shell.window.events.shown += lambda: shell.start_first_frame_watch()

        shell.run_tray()
        shell.run_watchdog()
        DIAG.mark("window.create_returned", window_url(web))
        log(f"准备进入图形循环:{window_url(web)}")
        DIAG.mark("webview.loop_entered")
        webview.start()          # 阻塞,直到窗口 destroy
        shell.state.on_quit()    # 走正常关闭时也要把后台收干净
        return 0
    except ImportError as e:
        # 少了 pywebview / pythonnet / PIL —— 包被装坏了
        die(f"{APP} 少了运行所需的组件:{e}\n\n请重新运行安装程序。")
    except Exception as e:
        # .NET 挂不上、WebView2 缺失都会落到这里。**不许只抛 CLR 栈**:
        # 业主看到一堆英文栈只会来问我。原始栈进日志,弹窗给人话。
        log(traceback.format_exc())
        die(f"{APP} 启动时出错:{e}\n\n"
            f"如果是第一次在这台电脑上打开,多半是缺少微软的 WebView2 运行时,\n"
            f"请重新运行安装程序(它会自动补装)。\n\n详细日志:{_log_path()}")
    finally:
        lock.release()
    return 1


# 🔴 模块体走完 = 所有 import 都办完了。这一条把"进程起来 → 拿到锁"那个
#    9.4 秒的黑块切开(判据 s17):云机器上它是全程最大的一块,而在 Linux 上
#    整条 import 链只要 130ms —— 差 70 倍,差的是 I/O 不是算力。
#    切开之后才知道到底是 import 慢、还是锁那一步慢。
DIAG.mark("shell.imports_done")

if __name__ == "__main__":
    sys.exit(main())

exec
/bin/bash -lc "sed -n '1,390p' bin/ds_shell.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
#!/usr/bin/env python3
"""OpenDesign 桌面外壳 —— Windows 胶水层(S1b)。

双击 OpenDesign.exe 走到的就是这里。它负责的事:
  拿单实例锁 → 挑端口 → 改写配置 → 拉起网关和 ds-web → 开一个桌面窗口装 ds-web
  → 关窗口收进托盘 → 托盘"退出"才真的收摊。

**这一层没有任何自动考卷验得了**(pywebview / pystray / WebView2 / .NET 全是 Windows 独有,
而且要有桌面会话)。所以它的所有**可判定逻辑**都被推到了 `ds_shell_core.py` 里,
那一层有 `tests/test_ds_shell_core.py` 逐条锁着。留在这个文件里的只剩"接线"。

接线接错了照样是坏的,所以这个文件的规矩是:
  ① 每一步失败都要变成**业主看得懂的一句话**,而且是**弹窗**——
     业主是双击图标进来的,没有终端可看,往 stderr 打等于没打。
  ② 弹窗用 ctypes 直接叫 MessageBoxW,**不依赖 pywebview/.NET**:
     偏偏最需要报错的时候(WebView2 缺失、.NET 挂不上)那些东西正好是坏的。
  ③ 每一处"我在 Linux 上验不了"的假设,都在注释里点名,并进 Windows 真机考卷。
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ds_common  # noqa: E402
import ds_credential  # noqa: E402  变量名从配置的 apiKey 引用里读,不许写死
import ds_diag  # noqa: E402  启动可观测性:run_id / 分阶段耗时 / 诊断包
import ds_shell_core as core  # noqa: E402

APP = "OpenDesign"
# 外壳打开页面时在地址里报的身份。前端靠它决定要不要画那条窗口栏
# (无边框之后三个按钮 + 拖动带 + 八个把手全是我们自己画的)。
# **唯一来源是 web/src/shellWindow.ts 的同名常量**,两边一字不差
# (tests/test_shell_window_contract.py x10 对表)。
# 为什么不用"pywebview 有没有把 api 注进页面"来判:它在 on_navigation_completed
# 之后才注入(页面脚本早跑完了)⇒ 前端首帧问它永远答 false,窗口栏整块不画。
# 0.89/0.90 两版就是这么发出去的(业主:「拖不动 / 右上角还是没有」)。
SHELL_MARK = "shell=1"


def window_url(port: int) -> str:
    """外壳打开的那个地址。**唯一来源** —— 开窗口和写日志都叫它。

    分开写两遍的代价已经付过一次:日志里印的地址少了标记,而那份
    `外壳.log` 正是业主报"没按钮"时我唯一的现场。
    (判据 x10 直接调它,不是去源码里 grep 字面量。)
    """
    return f"http://127.0.0.1:{port}/?{SHELL_MARK}"


# 锁位挑在一段不常用的高位端口上。它只是锁 + 唤醒通道,不承载数据。
LOCK_PORT = 18788
# 首选端口沿用现有部署(docs/install-windows.md / start.ps1),被占了会自动往后挪。
PREFERRED = {"gateway": 18790, "ws": 8765, "web": 8766}


# ---------------------------------------------------------------- 报错与日志
def _app_dir() -> Path:
    """这个软件在业主机器上自己的目录。日志和实验开关都住这儿。"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP


def _log_path() -> Path:
    d = _app_dir() / "Logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "外壳.log"


# ── 窗口动画开关(0.96.0 起**默认开**)──────────────────────────────
# 0.94/0.95 这里默认是**关**的,业主一句话点破了那个决定的自相矛盾:
#   「你为什么不直接给我做好动画的,要默认关闭动画」
# —— 我给 0.95 装了"不对就自动退回去"的保险,却又不敢依赖它。
#   要么保险可信、就该默认开;要么不可信、就不该把它当卖点。
#   我选了对自己最安全、对业主最麻烦的那一半:风险我躲了,力气他出。
#
# 而且 0.95 之后**「打开就白」在结构上已经没了**:开窗口时一个边框动作都不做,
# 方案 B 要等业主点缩小才装 ⇒ 就算真把画面搞坏,**重开软件就是好的**,
# 不像 0.93 那样一起来就是砖。既然最坏情况已经从"砖"降到"重开一下",
# 就没有理由再让业主自己去建文件。
DISABLE_FLAG = "关掉窗口动画.on"


def frame_animation_on() -> bool:
    """要不要接系统窗口框架(缩小/放大的动画靠它)。**默认开。**

    不想要就在 `%LOCALAPPDATA%\\OpenDesign\\` 里新建一个空文件,
    名字叫 `关掉窗口动画.on`,重开软件即可。删掉它就回到默认。

    🔴 **读不到环境时倒向"关"**(判据 f4 守着 except 必须 `return False`)。
    方向仍然是有讲究的,只是理由换了:这个逃生门是给"已经发现它坏了"的人用的。
    读不出文件系统时,把"可能已经关过"当成"关过"——
    让一个本来没事的人少一段动画(小),好过让一个已经被坑过的人再被坑一次(大)。
    """
    try:
        return not (_app_dir() / DISABLE_FLAG).is_file()
    except Exception:
        return False


def log(msg: str) -> None:
    """带时间戳写一行。

    🔴 时间戳是 08-14 那次真机红补上的:那份日志没有时间,于是「一起来就崩」和
    「等满 300s 超时」在事后长得一模一样,只能回头问业主等了多久。
    证据要自带能对账的东西 —— 一个 strftime 换的是一趟真机。

    🔴 2026-08-30(判据 s1):**补上日期** —— 上面那笔账只还了一半。
    业主 08-25 晚白屏、08-30 才回话,中间那几行属于哪一天,只有时分秒的日志答不了。
    续行缩进由 stamp 长度算出来,不写死数字(写死的那种迟早和格式对不上)。
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    pad = " " * (len(stamp) + 1)
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            for i, line in enumerate(msg.rstrip().splitlines() or [""]):
                # 多行文案(弹窗那种)只给第一行盖戳,其余缩进对齐 —— 免得每行都盖,
                # 反而看不出哪里是一条记录的开头。
                f.write(f"{stamp} {line}\n" if i == 0 else f"{pad}{line}\n")
    except OSError:
        pass


def web_ready_probe(port: int) -> bool:
    """工作台"就绪"的真正含义:`/api/health` 应答得了。

    🔴 **fail-closed**:任何异常都当成"还没就绪"。反过来写(拿不到就当好了)
    正是这个项目栽过的 fail-open 形状 —— 那样探针活着也等于没有。

    🔴 **绝不能走系统代理**(判据 s13;2026-08-30 四审孤腿 BLOCK 抓到、我实测坐实)。
    `urllib.request.urlopen` 对 127.0.0.1 **不绕过**代理:`proxy_bypass('127.0.0.1')`
    就是 False,而 Windows 上 `ProxyOverride` 里的 `<local>` 只匹配无点主机名。
    于是凡是配了系统代理的机器(公司代理、**以及 Clash 那类会设系统代理的 VPN 客户端**)
    上,这个探针对**健康**的工作台一律返回 False ⇒ `_wait_ready` 死等到 60s 超时
    ⇒ `StartupFailed` ⇒ **软件根本打不开**。
    观测层绝不能成为新的故障源 —— 这条红线是本单自己写的,第一版亲手违反了它。
    ⇒ 显式装一个空 `ProxyHandler`,任何环境里都直连。
    """
    import urllib.request
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


# 这一次启动的证据链。**在模块导入时就建**,不是在 main() 里 —— 那样 t0 才贴着
# 进程真正的起点(import 本身也可能慢,那段时间也该被量到)。
# 白屏和"打开好慢"都靠它留下的东西查(track opendesign-startup-observability)。
DIAG = ds_diag.StartupLog(emit=log)


def alert(msg: str, title: str = APP) -> None:
    """弹一个系统对话框。业主没有终端,这是唯一能被看见的出口。"""
    log(f"[提示] {msg}")
    try:
        ctypes.windll.user32.MessageBoxW(None, msg, title, 0x10)  # MB_ICONERROR
    except Exception:
        print(msg, file=sys.stderr)


def die(msg: str) -> None:
    alert(msg)
    sys.exit(1)


# ---------------------------------------------------------------- 路径
def install_root() -> Path:
    """包根:里面有 python\\ 和 ds\\。本文件在 <root>\\ds\\bin\\ 下。"""
    return HERE.parent.parent


def user_home() -> Path:
    """业主数据目录 —— **安装目录之外**(design:卸载/回滚不许碰数据)。

    这里同时是子进程眼里的 HOME/USERPROFILE,所以 nanobot 读的是
    <user_home>\\.nanobot\\config.json,而不是业主机器上原来那份。
    """
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "UserData"
    d.mkdir(parents=True, exist_ok=True)
    return d


def python_exe() -> Path:
    return install_root() / "python" / "python.exe"


def key_file(home: Path) -> Path:
    """机主自备的 LLM key 放在哪儿(deploy-security D1:部署者不发 key)。

    路径与现有部署一致(ds-nanobot.ps1:20),只是 USERPROFILE 换成了应用自己的数据目录。
    **报错文案要把这个路径原样念给业主听**,所以它得是个能被引用的单一来源。
    """
    return home / ".openDesign" / "key.txt"


def read_key(home: Path) -> str | None:
    try:
        return key_file(home).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


# ---------------------------------------------------------------- 托盘图标
def tray_image():
    """托盘图标。装机时安装器会放一份 图标.png 进来;没有就画一个,不为图标崩掉。"""
    from PIL import Image, ImageDraw

    # 安装器铺的是 ds\assets\图标.png(仓库里的 assets/图标.png,由 installer/make-icon.py
    # 与程序图标 opendesign.ico **同一份形状**生成)。路径挑在 assets\ 下是因为包里的 ds\
    # 是仓库根的镜像 —— 组包时那道"ds/ 里每个文件都必须是仓库里的"闸按这个对应关系查。
    png = install_root() / "ds" / "assets" / "图标.png"
    if png.exists():
        try:
            return Image.open(png)
        except Exception:
            pass
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(38, 70, 83, 255))
    d.rounded_rectangle((18, 18, 46, 46), radius=6, fill=(233, 196, 106, 255))
    return img


# ---------------------------------------------------------------- 主流程
def start_backend(home: Path, lock_port: int | None = None):
    """挑端口 → 改配置 → 按计划拉起后台。返回 (supervisor, web_port, restart_gateway)。

    **缺 key 不再是死路**(track opendesign-key-onboarding):界面无条件起,
    网关等着 —— 业主要在界面里填 key,而那个界面正是 ds-web 发的。
    填完之后 ds-web 通过锁通道回来叫 `restart_gateway`。
    这一层只剩接线,"起哪几条"由 core.startup_plan 判(判据 d1/d2 咬着)。
    """
    cfg = home / ".nanobot" / "config.json"
    if not cfg.exists():
        die(f"还没装好:找不到配置文件\n{cfg}\n\n请重新运行安装程序。")

    try:
        gw, ws, web = core.pick_ports(
            [PREFERRED["gateway"], PREFERRED["ws"], PREFERRED["web"]], span=20)
    except core.PortBusy as e:
        die(f"找不到可用的端口:{e}\n\n多半是有别的程序占着这几段端口,重启电脑再试一次。")

    try:
        core.patch_config(cfg, gateway_port=gw, ws_port=ws, python_exe=str(python_exe()),
                          data_root=core.data_root_for(str(home)))
    except core.ConfigUnusable as e:
        die(f"配置没法用:{e}\n\n请重新运行安装程序。")
    except OSError as e:
        die(f"写配置失败:{e}")

    def build_env():
        """每次都**现读** key 和配置:重启网关那一下走的就是这里,
        读到的必须是业主刚填进去的那份,不是启动时缓存的。"""
        key = read_key(home)
        key_var = None
        if key:
            try:
                with cfg.open("r", encoding="utf-8") as f:
                    key_var = ds_credential.env_var_name(json.load(f))
            except (OSError, ValueError, ds_credential.CredentialError) as e:
                die(f"配置里没写清楚 key 该放进哪个变量({e})。\n\n请重新运行安装程序。")
        # 🔴 **key 只进网关那条腿**(core.service_envs)。上一版把同一份 env 给了
        #    两条腿,ds-web 也拿到 key ⇒ status() 把外壳自注入误判成"外部遮蔽" ⇒
        #    装好的应用重启后,设置里改 key 的卡片永久只读,还让业主去清一个他
        #    从没设过的变量。(2026-08-16 四审 BLOCK,判据 J 组钉住。)
        return key, core.service_envs(
            dict(os.environ), ds_root=str(install_root() / "ds"), user_home=str(home),
            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)

    key, envs = build_env()

    # 🔴 08-14 业主真机红出来的那一条,别再写回去:
    # 上一版这里只 log 一句「没找到 key.txt,聊天会连不上大模型」就继续往下走,理由是
    # 「业主可能只是想看看待办,ds-web 是只读的、不需要 key」。**那句话是假的** ——
    # 配置里 "apiKey": "${DS_LLM_KEY}",nanobot 解析到没设的 ${VAR} 就整个拒绝启动,
    # 于是业主等来的是网关的一句英文 `Environment variable … is not set`。
    # (tests/test_ds_shell_core.py H5 真起了一次网关把这件事钉死,别再靠注释。)
    # 所以现在:起任何后台之前先扫一遍配置,缺什么当场说清楚、说该往哪儿放。
    plan = core.startup_plan(has_key=bool(key))

    # 缺 key **不再是错误**,是"该去填了" ⇒ 只有真要起网关时才拦缺变量。
    # (没有这个 if,业主永远走不到引导页:网关会死在缺变量上,而这一层直接 die。)
    if "网关" in plan["start"]:
        try:
            with cfg.open("r", encoding="utf-8") as f:
                # 拿**网关那条腿**的 env 去比,不是别的:key 只进它(service_envs),
                # 拿 ds-web 那份去比会说"DS_LLM_KEY 没设",而它本来就不该有。
                # (08-16 业主真机:这里写的是已经不存在的 `env` —— 有 key 的机器
                #  每次开机 NameError。判据 tests/test_shipped_names.py 咬着。)
                missing = core.missing_env_refs(json.load(f), envs["网关"])
        except (OSError, ValueError) as e:
            die(f"配置读不出来:{e}\n\n请重新运行安装程序。")
        # 说什么话在 core 里(判据 H6~H9 咬着);这一层只剩"有就弹"。
        trouble = core.missing_env_message(missing, app=APP, key_path=str(key_file(home)))
        if trouble:
            die(trouble)

    # 🔴 迁移必须在**起任何服务之前**(判据 h3)。网关是第一个起来的,它带着三个 MCP
    # 工具服务;老版本装过的机器上,档案还躺在安装目录里,而新的数据根是空的 ——
    # 那一刻业主问"我有哪些项目",助手会回"一个都没有",甚至在新根里建一个重名的。
    # ds_web 自己也会迁移一次(幂等),但它是**第二个**起来的,来不及。
    try:
        migration = core.prepare_data_root(user_home=str(home),
                                           ds_root=str(install_root() / "ds"))
    except ds_common.DataRootError as exc:
        die(f"数据目录不可用({exc})。\n\n请重新运行安装程序。")
    if migration["failed"]:
        die(f"你的资料从旧位置搬过来时出错了,先没有继续启动:\n{migration['failed']}\n\n"
            f"把这段发给我看看 —— 东西还在原处,没有丢。")

    logs = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"

    def gateway_service(e):
        return core.Service(name="网关", argv=[str(python_exe()), "-m", "nanobot", "gateway"],
                            env=e, ready_port=ws, log_path=logs / "网关.log",
                            # 冷启动要连 3 个 MCP 子进程,S0 真机上见过接近 4 分钟
                            ready_timeout=300)

    def web_service(e):
        return core.Service(name="工作台", argv=[str(python_exe()),
                                                 str(install_root() / "ds" / "bin" / "ds_web.py")],
                            env=e, ready_port=web, log_path=logs / "工作台.log",
                            # 🔴 2026-08-30(判据 s11):就绪 = **它真的应答了**,
                            #    不是"端口有人监听"。`ready_probe` 这个机制一直都在,
                            #    只是工作台从没接上 ⇒ 时间线里的"后端就绪"是半真话,
                            #    而整条启动耗时都建在这句话上面。
                            ready_probe=web_ready_probe,
                            ready_timeout=60)

    # plan 里那两个名字是 core 的说法("ds-web"/"网关");Service 名是业主看得见的
    # 中文名("工作台"),watchdog 和报错都用它。别把两套名字混着用。
    services = (([gateway_service(envs["网关"])] if "网关" in plan["start"] else [])
                + [web_service(envs["ds-web"])])

    sup = core.Supervisor()
    try:
        sup.start(services)
    except core.StartupFailed as e:
        sup.shutdown()
        die(f"{APP} 没能启动。\n\n{e}\n\n详细日志:{logs}")

    def restart_gateway():
        """业主在界面里填完 key ⇒ ds-web 通过锁通道叫到这里。

        **现读**一遍 key 和配置(build_env 就是干这个的),把网关换成新进程;
        界面那条腿一动不动 —— 他正看着的页面就是它发的。
        """
        k, fresh = build_env()      # fresh 是两条腿各自的 env,重启只换网关那条
        if not k:
            log("[重启网关] 收到请求,但 key.txt 还是空的 —— 不动")
            return
        try:
            sup.restart([gateway_service(fresh["网关"])])
            log("[重启网关] 完成")
        except Exception as exc:      # 回调跑在锁的线程里:炸出去会把那条线程带走
            log(f"[重启网关] 失败:{exc}")
            alert(f"key 已经存好了,但后台没能自己重启:\n{exc}\n\n"
                  f"请退出 {APP} 再打开一次。")

    return sup, web, restart_gateway


# ── winuser.h 的几个常量 ──────────────────────────────────────────────
# 🔴 值抄错一位**不会报错**,只会安静地设成别的位 ⇒ 判据 s1 逐个对表 winuser.h。
#    GWL_STYLE 是负数,别写成 0x10。
GWL_STYLE = -16
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

# ── 方案 B(track opendesign-native-frame)新增 ─────────────────────
# 0.92.0 只贴了上面那三个不参与绘制的位,真机证明**动画不归它们管** ——
# 归下面这两个。代价是它们会真的改变非客户区尺寸,所以必须同时接管
# WM_NCCALCSIZE 把那块地方吃掉。两件事同生共死(判据 n3)。
GWLP_WNDPROC = -4
WM_NCCALCSIZE = 0x0083

exec
/bin/bash -lc "sed -n '1,190p' bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
#!/usr/bin/env python3
"""OpenDesign 桌面外壳的平台无关内核。"""

from __future__ import annotations

import concurrent.futures
import functools
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import ds_common
from typing import Any


# ── 子进程创建的平台参数:唯一来源 ──────────────────────────────────────
#
# 业主 2026-08-17 装完 0.89.0:「为什么打开这个软件还会跳出命令行呢」——
# 两个黑窗口(网关一个、工作台一个),而且**关掉一个就等于杀掉一条腿**。
# 外壳自己是没有控制台的 `pythonw.exe`,却用 `python.exe`(控制台程序)起腿:
# **没有控制台的进程去起控制台程序,Windows 会为它新开一个控制台窗口。**
#
# 🔴 数值写死,不用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)`:
#    Linux 的 subprocess **没有**这两个常量,getattr 会退化成 0,
#    而 0 和"没设"一模一样 ⇒ 本机判据永远问不出东西(假绿)。
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
WINDOWS_SPAWN_FLAGS = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW


def spawn_kwargs(os_name: str = "") -> dict[str, Any]:
    """起子进程时要额外传给 `subprocess` 的平台参数 —— **唯一来源**。

    调用点不许自己拼:漏一位的代价是真机上冒一个业主关得掉的黑窗口,
    而本机一条判据都不会红(那一位只在 Windows 上有意义)。
    `tests/test_no_console_window.py` 机械地查"每个创建点是不是走了这儿"。
    """
    name = os_name or os.name
    if name == "posix":
        # 自成会话 ⇒ 收尸时按进程组收,孙进程跑不掉(c1/c2/c13 咬的就是它)
        return {"start_new_session": True}
    if name == "nt":
        return {"creationflags": WINDOWS_SPAWN_FLAGS}
    return {}


class PortBusy(RuntimeError):
    """端口段全被占。"""


class StartupFailed(RuntimeError):
    """子进程启动失败。"""


class ConfigUnusable(RuntimeError):
    """配置本身无法安全使用。"""


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否可以被当前进程绑定。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    """端口上是否有 TCP 服务正在接受连接。"""
    try:
        with socket.create_connection((host, int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def pick_port(preferred: int, *, span: int = 20) -> int:
    start = int(preferred)
    for port in range(start, start + int(span) + 1):
        if port_free(port):
            return port
    raise PortBusy(f"端口段 {start}..{start + int(span)} 全部被占")


def pick_ports(preferred: list[int], *, span: int = 20) -> list[int]:
    chosen: list[int] = []
    used: set[int] = set()
    for wanted in preferred:
        start = int(wanted)
        for port in range(start, start + int(span) + 1):
            if port not in used and port_free(port):
                chosen.append(port)
                used.add(port)
                break
        else:
            raise PortBusy(f"端口段 {start}..{start + int(span)} 没有可用端口")
    return chosen


def lock_sockopts(platform: str) -> list[tuple[str, int]]:
    """这个平台上,单实例锁的 socket 该设哪些选项。纯数据 —— 好让考卷问得出来。

    ⚠️ 兜底值必须是 Windows 上的真值 `-5`(= ~SO_REUSEADDR),**不能随手写 4**:
    4 在 Linux 上正好是 SO_REUSEADDR —— 恰恰是这把锁一辈子都不许设的那一个
    (Windows 上它允许后来者抢走监听端口 ⇒ 锁会被偷)。兜底写错方向 = 埋雷。
    """
    if platform.startswith("win"):
        return [("SO_EXCLUSIVEADDRUSE", int(getattr(socket, "SO_EXCLUSIVEADDRUSE", -5)))]
    return []


def lock_timeouts() -> dict[str, float]:
    """握手的两个期限。纯数据 —— 和 `lock_sockopts` 一个用意:好让考卷问得出来。

    **两个都是 1.5s,而且都不许再往下调。** 考卷 l2 钉着这条下限。

    🔴 这里曾经写着相反的话("connect 可以很短,因为对面活着时握手由内核在 backlog
    里完成"),并据此把 connect 缩到 0.25s。**那半句是错的,而且错法是可量的**
    (2026-09-01,三条评审腿里两条 BLOCK,加我自己共四次独立复现):

        本机 200 次回环 connect(对面**正常 accept**),见
        tracks/opendesign-slow-lock-scan/probes/connect_latency.py:
            中位 0.056ms   p99 1022.975ms   max 1023.173ms

    内核确实在 backlog 里完成握手 —— 但 backlog 一瞬间满掉就会丢 SYN,
    TCP 要等约 1 秒才重传。所以"对面活着 ⇒ connect 一定快"只在中位数上成立,
    **尾巴上不成立**。1.5s 罩得住整条实测尾巴,0.25s 罩不住 ⇒ 每次触发条件成立时
    约 1~3% 的概率把**活着的**第一份看成不存在 ⇒ 业主开出两份、两个后台对着
    同一个 data_root(评审腿查过:`pick_ports(span=20)` 会让第二份换端口照跑,
    没有第二层保护)。

    **那 9 秒是靠并发省下来的,不是靠缩这个期限:**
        串行 1.5s            9001.6ms   ← 探针模型,对上业主真机 9047ms
        并发 + connect=1.5   1502.5ms   快 6.0 倍,省 7.5s
        并发 + connect=0.25   251.2ms   只多省 1.25s
    (三个数各有收据:前两个在 probes-after-connect-1500,第三个在
     blackhole-with-connect-025-the-1250ms-question —— 2026-09-02 补,
     此前 "252ms" 是手抄的、仓库里没有出处,评审腿第三轮 LOW 第 4 条点名。)
    为那 1.25s 把数据面赌进去不划算,所以这一单**只要并发那一份收益**。

    由来:2026-09-01 业主真机第一份启动诊断。此前两个期限都是 1.5s,而且**串行**扫
    6 个锁位;他那台机器上每个锁位都耗满 ⇒ `manifest.done` 到 `lock.acquired`
    干等 **9047ms**,占整趟启动 11031ms 的 82%。他的原话是"直接没反应了十几秒"。
    (同样的扫描在本机 Linux 上是**毫秒级**:20 次扫 6 个空锁位,中位 0.9ms、max 4.0ms,
     收据 evidence/20260902T010857Z-01-empty-range-baseline-and-blackhole.txt;
     单遍会跳,另一遍是 1.1 / 4.6 —— 别引用具体值,量级才是结论。
     空端口瞬间被拒;Windows 上为什么耗满,
    见 tracks/opendesign-slow-lock-scan/proposal.md 的"还不知道的"。)

    ⚠️ 想把 connect 调回去,先在**那台 Windows** 上量一遍 connect_latency ——
    上面这组数来自 Linux,而那台机器的回环行为已经被证明和 Linux 不一样。
    """
    return {"connect": 1.5, "read": 1.5}


# 锁通道的线上协议。**公开常量,因为 ds_web 也要发这个帧** ——
# 两处各抄一份的代价我付过(见 ports_for 那段注释),这里只留一个真相源。
LOCK_HELLO = b"OpenDesign.ds_shell_core.lock.v1\n"
LOCK_SHOW = b"SHOW\n"
LOCK_RESTART = b"RESTART-BACKEND\n"     # 业主填完 key ⇒ 网关得重来一次才认新 env
LOCK_OK = b"OK\n"
# 🔴 应答**点名动词**:老外壳认不出 RESTART 也会回裸 OK,ds-web 就会把
#    "什么都没重启"报成 requested,界面对业主说「已自动应用新配置」——
#    正面违反「不许撒谎的重启」。带上动词,新 ds-web 碰上老外壳时才能
#    **正确降级**成"请手动重启"。(老 ds-web 碰上新外壳无碍:它比对的是前缀。)
LOCK_OK_RESTART = b"OK RESTART-BACKEND\n"


def recv_line(sock: socket.socket, deadline: float, limit: int = 4096) -> bytes:
    """读到第一个换行为止(不含换行);超时或对端关闭就返回已经读到的。

    模块级是因为 ds_web 那侧发完重启帧也要读这一行应答 —— 收发行的规矩只留一份。
    """
    buf = b""
    while b"\n" not in buf and len(buf) < limit:
        remain = deadline - time.monotonic()
        if remain <= 0:
            break

exec
/bin/bash -lc "sed -n '190,520p' bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
            break
        sock.settimeout(remain)
        try:
            chunk = sock.recv(limit)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0]


class InstanceLock:
    _HELLO = LOCK_HELLO
    _SHOW = LOCK_SHOW
    _RESTART = LOCK_RESTART
    _OK = LOCK_OK
    _OK_RESTART = LOCK_OK_RESTART

    port: int | None
    _sock: socket.socket | None

    def __init__(self, base_port: int, span: int = 5, on_show=None, on_restart=None):
        self.base_port = int(base_port)
        self.span = int(span)
        self.on_show = on_show
        self.on_restart = on_restart
        self.port = None
        self._sock = None
        self._thread: threading.Thread | None = None
        self._released = threading.Event()
        # 这把锁自己花了多少 —— 下一趟真机不该再靠人拿两个时间戳相减、再除以锁位数。
        # `scanned` 是**握手总次数**(两轮就是两轮之和),好让 `scan_ms / scanned`
        # 真的等于每格代价;`scan_ms` 是整个 `acquire()` 的墙钟。
        self.scan_ms: float = 0.0
        self.scanned: int = 0

    def acquire(self) -> bool:
        """True = 我是唯一实例(并已开始监听);False = 已有实例(SHOW 已送到)。"""
        t0 = time.monotonic()
        try:
            return self._acquire()
        finally:
            self.scan_ms = (time.monotonic() - t0) * 1000.0

    def _acquire(self) -> bool:
        # 第一份可能落在备用锁位上,所以先扫完整段握手,再尝试占新锁。
        hit = self._scan(self._ports())
        if hit is not None:
            self.port = hit
            return False

        for port in self._ports():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                for name, value in lock_sockopts(sys.platform):
                    opt = getattr(socket, name, None)
                    if opt is not None:
                        sock.setsockopt(socket.SOL_SOCKET, opt, value)
                sock.bind(("127.0.0.1", port))
                sock.listen(8)
            except OSError:
                sock.close()
                continue
            self._sock = sock
            self.port = port
            self._thread = threading.Thread(target=self._serve, name="ds-shell-lock", daemon=True)
            self._thread.start()

            # 🔴 并发裁决(业主快速双击两下走的就是这里)。
            # 上面那轮扫描解决不了同时启动:两份都会扫到"没人",然后一个绑 base、
            # 一个绑 base+1,**两份都以为自己是唯一的**。
            # 绑完再回头扫一次比自己**更靠前**的锁位:能应答的说明有人比我先站住了,
            # 我让位。因为"最靠前的那一格"只可能被一个人占住,所以恰好活下来一个,
            # 也不会两边互相让(让位只朝一个方向)。
            if self._someone_ahead_of(port):
                self.release()
                self.port = port
                return False
            return True

        raise PortBusy(f"单实例锁端口段 {self.base_port}..{self.base_port + self.span} 全部被占")

    def _someone_ahead_of(self, mine: int) -> bool:
        """我前面还有人吗 —— 并发启动时的**让位仲裁**。

        🔴 **它不是"快扫漏判"的兜底,别再这么用了**(2026-09-01 评审推翻的第二句话)。
        我曾在这里写"它是快扫漏判时的唯一兜底",三条评审腿里两条独立指出这是错的,
        而且拓扑摆在那儿:这一问只看 `p < mine`,所以**先起的那份落在比我更高的锁位时,
        这里一个口都不会问**。漏判最脆的那条路正好长这样 ——
        陌生程序占着 base ⇒ 第一份落到 base+1 ⇒ 陌生程序退出 ⇒
        第二份漏判、绑上 base ⇒ 走到这里前面没有锁位 ⇒ 放行 ⇒ **两份并存**。

        改成"整段都问"会引入**双向让位**:我问你、你问我,两边都让,业主双击后
        一个窗口都不开。(让位方向必须唯一,这正是"只问更靠前的"存在的理由。)

        🔴 这个数以前是"3 轮里有 1 轮",而**仓库里复现不出来** —— 2026-09-02 第二轮
        评审的两条腿各自独立指出:它是驳回这条修法的全部依据,却只活在这句注释里。
        补了探针 `tracks/opendesign-slow-lock-scan/probes/yield_race.py`,量的是一笔
        **取舍**(盲区堵不堵得住 × 同时启动活下来几份),三组实现:

            A 只问 p < mine(树上这个) 盲区**放行**   任何错开档上 0 存活都是 0
            B 绑完问整段(评审建议的)  盲区堵住      0 存活只出现在 ≲2ms 的对齐窗口内
            C 只让 base 上那份回头问   盲区堵住      同上(B/C 谁更窄写不得,见下)

        🔴 **我先前在这里写的"结构性做不到两全"是错的,是我的量具造出来的**
        (2026-09-02 第三轮:降级成瞎审的 subglm 与我自审 D2 各自独立指出
        "只量过 Barrier 对齐这一种情态")。补量错开启动后:两份的 acquire 只要错开
        **2ms 以上**,B 和 C 的 0 存活在五遍(30/40/40/20/20 轮)里**一次都没再出现**
        (五遍指"≥2ms 的档"都跑过;**2.0ms 那一格本身只在四遍里**,第一遍走的是
         0/10/50/200/500);
        1ms 那一档两组都掉到噪声底:带 1ms 档的四遍分别是
        B=1/40 C=0/40 / B=1/40 C=0/40 / B=0/20 C=1/20 / B=1/20 C=0/20
        —— 每一格不是 0 次就是 1 次,**这个样本量(20~40 轮)根本判不出
        两组有没有差别** ⇒ **不许写 B/C 谁的窗口更窄**。
        (2026-09-02 第五轮 submimo 打在这句话上:原先写的"方向不稳/翻面"
         是把噪声读成了方向 —— "量不到方向"和"方向在变"是两件事。)
        (2026-09-02 第四轮 subkimi 指出:我 09:50 在这里写下"C 已经是 0",
         70 秒后自己跑出的那份收据就把方向写反了,而它和下面那条 ⚠️
         "别引用其中任何一个比例" 在同一段注释里 —— 违反的是我六行后自己立的规矩。)
        收据:`evidence/*yield-race-stagger-sweep-30*`、`*stagger-fine-40*`(含 repeat)、
        `*acquire-duration-explains-the-window*`。
        ⇒ 真实结论是:**双向让位的危险窗口只有 1~2ms 量级,不是结构性的**。
        这个宽度**有机制解释、不是巧合**:空段上单份 acquire 实测中位 1.021ms、
        p90 1.211ms、max 2.722ms(收据 `*acquire-duration-explains-the-window*`),
        而双向让位要求两份都在对方扫描之前绑好 ⇒ 窗口量级 = 这个耗时的量级。
        ⚠️ **但这条对应只在 Linux、扫描很快时量到过**:业主那台机器上快扫会大面积超时
        (本刀量到的 9047ms → 1502ms),那里 acquire 慢得多。窗口会不会跟着变宽,
        取决于"绑完到真正发出 connect"之间有多久 —— **我没量过,这是推断不是测量**,
        已写进下一单的第 0 步。
        所以"这条修法行不通"不成立;成立的只有一句更小的话 ——
        它把一个**极窄的 0 存活窗口**换来盲区被堵住,是一笔**取舍**,不是一个错误。

        本刀仍然不改让位方向,理由只有两条(都不是"它行不通"):
          1. 那条盲区是**既有**的,不是本刀引入的回归(本刀只动扫描代价与期限);
          2. 换方向要重开判据与评审轮次,而这一刀的存在理由是"双击后别干等十几秒"。
        评估 C 是不是够、还是真要加先来后到字段,是 track
        `opendesign-lock-seniority-field` 的第一件事(那一单的题面已按这份收据改过)。

        ⚠️ **别引用其中任何一个比例**:错开启动那五遍(30/40/40/20/20 轮)在 0ms
        那一档给出过 3/20、4/20、5/20、5/20、6/30、10/30、12/40、13/40、14/40、21/40,
        方差很大 —— 跨度 3/20(0.15)到 21/40(0.525)。
        (另有一个 18/30 来自**错开启动补量之前**那一版,不在这五遍里;我 2026-09-02
         上午正是拿它写成"实测 60%、比原话严重一倍",下一遍就 30%。)
        **每一遍都成立的只有定性那几条**:A 任何档上都没出现过 0 存活;
        B/C 只在对齐窗口内出现;存活 2 份在所有组、所有档、所有遍里都是 0。
        探针还是同进程两线程 + Linux 回环,业主那台 Windows 上两个进程的对齐窗口
        宽度不一样,所以这些数更不能当成他那台机器上的概率。

        **所以现在防线在前面:快扫的 connect 期限必须罩得住实测尾巴(l2 钉着下限)**,
        让"漏判"这个前提本身够不着。`patient` 保留:它在 connect 被调短时自动重新
        生效(l5 靠注入 connect=0 钉着它),今天两个期限一样宽,它是空操作。

        代价只落在**罕见**分支上:绑到首选锁位时这里一个口都不用问(前面没有锁位),
        业主每次启动付的仍然只有一轮快扫。
        """
        # 这是**第二轮**整段扫描 —— 串行时代业主为一次启动付的是两轮超时
        # (考卷 l1 量到 15.0s,正是 5 个哑巴锁位 × 1.5s × 两轮)。
        return self._scan((p for p in self._ports() if p < mine), patient=True) is not None

    def _scan(self, ports, patient: bool = False) -> int | None:
        """并发对一段锁位握手,返回**最靠前**那个应答 OK 的锁位(没有就 None)。

        为什么必须并发:每个锁位在最坏情况下都要耗满超时,而**串行会把它们加起来**。
        业主真机上 6 个锁位一个都不肯快速失败 ⇒ 9047ms,他看到的就是"双击了没反应"。
        并发之后整段的代价 = **一个**超时,不再随锁位数量增长。

        顺序语义保持不变:`pool.map` 按入参顺序返回,所以仍然是"最靠前的那个赢" ——
        并发裁决(绑完回头看有没有人比我更靠前)靠的就是这个方向唯一。

        ⚠️ 与串行的唯一行为差异:串行遇到第一个应答就不再往下问,并发是整段都问一遍
        ⇒ 万一真有两份在跑(那本身是 bug),两份都会被叫到前台。已知且可接受:
        单实例世界里最多只有一份,而"多叫醒一个窗口"不伤数据。
        """
        ports = list(ports)
        # 🔴 **累加,不是取最大**:第二轮(`_someone_ahead_of`)扫的永远是第一轮的子集,
        #    取 max 会让这个字段恒等于 span+1、把兜底那一轮整个吞掉 —— 而 `scan_ms`
        #    是含两轮的墙钟 ⇒ 业主拿它一除,每格代价放大 1.5 倍。判据 l6 钉住
        #    "字段 == 握手函数真被调用的次数"(2026-09-01 接手复核)。
        self.scanned += len(ports)
        if not ports:
            return None
        probe = functools.partial(self._send_show, patient=patient)
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(ports), thread_name_prefix="ds-shell-lock-scan") as pool:
            answered = list(pool.map(probe, ports))
        for port, ok in zip(ports, answered):
            if ok:
                return port
        return None

    def release(self) -> None:
        """放开锁,并且**立刻**不再应答握手。

        只 close() 是不够的:服务线程这时正阻塞在旧 socket 的 accept() 里,而关掉一个
        正被 accept 阻塞的 socket 并不保证把它叫醒(Linux 实测不醒,Windows 同样不保证)。
        于是下一次握手连进来时 accept 才返回、线程照样回了个 OK ⇒ **锁已经放开了,
        新实例却被告知"已有一份在跑"**,业主看到的是双击图标没反应。

        叫醒的办法:先 shutdown() 断开监听,再自连一次把可能仍阻塞的 accept 顶出来。
        """
        self._released.set()
        sock = self._sock
        port = self.port
        self._sock = None
        self.port = None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass          # 监听 socket 上 shutdown 在有的平台直接报错,不影响下一步
        if port:
            try:          # 自连一次:把仍卡在 accept 里的线程顶出来(它一醒就看见 _released)
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    pass
            except OSError:
                pass
        try:
            sock.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _ports(self):
        return range(self.base_port, self.base_port + self.span + 1)

    def _send_show(self, port: int, patient: bool = False) -> bool:
        """连上去握一次手。对上了 = 那边是另一份 OpenDesign(SHOW 已送到)。

        收发都**循环读到整行**:TCP 没有消息边界,一次 recv 恰好等于整帧只是回环上的
        运气;分片就把真实例认成陌生人 ⇒ 开出第二份。
        """
        t = lock_timeouts()
        # patient=True:连接也用回话那个宽期限。只有 `_someone_ahead_of` 走这条 ——
        # 那一刻我们已经知道"锁位被占而快扫没问出来",短期限不该再被信任。
        connect_deadline = t["read"] if patient else t["connect"]
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=connect_deadline) as s:
                s.settimeout(t["read"])
                s.sendall(self._HELLO + self._SHOW)
                return self._recv_line(
                    s, deadline=time.monotonic() + t["read"]) == self._OK.strip()
        except OSError:
            return False

    _recv_line = staticmethod(recv_line)

    def _serve(self) -> None:
        # 捞一份本地引用:release() 会把 self._sock 置 None,再用 self._sock 就是 AttributeError。
        sock = self._sock
        if sock is None:
            return
        while not self._released.is_set():
            try:
                conn, _ = sock.accept()
            except OSError:
                break
            # 醒来之后**再问一次**:release() 的自连就是来顶醒我的,
            # 而这一刻锁已经放开了 —— 这时候还回 OK,就等于替一把不存在的锁挡人。
            if self._released.is_set():
                conn.close()
                break
            # 每条连接单独一个线程处理。**不许在主循环里同步处理**:
            # 端口扫描器(或任何连上就不说话的东西)会把这个循环堵住,而这段时间里
            # 第二个实例握手会超时、把真实例当成陌生人 ⇒ 开出第二份 OpenDesign。
            threading.Thread(target=self._handle, args=(conn,),
                             name="ds-shell-lock-conn", daemon=True).start()

    @classmethod
    def _recv_frame(cls, sock: socket.socket, deadline: float,
                    settle: float = 0.35, limit: int = 4096) -> tuple[bytes, bytes]:
        """读一整帧:第一行 HELLO,第二行动词(**可能没有**)。

        🔴 为什么不能连着调两次 `_recv_line`:那个函数每次都从 socket 重新读,
        **把同一个包里多出来的部分丢掉**。而 HELLO 和动词几乎总在同一个包里到达
        ⇒ 分两次读会把动词连缓冲一起扔了,然后干等第二行到超时。

        只发了 HELLO 的老实例(以及升级瞬间还在跑的那份)必须照常工作:
        第一行到手后只再宽限 `settle`,拿不到动词就按"没有动词"处理。
        """
        buf = b""
        grace: float | None = None
        while len(buf) < limit and buf.count(b"\n") < 2:
            now = time.monotonic()
            if buf.count(b"\n") >= 1 and grace is None:
                grace = now + settle
            remain = (min(deadline, grace) if grace is not None else deadline) - now
            if remain <= 0:
                break
            sock.settimeout(remain)
            try:
                chunk = sock.recv(limit)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
        parts = buf.split(b"\n")
        return parts[0], (parts[1] if len(parts) > 1 else b"")

    def _handle(self, conn: socket.socket) -> None:
        verb = b""
        with conn:
            try:
                head, verb = self._recv_frame(conn, deadline=time.monotonic() + 2.0)
                if not head.startswith(self._HELLO.strip()):
                    return
                if self._released.is_set():
                    return
                # 先认动词再决定回什么 —— 回裸 OK 就等于说"我收到了"而不说"我认了什么"
                is_restart = verb.strip() == self._RESTART.strip()
                conn.sendall(self._OK_RESTART if is_restart else self._OK)
            except OSError:
                return
        # 动词分派。**认不出的一律退回 SHOW**:重启会掐断他正在进行的对话,
        # 而把窗口叫到前台最多是打扰一下 ⇒ 拿不准时选那个不伤人的。
        cb = self.on_restart if is_restart else self.on_show
        if cb is not None:
            cb()


@dataclass
class Service:
    name: str
    argv: list[str]
    env: dict
    ready_port: int
    log_path: Path

exec
/bin/bash -lc "sed -n '519,690p' bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
    ready_port: int
    log_path: Path
    ready_timeout: float = 60.0
    # 可选的身份探针:收到 ready_port 后再问一句"听这个端口的真是你吗"。
    # "端口有人听"只说明有人听 —— 陌生进程抢在中间那一瞬占了端口,一样是绿的。
    # ds-web 用 /api/health 自报版本;不给探针就退化成只看端口。
    ready_probe: Any = None


@dataclass
class _Managed:
    service: Service
    proc: subprocess.Popen
    log_file: Any
    job_handle: Any = None
    pgid: int | None = None      # POSIX:开跑时记下进程组,别等父进程死了才去问


class Supervisor:
    def __init__(self):
        self._children: list[_Managed] = []
        self._shutdown_lock = threading.Lock()

    def start(self, services: list[Service]) -> None:
        ports = [int(s.ready_port) for s in services]
        if len(set(ports)) != len(ports):
            raise StartupFailed(f"服务端口重复: {ports}")
        for svc in services:
            if not port_free(int(svc.ready_port)):
                raise StartupFailed(f"{svc.name} 的端口 {svc.ready_port} 已被占用")

        try:
            for svc in services:
                child = self._spawn(svc)
                self._children.append(child)
                self._wait_ready(child)
            # 全部就绪之后再点一次名:等后面那条腿的这段时间里,前面的可能已经崩了。
            # 少了这一下,业主看到的是"窗口正常打开、聊天永远连不上、而且没有任何报错"。
            dead = self.poll_dead()
            if dead:
                raise StartupFailed(self._failure_message(
                    self._by_name(dead[0]).service, "起来之后又退出了",
                    self._by_name(dead[0]).proc.poll()))
        except BaseException:
            # 不只接 StartupFailed:建日志目录失败之类会抛 OSError,
            # 接不住就把已经起好的腿丢在那儿变成孤儿(业主下次打开撞端口,还查不出是谁)。
            self.shutdown()
            raise

    def restart(self, services: list[Service]) -> None:
        """把点名的几条腿换成新的(通常只是换了 env),**其余腿一动不动**。

        业主填完 key 之后要走的就是这条路:网关只在启动时读一次环境变量,
        不换一个新进程就永远认不到新 key。而 ds-web **不能**跟着换 ——
        他正看着的那个页面就是 ds-web 发的。

        与 `start()` 的差别是故意的,别照抄那边:start 半路失败会把已起的全停掉
        (半拉子启动没有意义);这里失败**不许连坐** —— 界面没有理由陪葬,
        而且他得看得见"重启失败"这句话。
        
        🔴 **不持 `_shutdown_lock` 是有意的取舍**(08-17 四审两腿都提):
        托盘"退出"和这里交错时,新起的网关可能落在 `shutdown()` 的名册快照之后
        ⇒ 理论上留一个孤儿。没加锁是因为 `shutdown()` 持的是同一把,重启途中
        点退出会让业主干等到 300s 超时 —— 这个仓库有过"重入即永久挂死"的先例。
        Windows 上外壳退出时 Job 的 KILL_ON_JOB_CLOSE 会兜底,窗口只有毫秒宽。
        **下一个想加锁的人:先把 shutdown 那侧的等待改成可中断的,再动这里。**
        """
        names = {s.name for s in services}
        old = [c for c in self._children if c.service.name in names]
        # 🔴 **先除名,再动手**(判据 c19)。反过来写会留下一个窗口:旧腿已经被杀、
        # 却还挂在名册上 —— 看门狗每 3 秒问一次 `poll_dead()`,问在这个窗口里就会
        # 弹「网关意外退出了,请退出后重新打开」,而那一刻其实是**正常重启**,
        # 而且那句指令(退出后重开)恰好会打断正在进行的重启。
        self._children = [c for c in self._children if c not in old]
        for child in old:
            self._terminate_tree(child)
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if all(c.proc.poll() is not None for c in old):
                break
            time.sleep(0.05)
        # 🔴 收尸要走**和 shutdown 同一套**(判据 c18)。少了这一步,Windows 上
        # `_terminate_tree` 只 terminate 了 nanobot 本尊,它带的 3 个 MCP 工具服务
        # 留在 Job 里没人收 —— 关 Job(KILL_ON_JOB_CLOSE)才是那边收整棵树的机制。
        # Linux 看不出来:那边 `_terminate_tree` 打的是整个进程组,孙子跟着一起走。
        # 业主每按一次"保存 key",机器上就多 3 个孤儿。
        for child in old:
            self._kill_tree(child)
            self._close_job(child)
            try:
                child.log_file.close()
            except Exception:
                pass

        for svc in services:
            # 端口得**真的还回来**再起新的。少这一步,新进程 bind 失败,
            # 而业主看到的症状是"点了保存,什么也没发生"。
            port_deadline = time.monotonic() + 5.0
            while not port_free(int(svc.ready_port)):
                if time.monotonic() > port_deadline:
                    raise StartupFailed(
                        f"{svc.name} 的端口 {svc.ready_port} 一直没释放,没能重启")
                time.sleep(0.05)
            child = self._spawn(svc)
            self._children.append(child)
            try:
                self._wait_ready(child)
            except BaseException:
                # 只收自己这一条,别动别人(上面那段 docstring 的"不连坐"就在这儿落地)。
                # 🔴 08-17(四审 subkimi F-2,判据 c22):收尸要走**和上面收旧腿
                # 完全同一套**。这里原来只有 `_terminate_tree` —— Windows 上那等于
                # 只杀了 nanobot 本尊,它带的 3 个 MCP 留在 Job 里没人收
                # (KILL_ON_JOB_CLOSE 不触发),外壳里每失败一次还漏一个日志句柄。
                # 同一个函数里两条路不一致,c18 只钉住了旧腿那一半。
                self._kill_tree(child)
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
                self._children = [c for c in self._children if c is not child]
                raise

    def shutdown(self) -> None:
        with self._shutdown_lock:
            children = list(self._children)
            if not children:
                return

            for child in children:
                self._terminate_tree(child)

            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                if all(child.proc.poll() is not None for child in children):
                    break
                time.sleep(0.05)

            for child in children:
                # posix 上即使父进程已经死了也要再 KILL 一遍进程组:
                # 活着的可能只剩孙进程,而 poll() 问的只是父进程。
                if child.proc.poll() is None or child.pgid or child.job_handle:
                    self._kill_tree(child)

            final_deadline = time.monotonic() + 4.0
            for child in children:
                remaining = max(0.0, final_deadline - time.monotonic())
                try:
                    child.proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    pass

            # 直接子进程死了 ≠ 收干净了:孙进程(nanobot 的 3 个 MCP)还要一会儿才落地,
            # 而它们手里攥着端口。这里等**整个进程组**真的空掉再返回 ——
            # 否则业主点完"退出"马上再双击,新的一份会撞在还没放开的端口上。
            group_deadline = time.monotonic() + 3.0
            while time.monotonic() < group_deadline:
                if all(self._group_gone(c) for c in children):
                    break
                time.sleep(0.05)

            for child in children:
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
            self._children.clear()

    def take_dead(self) -> list[tuple[str, str]]:
        """死掉的腿:**名字和死因一次拿全**(判据 c21)。


exec
/bin/bash -lc "sed -n '1220,1265p' bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
class ShellState:
    visible: bool
    exiting: bool

    def __init__(self, ui, on_stop):
        self.ui = ui
        self.on_stop = on_stop
        self.visible = True
        self.exiting = False
        # 事件从三个方向来:锁的监听线程(第二次双击)、托盘线程、UI 线程。
        # 没有这把锁,"检查 exiting 再置位"是两步 —— 两个线程能一起穿过去,
        # 后台被收两遍、窗口被销毁两遍。锁只护**状态判定**,不护 UI 调用本身。
        self._lock = threading.RLock()

    def on_close_requested(self) -> bool:
        with self._lock:
            if self.exiting:
                return True
            self.visible = False
        self.ui.hide_window()
        return False

    def on_show(self) -> None:
        with self._lock:
            if self.exiting:
                return
            self.visible = True
        self.ui.show_window()

    def on_quit(self) -> None:
        with self._lock:
            if self.exiting:
                return
            self.exiting = True
            self.visible = False
        self.on_stop()
        self.ui.destroy()

codex
进程关系已经明确：真正持有窗口的是 `ds_shell.py`，它再监管工作台和网关；托盘“退出”会收掉整棵后台并释放单实例锁。当前 health 只证明 `ds-web` 活着，且返回 `VERSION` 和 `ds_root`；它还不能证明“这是本次刚拉起的那棵新进程”，所以方案需要给本次更新加一次性身份握手，防止把残留旧进程或抢端口者误判成成功。
exec
/bin/bash -lc "rg -n \"def data_root|DATA_ROOT|migrate_legacy_data|atomic|replace\" bin/ds_common.py; sed -n '1,260p' bin/ds_common.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
41:DATA_ROOT_ENV = "DS_DATA_ROOT"
71:def data_root(ds_root: str) -> str:
77:    if DATA_ROOT_ENV not in os.environ:
80:    configured = os.environ[DATA_ROOT_ENV]
82:        raise DataRootError(f"{DATA_ROOT_ENV} 已设置但是空串")
116:    rel = relative.replace(os.sep, "/")
201:                    unknown.append(rel.replace(os.sep, "/"))
209:                    unknown.append(rel.replace(os.sep, "/"))
211:                unknown.append(top.replace(os.sep, "/") + "/")
213:            unknown.append(top.replace(os.sep, "/"))
217:def migrate_legacy_data(ds_root: str) -> dict:
316:        s = s.replace("|", "/")
#!/usr/bin/env python3
"""ds_common — 三个工具层共享的最小公共件。

只收"改一处必须处处同步"的东西,别往这里堆:
  - within():全项目唯一的防逃逸谓词(realpath containment)。
  - sanitize_field():字段消毒 —— 单行契约的物理保证。账本/索引都是"一行一条"
    的追加式文本,字段里的换行等于伪造整行(状态词表/锚定/页脚全被打穿),
    必须在写入口折叠掉;竖线是 refs 索引的字段分隔符,同理可选禁掉。
  - bump_last_updated() / LASTUPD_DATE_RE:页脚锚定语义的唯一定义 ——
    **行首锚定 + 取最后一处(页脚)**,写侧读侧共用,防两侧分叉。
  - locked_rw():排他锁读改写;错误路径置 box["write"]=False 则完全不碰文件。
"""
from __future__ import annotations

import errno
import os
import shutil
import time
import re
from contextlib import contextmanager
from datetime import date

import ds_lock  # 跨平台排他锁,同目录模块

_LASTUPD_LINE_RE = re.compile(r"^最后更新[:：]")
# 读侧(ds_todo)用:行首锚定,提取日期
LASTUPD_DATE_RE = re.compile(r"^最后更新[:：]\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)

# T4b 批次行 `- C{起}-C{止} {日期} {标题}` 的唯一定义 —— 读侧(ds_todo.collect)与
# 写侧(ds_tools._upsert_batch_line)共用这一份。本项目自己立过"同一个命中不设第二个
# 正则,双正则会漂移"的规矩(见 ds_todo 顶部),批次行不破例。
# 行首是 `- C` 而非 `- [状态]`,所以变更行正则永远命中不了它(反之亦然)。
BATCH_LINE_RE = re.compile(
    r"^- C(?P<from>\d+)-C(?P<to>\d+) (?P<date>\d{4}-\d{2}-\d{2}) (?P<title>.*)$")

# 变更行尾截止日 token(track opendesign-todo-duedate):行尾锚定,正文中间的
# ⏳日期 不误伤;读写两侧(ds_todo.parse_change / ds_tools.set_due_date)共用本 helper,
# 消漂移。
DUE_SUFFIX_RE = re.compile(r"\s*⏳(\d{4}-\d{2}-\d{2})\s*$")

DATA_ROOT_ENV = "DS_DATA_ROOT"


class DataRootError(Exception):
    """数据根不可用。"""


# 装出来的形态才有的东西(启动器 exe 与包内 python 都在 ds/ 的**同级**)。
# 用它来判"上一级到底是不是安装目录"。
_INSTALL_MARKERS = ("OpenDesign.exe", os.path.join("python", "pythonw.exe"))


def _deletable_roots(ds_root: str) -> list[str]:
    """卸载/更新会整棵删掉的地方 —— 业主的东西一样都不许落在这里面。

    - `ds_root` 本身:更新时整棵替换,永远危险。
    - 它的上一级:**只在装出来的形态下**才是安装目录($INSTDIR 底下还有 python\\ 和
      启动器 exe)。开发仓 / 考卷台架里上一级只是个无辜目录,拦它就是误报 ——
      而 2026-08-15 实测,这个误报当场把两条真联跑考卷打红,并且把我引向了
      一个根本没发生的"实现写错了"。**误报和假绿一样坏。**
    """
    real = os.path.realpath(ds_root)
    roots = [real]
    parent = os.path.dirname(real)
    if parent and parent != real and any(
            os.path.exists(os.path.join(parent, m)) for m in _INSTALL_MARKERS):
        roots.append(parent)
    return roots


def data_root(ds_root: str) -> str:
    """返回业主数据根。

    环境变量缺席时保持旧行为;显式配置错误时 fail closed,
    绝不回退到安装目录。
    """
    if DATA_ROOT_ENV not in os.environ:
        return ds_root

    configured = os.environ[DATA_ROOT_ENV]
    if configured == "":
        raise DataRootError(f"{DATA_ROOT_ENV} 已设置但是空串")

    try:
        resolved = os.path.realpath(configured)
        # 无效路径在创建前先拒绝,连空目录也不留在会被删掉的地方。
        for danger in _deletable_roots(ds_root):
            if within(os.path.normcase(danger), os.path.normcase(resolved)):
                raise DataRootError(f"数据根不能放在会被卸载删掉的地方: {resolved}")
        os.makedirs(resolved, exist_ok=True)
    except DataRootError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise DataRootError(f"数据根无法创建或访问: {configured}: {exc}") from exc

    if not os.path.isdir(resolved):
        raise DataRootError(f"数据根不是目录: {resolved}")
    return resolved


_LEGACY_DATA_DIRS = ("projects", "clients", "refs", "organize")
_LEGACY_DATA_FILES = ("index.md", "refs-index.md", "refs-vocab.md")
_LEGACY_CONFIG_ENTRIES = (
    "workspace.json",
    "workspace.json.lock",
    "workspace.json.bak",
    "consent.json",
    "pending.lock",
    "pending",
    "taxonomy.json",
)


def _move_legacy_entry(source: str, target: str, relative: str, report: dict) -> None:
    """同名不覆盖的同卷递归搬运。"""
    rel = relative.replace(os.sep, "/")
    if os.path.isdir(source) and not os.path.islink(source):
        if os.path.lexists(target) and (not os.path.isdir(target)
                                           or os.path.islink(target)):
            report["skipped"].append(rel)
            return
        try:
            os.makedirs(target, exist_ok=True)
            names = sorted(os.listdir(source))
        except OSError as exc:
            report["failed"].append({"path": rel, "error": str(exc)})
            return
        if not names:
            report["moved"].append(rel + "/")
        for name in names:
            _move_legacy_entry(
                os.path.join(source, name),
                os.path.join(target, name),
                os.path.join(relative, name),
                report,
            )
        try:
            os.rmdir(source)  # 只删已搬空的目录;有跳过/失败项时会自然保留。
        except OSError:
            pass
        return

    if os.path.lexists(target):
        report["skipped"].append(rel)
        return
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            os.rename(source, target)  # 同卷:一步到位,原子。
        except OSError as exc:
            # 🔴 跨卷(业主把程序装到别的盘)时 rename 抛 EXDEV。上一版把它记进 failed,
            # 而外壳和 ds-web 都会因为 failed 拒绝启动 ⇒ **应用永久打不开**,
            # 数据安全但人被锁在门外(四审 subdeepseek)。这里退化成"拷过去再删原件":
            # 先拷完并落盘,确认目标在,才删来源 —— 中途断电最坏是留一份副本,不丢东西。
            if exc.errno != errno.EXDEV:
                raise
            shutil.copy2(source, target)
            if not os.path.exists(target):
                raise
            os.unlink(source)
        report["moved"].append(rel)
    except OSError as exc:
        report["failed"].append({"path": rel, "error": str(exc)})


# 装什么样就该一直是什么样的那些 —— 它们**不是**"没认识的数据",报出来只会淹掉真货。
# (闸③ 实测:不排除的话,真安装包里 unknown 是几千条 bin/*.py 与 web/dist/**,
#  而 canary 就在里面。一份谁都不会读的报告不算报告。)
_CODE_TOP = ("bin", "web", "assets", "workspace", "installer", "docs", "schema", "skills")
_CODE_FILES = ("版本号.txt", "README.md")
_CODE_CONFIG_PREFIX = ("nanobot.config", "taxonomy.default.json", "workspace.example.json")


def _unknown_legacy_entries(legacy_root: str) -> list[str]:
    """列出迁移清单未覆盖的文件,避免未来新数据种类被静默遗忘。

    **只报数据形状的东西**:代码那一份按上面的名单排除掉,否则 canary 会被噪音淹掉。
    """
    known_top = set(_LEGACY_DATA_DIRS) | set(_LEGACY_DATA_FILES) \
        | set(_CODE_TOP) | set(_CODE_FILES)
    known_config = set(_LEGACY_CONFIG_ENTRIES)
    unknown: list[str] = []
    try:
        top_names = sorted(os.listdir(legacy_root))
    except OSError as exc:
        return [f"<scan failed: {exc}>"]

    for top in top_names:
        if top in known_top:
            continue
        top_path = os.path.join(legacy_root, top)
        if top == "config" and os.path.isdir(top_path):
            for base, dirs, files in os.walk(top_path):
                rel_base = os.path.relpath(base, top_path)
                if rel_base == ".":
                    dirs[:] = [d for d in dirs if d not in known_config]
                    files = [f for f in files if f not in known_config
                             and not f.startswith(_CODE_CONFIG_PREFIX)]
                for name in files:
                    rel = os.path.relpath(os.path.join(base, name), legacy_root)
                    unknown.append(rel.replace(os.sep, "/"))
            continue
        if os.path.isdir(top_path) and not os.path.islink(top_path):
            found = False
            for base, _dirs, files in os.walk(top_path):
                for name in files:
                    found = True
                    rel = os.path.relpath(os.path.join(base, name), legacy_root)
                    unknown.append(rel.replace(os.sep, "/"))
            if not found:
                unknown.append(top.replace(os.sep, "/") + "/")
        else:
            unknown.append(top.replace(os.sep, "/"))
    return unknown


def migrate_legacy_data(ds_root: str) -> dict:
    """当数据根已外置时,把 ds_root 下的遗留业主数据幂等搬过去。"""
    target_root = data_root(ds_root)
    report = {
        "data_root": target_root,
        "moved": [],
        "skipped": [],
        "unknown": [],
        "failed": [],
    }
    legacy_root = os.path.realpath(ds_root)
    if os.path.realpath(target_root) == legacy_root:
        return report

    for name in _LEGACY_DATA_DIRS + _LEGACY_DATA_FILES:
        source = os.path.join(legacy_root, name)
        if os.path.lexists(source):
            _move_legacy_entry(source, os.path.join(target_root, name), name, report)

    for name in _LEGACY_CONFIG_ENTRIES:
        source = os.path.join(legacy_root, "config", name)
        if os.path.lexists(source):
            _move_legacy_entry(
                source,
                os.path.join(target_root, "config", name),
                os.path.join("config", name),
                report,
            )

    report["unknown"] = _unknown_legacy_entries(legacy_root)
    _write_migration_note(target_root, report)
    return report


def _write_migration_note(data_root_path: str, report: dict) -> None:
    """把这次搬运写成一份**业主看得见**的记录。

    🔴 四审两腿同时点名:`unknown`/`skipped` 只进返回值,而生产路径只查 `failed`
    ⇒ 那张"没认识的东西"的网**没接电** —— 将来新加一种数据种类,它留在安装目录里
    被卸载删掉,而所有判据照样绿。design 3b 自己写着"搬完在日志里记一行",这就是那一行。
    """
    if not (report["moved"] or report["skipped"] or report["unknown"] or report["failed"]):
        return
    try:

exec
/bin/bash -lc "sed -n '960,1050p' bin/ds_shell_core.py" in /root/.openclaw/workspace/projects/design-studio
exec
/bin/bash -lc "sed -n '1,240p' installer/launcher.nsi" in /root/.openclaw/workspace/projects/design-studio
exec
/bin/bash -lc "rg -n \"def |UserData|Data|write|open\\(|mkdir|replace|config|home|ds-root\" bin/ds_provision.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
            import ctypes
            from ctypes import wintypes

            # 同上:不声明 argtypes,64 位句柄会被截成 32 位 ⇒ 关的是别的东西,
            # 而 KILL_ON_JOB_CLOSE 那条命就白挂了(这一处是第二个现场,别只修一个)。
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CloseHandle.restype = wintypes.BOOL
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            k32.CloseHandle(child.job_handle)
        except Exception:
            pass
        child.job_handle = None


# OpenDesign 自己的三个 MCP(名字与 config/nanobot.config.windows.jsonc 一致)。
# 只有它们的 command 会被改写指向包内 python —— 机主自己装的第三方 MCP
# (npx / 别的 exe)一个字都不许动,改了就是把人家的工具弄坏。
OUR_MCP = ("design-studio", "design-studio-organize", "design-studio-refs")


def patch_config(path, *, gateway_port: int, ws_port: int, python_exe: str,
                 data_root: str | None = None) -> None:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    ws = cfg.get("channels", {}).get("websocket", {})
    if ws.get("enabled") is not True:
        raise ConfigUnusable("聊天通道没打开,请重新运行安装程序设置登录口令")
    token = ws.get("token")
    if not token:
        raise ConfigUnusable("聊天通道缺少登录口令,请重新运行安装程序设置")
    # 🔴 口令必须是浏览器发得出去的。前端把它放进 HTTP 头,而 fetch 的头值只收
    # Latin-1(web/src/chat/connection.ts:85 已经明确拒收)⇒ 中文口令会让两条腿
    # 全部正常起来、界面也正常,**唯独第一句话永远发不出去**。
    # 这里 fail closed:宁可现在报一句人话,也不要业主拿着一台"看着装好了"的机器来问。
    try:
        str(token).encode("latin-1")
    except UnicodeEncodeError:
        raise ConfigUnusable(
            "登录口令里有中文或特殊字符,浏览器发不出去 —— 请改成字母数字口令") from None

    servers = cfg.get("tools", {}).get("mcpServers")
    if not isinstance(servers, dict):
        raise ConfigUnusable("配置里没有工具服务(mcpServers),这份配置是残的")
    missing = [n for n in OUR_MCP if not isinstance(servers.get(n), dict)]
    if missing:
        raise ConfigUnusable(f"配置里缺少 OpenDesign 自己的工具服务:{'、'.join(missing)}")

    cfg.setdefault("gateway", {})["port"] = int(gateway_port)
    ws["port"] = int(ws_port)
    for name in OUR_MCP:
        servers[name]["command"] = str(python_exe)
        # 🔴 三个 MCP **不是外壳起的** —— 网关按这里的 env 块起它们,而 MCP SDK 的
        # stdio 客户端只继承一份固定白名单,DS_DATA_ROOT 不在里面。不写进来的话:
        # 助手(聊天侧)建的档案全部落回安装目录 = 卸载会删的地方,而工作台读数据根
        # ⇒ 同一份档案两个世界,重启时迁移再把它搬走,来回翻。
        # 四审 subkimi 抓的 BLOCK;判据 d4 咬着。写绝对路径,不用 ${VAR}:
        # 那要 loader 展开,而它只在网关自己的 env 里查得到。
        if data_root:
            servers[name].setdefault("env", {})[ds_common.DATA_ROOT_ENV] = str(data_root)

    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{cfg_path.name}.", suffix=".tmp", dir=str(cfg_path.parent)
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        try:
            mode = cfg_path.stat().st_mode
            os.chmod(tmp_name, mode)
        except OSError:
            pass
        os.replace(tmp_name, cfg_path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


# nanobot 会把配置里的 `${VAR}` 换成环境变量,而**任何一个没设的都会让网关整个拒绝启动**
# (nanobot/config/loader.py:143-149 抛 ValueError)。下面这条正则与它逐字一致。
#
# 🔴 为什么要有这一段(2026-08-14 业主真机实证,不是推演):

 succeeded in 0ms:
; OpenDesign 启动器 —— 业主每天双击的就是这个 exe。
;
; 它不是安装器,只是一个**带自己图标的壳**:确认包是完整的,然后把真正的外壳
; (python\pythonw.exe + ds\bin\ds_shell.py)拉起来,自己立刻退出。
;
; 为什么要有它,而不是让快捷方式直接指 pythonw.exe:
;   · 快捷方式和任务管理器里得是 "OpenDesign" 而不是 "pythonw",
;     图标得是我们自己的(exe 的图标只能编进 exe 里,快捷方式改不了进程的身份);
;   · 开机自启那条注册表值要指一个稳定的东西,将来换启动方式只改这一个文件;
;   · 包被装坏时(杀软吃掉了 python\)业主得看到一句中文,而不是双击没反应。
;
; 用 NSIS 编它是顺手:安装器本来就用 NSIS,不必为一个 40KB 的壳再引一条工具链。
; `SilentInstall silent` = 编出来的 exe 不显示任何安装界面,直接跑 Section。
;
; 判据:installer/check-installer.py 的 L1~L6。

Unicode true

!define APP "OpenDesign"

Name "${APP}"
OutFile "OpenDesign.exe"
Icon "opendesign.ico"
SilentInstall silent
RequestExecutionLevel user

VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName"     "${APP}"
VIAddVersionKey "FileDescription" "${APP} 启动器"
VIAddVersionKey "FileVersion"     "${APPVER}.0"
VIAddVersionKey "ProductVersion"  "${APPVER}"
VIAddVersionKey "LegalCopyright"  "OpenDesign"

Section
  ; $EXEDIR = 这个 exe 所在的目录 = 安装根。**不写死路径**:业主可以把安装目录
  ; 挑到别处,而快捷方式和开机自启都是指到这个 exe 的。
  SetOutPath "$EXEDIR"

  IfFileExists "$EXEDIR\python\pythonw.exe" py_ok 0
    MessageBox MB_ICONSTOP "${APP} 好像没装完整:找不到$\n$EXEDIR\python\pythonw.exe$\n$\n请重新运行安装程序。$\n(如果电脑上装了杀毒软件,也可能是它把文件删了。)"
    Abort
  py_ok:

  IfFileExists "$EXEDIR\ds\bin\ds_shell.py" ds_ok 0
    MessageBox MB_ICONSTOP "${APP} 好像没装完整:找不到$\n$EXEDIR\ds\bin\ds_shell.py$\n$\n请重新运行安装程序。"
    Abort
  ds_ok:

  ; pythonw 而不是 python:后者会留一个黑窗口在任务栏上,业主会以为是病毒。
  ; Exec 而不是 ExecWait:起完就退,别让启动器一直挂在任务管理器里。
  Exec '"$EXEDIR\python\pythonw.exe" "$EXEDIR\ds\bin\ds_shell.py"'
SectionEnd

 succeeded in 0ms:
4:    python ds_provision.py --home <数据目录> --ds-root <ds 目录> [--token 口令]
9:`<数据目录>\\.nanobot\\config.json` 才起得来后台 —— **那份文件从来没人生成过**。
21:**① 只写 `--home` 底下。** 业主机器上很可能**已经有一份他自己在用的**
22:`~/.nanobot/config.json`(openclaw 那套)。碰它 = 把他现有的东西弄坏,而且他不会知道
24:本脚本**不复用** `bin/enable_webui.py`(它写死了 `~/.nanobot/config.json`,
49:TEMPLATE_NAME = "nanobot.config.windows.jsonc"
56:def new_token() -> str:
60:def check_token(token: str) -> str:
66:    与 `ds_shell_core.patch_config` 的那道闸是同一件事,两边都要有:
79:def write_json(path: Path, data: dict) -> None:
81:    path.parent.mkdir(parents=True, exist_ok=True)
85:        with os.fdopen(fd, "w", encoding="utf-8") as f:
87:            f.write("\n")
90:        os.replace(tmp_name, path)
100:def default_config() -> dict:
103:        from nanobot.config.schema import Config
111:def load_existing(cfg_path: Path) -> dict | None:
119:        with cfg_path.open("r", encoding="utf-8") as f:
144:def set_websocket(cfg: dict, token: str) -> None:
148:    那个脚本写死了 `~/.nanobot/config.json`(老装法里那样是对的),而这里绝不能碰 `~`。
158:def merge_template(python_exe: str, ds_root: Path, cfg_path: Path) -> None:
161:    起子进程而不是 import:`ds_merge_config.py` 里有一整套"别把机主选好的大脑重置回
164:    template = ds_root / "config" / TEMPLATE_NAME
167:    merger = ds_root / "bin" / "ds_merge_config.py"
182:                       # 🔴 解码侧也要 replace(panel subglm 抓到,我自审两遍没看见)。
183:                       # 编码侧给了 replace、这里却还是 strict:盘上那份合并脚本
187:                       errors="replace", timeout=180, env=env)
192:def write_token_note(home: Path, token: str) -> Path:
198:    note = home / ".openDesign" / "登录口令.txt"
199:    note.parent.mkdir(parents=True, exist_ok=True)
200:    note.write_text(
208:def provision(home: Path, ds_root: Path, token: str | None, python_exe: str) -> dict:
209:    home.mkdir(parents=True, exist_ok=True)
210:    cfg_path = home / ".nanobot" / "config.json"
214:    if not (ds_root / "config" / TEMPLATE_NAME).is_file():
216:                      f"{ds_root / 'config' / TEMPLATE_NAME}\n请重新运行安装程序。")
221:        cfg = default_config()
241:        write_json(staging, cfg)
243:        os.replace(staging, cfg_path)
251:    note = write_token_note(home, final)
259:def _talk_utf8() -> None:
268:    `errors="replace"` 是刻意的:输出通道是给人看的,**它有权难看,没权杀进程**。
273:            stream.reconfigure(encoding="utf-8", errors="replace")
278:def main(argv: list[str]) -> int:
281:    ap.add_argument("--home", required=True, help="业主数据目录(%%LOCALAPPDATA%%\\OpenDesign\\UserData)")
282:    ap.add_argument("--ds-root", required=True, help="装好的 ds 目录(里面有 bin\\ 和 config\\)")
287:        provision(Path(a.home), Path(a.ds_root), a.token, a.python)

exec
/bin/bash -lc 'wc -l .github/scripts/windows-package-probe.ps1 .github/scripts/windows-gui-probe.ps1 .github/scripts/windows-nonempty-probe.ps1' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
  481 .github/scripts/windows-package-probe.ps1
  138 .github/scripts/windows-gui-probe.ps1
  126 .github/scripts/windows-nonempty-probe.ps1
  745 total

exec
/bin/bash -lc 'rg -n -i "health|version|install|uninstall|silent|exit|verdict|phase|process|data|localappdata|OpenDesign|screenshot" .github/scripts/windows-package-probe.ps1 .github/scripts/windows-gui-probe.ps1 .github/scripts/windows-nonempty-probe.ps1' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
.github/scripts/windows-package-probe.ps1:8:#    旧文案写"脚本自己崩了才 exit 非零",但脚本末尾没有 exit 语句 ⇒ pwsh 拿
.github/scripts/windows-package-probe.ps1:9:#    **最后一个原生命令的 $LASTEXITCODE** 当脚本退出码。run 33306843034 就是这么
.github/scripts/windows-package-probe.ps1:13:#    现在改成:**任何一相自报 FAIL ⇒ exit 1**,否则 exit 0(见文件末尾)。
.github/scripts/windows-package-probe.ps1:19:    [string]$Tag    = "win-installer-0.97.0",
.github/scripts/windows-package-probe.ps1:20:    [string]$Asset  = "OpenDesign-Setup-0.97.0.exe",
.github/scripts/windows-package-probe.ps1:28:$InstallDir = "$env:LOCALAPPDATA\Programs\OpenDesign"
.github/scripts/windows-package-probe.ps1:29:$DataRoot   = "$env:LOCALAPPDATA\OpenDesign"
.github/scripts/windows-package-probe.ps1:30:$phases     = [ordered]@{}
.github/scripts/windows-package-probe.ps1:34:function Say([string]$k, [string]$v) { $phases[$k] = $v; "PHASE $k : $v" }
.github/scripts/windows-package-probe.ps1:37:#    原来闸只有一条路:读进程内的 $phases、在里面找 "FAIL" 字样。外部评审实测出
.github/scripts/windows-package-probe.ps1:39:#      · 闸前面补一行 `$phases = @{}` ⇒ 闸读到的是空的;
.github/scripts/windows-package-probe.ps1:40:#      · Get-Verdict 最终 return 里多一个 `-replace "FAIL", ""` ⇒ 裁决被洗白。
.github/scripts/windows-package-probe.ps1:42:#    ⇒ 每一相的裁决**退出码**(不是那句话)另外落进 verdicts.tsv,
.github/scripts/windows-package-probe.ps1:45:#    ① `Say-Verdict` 这一个函数体里改两下(先 `$script:lastRc = 0`、再把 `Say $k $v`
.github/scripts/windows-package-probe.ps1:46:#       换成 `Say $k ($v -replace "FAIL","")`)⇒ 收据的 rc 列恒 0 且 $phases 里没有 FAIL
.github/scripts/windows-package-probe.ps1:47:#       ⇒ **三条路一起死**。收据的 rc 和 phases 的文本都从这一个函数流过。
.github/scripts/windows-package-probe.ps1:50:# 🔴 **而且三条路只覆盖 4 个相**:只有 `Say-Verdict` 的相(5/6/8/10)进 verdicts.tsv。
.github/scripts/windows-package-probe.ps1:55:$VerdictLog     = Join-Path $OutDir 'verdicts.tsv'
.github/scripts/windows-package-probe.ps1:57:function Say-Verdict([string]$k, [string]$v) {
.github/scripts/windows-package-probe.ps1:59:        Add-Content -Path $VerdictLog -Encoding utf8
.github/scripts/windows-package-probe.ps1:66:#    ⇒ 探针只**采事实**,判定交给 bin/probe_verdict.py(纯函数,有 11 条行为判据守着)。
.github/scripts/windows-package-probe.ps1:68:function Get-Verdict([string]$kind, $facts) {
.github/scripts/windows-package-probe.ps1:69:    $judge = Join-Path $PSScriptRoot '..\..\bin\probe_verdict.py'
.github/scripts/windows-package-probe.ps1:70:    $py     = "$InstallDir\python\python.exe"
.github/scripts/windows-package-probe.ps1:84:        #    守卫 ⇒ **traceback 被当成裁决原样 Say 出去**,闸找不到 FAIL ⇒ exit 0。
.github/scripts/windows-package-probe.ps1:87:        $rc   = $LASTEXITCODE
.github/scripts/windows-package-probe.ps1:148:  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
.github/scripts/windows-package-probe.ps1:149:  public static int Pid(IntPtr h) { int p; GetWindowThreadProcessId(h, out p); return p; }
.github/scripts/windows-package-probe.ps1:157:"@ -ErrorAction SilentlyContinue
.github/scripts/windows-package-probe.ps1:160:function Dump-Dialogs([string]$Match = 'OpenDesign') {
.github/scripts/windows-package-probe.ps1:182:#    **标题分不开** —— ds_shell.py 的 alert()/die() 用的标题就是 APP = OpenDesign。
.github/scripts/windows-package-probe.ps1:184:#    的 `$appTitle` 传进来。外部评审实测:在 `$appTitle = 'OpenDesign'` 下面补一行
.github/scripts/windows-package-probe.ps1:187:#    ⇒ 这里**看见什么报什么**,挑哪个是我们的交给 bin/probe_verdict.py(那边跑得动,
.github/scripts/windows-package-probe.ps1:216:#    或被 IfSilent 挡住),而 installer/OpenDesign.nsi 里 4 个 MessageBox 一个都没有。
.github/scripts/windows-package-probe.ps1:220:    $ip = Start-Process (Resolve-Path $setup) -ArgumentList '/S' -PassThru
.github/scripts/windows-package-probe.ps1:222:    while (-not $ip.HasExited -and $sw.Elapsed.TotalMinutes -lt 3) {
.github/scripts/windows-package-probe.ps1:224:        Save-Screen ("{0}/2{1}-installing.png" -f $OutDir, $tick)
.github/scripts/windows-package-probe.ps1:225:        $t = Get-Process | Where-Object { $_.MainWindowTitle } |
.github/scripts/windows-package-probe.ps1:226:             ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
.github/scripts/windows-package-probe.ps1:231:    if ($ip.HasExited) {
.github/scripts/windows-package-probe.ps1:233:        $r2 = if ($ip.ExitCode -eq 0) { "退出码 0" } else { "FAIL - 退出码 $($ip.ExitCode)" }
.github/scripts/windows-package-probe.ps1:236:        Save-Screen "$OutDir/29-installer-stuck.png"
.github/scripts/windows-package-probe.ps1:237:        $t = Get-Process | Where-Object { $_.MainWindowTitle } |
.github/scripts/windows-package-probe.ps1:238:             ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
.github/scripts/windows-package-probe.ps1:243:        Stop-Process -Id $ip.Id -Force -ErrorAction SilentlyContinue
.github/scripts/windows-package-probe.ps1:248:$must = @("$InstallDir\OpenDesign.exe", "$InstallDir\python\pythonw.exe", "$InstallDir\ds\bin\ds_shell.py")
.github/scripts/windows-package-probe.ps1:252:    $size = [Math]::Round(((Get-ChildItem $InstallDir -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 0)
.github/scripts/windows-package-probe.ps1:261:    $py = "$InstallDir\python\python.exe"
.github/scripts/windows-package-probe.ps1:262:    $pv = "$InstallDir\ds\bin\ds_provision.py"
.github/scripts/windows-package-probe.ps1:264:        $o = & $py $pv --home "$DataRoot\UserData" --ds-root "$InstallDir\ds" 2>&1
.github/scripts/windows-package-probe.ps1:265:        $rc = $LASTEXITCODE
.github/scripts/windows-package-probe.ps1:275:    Start-Process "$InstallDir\OpenDesign.exe" | Out-Null
.github/scripts/windows-package-probe.ps1:276:    Say '4 启动' "OK - 已拉起 OpenDesign.exe"
.github/scripts/windows-package-probe.ps1:288:#    在 PHASE 4 之后静默 29 分钟被超时砍掉,verdicts.tsv 从来没生成过 ⇒ 路二/路三
.github/scripts/windows-package-probe.ps1:301:            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$p/api/health" -TimeoutSec 2
.github/scripts/windows-package-probe.ps1:302:            if ($h.version) { $answers["$p"] = "$($h.version)" }
.github/scripts/windows-package-probe.ps1:308:Say-Verdict '5 服务活了吗' (Get-Verdict 'health' @{ answers = $answers; tried = $tried })
.github/scripts/windows-package-probe.ps1:310:# ── 6 窗口在不在:等 **OpenDesign 自己的**窗口出现 ─────────────────
.github/scripts/windows-package-probe.ps1:313:#    当场照出来 —— 那一刻 OpenDesign 的窗口根本不在列表里(41s 的截图上它才出现),
.github/scripts/windows-package-probe.ps1:316:#    改成:轮询等标题里带 OpenDesign 的那个(照第 5 相的写法),60s 没等到才 FAIL。
.github/scripts/windows-package-probe.ps1:319:#    alert()/die() 弹的报错框标题**就是** APP = OpenDesign,所以"后端活着 + 屏幕上
.github/scripts/windows-package-probe.ps1:322:#    `$wins`(标题含 OpenDesign 的顶层窗口 + 它们的窗口类)和 `$ours`(老口径:
.github/scripts/windows-package-probe.ps1:324:#    `bin/probe_verdict.py::window_verdict`,那里有 11 条行为判据守着。
.github/scripts/windows-package-probe.ps1:332:    $procs = @(Get-Process | Where-Object { $_.MainWindowTitle } |
.github/scripts/windows-package-probe.ps1:333:               ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" })
.github/scripts/windows-package-probe.ps1:335:    $v6 = Get-Verdict 'window' @{
.github/scripts/windows-package-probe.ps1:339:            #    资源管理器开着 OpenDesign 这个文件夹,就是一个标题 OpenDesign、
.github/scripts/windows-package-probe.ps1:343:            proc = (Get-Process -Id $_.Pid -ErrorAction SilentlyContinue).ProcessName } })
.github/scripts/windows-package-probe.ps1:347:Say-Verdict '6 窗口在不在' $v6
.github/scripts/windows-package-probe.ps1:376:#    `bin/probe_verdict.py::REQUIRED_LOGS` —— 这一段只采"谁在、多大"。
.github/scripts/windows-package-probe.ps1:380:        $log = "$DataRoot\Logs\$n"
.github/scripts/windows-package-probe.ps1:386:    Say-Verdict '8 收日志' (Get-Verdict 'logs' @{ present = $present })
.github/scripts/windows-package-probe.ps1:396:    #    出处:installer/OpenDesign.nsi:245 那行 ExecToLog 用的就是 "$INSTDIR\python\python.exe"。
.github/scripts/windows-package-probe.ps1:397:    $py = "$InstallDir\python\python.exe"
.github/scripts/windows-package-probe.ps1:405:sys.path.insert(0, r'$InstallDir\ds\bin')
.github/scripts/windows-package-probe.ps1:409:d.export_bundle(out, app_dir=r'$DataRoot')
.github/scripts/windows-package-probe.ps1:413:    $rc9 = $LASTEXITCODE
.github/scripts/windows-package-probe.ps1:423:    Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
.github/scripts/windows-package-probe.ps1:424:        Stop-Process -Force -ErrorAction SilentlyContinue
.github/scripts/windows-package-probe.ps1:429:    Start-Process "$InstallDir\OpenDesign.exe"
.github/scripts/windows-package-probe.ps1:437:                $h = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -UseBasicParsing `
.github/scripts/windows-package-probe.ps1:444:    Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue
.github/scripts/windows-package-probe.ps1:447:    $v10 = Get-Verdict 'health' @{ answers = $answers2; tried = $tried2 }
.github/scripts/windows-package-probe.ps1:448:    Say-Verdict '10 带系统代理启动' ("{0}({1}s,颜色 {2} 种 / 近白 {3}%)" -f `
.github/scripts/windows-package-probe.ps1:450:    Copy-Item "$DataRoot\Logs\外壳.log" "$OutDir/外壳-带代理.log" -Force -ErrorAction SilentlyContinue
.github/scripts/windows-package-probe.ps1:453:Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
.github/scripts/windows-package-probe.ps1:454:    Stop-Process -Force -ErrorAction SilentlyContinue
.github/scripts/windows-package-probe.ps1:456:"" ; "==================== VERDICT ===================="
.github/scripts/windows-package-probe.ps1:457:foreach ($k in $phases.Keys) { "{0,-16} {1}" -f $k, $phases[$k] }
.github/scripts/windows-package-probe.ps1:462:# 不写这段的话,退出码 = 最后一个原生命令的 $LASTEXITCODE(见文件头)。
.github/scripts/windows-package-probe.ps1:464:$failed = @($phases.GetEnumerator() | Where-Object { $_.Value -match 'FAIL' } | ForEach-Object { $_.Key })
.github/scripts/windows-package-probe.ps1:465:# 路二:判定器的**退出码**收据(那句话被洗白、或 $phases 被重播成空的,这条照样在)。
.github/scripts/windows-package-probe.ps1:468:if (Test-Path $VerdictLog) {
.github/scripts/windows-package-probe.ps1:469:    "" ; "---- 裁决收据 verdicts.tsv ----" ; Get-Content $VerdictLog | ForEach-Object { "  $_" }
.github/scripts/windows-package-probe.ps1:470:    $hard = @(Get-Content $VerdictLog | Where-Object { $_ -like "1`t*" })
.github/scripts/windows-package-probe.ps1:472:    $hard = @("(没有 verdicts.tsv:探针没跑到落账那一步)")
.github/scripts/windows-package-probe.ps1:477:    "⇒ exit 1"
.github/scripts/windows-package-probe.ps1:478:    exit 1
.github/scripts/windows-package-probe.ps1:480:"没有任何一相自报 FAIL,收据里也没有 ⇒ exit 0(**白屏读数不在闸内**,仍要看图)"
.github/scripts/windows-package-probe.ps1:481:exit 0
.github/scripts/windows-nonempty-probe.ps1:3:# 要定案的那件事(2026-08-25,track opendesign-fresh-install-fix 的评审冲突):
.github/scripts/windows-nonempty-probe.ps1:4:#   installer/OpenDesign.nsi 的 CheckDirEmpty 挂在 MUI 目录页的 **leave 回调**上
.github/scripts/windows-nonempty-probe.ps1:23:# 🔴 同别的探针:**只报告,不判卷**。脚本自己崩了才 exit 非零;结论由主 agent 下。
.github/scripts/windows-nonempty-probe.ps1:26:    [string]$Tag    = 'win-installer-0.98.0',
.github/scripts/windows-nonempty-probe.ps1:27:    [string]$Asset  = 'OpenDesign-Setup-0.98.0.exe',
.github/scripts/windows-nonempty-probe.ps1:34:function Say([string]$k, [string]$v) { "PHASE $k : $v" }
.github/scripts/windows-nonempty-probe.ps1:48:"@ -ErrorAction SilentlyContinue
.github/scripts/windows-nonempty-probe.ps1:71:Remove-Item -Recurse -Force $Target -ErrorAction SilentlyContinue
.github/scripts/windows-nonempty-probe.ps1:81:$ip = Start-Process $setup -ArgumentList "/S /D=$Target" -PassThru
.github/scripts/windows-nonempty-probe.ps1:82:while (-not $ip.HasExited -and $sw.Elapsed.TotalSeconds -lt $WaitSec) {
.github/scripts/windows-nonempty-probe.ps1:87:if ($ip.HasExited) {
.github/scripts/windows-nonempty-probe.ps1:88:    Say '3 静默安装' "退出了 —— 退出码 $($ip.ExitCode),耗时 $([int]$sw.Elapsed.TotalSeconds)s"
.github/scripts/windows-nonempty-probe.ps1:96:$installed = Test-Path $sentinel
.github/scripts/windows-nonempty-probe.ps1:98:    $(if ($installed) { '在 —— 装进去了' } else { '不在 —— 没装进去' }),
.github/scripts/windows-nonempty-probe.ps1:99:    (Get-ChildItem $Target -Force -ErrorAction SilentlyContinue).Count)
.github/scripts/windows-nonempty-probe.ps1:102:$aliveAfterInstall = Test-Path $mine
.github/scripts/windows-nonempty-probe.ps1:103:Say '5 装完之后业主的文件' ("{0}" -f $(if ($aliveAfterInstall) {
.github/scripts/windows-nonempty-probe.ps1:110:    $u = Start-Process $uninst -ArgumentList "/S _?=$Target" -PassThru
.github/scripts/windows-nonempty-probe.ps1:112:    while (-not $u.HasExited -and $usw.Elapsed.TotalSeconds -lt 120) { Start-Sleep -Seconds 10 }
.github/scripts/windows-nonempty-probe.ps1:116:        $(if ($u.HasExited) { "退出码 $($u.ExitCode)" } else { '**没退出**' }))
.github/scripts/windows-gui-probe.ps1:9:# 🔴 这个脚本**只报告,不判卷**:它自己跑崩了才 exit 非零(=探针坏了)。
.github/scripts/windows-gui-probe.ps1:10:#    四问的答案在日志的 VERDICT 段和 probe-out/ 里的图上 —— 结论由主 agent 看图下,
.github/scripts/windows-gui-probe.ps1:74:    $proc = Start-Process powershell -PassThru -ArgumentList @(
.github/scripts/windows-gui-probe.ps1:87:    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
.github/scripts/windows-gui-probe.ps1:104:$html = '<html><body style="margin:0;background:#00FF7F"><h1 style="color:#000">OpenDesign CI probe</h1></body></html>'
.github/scripts/windows-gui-probe.ps1:111:    $eproc = Start-Process $edge -PassThru -ArgumentList @(
.github/scripts/windows-gui-probe.ps1:125:    if ($eproc -and -not $eproc.HasExited) { Stop-Process -Id $eproc.Id -Force -ErrorAction SilentlyContinue }
.github/scripts/windows-gui-probe.ps1:129:"" ; "==================== VERDICT ===================="

exec
/bin/bash -lc "sed -n '1,260p' .github/scripts/windows-package-probe.ps1" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
﻿# 真安装包探针 —— 把业主真正双击的那个 45MB 安装包搬上云 Windows 机器,
# 走完「下载 → 静默装 → 启动 → 等它活过来 → 截图 → 收日志」,再把图交出来。
#
# 它要替业主挡掉的是这一类(而不是"动画好不好看"):
#   0.89 装完打开就崩 / 0.90 窗口栏整块没画出来 / 0.93 打开全是白的
#
# 🔴 退出码的契约(2026-08-30 重写,原来那句是**假的**):
#    旧文案写"脚本自己崩了才 exit 非零",但脚本末尾没有 exit 语句 ⇒ pwsh 拿
#    **最后一个原生命令的 $LASTEXITCODE** 当脚本退出码。run 33306843034 就是这么
#    红的:第 9 相那个 python 因为打印中文炸了(见下),rc=1 泄漏出来染红整个 run,
#    而产品一点问题都没有。反过来更坏:第 10 相真喊 "🔴 FAIL" 时,只要后面没有
#    原生命令,整个 run 照样是**绿的**。
#    现在改成:**任何一相自报 FAIL ⇒ exit 1**,否则 exit 0(见文件末尾)。
#    ⚠️ 绿**不等于**产品没问题 —— 白屏体检给的是读数(颜色数 / 近白百分比),
#    判读仍然要主 agent 看图。闸只兜机器能独自断定的那几件:装机退出码、
#    配置 rc、导出 rc、端口通不通、窗口在不在、文件在不在。

param(
    [string]$Tag    = "win-installer-0.97.0",
    [string]$Asset  = "OpenDesign-Setup-0.97.0.exe",
    [string]$OutDir = "probe-out"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$InstallDir = "$env:LOCALAPPDATA\Programs\OpenDesign"
$DataRoot   = "$env:LOCALAPPDATA\OpenDesign"
$phases     = [ordered]@{}
# 🔴 应用用 `core.pick_ports([8766,…], span=20)` 挑端口,被占就往后挪(ds_shell.py:248)。
#    探针原来把 8766 写死 ⇒ 8767 上健康启动也判 FAIL(**健康假红**)。扫整段。
$PortSpan   = 8766..8786
function Say([string]$k, [string]$v) { $phases[$k] = $v; "PHASE $k : $v" }

# 🔴 **退出闸的第二条路**(2026-08-31,第六轮 panel)。
#    原来闸只有一条路:读进程内的 $phases、在里面找 "FAIL" 字样。外部评审实测出
#    两种**单点**改法,任何事故都能整趟绿:
#      · 闸前面补一行 `$phases = @{}` ⇒ 闸读到的是空的;
#      · Get-Verdict 最终 return 里多一个 `-replace "FAIL", ""` ⇒ 裁决被洗白。
#    两种改完 50 条判据全绿。**一条路的闸,改一处就没了。**
#    ⇒ 每一相的裁决**退出码**(不是那句话)另外落进 verdicts.tsv,
#      由 workflow 里**另一个文件、另一步**独立复核(见 windows-package-probe.yml)。
# 🔴 **上面那句"绕过它要同时改两个文件"是假的,2026-08-31 第七轮 panel 两条腿各自证伪。**
#    ① `Say-Verdict` 这一个函数体里改两下(先 `$script:lastRc = 0`、再把 `Say $k $v`
#       换成 `Say $k ($v -replace "FAIL","")`)⇒ 收据的 rc 列恒 0 且 $phases 里没有 FAIL
#       ⇒ **三条路一起死**。收据的 rc 和 phases 的文本都从这一个函数流过。
#    ② 闸条件 `if ($failed.Count -or $hard.Count)` 改成 `if ($false)` ⇒ 路一路二一起死。
#    两种改法当时 75 条判据全绿。已各上一条止血钉(s22)+ 变异(M79/M80)。
# 🔴 **而且三条路只覆盖 4 个相**:只有 `Say-Verdict` 的相(5/6/8/10)进 verdicts.tsv。
#    用 `Say` 的那七个相(1 下载 / 2 装机 / 3 查文件 / 3.5 配置 / 4 启动 / 7 白屏 /
#    9 导出)的 FAIL **从不落账** ⇒ 路二路三对它们完全够不着,闸仍然只有一条路。
#    "0.89 装完就崩"这类正是它们负责的场景。**这是本刀的已知缺口,进下一刀。**
#    ⚠️ 止血钉是字符串钉,**是抬门槛不是证明** —— 真正的解法见 verify.md「下一刀」。
$VerdictLog     = Join-Path $OutDir 'verdicts.tsv'
$script:lastRc  = 1        # fail-closed:没拿到裁决就当红
function Say-Verdict([string]$k, [string]$v) {
    ("{0}`t{1}`t{2}" -f $script:lastRc, $k, ($v -replace "`t", ' ')) |
        Add-Content -Path $VerdictLog -Encoding utf8
    Say $k $v
}

# 🔴 判定("机器事实 → 该不该 FAIL")**不在这个脚本里**。
#    这支脚本本机跑不了(没有 pwsh)⇒ 写在这里的判定谁都验不了,而 2026-08-30 那一晚
#    它被外部评审连打回十几次(极性、取值、守卫、终止条件、参数,每一种静态判据都全绿)。
#    ⇒ 探针只**采事实**,判定交给 bin/probe_verdict.py(纯函数,有 11 条行为判据守着)。
#    用**仓库里这一份**(和本脚本同版本),不是装出来的那份旧的。
function Get-Verdict([string]$kind, $facts) {
    $judge = Join-Path $PSScriptRoot '..\..\bin\probe_verdict.py'
    $py     = "$InstallDir\python\python.exe"
    $errLog = Join-Path $OutDir ("judge-{0}.err" -f $kind)
    $script:lastRc = 1        # 每次进来先当红,只有真拿到裁决才改写
    if (-not (Test-Path $judge)) { return "FAIL - 判定器不在:$judge" }
    if (-not (Test-Path $py))    { return "FAIL - 判定器跑不成:找不到 $py" }
    try {
        # 🔴 `-EscapeHandling EscapeNonAscii`:把中文转成 \uXXXX。
        #    不加的话,PowerShell 往原生进程写管道用的是**控制台代码页**
        #    (en-US runner = cp1252)⇒ 中文键被打坏 ⇒ 判定器一个都查不到 ⇒ **假红**。
        #    run 33321769218 就是这么红的:第 8 相说三份日志全缺席,而同一秒第 9 相
        #    导出的包里它们明明在。纯 ASCII 的 JSON 任何代码页都打不坏。
        $json = $facts | ConvertTo-Json -Depth 6 -Compress -EscapeHandling EscapeNonAscii
        # 🔴 **stdout 和 stderr 必须分开抓**。原来是 `2>&1`:判定器语法错/import 炸时
        #    traceback 全在 stderr、stdout 是空的,合并之后"输出非空" ⇒ rc=1 穿过下面的
        #    守卫 ⇒ **traceback 被当成裁决原样 Say 出去**,闸找不到 FAIL ⇒ exit 0。
        #    第 2e 轮外部评审用一个语法错的判定器逐行模拟过。**裁决只能来自 stdout。**
        $out  = $json | & $py $judge $kind 2>$errLog
        $rc   = $LASTEXITCODE
    } catch { return "FAIL - 判定器炸了:$($_.Exception.Message)" }
    $errText = if (Test-Path $errLog) { (Get-Content $errLog -Raw) } else { "" }
    if (-not $out) { return "FAIL - 判定器没有输出(rc=$rc,stderr:$errText)" }
    # 🔴 **rc 只有 0(OK)和 1(FAIL)是裁决,别的都是"判定器自己坏了"**。
    #    上面那句 `2>&1` 把 stderr 并进了 $out,所以"输出非空"根本不等于"给了裁决":
    #    判定器 import 期炸(traceback 在 stderr)、kind 分发键被改名(rc=2 + 用法串),
    #    都会变成一句没有 FAIL 的话被原样 Say 出去 ⇒ 整趟绿。第 2d 轮外部评审实测过。
    if ($rc -ne 0 -and $rc -ne 1) { return "FAIL - 判定器异常退出(rc=$rc):$out" }
    $script:lastRc = $rc
    return (("$out" -replace "`r?`n", " ").Trim())
}

function Save-Screen([string]$Path) {
    $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}

# 白屏体检:在图的中心区域采样,看颜色有多"单调"。
# 我们的界面是有颜色、有结构的;**一整块白 = 0.93 那次的形状**。
# 这不是判据,是一个能把"白屏"和"正常界面"分开的数字,给主 agent 看图时当参照。
function Test-Blankness([string]$Path) {
    $bmp = New-Object System.Drawing.Bitmap $Path
    $x0 = [int]($bmp.Width * 0.2); $x1 = [int]($bmp.Width * 0.8)
    $y0 = [int]($bmp.Height * 0.2); $y1 = [int]($bmp.Height * 0.8)
    $seen = @{}; $white = 0; $n = 0
    for ($y = $y0; $y -lt $y1; $y += 5) {
        for ($x = $x0; $x -lt $x1; $x += 5) {
            $p = $bmp.GetPixel($x, $y); $n++
            $key = "{0}-{1}-{2}" -f [int]($p.R / 16), [int]($p.G / 16), [int]($p.B / 16)
            $seen[$key] = 1
            if ($p.R -ge 235 -and $p.G -ge 235 -and $p.B -ge 235) { $white++ }
        }
    }
    $bmp.Dispose()
    return [PSCustomObject]@{
        Colors = $seen.Count
        WhitePct = [Math]::Round(100.0 * $white / $n, 1)
    }
}


# 卡住时光有截图不够 —— 弹框可能被别的窗口盖住(第二跑就是这样:装机卡住那 8 分钟里
# 屏幕上盖着 runner 自己的终端,弹框在它后面,图上一个字都看不见)。
# 所以直接问 Windows 要那个框里的**文字**:枚举它的子控件,把 text 全掏出来。
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W32 {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
  public static int Pid(IntPtr h) { int p; GetWindowThreadProcessId(h, out p); return p; }
  public static string Text(IntPtr h) {
    var sb = new StringBuilder(2048); GetWindowTextW(h, sb, 2048); return sb.ToString();
  }
  public static string Cls(IntPtr h) {
    var sb = new StringBuilder(256); GetClassNameW(h, sb, 256); return sb.ToString();
  }
}
"@ -ErrorAction SilentlyContinue

$script:dlg = @()
function Dump-Dialogs([string]$Match = 'OpenDesign') {
    $script:dlg = @()
    $ccb = [W32+EnumProc]{ param($c, $m)
        $ct = [W32]::Text($c); if ($ct) { $script:dlg += "    L $ct" }; return $true }
    $cb = [W32+EnumProc]{ param($h, $l)
        if ([W32]::IsWindowVisible($h)) {
            $t = [W32]::Text($h)
            if ($t -like "*$Match*") {
                $script:dlg += "  window: [$t]"
                [void][W32]::SetForegroundWindow($h)
                [void][W32]::EnumChildWindows($h, $ccb, [IntPtr]::Zero)
            }
        }
        return $true }
    [void][W32]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:dlg
}

$script:appwins = @()
# 「屏幕上**所有**可见的、有标题的顶层窗口」+ 每个的窗口类。
# 🔴 类名是分开"报错框"和"真窗口"的唯一可靠依据:MessageBoxW 弹的框窗口类恒为
#    `#32770`(Windows 的对话框类),而 pywebview 的主窗口不是。
#    **标题分不开** —— ds_shell.py 的 alert()/die() 用的标题就是 APP = OpenDesign。
# 🔴 **不在这里挑**(2026-08-31,第六轮 panel):原来它按标题过滤,应用名由第 6 相
#    的 `$appTitle` 传进来。外部评审实测:在 `$appTitle = 'OpenDesign'` 下面补一行
#    `$appTitle = ''`,50 条判据全绿(静态断言只看得见第一次赋值),而 `-like "**"`
#    匹配任何非空标题 ⇒ CI 机器上那个终端就顶替了我们的窗口 ⇒「界面没画出来」整趟绿。
#    ⇒ 这里**看见什么报什么**,挑哪个是我们的交给 bin/probe_verdict.py(那边跑得动,
#      s19 直接喂事实就能验)。
function Get-AllWindows {
    $script:appwins = @()
    $cb = [W32+EnumProc]{ param($h, $l)
        if ([W32]::IsWindowVisible($h)) {
            $t = [W32]::Text($h)
            if ($t) {
                $script:appwins += [PSCustomObject]@{
                    Title = $t; Class = [W32]::Cls($h); Pid = [W32]::Pid($h) }
            }
        }
        return $true }
    [void][W32]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:appwins
}

# ── 1 下载业主真正装的那个包 ──────────────────────────────────────
try {
    & gh release download $Tag --repo $env:GITHUB_REPOSITORY --pattern $Asset --dir $OutDir --clobber
    $setup = Join-Path $OutDir $Asset
    $mb = [Math]::Round((Get-Item $setup).Length / 1MB, 1)
    Say '1 下载安装包' "OK - $Asset,$mb MB"
} catch { Say '1 下载安装包' "FAIL - $($_.Exception.Message)"; throw }

# ── 2 静默安装(NSIS /S) ─────────────────────────────────────────
# 🔴 **不用 -Wait**。第一跑(32798142734)在这里挂了 15 分钟、最后被我掐掉,
#    而 -Wait 的形状是「卡住了就什么都看不见」—— 连一张能说明卡在哪的图都没有。
#    NSIS 的规矩:`/S` 只跳过安装界面,**`MessageBox` 照弹**(除非带 /SD 默认值
#    或被 IfSilent 挡住),而 installer/OpenDesign.nsi 里 4 个 MessageBox 一个都没有。
#    所以这里改成:边等边截图、边列窗口标题 —— **让"它在等谁点确定"变成看得见的**。
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $ip = Start-Process (Resolve-Path $setup) -ArgumentList '/S' -PassThru
    $tick = 0
    while (-not $ip.HasExited -and $sw.Elapsed.TotalMinutes -lt 3) {
        Start-Sleep -Seconds 45; $tick++
        Save-Screen ("{0}/2{1}-installing.png" -f $OutDir, $tick)
        $t = Get-Process | Where-Object { $_.MainWindowTitle } |
             ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
        "  [装机中 $([int]$sw.Elapsed.TotalSeconds)s] 屏幕上的窗口: $(if($t){$t -join ' | '}else{'(无)'})"
        Dump-Dialogs | ForEach-Object { $_ }
    }
    $sw.Stop()
    if ($ip.HasExited) {
        # 🔴 非零退出码就是"装失败",文案必须带 FAIL —— 否则末尾那道闸看不见它。
        $r2 = if ($ip.ExitCode -eq 0) { "退出码 0" } else { "FAIL - 退出码 $($ip.ExitCode)" }
        Say '2 静默安装' "$r2,耗时 $([int]$sw.Elapsed.TotalSeconds)s"
    } else {
        Save-Screen "$OutDir/29-installer-stuck.png"
        $t = Get-Process | Where-Object { $_.MainWindowTitle } |
             ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
        "---- 卡住时那个框里到底写的什么 ----"
        Dump-Dialogs | ForEach-Object { $_ }
        Save-Screen "$OutDir/29b-dialog-front.png"
        Say '2 静默安装' "FAIL - 3 分钟没退出,**卡住了**。屏幕上的窗口: $(if($t){$t -join ' | '}else{'(无标题窗口)'})"
        Stop-Process -Id $ip.Id -Force -ErrorAction SilentlyContinue
    }
} catch { Say '2 静默安装' "FAIL - $($_.Exception.Message)" }

# ── 3 装完了吗:查文件,不查安装器的自述 ────────────────────────────
$must = @("$InstallDir\OpenDesign.exe", "$InstallDir\python\pythonw.exe", "$InstallDir\ds\bin\ds_shell.py")
$missing = $must | Where-Object { -not (Test-Path $_) }
if ($missing) { Say '3 装完查文件' "FAIL - 少了:$($missing -join ', ')" }
else {
    $size = [Math]::Round(((Get-ChildItem $InstallDir -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 0)
    Say '3 装完查文件' "OK - 三个关键文件都在,装完 $size MB"
}

# ── 3.5 那句"配置初始化没有成功(错误码 2)"到底是什么 ────────────
# 弹框只给了错误码,**人话那一段被静默安装吞掉了**(nsExec::ExecToLog 写进
# 安装器的日志窗,而 /S 根本不开那个窗)。所以这里自己把同一条命令再跑一遍,
# 把 stderr 原样接住 —— ds_provision.py 承诺过"给业主的是人话不是栈"。
try {

exec
/bin/bash -lc "sed -n '208,330p' bin/ds_common.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
                    rel = os.path.relpath(os.path.join(base, name), legacy_root)
                    unknown.append(rel.replace(os.sep, "/"))
            if not found:
                unknown.append(top.replace(os.sep, "/") + "/")
        else:
            unknown.append(top.replace(os.sep, "/"))
    return unknown


def migrate_legacy_data(ds_root: str) -> dict:
    """当数据根已外置时,把 ds_root 下的遗留业主数据幂等搬过去。"""
    target_root = data_root(ds_root)
    report = {
        "data_root": target_root,
        "moved": [],
        "skipped": [],
        "unknown": [],
        "failed": [],
    }
    legacy_root = os.path.realpath(ds_root)
    if os.path.realpath(target_root) == legacy_root:
        return report

    for name in _LEGACY_DATA_DIRS + _LEGACY_DATA_FILES:
        source = os.path.join(legacy_root, name)
        if os.path.lexists(source):
            _move_legacy_entry(source, os.path.join(target_root, name), name, report)

    for name in _LEGACY_CONFIG_ENTRIES:
        source = os.path.join(legacy_root, "config", name)
        if os.path.lexists(source):
            _move_legacy_entry(
                source,
                os.path.join(target_root, "config", name),
                os.path.join("config", name),
                report,
            )

    report["unknown"] = _unknown_legacy_entries(legacy_root)
    _write_migration_note(target_root, report)
    return report


def _write_migration_note(data_root_path: str, report: dict) -> None:
    """把这次搬运写成一份**业主看得见**的记录。

    🔴 四审两腿同时点名:`unknown`/`skipped` 只进返回值,而生产路径只查 `failed`
    ⇒ 那张"没认识的东西"的网**没接电** —— 将来新加一种数据种类,它留在安装目录里
    被卸载删掉,而所有判据照样绿。design 3b 自己写着"搬完在日志里记一行",这就是那一行。
    """
    if not (report["moved"] or report["skipped"] or report["unknown"] or report["failed"]):
        return
    try:
        os.makedirs(data_root_path, exist_ok=True)
        with open(os.path.join(data_root_path, "迁移记录.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"—— {time.strftime('%Y-%m-%d %H:%M:%S')} 从旧位置搬运 ——\n")
            fh.write(f"搬过来 {len(report['moved'])} 项;"
                     f"同名跳过 {len(report['skipped'])} 项;"
                     f"没认识的 {len(report['unknown'])} 项;"
                     f"失败 {len(report['failed'])} 项\n")
            for label, key in (("同名跳过(旧的那份还在原处)", "skipped"),
                               ("没认识的东西(留在原处,卸载会删掉,发给我看看)", "unknown"),
                               ("失败", "failed")):
                if report[key]:
                    fh.write(f"  {label}:\n")
                    for item in report[key][:50]:
                        fh.write(f"    {item}\n")
    except OSError:
        pass


def split_due(text: str) -> tuple[str, str | None]:
    """把行尾 ⏳YYYY-MM-DD 从正文切出。无则原文返回、due=None。"""
    m = DUE_SUFFIX_RE.search(text)
    if not m:
        return text, None
    return text[:m.start()], m.group(1)


def format_due_suffix(due: str | None) -> str:
    return f" ⏳{due}" if due else ""


def section_bounds(lines: list[str], header: str) -> tuple[int, int] | None:
    """指定二级段的 (标题行下标, 段尾下标)。段尾=其后第一条 `## `/`---` 或文件末。
    段缺失返回 None。

    单一真相源:`ds_tools`(阶段历史/变更历史写侧)与 `ds_todo`(变更历史读侧)共用。
    track opendesign-note-source 把读模型搬进 ds_todo 时,这个通用扫描器一度在两个
    模块里各留了一份 —— 一件事两处定义,正是这一单要消灭的形状,所以收到这儿。
    """
    hidx = next((i for i, l in enumerate(lines) if l.startswith(header)), None)
    if hidx is None:
        return None
    end = next((j for j in range(hidx + 1, len(lines))
                if lines[j].startswith("## ") or lines[j].startswith("---")), len(lines))
    return hidx, end


def within(base: str, target: str) -> bool:
    """target 是否等于 base 或落在 base 之下。两参都必须已经 realpath。"""
    return target == base or target.startswith(base + os.sep)


def sanitize_field(value: str, ban_pipe: bool = False) -> str:
    """折叠成单行:换行/回车 → 空格;ban_pipe 时竖线 → /(不可注入字段分隔符)。"""
    s = re.sub(r"[\r\n]+", " ", value or "").strip()
    if ban_pipe:
        s = s.replace("|", "/")
    return s


def today_str(today: str | None) -> str:
    return today or date.today().isoformat()


def bump_last_updated(lines: list[str], today: str) -> None:
    """更新页脚:行首锚定、最后一处。无则不硬造(真实文件恒有;保持不删行原则)。"""
    for i in range(len(lines) - 1, -1, -1):
        if _LASTUPD_LINE_RE.match(lines[i]):
            lines[i] = f"最后更新: {today}"
            return


exec
/bin/bash -lc "sed -n '200,270p' bin/ds_provision.py" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
    note.write_text(
        "OpenDesign 聊天登录口令(第一次在聊天里输一次,之后浏览器会记住):\n\n"
        f"    {token}\n\n"
        "这台电脑上自动生成的,不用改。想换的话把这个文件删掉再重新运行安装程序即可。\n",
        encoding="utf-8")
    return note


def provision(home: Path, ds_root: Path, token: str | None, python_exe: str) -> dict:
    home.mkdir(parents=True, exist_ok=True)
    cfg_path = home / ".nanobot" / "config.json"

    # 先把"包完不完整"问清楚,再动任何文件 —— 免得产出半份配置。
    # 同一条思路的实证:S1b-r2 把"缺 ${VAR}"的检查提到起后台之前。
    if not (ds_root / "config" / TEMPLATE_NAME).is_file():
        raise Trouble(f"这份安装包不完整:找不到配置模板\n"
                      f"{ds_root / 'config' / TEMPLATE_NAME}\n请重新运行安装程序。")

    cfg = load_existing(cfg_path)
    fresh = cfg is None
    if fresh:
        cfg = default_config()

    existing = str((cfg.get("channels", {}).get("websocket", {}) or {}).get("token") or "").strip()
    if token:
        final = check_token(token)          # 显式给的:当场验,不合格立刻说
        why = "用了命令行给的口令"
    elif existing:
        final = check_token(existing)       # 业主自己设过的:原样留着
        why = "沿用已有的口令(没有改动)"
    else:
        final = new_token()
        why = "自动生成了一个口令"

    # 🔴 顺序是**先在一份临时配置上做完所有事,最后一步才原子换名**。
    # 原来是"先落盘再合并" ⇒ 合并炸了就正好留下一份"开了通道但没有工具服务"的半成品,
    # 而本模块自己写着"半份配置比没有配置更坏"(外壳会拿着它去起后台,然后死在别处)。
    # 承诺与实现对不上,是四审 subdeepseek F3 指出来的。
    set_websocket(cfg, final)
    staging = cfg_path.with_name(cfg_path.name + ".new")
    try:
        write_json(staging, cfg)
        merge_template(python_exe, ds_root, staging)
        os.replace(staging, cfg_path)
    finally:
        # 合并脚本会在目标旁边留一份 .bak-<时间戳>;临时目标的那些备份是垃圾,清掉。
        for junk in list(cfg_path.parent.glob(staging.name + ".bak-*")) + [staging]:
            try:
                junk.unlink()
            except OSError:
                pass
    note = write_token_note(home, final)

    print(f"配置就绪:{cfg_path}")
    print(f"  {'全新生成' if fresh else '在已有配置上更新'};{why}")
    print(f"  口令记在:{note}")
    return cfg


def _talk_utf8() -> None:
    """把自己的 stdout/stderr 重设成 UTF-8。

    🔴 **一句成功提示不该有能力弄死一次已经成功的合并**(2026-08-25,云机器实测
    run 32801760571)。英文 Windows 上这个进程的 stdout 是 cp1252,写不出
    "已合并"三个汉字 ⇒ `UnicodeEncodeError` ⇒ 退出码非零 ⇒ 上一层判定"合并失败"
    ⇒ 临时配置被删 ⇒ **全新的非中文 Windows 装不上,而且现象是安装程序假死**。
    配置那时其实早就写好了 —— 死的只是最后那句话。

    `errors="replace"` 是刻意的:输出通道是给人看的,**它有权难看,没权杀进程**。
    判据:tests/test_ds_provision.py 的 f1/f2。
    """

exec
/bin/bash -lc "rg -n \"update|更新|release\" web/src -g '"'!**/dist/**'"'" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
web/src/TodoPage.tsx:402:  // 闲置项目 = 已建档项目 − 有卡的 − 已被「档案 N 天没更新」独立行报过的(不重复说同一件事)。
web/src/TodoPage.tsx:663:              档案 {s.days} 天没更新(无未办结条目)
web/src/App.tsx:2:import { autoCheckEnabled, AUTO_CHECK_PREF } from "./update";
web/src/App.tsx:3:import type { UpdateInfo, UpdateState } from "./update";
web/src/App.tsx:41:const UPDATE_PREFS_KEY = "ds.prefs.update";
web/src/App.tsx:87:  // 查更新(track opendesign-in-app-update,第一刀:只查不装)
web/src/App.tsx:88:  const [updateState, setUpdateState] = useState<UpdateState>("idle");
web/src/App.tsx:89:  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
web/src/App.tsx:90:  // 自动查更新的开关(默认开)。存 localStorage,和左栏那些展开偏好同一套。
web/src/App.tsx:151:  // 工作区聊天列的连接上下文:切项目才重派生(映射更新不触发重连)。
web/src/App.tsx:172:    // projThreads 故意不入依赖:记账更新不该触发重连,只有切项目才重派生
web/src/App.tsx:226:          // 默认选中:最近更新的未交付已建档项目(设计师"手头项目");
web/src/App.tsx:232:            .sort((a, b) => (b.last_update ?? "").localeCompare(a.last_update ?? ""))[0];
web/src/App.tsx:248:  // 查更新:挂载后问一次(后端带 6 小时缓存,不会把 GitHub 问烦)。
web/src/App.tsx:251:  //    catch 现在进 done ⇒ 设置里那一行显示"查不到更新",自动查也一样。
web/src/App.tsx:257:    fetch(force ? "/api/update/check?force=1" : "/api/update/check")
web/src/App.tsx:265:        //    业主**手动点了「检查更新」**却看见和没点一样,正是本单在治的那类病。
web/src/App.tsx:272:  //    (判据 u10;手动点「检查更新」当然照旧,那是他自己按的)。
web/src/App.tsx:491:  const updateLlmKeyStatus = useCallback((st: KeyStatus) => setLlmKeyStatus(st), []);
web/src/App.tsx:506:        // 乐观更新会在失败时把界面停在错的档位上 —— 这一格宁可慢一拍,
web/src/App.tsx:524:      updateState={updateState}
web/src/App.tsx:525:      updateInfo={updateInfo}
web/src/App.tsx:647:          <LlmKeyCard initialStatus={llmKeyStatus} onStatus={updateLlmKeyStatus} />
web/src/chat/transcript.ts:6://   - reasoning_* / goal_status / session_updated / tool_hint / progress
web/src/chat/transcript.ts:52:  set_change_status: "更新了事项状态",
web/src/chat/transcript.ts:57:  set_stage: "更新了项目阶段",
web/src/workspace/CompanionColumn.tsx:126:  /** §I4:「最近更新」行点击 —— 白名单内开该文件本身,白名单外退化为开所在文件夹
web/src/workspace/CompanionColumn.tsx:406:              <div className="file-sub">最近更新</div>
web/src/workspace/Sidebar.tsx:2:import { updateLabel, downloadUrl, notesSummary, hasUpdateBadge, badgeTitle } from "../update";
web/src/workspace/Sidebar.tsx:3:import type { UpdateInfo, UpdateState } from "../update";
web/src/workspace/Sidebar.tsx:22:export type SessionItem = { key: string; title?: string; preview?: string; updated_at?: string };
web/src/workspace/Sidebar.tsx:50:  /** 查更新(track opendesign-in-app-update)。这个按钮此前**没有 onClick**,点了没反应。 */
web/src/workspace/Sidebar.tsx:51:  updateState: UpdateState;
web/src/workspace/Sidebar.tsx:52:  updateInfo: UpdateInfo | null;
web/src/workspace/Sidebar.tsx:54:  /** 自动查更新开关(默认开)。业主的机器该业主做主 —— 见 update.ts 里那段理由。 */
web/src/workspace/Sidebar.tsx:78:  onSearch, health, updateState, updateInfo, onCheckUpdate, autoCheck, onToggleAutoCheck,
web/src/workspace/Sidebar.tsx:243:                <span className="when">{relTime(s.updated_at)}</span>
web/src/workspace/Sidebar.tsx:362:            disabled={updateState === "checking"}
web/src/workspace/Sidebar.tsx:363:            title="问一次 GitHub:有没有比这台机器上更新的版本"
web/src/workspace/Sidebar.tsx:365:            <span className="lbl muted">检查更新</span>
web/src/workspace/Sidebar.tsx:367:              {updateLabel({
web/src/workspace/Sidebar.tsx:368:                state: updateState,
web/src/workspace/Sidebar.tsx:369:                info: updateInfo,
web/src/workspace/Sidebar.tsx:374:          {updateInfo?.update_available && (
web/src/workspace/Sidebar.tsx:377:              href={downloadUrl(updateInfo.release_url)}
web/src/workspace/Sidebar.tsx:381:              <span className="lbl">下载 {updateInfo.latest ?? "新版本"}</span>
web/src/workspace/Sidebar.tsx:383:                {notesSummary(updateInfo.notes) || "去发布页 ›"}
web/src/workspace/Sidebar.tsx:404:            {hasUpdateBadge(updateInfo) && (
web/src/workspace/Sidebar.tsx:405:              <span className="update-dot" title={badgeTitle(updateInfo)}> ●</span>
web/src/workspace/ChangesColumn.tsx:204:  // update_client 补(核心 create_project 空业主时不写 [[链接]]、不建 stub)。
web/src/workspace/WindowChrome.tsx:66:  //    就派过了(页面重挂、热更新),所以两条路都要走。
web/src/workspace/FolderVisibilityCard.tsx:128:          setMsg("已保存。项目列表按你的选择更新了。");
web/src/gallery.ts:21:  // 定位索引条目(POST /api/refs/update 的 ref_id)与回填备注。ws 图不在索引里,
web/src/GalleryPage.tsx:3:import { fetchFilesImages, fetchRefsData, openFolder, updateRef } from "./api";
web/src/GalleryPage.tsx:170:      await updateRef({
web/src/api.ts:14:  last_update: string | null;
web/src/api.ts:537:export async function updateRef(body: UpdateRefBody): Promise<void> {
web/src/api.ts:538:  const r = await fetch("/api/refs/update", {
web/src/app.css:2718:/* 伴随列文件区:类目行(可点=打开资源管理器)+ 最近更新 */
web/src/app.css:3187:/* 「有新版」的记号:挂在收起来的设置行上(track opendesign-in-app-update,评审 F2)。
web/src/app.css:3189:.update-dot { color: #3b82f6; font-size: 0.8em; vertical-align: middle; }
web/src/TodoRail.tsx:34:  // 「记一下 XX」,变更已写进档案,而**同一屏**的待办列表纹丝不动,要切走再切回才更新
web/src/todo.ts:283:/** 闲置项目 = 全部项目 − 有卡的 − 已在「档案 N 天没更新」独立行报过的。保持 allKeys 传入序。 */
web/src/update.ts:1:// 查更新那一行在界面上说什么(track opendesign-in-app-update,第一刀)。
web/src/update.ts:3:// 这个文件只管**措辞**,不碰网络;拿数据的是 /api/update/check。
web/src/update.ts:4:// 判据:tests/test_update_ui.mjs
web/src/update.ts:11:  update_available: boolean;
web/src/update.ts:17:  release_url: string | null;
web/src/update.ts:29:const RELEASE_URL_RE = /^https:\/\/github\.com\/SunJ1ayu\/OpenDesign\/releases\//;
web/src/update.ts:31:/** 放行本仓 releases 下的 https 地址;别的一律 null。 */
web/src/update.ts:38:export const RELEASES_PAGE = "https://github.com/SunJ1ayu/OpenDesign/releases";
web/src/update.ts:56:export function hasUpdateBadge(info: { update_available: boolean } | null | undefined): boolean {
web/src/update.ts:57:  return !!info && info.update_available === true;
web/src/update.ts:62: * 🔴 和 `updateLabel` 是**同一个组合**(有新版但后端没给版本号,评审 F-D):
web/src/update.ts:71:/** 自动查更新的开关键。默认**开**,只有业主显式关过才算关。 */
web/src/update.ts:72:export const AUTO_CHECK_PREF = "update.autoCheck";
web/src/update.ts:77: * 大模型接口。查更新给它加了一个**无条件的**外部目的地(每次打开都发)。
web/src/update.ts:84:/** 更新说明取第一句有意义的话,洗掉 markdown 记号并截断。
web/src/update.ts:86: * 后端把 release 正文整段带下来了。**取了就要用** —— 留一个"取了不显示"的字段
web/src/update.ts:159:export function updateLabel(
web/src/update.ts:165:  if (s.state === "done" && !s.info) return "查不到更新";
web/src/update.ts:172:  if (info.error) return "查不到更新";
web/src/update.ts:173:  if (info.update_available && info.latest) return `有新版 ${info.latest} ›`;
web/src/update.ts:174:  // 评审 F-D:`update_available` 为真但没版本号时,原来会掉进下面那句 ——
web/src/update.ts:177:  if (info.update_available) return "有新版 ›";

exec
/bin/bash -lc "sed -n '260,480p' .github/scripts/windows-package-probe.ps1" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
try {
    $py = "$InstallDir\python\python.exe"
    $pv = "$InstallDir\ds\bin\ds_provision.py"
    if ((Test-Path $py) -and (Test-Path $pv)) {
        $o = & $py $pv --home "$DataRoot\UserData" --ds-root "$InstallDir\ds" 2>&1
        $rc = $LASTEXITCODE
        "---- ds_provision.py 原样输出(rc=$rc) ----"
        $o | ForEach-Object { "  $_" }
        Say '3.5 配置初始化说了什么' $(if ($rc -eq 0) { "rc=0" } else { "FAIL - rc=$rc" })
    } else { Say '3.5 配置初始化说了什么' "FAIL - 找不到 python 或 ds_provision.py" }
} catch { Say '3.5 配置初始化说了什么' "FAIL - $($_.Exception.Message)" }

# ── 4 双击它(业主每天做的动作) ────────────────────────────────────
try {
    $script:launch = [Diagnostics.Stopwatch]::StartNew()
    Start-Process "$InstallDir\OpenDesign.exe" | Out-Null
    Say '4 启动' "OK - 已拉起 OpenDesign.exe"
} catch { Say '4 启动' "FAIL - $($_.Exception.Message)" }

# ── 5 它活过来了吗:问它自己的健康端点(不看窗口,看服务) ──────────────
# 🔴 **不预填**(2026-08-31):原来先把整段端口填成 $null、再让判定器从 answers 的
#    键反推"试过哪一段"。外部评审实测:把那个 $null 改成 "0"(一个字符),整段端口
#    就全"活着" ⇒ 后端死了也绿,50 条判据全绿。answers 只放**真答上来的**,
#    "试过谁"另作一个事实 $tried 交出去 —— 能被预填造出来的东西不能同时当证据。
# 🔴 **墙钟,不是次数**(2026-08-31):原来是 `for ($i = 0; $i -lt 60; $i++)`。
#    看着有上限,而真实最坏耗时 = 60 × (21 个端口 × `-TimeoutSec 2` + 3s sleep)
#    = **45 分钟**,大于 job 的 `timeout-minutes: 30` —— 那个"单轮成本"根本不在代码里。
#    后果不是"慢",是**闸走不到落账那一步**:run 33373282485 / 33373571950 两趟注入
#    在 PHASE 4 之后静默 29 分钟被超时砍掉,verdicts.tsv 从来没生成过 ⇒ 路二/路三
#    只能从"收据缺席"红,而不是从"读出 FAIL 裁决"红。而"后端起不来"正是这支探针
#    最该报出来的场景之一 —— 它在那个场景里自己先卡死。干净趟撞不到:8766 第一个
#    就应答,第一轮就 break(run 33374468524 实测 86s)。
#    ⚠️ 内层也要看表:一圈扫 21 个死端口最坏 42s,不看的话"上限 150s"是假的。
#    第 10 相当时就是这么写的(`while ($sw.Elapsed...)`)—— 这是不对称,不是设计。
$answers = @{}
$tried   = @($PortSpan)
$sw5 = [Diagnostics.Stopwatch]::StartNew()
while ($sw5.Elapsed.TotalSeconds -lt 150) {
    foreach ($p in $PortSpan) {
        if ($sw5.Elapsed.TotalSeconds -ge 150) { break }
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$p/api/health" -TimeoutSec 2
            if ($h.version) { $answers["$p"] = "$($h.version)" }
        } catch { }
    }
    if ($answers.Count) { break }
    Start-Sleep -Seconds 3
}
Say-Verdict '5 服务活了吗' (Get-Verdict 'health' @{ answers = $answers; tried = $tried })

# ── 6 窗口在不在:等 **OpenDesign 自己的**窗口出现 ─────────────────
# 🔴 2026-08-30 修:原来问的是"屏幕上有没有**任何**带标题的窗口",而 CI 机器上
#    永远有一个 WindowsTerminal ⇒ **这一相永远不会红**。这不是推的:run 33310976051
#    当场照出来 —— 那一刻 OpenDesign 的窗口根本不在列表里(41s 的截图上它才出现),
#    而这一相照样报了 OK。这恰恰是本探针存在的理由那一问(0.89 崩 / 0.91 窗口栏
#    没画出来 / 0.93 白屏),却是全脚本唯一一处**结构上不可能红**的断言。
#    改成:轮询等标题里带 OpenDesign 的那个(照第 5 相的写法),60s 没等到才 FAIL。
#    固定 sleep 8s 本来就是抽签 —— 上一趟抽中了,这一趟没抽中。
# 🔴 2026-08-30 第二处(第二轮外部评审报的):光认**标题**不够 —— ds_shell.py 的
#    alert()/die() 弹的报错框标题**就是** APP = OpenDesign,所以"后端活着 + 屏幕上
#    只剩报错框"会整趟绿,而业主眼里软件压根没打开。⇒ 还得看窗口**类**。
# 🔴 2026-08-30 第三处:**判定不在这儿了**。这一段只负责采两样事实 ——
#    `$wins`(标题含 OpenDesign 的顶层窗口 + 它们的窗口类)和 `$ours`(老口径:
#    进程主窗口标题)。"哪种算真窗口、哪种是报错框、枚举不到时怎么办"全在
#    `bin/probe_verdict.py::window_verdict`,那里有 11 条行为判据守着。
#    原因:这支脚本本机跑不了,写在这里的判定谁都验不了(那一晚被打回十几次)。
# 🔴 这一段**不许出现应用名**(2026-08-31):谁算"我们的窗口"由判定器说。
#    连**等到什么时候为止**也归它 —— 这里是全量枚举,屏幕上永远有别人的窗口
#    (CI 机器上那个终端),拿"枚举到东西了吗"当终止条件等于一秒就走人。
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 4
    $procs = @(Get-Process | Where-Object { $_.MainWindowTitle } |
               ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" })
    $wins  = @(Get-AllWindows)                                     # 看见什么报什么
    $v6 = Get-Verdict 'window' @{
        wins  = @($wins | ForEach-Object { @{
            title = $_.Title; cls = $_.Class
            # 🔴 **这个窗口属于谁**。只按标题认窗口认不出"别人家的同名窗口":业主机器上
            #    资源管理器开着 OpenDesign 这个文件夹,就是一个标题 OpenDesign、
            #    类 CabinetWClass 的窗口 ⇒ 应用只弹了报错框也会被判成 OK。
            #    这一刀先**采上来写进读数**,暂不据它判 —— 我们那个窗口的属主进程
            #    真名叫什么,等这一趟真跑打印出来再说(凭猜写规则是本项目的老坑)。
            proc = (Get-Process -Id $_.Pid -ErrorAction SilentlyContinue).ProcessName } })
        procs = $procs
    }
} while ($script:lastRc -ne 0 -and (Get-Date) -lt $deadline)
Say-Verdict '6 窗口在不在' $v6

# ── 7 截图 + 白屏体检 ─────────────────────────────────────────────
# 🔴 **一张图分不开"还在加载"和"真的白"**(0.98 那一跑:窗口开了、服务通了、
#    日志零报错,而截图整块白 —— 这两种可能当时分不开,分不开就不许挑一个说)。
#    所以隔一段拍一张,让"白不白"变成一条**随时间的曲线**:
#    一路白到底 = 真白屏(0.93 那个至今没定案的病);中途有东西了 = 我截早了。
try {
    $shots = @()
    foreach ($wait in 0, 20, 30, 30, 60) {
        if ($wait -gt 0) { Start-Sleep -Seconds $wait }
        $t = [int]$script:launch.Elapsed.TotalSeconds
        $f = "{0}/1{1}-app-{2}s.png" -f $OutDir, $shots.Count, $t
        Save-Screen $f
        $b = Test-Blankness $f
        $shots += "启动后 ${t}s: 颜色 $($b.Colors) 种 / 近白 $($b.WhitePct)%"
        "  [白屏体检] $($shots[-1])"
    }
    Say '7 截图与白屏体检' ($shots -join " | ")
} catch { Say '7 截图与白屏体检' "FAIL - $($_.Exception.Message)" }

# ── 8 把现场收走 ───────────────────────────────────────────────
# 🔴 2026-08-30 业主一句「你的机子是 linux,github 的云 windows 你不一定看得全是不是」
#    问出来的:这里原来**只收 外壳.log** —— 而 0.98.1 改的时间戳有一半在 工作台.log 上,
#    那一半在 Windows 上从没被验证过。三份一起收,别再自己给自己留盲区。
# 🔴 2026-08-30 第二处(同一轮评审):原来三份**全缺席**也只写"缺席"两个字、
#    不带 FAIL ⇒ 末尾那道闸(`-match 'FAIL'`)看不见它 ⇒ "应用根本没起来、
#    现场是空的"这种最该红的情况,整趟是绿的、构件是空的。
#    **哪几份必须有**(外壳/工作台必须、网关豁免)写在
#    `bin/probe_verdict.py::REQUIRED_LOGS` —— 这一段只采"谁在、多大"。
try {
    $present = @{}
    foreach ($n in @('外壳.log', '工作台.log', '网关.log')) {
        $log = "$DataRoot\Logs\$n"
        if (Test-Path $log) {
            Copy-Item $log "$OutDir/$n" -Force
            $present[$n] = (Get-Item $log).Length
        } else { $present[$n] = $null }
    }
    Say-Verdict '8 收日志' (Get-Verdict 'logs' @{ present = $present })
} catch { Say '8 收日志' "FAIL - $($_.Exception.Message)" }

# ── 9 托盘导出诊断:在 Windows 上真跑一遍那段代码 ────────────────────
# 🔴 同一问问出来的第二个盲区:探针不做任何交互 ⇒ 0.98.1 的**主打功能**
#    「导出本次启动诊断」在 Windows 上**一次都没跑过**。右键点托盘不好自动化,
#    但那段代码本身可以用装好的那个 python 直接跑 —— 至少证明中文文件名、
#    zip、路径这些在真 Windows 上是成立的(不能证明菜单点得动,那条留给业主)。
try {
    # 🔴 路径:python 在 $INSTDIR\python\,**不在** ds\python\(第一版写错,当场 FAIL —— 探针自己坏了)。
    #    出处:installer/OpenDesign.nsi:245 那行 ExecToLog 用的就是 "$INSTDIR\python\python.exe"。
    $py = "$InstallDir\python\python.exe"
    # 🔴 子进程的 stdout 在 Windows 上是 ANSI 代码页(en-US runner = cp1252),
    #    print 中文文件名 ⇒ UnicodeEncodeError ⇒ 这一相拿到的是栈、不是答案。
    #    仓里现成写法:bin/ds_provision.py:273 自己把流转成 utf-8(所以 3.5 相的
    #    中文一直打得出来)。这里照抄。本机已逐字符复现,见 evidence 里那份红收据。
    $code = @"
import sys, zipfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'$InstallDir\ds\bin')
import ds_diag
d = ds_diag.StartupLog(emit=lambda s: None)
out = r'$OutDir\诊断包-windows.zip'
d.export_bundle(out, app_dir=r'$DataRoot')
print('NAMES=' + '|'.join(zipfile.ZipFile(out).namelist()))
"@
    $r = & $py -c $code 2>&1
    $rc9 = $LASTEXITCODE
    $t9  = "$r" -replace "`r?`n", " "
    Say '9 托盘导出诊断(直接跑那段代码)' $(if ($rc9 -eq 0) { $t9 } else { "FAIL - rc=$rc9 $t9" })
} catch { Say '9 托盘导出诊断(直接跑那段代码)' "FAIL - $($_.Exception.Message)" }

# ── 10 带系统代理再启动一次:验 0.98.1 修的那个"软件打不开" ──────────
# 🔴 第三个盲区,而且是最要命的:CI 机器上**没有系统代理**,而业主机器上**有**
#    (跑着 VPN)。0.98.1 修的正是"就绪探针走了系统代理 ⇒ 死等 60s ⇒ 启动失败"。
#    不在这儿造一个代理,那个修复在 Windows 上就是**未验证**的。
try {
    Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    $env:HTTP_PROXY  = 'http://127.0.0.1:9'    # 9 端口没人听 = 走代理必失败
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Process "$InstallDir\OpenDesign.exe"
    $answers2 = @{}
    $tried2   = @($PortSpan)          # 同第 5 相:不预填,"试过谁"单独交出去
    while ($sw.Elapsed.TotalSeconds -lt 90) {
        Start-Sleep -Seconds 5
        foreach ($p in $PortSpan) {
            if ($sw.Elapsed.TotalSeconds -ge 90) { break }   # 同第 5 相:内层也要看表
            try {
                $h = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -UseBasicParsing `
                     -TimeoutSec 2 -Proxy $null
                if ($h.StatusCode -eq 200) { $answers2["$p"] = 'up' }
            } catch { }
        }
        if ($answers2.Count) { break }
    }
    Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Save-Screen "$OutDir/30-proxy-launch.png"
    $b2 = Test-Blankness "$OutDir/30-proxy-launch.png"
    $v10 = Get-Verdict 'health' @{ answers = $answers2; tried = $tried2 }
    Say-Verdict '10 带系统代理启动' ("{0}({1}s,颜色 {2} 种 / 近白 {3}%)" -f `
        $v10, [int]$sw.Elapsed.TotalSeconds, $b2.Colors, $b2.WhitePct)
    Copy-Item "$DataRoot\Logs\外壳.log" "$OutDir/外壳-带代理.log" -Force -ErrorAction SilentlyContinue
} catch { Say '10 带系统代理启动' "FAIL - $($_.Exception.Message)" }

Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

"" ; "==================== VERDICT ===================="
foreach ($k in $phases.Keys) { "{0,-16} {1}" -f $k, $phases[$k] }
"================================================="
"图和日志在构件里。**这段文字不是结论** —— 主 agent 看图之后才下。"

# ── 退出码:只兜"机器能独自断定"的那几件,不替人判白屏 ────────────────
# 不写这段的话,退出码 = 最后一个原生命令的 $LASTEXITCODE(见文件头)。
# 路一:各相**说出来的那句话**里有没有 FAIL(try/catch 里 Say 的 FAIL 只有这条看得见)。
$failed = @($phases.GetEnumerator() | Where-Object { $_.Value -match 'FAIL' } | ForEach-Object { $_.Key })
# 路二:判定器的**退出码**收据(那句话被洗白、或 $phases 被重播成空的,这条照样在)。
#       收据不见了本身算红 —— 探针没跑到落账那一步,不能当"没问题"。
$hard = @()
if (Test-Path $VerdictLog) {
    "" ; "---- 裁决收据 verdicts.tsv ----" ; Get-Content $VerdictLog | ForEach-Object { "  $_" }
    $hard = @(Get-Content $VerdictLog | Where-Object { $_ -like "1`t*" })
} else {
    $hard = @("(没有 verdicts.tsv:探针没跑到落账那一步)")
}
if ($failed.Count -or $hard.Count) {
    if ($failed.Count) { "🔴 自报 FAIL 的相:$($failed -join ', ')" }
    if ($hard.Count)   { "🔴 收据里的 FAIL 裁决:$($hard.Count) 条" ; $hard | ForEach-Object { "    $_" } }
    "⇒ exit 1"
    exit 1
}
"没有任何一相自报 FAIL,收据里也没有 ⇒ exit 0(**白屏读数不在闸内**,仍要看图)"

exec
/bin/bash -lc "sed -n '1,210p' web/src/update.ts; sed -n '240,280p' web/src/App.tsx; sed -n '345,390p' web/src/workspace/Sidebar.tsx" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
// 查更新那一行在界面上说什么(track opendesign-in-app-update,第一刀)。
//
// 这个文件只管**措辞**,不碰网络;拿数据的是 /api/update/check。
// 判据:tests/test_update_ui.mjs
//
// 🔴 这里唯一不能错的方向:**查不动的时候不许说「已是最新」**(判据 u3)。
//    那是把失败伪装成成功,业主会以为自己在最新版上,而他可能落后好几版。

export type UpdateInfo = {
  current: string;
  update_available: boolean;
  latest: string | null;
  asset: { name: string; url: string; size: number; digest: string | null } | null;
  notes: string;
  error: string | null;
  /** 发布页地址 —— **由 GitHub 给的**(评审 F1),不是我们拿版本号拼的。 */
  release_url: string | null;
};

export type UpdateState = "idle" | "checking" | "done";

// 🔴 评审 F1(2026-09-07,subdeepseek 抓到、我复现确认):**地址不再由我们拼。**
//
// 原来这里拿 `latest` 拼 `…/tag/win-installer-${version}`。而我修 S1 时给版本号补了零
// (`1.0` → `1.0.0`),于是业主宣布 1.0、tag 打成 `win-installer-1.0` 的那一天,
// 拼出来的是 `win-installer-1.0.0` —— **认出来了,却给一个 404 的链接**。
// 现在地址由 GitHub 在 html_url 里给,这个函数只负责**验它**:
// 界面上那个链接是要业主去点的,所以后端给什么就渲染什么是不行的。
const RELEASE_URL_RE = /^https:\/\/github\.com\/SunJ1ayu\/OpenDesign\/releases\//;

/** 放行本仓 releases 下的 https 地址;别的一律 null。 */
export function safeReleaseUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return RELEASE_URL_RE.test(url) ? url : null;
}

/** 本仓发布页 —— 编译期常量,永远打得开。 */
export const RELEASES_PAGE = "https://github.com/SunJ1ayu/OpenDesign/releases";

/** 业主要点的那个地址:验过就用它,验不过退回发布页。
 *
 * 🔴 评审 F-C:GitHub 在仓库改名/转 Org 之后会把 `html_url` 换成新 full_name,
 * 前缀闸会把它拦下 ⇒ 下载那一行**静默消失**,而"有新版"的蓝点还亮着 ——
 * 业主看见有新版,却没有任何地方可点。**闸掉一个可疑地址是对的,
 * 但不能因此把业主晾在那儿。**
 */
export function downloadUrl(url: string | null | undefined): string {
  return safeReleaseUrl(url) ?? RELEASES_PAGE;
}

/** 设置那一行要不要挂个"有新版"的记号。
 *
 * 🔴 评审 F2:那句"有新版"原来只出现在**默认收起来的**设置弹层里 ——
 * 规格写的是"软件告诉你",做出来是"你翻开菜单才看得到"。业主不会天天翻设置。
 */
export function hasUpdateBadge(info: { update_available: boolean } | null | undefined): boolean {
  return !!info && info.update_available === true;
}

/** 蓝点的悬停说明。
 *
 * 🔴 和 `updateLabel` 是**同一个组合**(有新版但后端没给版本号,评审 F-D):
 * 那边修了、这边原样拼 `${info?.latest}` ⇒ 悬停上去写着「有新版 null」。
 * 第三轮自审 MR-2 —— **一个 bug 只修一侧,就是造了一个新分叉**(判据 u19/u20 + e2e D)。
 */
export function badgeTitle(info: { latest?: string | null } | null | undefined): string {
  const v = info?.latest;
  return v ? `有新版 ${v}` : "有新版";
}

/** 自动查更新的开关键。默认**开**,只有业主显式关过才算关。 */
export const AUTO_CHECK_PREF = "update.autoCheck";

/** 要不要在打开软件时自动查一次。
 *
 * 🔴 这个开关存在的理由:这一单之前,这个软件唯一往外连的地方是业主自己配了 key 的
 * 大模型接口。查更新给它加了一个**无条件的**外部目的地(每次打开都发)。
 * 功能上没问题,但**业主的机器该业主做主** —— 给得起这个开关就该给。
 */
export function autoCheckEnabled(prefs: Record<string, boolean>): boolean {
  return prefs[AUTO_CHECK_PREF] !== false;
}

/** 更新说明取第一句有意义的话,洗掉 markdown 记号并截断。
 *
 * 后端把 release 正文整段带下来了。**取了就要用** —— 留一个"取了不显示"的字段
 * 等于假装做了这件事(S4 自审)。界面上只放得下一行,所以这里只取一行。
 */
// setext 标题的下划线(标题写在上一行,下一行整行是 === 或 ---)与分隔线。
// 🔴 第三轮评审 F1:原来只认 ATX(`# 标题`)⇒ setext 写法的标题被当正文印给业主,
//    而正文以 `---` 开头时界面上直接印一串横杠,还把"去发布页 ›"那句兜底顶掉。
//    和 submimo 补充 1 治的是同一种病,只是形态不同。
const SETEXT_UNDERLINE = /^\s*(?:=+|-+)\s*$/;
const HORIZONTAL_RULE = /^\s*([-*_=])\s*(?:\1\s*){2,}$/;
// 列表项的记号。setext 的标题必须是**段落**,而列表不是段落 ——
// GitHub 把 `- 要点` 后面紧跟的 `---` 渲染成"列表项 + 分隔线",不是标题(判据 u25)。
const LIST_ITEM = /^\s*(?:[-*+]\s|\d+[.)]\s)/;

/** 哪些行属于 setext 标题(**标题那几行 + 下划线那一行**,全都要跳)。
 *
 * 🔴 第二刀开工时补的三条(第四轮 panel 的 LOW,第一刀判"接受不改"):
 * 原来的写法是**每行各自问一句"我的下一行是不是下划线"**,于是同一个根子长出三种病:
 *   u23 管不到下划线**自己** —— `HORIZONTAL_RULE` 要求"首字符 + 至少 2 个同样的",
 *       `==` / `--` 这种两字符的下划线漏网,标题跳掉之后它自己成了"第一句有意义的话";
 *   u24 管不到标题有**好几行** —— setext 的标题是下划线上面**那一整段**,只跳最后一行,
 *       前半截照印给业主;
 *   u25 **误伤列表** —— `- 要点` 的下一行恰好是 `---` 时,业主最想看的那条要点被吞掉。
 *
 * 所以改成按**段落**看:先找下划线,再往回收它上面那一整段连续非空行。
 * 这样三条同时消失 —— 因为它们本来就是一个 bug 的三种形态。
 */
function setextRows(rows: string[]): Set<number> {
  const skip = new Set<number>();
  for (let i = 0; i < rows.length; i++) {
    if (!SETEXT_UNDERLINE.test(rows[i])) continue;
    // 往回收:下划线上面那段连续非空行。
    let start = i;
    while (start > 0 && rows[start - 1].trim() !== "") start--;
    // ⚠️ 这里曾经有一句 `if (start === i) continue;`(上面没段落就当分隔线放过)。
    //    **删掉了,而且是变异测试逼出来的**:m4 把它去掉,24 条判据一条都没红 ⇒
    //    我给它写的理由("正文以 `---` 开头那一路走的就是这里")是**假的** ——
    //    `---` 本来就被 HORIZONTAL_RULE 接住,跟这句没关系。
    //    真去量了一遍才发现它不只是多余,是**有害**:开头是两字符的 `==` / `--` 时,
    //    它让那一行漏到正文里印给业主(u23 那个 bug 换了个位置而已)。判据 u26 钉住。
    //    留这段话是因为下一个人很可能想把这个"看起来该有的"豁免加回来。
    // 段落的第一行是列表项 ⇒ 它是列表不是段落,那根 `---` 是分隔线(判据 u25)。
    if (LIST_ITEM.test(rows[start])) continue;
    for (let r = start; r <= i; r++) skip.add(r);
  }
  return skip;
}

export function notesSummary(notes: string | null | undefined, max = 80): string {
  if (!notes) return "";
  const rows = notes.split(/\r?\n/);
  const setext = setextRows(rows);
  for (let i = 0; i < rows.length; i++) {
    const raw = rows[i];
    // 🔴 跳过的依据是"**它本来就是个 markdown 标题**",不是"它以某几个词开头"。
    //    原来按开头几个词判,会把「这一版修了一个导致白屏的 bug」这种**正文**也跳掉
    //    (submimo 第二轮补充 1)。标题没信息量,正文有 —— 分界线在记号上,不在词上。
    const isAtx = /^\s*#+\s/.test(raw);
    const isSetext = setext.has(i);
    const isRule = HORIZONTAL_RULE.test(raw);
    // 标题整行跳过,所以这里**不再剥 `#`** —— 剥它反而有害:
    // 一行 `#123 修复了…`(issue 编号,不是标题)会被剥成 `123 修复了…`。
    // 红检 v6 漏网把这条照了出来:那个替换在加了 isAtx 之后已是半死代码,
    // 而半死代码里还藏着一个真 bug。
    const line = raw
      .replace(/\*\*|__|`/g, "")     // 粗体 / 行内代码
      .trim();
    if (!line) continue;
    if (isAtx || isSetext || isRule) continue;
    return line.length > max ? line.slice(0, max - 1) + "…" : line;
  }
  return "";
}

export function updateLabel(
  s: { state: UpdateState; info: UpdateInfo | null; version?: string | null },
): string {
  if (s.state === "checking") return "检查中…";
  // 评审 F3:查完了却什么都没拿到(端点 403 那条路可达),**不许长得像"还没查过"** ——
  // 那正是本单在治的"安静地错"。只有 idle 才显示版本号。
  if (s.state === "done" && !s.info) return "查不到更新";
  if (s.state === "idle" || !s.info) {
    return s.version ? `ds-web v${s.version}` : "服务离线";
  }
  const info = s.info;
  // 顺序要紧:先问"查成了没有",再问"有没有新版"。
  // 反过来写的话,一次断网就会显示成"已是最新"(判据 u3 钉的就是这个次序)。
  if (info.error) return "查不到更新";
  if (info.update_available && info.latest) return `有新版 ${info.latest} ›`;
  // 评审 F-D:`update_available` 为真但没版本号时,原来会掉进下面那句 ——
  // 于是"有新版"的蓝点亮着,而同一屏上写着"已是最新"。今天后端产生不了这个组合,
  // 但这是个未来的回归绊线,不是理论洁癖。
  if (info.update_available) return "有新版 ›";
  return `已是最新 v${info.current}`;
}
  // 服务信息:挂载一次(版本/model/ds_root 不随聊天变)
  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setHealth({ version: d.version, ds_root: d.ds_root, model: d.model ?? null }))
      .catch(() => setHealth(null));
  }, []);

  // 查更新:挂载后问一次(后端带 6 小时缓存,不会把 GitHub 问烦)。
  //
  // ⚠️ 这里原来写着"失败一律安静"—— 评审 F-A 之后那句话就成了假的(第三轮自审 MR-1):
  //    catch 现在进 done ⇒ 设置里那一行显示"查不到更新",自动查也一样。
  //    改口不是妥协:失败**不弹任何东西、不打断**,但也不装作没查过 —— 那一行本来就是
  //    业主主动翻开设置才看得见的地方,在那儿说实话不打扰谁。
  //    (能走到 catch 的只有"ds_web 自己不可达";没网是后端回 200+error,走 F3 那条路。)
  const checkUpdate = useCallback((force: boolean) => {
    setUpdateState("checking");
    fetch(force ? "/api/update/check?force=1" : "/api/update/check")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: UpdateInfo | null) => {
        setUpdateInfo(d);
        setUpdateState("done");
      })
      .catch(() => {
        // 🔴 评审 F-A:原来这里回到 idle,而 idle+null 显示的是版本号 ——
        //    业主**手动点了「检查更新」**却看见和没点一样,正是本单在治的那类病。
        //    ds_web 不可达是很窄的一条路(桌面壳里),但窄不等于可以安静。
        setUpdateInfo(null);
        setUpdateState("done");
      });
  }, []);
  // 🔴 关掉之后就**一次都不许自动发** —— 这是业主对自己机器往外连什么的决定权
  //    (判据 u10;手动点「检查更新」当然照旧,那是他自己按的)。
  useEffect(() => {
    if (autoCheck) checkUpdate(false);
  }, [autoCheck, checkUpdate]);

  const toggleAutoCheck = useCallback(() => {
    setAutoCheck((prev) => {
      const next = !prev;
      try {
                + "读走那边的资料,而你不会看到任何提示。\n\n确定要关掉吗?")) return;
              onSetConsentMode(next);
            }}
          >
            <span className="lbl">危险动作确认</span>
            <span className="val">
              {consentMode === null ? "…"
                : consentMode === "ask" ? "每次问我 ›" : "不用问 ›"}
            </span>
          </button>
          <button className="item" title="⌘N 新对话 · ⌘K 搜索">
            <span className="lbl">快捷键</span>
          </button>
          <div className="divider" />
          <button
            className="item"
            onClick={onCheckUpdate}
            disabled={updateState === "checking"}
            title="问一次 GitHub:有没有比这台机器上更新的版本"
          >
            <span className="lbl muted">检查更新</span>
            <span className="val mono faint">
              {updateLabel({
                state: updateState,
                info: updateInfo,
                version: health ? health.version : null,
              })}
            </span>
          </button>
          {updateInfo?.update_available && (
            <a
              className="item"
              href={downloadUrl(updateInfo.release_url)}
              target="_blank"
              rel="noreferrer"
            >
              <span className="lbl">下载 {updateInfo.latest ?? "新版本"}</span>
              <span className="val faint">
                {notesSummary(updateInfo.notes) || "去发布页 ›"}
              </span>
            </a>
          )}
          <button className="item" onClick={onToggleAutoCheck}>
            <span className="lbl muted">打开时自动检查</span>
            <span className="val">{autoCheck ? "开 ›" : "关 ›"}</span>
          </button>

exec
/bin/bash -lc 'git diff --stat; git diff --cached --stat' in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
 tests/test_ds_update.py                            |   66 +
 tests/test_update_ui.mjs                           |   11 +
 .../opendesign-in-app-update-install/decision.json |    2 +-
 .../evidence/dualplan-gpt56sol.md                  | 7721 +++++++++++++++++++-
 web/src/update.ts                                  |   40 +-
 5 files changed, 7836 insertions(+), 4 deletions(-)
 tests/test_update_ui.mjs                           |  28 +++
 ...0260908T110326Z-01-red-u23-u25-notes-setext.txt | 212 +++++++++++++++++++++
 .../evidence/dualplan-gpt56sol.md                  |   9 +
 3 files changed, 249 insertions(+)

exec
/bin/bash -lc "nl -ba bin/ds_update.py | sed -n '1,240p'" in /root/.openclaw/workspace/projects/design-studio
exec
/bin/bash -lc "nl -ba installer/OpenDesign.nsi | sed -n '35,175p'; nl -ba installer/OpenDesign.nsi | sed -n '235,295p'" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 22ms:
     1	#!/usr/bin/env python3
     2	"""查更新:问一次 GitHub,答"线上有没有比我新的版本"(track opendesign-in-app-update)。
     3	
     4	这个模块**只查不装**。装是第二刀的事,住在别处。
     5	
     6	🔴 **写这个文件的人必须知道的一件事**(2026-09-07 实测,判据 t1/t1b 钉着):
     7	
     8	    GET /repos/SunJ1ayu/OpenDesign/releases/latest  →  404 Not Found
     9	
    10	那个接口**按 GitHub 的设计跳过 prerelease**,而本仓至今 **20 个 release 全是 prerelease**。
    11	所以这里必须用 `/releases`(列表,含预发布)**自己挑**。改回那个"标准接口"的后果不是报错,
    12	是**功能永远查不到新版本、界面永远显示"已是最新"** —— 一条恒绿路径,比没有更新功能更坏。
    13	
    14	信任根就一条:**HTTPS 到 github.com**。资产的 sha256 由 GitHub 在 `digest` 字段里给
    15	(实测与我们发版时记的那串一致),它挡得住"下坏了/下了半截/被中间人换了包",
    16	**挡不住"GitHub 账号被盗后换了资产"** —— 我们没有代码签名证书,这是明账,不假装有。
    17	"""
    18	from __future__ import annotations
    19	
    20	import json
    21	import re
    22	import threading
    23	import time
    24	import urllib.request
    25	
    26	REPO = "SunJ1ayu/OpenDesign"
    27	API_BASE = "https://api.github.com"
    28	# 故意拼出来而不是写成一整串:t1b 那道结构闸扫的是本文件的源码。
    29	RELEASES_PATH = "/repos/{repo}/releases"
    30	# 版本号=**2~4 段数字**。单段不算(会撞上一堆随便的数字),形状必须整段吻合。
    31	# 🔴 收两段是 S1 自审改的:原来只认三段,业主哪天宣布 1.0、tag 打成 `win-installer-1.0`,
    32	#    那一版在更新检查里就**根本不存在,而且一声不吭** —— 和本单开头那个
    33	#    /releases/latest 404 是同一种病。web/src/update.ts 的 releasePageUrl 与这里同口径。
    34	_NUM = r"\d+(?:\.\d+){1,3}"
    35	ASSET_RE = re.compile(rf"^OpenDesign-Setup-({_NUM})\.exe$")
    36	TAG_RE = re.compile(rf"^win-installer-({_NUM})$")
    37	BARE_RE = re.compile(rf"^({_NUM})$")
    38	TIMEOUT_S = 10
    39	
    40	
    41	def parse_version(text):
    42	    """认三种写法:`0.98.3` / `win-installer-0.98.3` / `OpenDesign-Setup-0.98.3.exe`。
    43	
    44	    整段吻合才算,**不做"从一串字里捞个版本号出来"** —— 那样 `0.98.x` 会被捞成 0.98,
    45	    而它其实是个坏版本号。
    46	
    47	    取不出来返回 None —— **绝不抛**。读不出版本号是"我不知道",不是"出事了":
    48	    上层遇到 None 一律不提示更新(判据 t3d)。
    49	    """
    50	    if not isinstance(text, str):
    51	        return None
    52	    t = text.strip()
    53	    for rx in (BARE_RE, TAG_RE, ASSET_RE):
    54	        m = rx.match(t)
    55	        if m:
    56	            parts = [int(n) for n in m.group(1).split(".")]
    57	            # 补零到三段:`0.98` 和 `0.98.0` 是同一版,不是前者更小(判据 t2g)。
    58	            while len(parts) < 3:
    59	                parts.append(0)
    60	            return tuple(parts)
    61	    return None
    62	
    63	
    64	def _installer_asset(release):
    65	    """挑出这个 release 里那个业主真正双击的安装包;没有就 None。
    66	
    67	    没有安装包的 release 不是"可更新到的版本" —— 选中它等于把业主指向一个下不动的东西
    68	    (判据 t1c)。
    69	    """
    70	    for asset in release.get("assets") or []:
    71	        if not isinstance(asset, dict):
    72	            continue
    73	        if ASSET_RE.match(asset.get("name") or ""):
    74	            return asset
    75	    return None
    76	
    77	
    78	def release_version(release):
    79	    """一个 release 代表哪一版:先看 tag,tag 认不出再看安装包文件名。"""
    80	    if not isinstance(release, dict):
    81	        return None
    82	    return (parse_version(release.get("tag_name"))
    83	            or parse_version((_installer_asset(release) or {}).get("name")))
    84	
    85	
    86	def pick_latest(releases):
    87	    """从 `/releases` 的响应里挑出最新的**可安装**版本。
    88	
    89	    **预发布算数**(见文件头);草稿不算(业主下不到,判据 t1d);
    90	    没有安装包资产的不算(判据 t1c)。
    91	    """
    92	    best = None
    93	    best_ver = None
    94	    for rel in releases or []:
    95	        if not isinstance(rel, dict) or rel.get("draft"):
    96	            continue
    97	        if _installer_asset(rel) is None:
    98	            continue
    99	        ver = release_version(rel)
   100	        if ver is None:
   101	            continue
   102	        if best_ver is None or ver > best_ver:
   103	            best, best_ver = rel, ver
   104	    return best
   105	
   106	
   107	def decide(current, releases):
   108	    """给定"我现在是哪一版"和线上列表,答"要不要提示业主更新"。
   109	
   110	    只在**线上严格比本地新**时才提示:相等不提示,本地更新也不提示
   111	    (开发机上本地永远比线上新,那时提示"更新"其实是往回装 —— 判据 t3b)。
   112	    """
   113	    out = {"current": current, "update_available": False, "latest": None,
   114	           "asset": None, "notes": "", "error": None, "release_url": None}
   115	    here = parse_version(current)
   116	    if here is None:
   117	        out["error"] = "读不出本机版本号,不提示更新"
   118	        return out
   119	    rel = pick_latest(releases)
   120	    if rel is None:
   121	        out["error"] = "线上没有可安装的版本"
   122	        return out
   123	    there = release_version(rel)
   124	    out["latest"] = ".".join(str(n) for n in there)
   125	    if there <= here:
   126	        return out
   127	    asset = _installer_asset(rel)
   128	    out["update_available"] = True
   129	    out["notes"] = rel.get("body") or ""
   130	    # 🔴 F1(评审抓到、我复现确认):**地址由 GitHub 给,不许我们拿版本号拼**。
   131	    #    我修 S1 时给版本号补了零(1.0 → 1.0.0),界面拿 latest 去拼就成了
   132	    #    `win-installer-1.0.0` —— 而真实 tag 是 `win-installer-1.0`,点开 404。
   133	    #    认出来了却给一个打不开的链接,又一条"看起来在工作"。
   134	    out["release_url"] = rel.get("html_url")
   135	    out["asset"] = {
   136	        "name": asset.get("name"),
   137	        "url": asset.get("browser_download_url"),
   138	        "size": asset.get("size") or 0,
   139	        # "sha256:<hex>" —— GitHub 自己给的,第二刀下载完拿它对。
   140	        "digest": asset.get("digest"),
   141	    }
   142	    return out
   143	
   144	
   145	def releases_url(repo=REPO):
   146	    """要问的那个地址,**逐字节可断言**(判据 t11)。
   147	
   148	    评审 F5 指出:t1b 那道 AST 闸只咬"一整条字符串里含 releases/latest",
   149	    把 `/latest` 拆成另一个字面量拼上去,t1 和 t1b 都躲得过。
   150	    ⇒ 与其扫源码,不如直接断言拼出来的结果是什么。
   151	    """
   152	    return API_BASE + RELEASES_PATH.format(repo=repo) + "?per_page=100"
   153	
   154	
   155	def fetch_releases(repo=REPO, timeout=TIMEOUT_S):
   156	    """唯一碰网络的函数。判据一律注入替身,不打真网(2026-08-10 那次事故立的规矩)。"""
   157	    url = releases_url(repo)
   158	    req = urllib.request.Request(url, headers={
   159	        "Accept": "application/vnd.github+json",
   160	        "User-Agent": "OpenDesign-updater",
   161	    })
   162	    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (常量 https)
   163	        return json.loads(resp.read().decode("utf-8"))
   164	
   165	
   166	def check_for_update(current, fetch=None):
   167	    """查一次。**任何异常都不许漏出去** —— 查更新失败是小事,把一坨栈甩给业主是大事。
   168	
   169	    ⚠️ 名字不叫 `check`:`tests/dead_assertions.py` 把**任何叫 `check(` 的调用**当成断言
   170	    (测试里常见的自定义断言助手),撞名会让那道闸对我的判据发出误报。
   171	    2026-09-07 实测撞过一次,改名比削弱那道闸便宜得多。
   172	
   173	    `fetch=None` 时到**调用那一刻**才去取 `fetch_releases`。默认参数在 def 那一刻就固化了,
   174	    那样判据里替换 `ds_update.fetch_releases` 根本不生效,离线判据会悄悄变成真去打网
   175	    (判据 t9d 钉的就是这件事)。
   176	    """
   177	    try:
   178	        releases = (fetch or fetch_releases)()
   179	    except Exception as exc:  # noqa: BLE001 —— 故意兜底,判据 t7d 就是钉它
   180	        return {"current": current, "update_available": False, "latest": None,
   181	                "asset": None, "notes": "", "release_url": None,
   182	                "error": f"查更新失败:{exc.__class__.__name__}: {exc}"}
   183	    if isinstance(releases, str):
   184	        try:
   185	            releases = json.loads(releases)
   186	        except Exception:  # noqa: BLE001
   187	            return {"current": current, "update_available": False, "latest": None,
   188	                    "asset": None, "notes": "", "release_url": None,
   189	                    "error": "查更新失败:线上返回的不是 JSON"}
   190	    if not isinstance(releases, list):
   191	        return {"current": current, "update_available": False, "latest": None,
   192	                "asset": None, "notes": "", "release_url": None,
   193	                "error": "查更新失败:线上返回的不是版本列表"}
   194	    try:
   195	        return decide(current, releases)
   196	    except Exception as exc:  # noqa: BLE001
   197	        return {"current": current, "update_available": False, "latest": None,
   198	                "asset": None, "notes": "", "release_url": None,
   199	                "error": f"查更新失败:{exc.__class__.__name__}: {exc}"}
   200	
   201	
   202	# ── 缓存 ────────────────────────────────────────────────────────────────────
   203	# 未登录的 GitHub API 每小时 60 次。每开一次界面、每点一下都真去问,业主很快会被限流,
   204	# 而限流的样子恰恰是"查不到新版本" —— 一条安静的错。
   205	#
   206	# 🔴 方向必须写死:**失败不许进缓存**(判据 t8d)。一次断网如果把"查不到"钉死 6 小时,
   207	#    业主点「检查更新」也没反应,他看到的和"功能坏了"一模一样。
   208	CACHE_TTL_S = 6 * 3600
   209	_cache_lock = threading.Lock()
   210	_cache = {}  # {缓存键: (时刻, 结果)}
   211	
   212	
   213	def _cache_key(current):
   214	    """按**本机版本号**分键:装完新版之后旧答案立刻作废(判据 t8e,变异 m12 咬这一行)。
   215	
   216	    单独抽成一个函数不是为了好看 —— 是为了让"按什么分键"这件事**在一处可判**:
   217	    读和写都走它,红检改这一行就能表达"不按版本分键了",不用改两处。
   218	    """
   219	    return current
   220	
   221	
   222	def cache_clear():
   223	    with _cache_lock:
   224	        _cache.clear()
   225	
   226	
   227	def check_cached(current, fetch=None, now=time.time, force=False, ttl=None):
   228	    """带缓存地查一次。`force=True` 是业主亲手点了「检查更新」—— 那一下必须真去问。"""
   229	    ttl = CACHE_TTL_S if ttl is None else ttl
   230	    t = now()
   231	    if not force:
   232	        with _cache_lock:
   233	            hit = _cache.get(_cache_key(current))
   234	        if hit and t - hit[0] < ttl:
   235	            return hit[1]
   236	    result = check_for_update(current, fetch=fetch)
   237	    if not result.get("error"):
   238	        with _cache_lock:
   239	            _cache[_cache_key(current)] = (t, result)
   240	    return result

exec
/bin/bash -lc "nl -ba bin/ds_shell.py | sed -n '45,200p'; nl -ba bin/ds_shell.py | sed -n '234,375p'; nl -ba bin/ds_shell.py | sed -n '1100,1190p'; nl -ba bin/ds_shell.py | sed -n '1288,1388p'" in /root/.openclaw/workspace/projects/design-studio
exec
/bin/bash -lc "nl -ba bin/ds_web.py | sed -n '80,105p'; nl -ba bin/ds_web.py | sed -n '910,930p'; nl -ba bin/ds_web.py | sed -n '1020,1045p'; nl -ba bin/ds_web.py | sed -n '2585,2620p'" in /root/.openclaw/workspace/projects/design-studio
 succeeded in 0ms:
    45	SHELL_MARK = "shell=1"
    46	
    47	
    48	def window_url(port: int) -> str:
    49	    """外壳打开的那个地址。**唯一来源** —— 开窗口和写日志都叫它。
    50	
    51	    分开写两遍的代价已经付过一次:日志里印的地址少了标记,而那份
    52	    `外壳.log` 正是业主报"没按钮"时我唯一的现场。
    53	    (判据 x10 直接调它,不是去源码里 grep 字面量。)
    54	    """
    55	    return f"http://127.0.0.1:{port}/?{SHELL_MARK}"
    56	
    57	
    58	# 锁位挑在一段不常用的高位端口上。它只是锁 + 唤醒通道,不承载数据。
    59	LOCK_PORT = 18788
    60	# 首选端口沿用现有部署(docs/install-windows.md / start.ps1),被占了会自动往后挪。
    61	PREFERRED = {"gateway": 18790, "ws": 8765, "web": 8766}
    62	
    63	
    64	# ---------------------------------------------------------------- 报错与日志
    65	def _app_dir() -> Path:
    66	    """这个软件在业主机器上自己的目录。日志和实验开关都住这儿。"""
    67	    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP
    68	
    69	
    70	def _log_path() -> Path:
    71	    d = _app_dir() / "Logs"
    72	    d.mkdir(parents=True, exist_ok=True)
    73	    return d / "外壳.log"
    74	
    75	
    76	# ── 窗口动画开关(0.96.0 起**默认开**)──────────────────────────────
    77	# 0.94/0.95 这里默认是**关**的,业主一句话点破了那个决定的自相矛盾:
    78	#   「你为什么不直接给我做好动画的,要默认关闭动画」
    79	# —— 我给 0.95 装了"不对就自动退回去"的保险,却又不敢依赖它。
    80	#   要么保险可信、就该默认开;要么不可信、就不该把它当卖点。
    81	#   我选了对自己最安全、对业主最麻烦的那一半:风险我躲了,力气他出。
    82	#
    83	# 而且 0.95 之后**「打开就白」在结构上已经没了**:开窗口时一个边框动作都不做,
    84	# 方案 B 要等业主点缩小才装 ⇒ 就算真把画面搞坏,**重开软件就是好的**,
    85	# 不像 0.93 那样一起来就是砖。既然最坏情况已经从"砖"降到"重开一下",
    86	# 就没有理由再让业主自己去建文件。
    87	DISABLE_FLAG = "关掉窗口动画.on"
    88	
    89	
    90	def frame_animation_on() -> bool:
    91	    """要不要接系统窗口框架(缩小/放大的动画靠它)。**默认开。**
    92	
    93	    不想要就在 `%LOCALAPPDATA%\\OpenDesign\\` 里新建一个空文件,
    94	    名字叫 `关掉窗口动画.on`,重开软件即可。删掉它就回到默认。
    95	
    96	    🔴 **读不到环境时倒向"关"**(判据 f4 守着 except 必须 `return False`)。
    97	    方向仍然是有讲究的,只是理由换了:这个逃生门是给"已经发现它坏了"的人用的。
    98	    读不出文件系统时,把"可能已经关过"当成"关过"——
    99	    让一个本来没事的人少一段动画(小),好过让一个已经被坑过的人再被坑一次(大)。
   100	    """
   101	    try:
   102	        return not (_app_dir() / DISABLE_FLAG).is_file()
   103	    except Exception:
   104	        return False
   105	
   106	
   107	def log(msg: str) -> None:
   108	    """带时间戳写一行。
   109	
   110	    🔴 时间戳是 08-14 那次真机红补上的:那份日志没有时间,于是「一起来就崩」和
   111	    「等满 300s 超时」在事后长得一模一样,只能回头问业主等了多久。
   112	    证据要自带能对账的东西 —— 一个 strftime 换的是一趟真机。
   113	
   114	    🔴 2026-08-30(判据 s1):**补上日期** —— 上面那笔账只还了一半。
   115	    业主 08-25 晚白屏、08-30 才回话,中间那几行属于哪一天,只有时分秒的日志答不了。
   116	    续行缩进由 stamp 长度算出来,不写死数字(写死的那种迟早和格式对不上)。
   117	    """
   118	    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
   119	    pad = " " * (len(stamp) + 1)
   120	    try:
   121	        with _log_path().open("a", encoding="utf-8") as f:
   122	            for i, line in enumerate(msg.rstrip().splitlines() or [""]):
   123	                # 多行文案(弹窗那种)只给第一行盖戳,其余缩进对齐 —— 免得每行都盖,
   124	                # 反而看不出哪里是一条记录的开头。
   125	                f.write(f"{stamp} {line}\n" if i == 0 else f"{pad}{line}\n")
   126	    except OSError:
   127	        pass
   128	
   129	
   130	def web_ready_probe(port: int) -> bool:
   131	    """工作台"就绪"的真正含义:`/api/health` 应答得了。
   132	
   133	    🔴 **fail-closed**:任何异常都当成"还没就绪"。反过来写(拿不到就当好了)
   134	    正是这个项目栽过的 fail-open 形状 —— 那样探针活着也等于没有。
   135	
   136	    🔴 **绝不能走系统代理**(判据 s13;2026-08-30 四审孤腿 BLOCK 抓到、我实测坐实)。
   137	    `urllib.request.urlopen` 对 127.0.0.1 **不绕过**代理:`proxy_bypass('127.0.0.1')`
   138	    就是 False,而 Windows 上 `ProxyOverride` 里的 `<local>` 只匹配无点主机名。
   139	    于是凡是配了系统代理的机器(公司代理、**以及 Clash 那类会设系统代理的 VPN 客户端**)
   140	    上,这个探针对**健康**的工作台一律返回 False ⇒ `_wait_ready` 死等到 60s 超时
   141	    ⇒ `StartupFailed` ⇒ **软件根本打不开**。
   142	    观测层绝不能成为新的故障源 —— 这条红线是本单自己写的,第一版亲手违反了它。
   143	    ⇒ 显式装一个空 `ProxyHandler`,任何环境里都直连。
   144	    """
   145	    import urllib.request
   146	    try:
   147	        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
   148	        with opener.open(
   149	                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:
   150	            return r.status == 200
   151	    except Exception:
   152	        return False
   153	
   154	
   155	# 这一次启动的证据链。**在模块导入时就建**,不是在 main() 里 —— 那样 t0 才贴着
   156	# 进程真正的起点(import 本身也可能慢,那段时间也该被量到)。
   157	# 白屏和"打开好慢"都靠它留下的东西查(track opendesign-startup-observability)。
   158	DIAG = ds_diag.StartupLog(emit=log)
   159	
   160	
   161	def alert(msg: str, title: str = APP) -> None:
   162	    """弹一个系统对话框。业主没有终端,这是唯一能被看见的出口。"""
   163	    log(f"[提示] {msg}")
   164	    try:
   165	        ctypes.windll.user32.MessageBoxW(None, msg, title, 0x10)  # MB_ICONERROR
   166	    except Exception:
   167	        print(msg, file=sys.stderr)
   168	
   169	
   170	def die(msg: str) -> None:
   171	    alert(msg)
   172	    sys.exit(1)
   173	
   174	
   175	# ---------------------------------------------------------------- 路径
   176	def install_root() -> Path:
   177	    """包根:里面有 python\\ 和 ds\\。本文件在 <root>\\ds\\bin\\ 下。"""
   178	    return HERE.parent.parent
   179	
   180	
   181	def user_home() -> Path:
   182	    """业主数据目录 —— **安装目录之外**(design:卸载/回滚不许碰数据)。
   183	
   184	    这里同时是子进程眼里的 HOME/USERPROFILE,所以 nanobot 读的是
   185	    <user_home>\\.nanobot\\config.json,而不是业主机器上原来那份。
   186	    """
   187	    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "UserData"
   188	    d.mkdir(parents=True, exist_ok=True)
   189	    return d
   190	
   191	
   192	def python_exe() -> Path:
   193	    return install_root() / "python" / "python.exe"
   194	
   195	
   196	def key_file(home: Path) -> Path:
   197	    """机主自备的 LLM key 放在哪儿(deploy-security D1:部署者不发 key)。
   198	
   199	    路径与现有部署一致(ds-nanobot.ps1:20),只是 USERPROFILE 换成了应用自己的数据目录。
   200	    **报错文案要把这个路径原样念给业主听**,所以它得是个能被引用的单一来源。
   234	def start_backend(home: Path, lock_port: int | None = None):
   235	    """挑端口 → 改配置 → 按计划拉起后台。返回 (supervisor, web_port, restart_gateway)。
   236	
   237	    **缺 key 不再是死路**(track opendesign-key-onboarding):界面无条件起,
   238	    网关等着 —— 业主要在界面里填 key,而那个界面正是 ds-web 发的。
   239	    填完之后 ds-web 通过锁通道回来叫 `restart_gateway`。
   240	    这一层只剩接线,"起哪几条"由 core.startup_plan 判(判据 d1/d2 咬着)。
   241	    """
   242	    cfg = home / ".nanobot" / "config.json"
   243	    if not cfg.exists():
   244	        die(f"还没装好:找不到配置文件\n{cfg}\n\n请重新运行安装程序。")
   245	
   246	    try:
   247	        gw, ws, web = core.pick_ports(
   248	            [PREFERRED["gateway"], PREFERRED["ws"], PREFERRED["web"]], span=20)
   249	    except core.PortBusy as e:
   250	        die(f"找不到可用的端口:{e}\n\n多半是有别的程序占着这几段端口,重启电脑再试一次。")
   251	
   252	    try:
   253	        core.patch_config(cfg, gateway_port=gw, ws_port=ws, python_exe=str(python_exe()),
   254	                          data_root=core.data_root_for(str(home)))
   255	    except core.ConfigUnusable as e:
   256	        die(f"配置没法用:{e}\n\n请重新运行安装程序。")
   257	    except OSError as e:
   258	        die(f"写配置失败:{e}")
   259	
   260	    def build_env():
   261	        """每次都**现读** key 和配置:重启网关那一下走的就是这里,
   262	        读到的必须是业主刚填进去的那份,不是启动时缓存的。"""
   263	        key = read_key(home)
   264	        key_var = None
   265	        if key:
   266	            try:
   267	                with cfg.open("r", encoding="utf-8") as f:
   268	                    key_var = ds_credential.env_var_name(json.load(f))
   269	            except (OSError, ValueError, ds_credential.CredentialError) as e:
   270	                die(f"配置里没写清楚 key 该放进哪个变量({e})。\n\n请重新运行安装程序。")
   271	        # 🔴 **key 只进网关那条腿**(core.service_envs)。上一版把同一份 env 给了
   272	        #    两条腿,ds-web 也拿到 key ⇒ status() 把外壳自注入误判成"外部遮蔽" ⇒
   273	        #    装好的应用重启后,设置里改 key 的卡片永久只读,还让业主去清一个他
   274	        #    从没设过的变量。(2026-08-16 四审 BLOCK,判据 J 组钉住。)
   275	        return key, core.service_envs(
   276	            dict(os.environ), ds_root=str(install_root() / "ds"), user_home=str(home),
   277	            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)
   278	
   279	    key, envs = build_env()
   280	
   281	    # 🔴 08-14 业主真机红出来的那一条,别再写回去:
   282	    # 上一版这里只 log 一句「没找到 key.txt,聊天会连不上大模型」就继续往下走,理由是
   283	    # 「业主可能只是想看看待办,ds-web 是只读的、不需要 key」。**那句话是假的** ——
   284	    # 配置里 "apiKey": "${DS_LLM_KEY}",nanobot 解析到没设的 ${VAR} 就整个拒绝启动,
   285	    # 于是业主等来的是网关的一句英文 `Environment variable … is not set`。
   286	    # (tests/test_ds_shell_core.py H5 真起了一次网关把这件事钉死,别再靠注释。)
   287	    # 所以现在:起任何后台之前先扫一遍配置,缺什么当场说清楚、说该往哪儿放。
   288	    plan = core.startup_plan(has_key=bool(key))
   289	
   290	    # 缺 key **不再是错误**,是"该去填了" ⇒ 只有真要起网关时才拦缺变量。
   291	    # (没有这个 if,业主永远走不到引导页:网关会死在缺变量上,而这一层直接 die。)
   292	    if "网关" in plan["start"]:
   293	        try:
   294	            with cfg.open("r", encoding="utf-8") as f:
   295	                # 拿**网关那条腿**的 env 去比,不是别的:key 只进它(service_envs),
   296	                # 拿 ds-web 那份去比会说"DS_LLM_KEY 没设",而它本来就不该有。
   297	                # (08-16 业主真机:这里写的是已经不存在的 `env` —— 有 key 的机器
   298	                #  每次开机 NameError。判据 tests/test_shipped_names.py 咬着。)
   299	                missing = core.missing_env_refs(json.load(f), envs["网关"])
   300	        except (OSError, ValueError) as e:
   301	            die(f"配置读不出来:{e}\n\n请重新运行安装程序。")
   302	        # 说什么话在 core 里(判据 H6~H9 咬着);这一层只剩"有就弹"。
   303	        trouble = core.missing_env_message(missing, app=APP, key_path=str(key_file(home)))
   304	        if trouble:
   305	            die(trouble)
   306	
   307	    # 🔴 迁移必须在**起任何服务之前**(判据 h3)。网关是第一个起来的,它带着三个 MCP
   308	    # 工具服务;老版本装过的机器上,档案还躺在安装目录里,而新的数据根是空的 ——
   309	    # 那一刻业主问"我有哪些项目",助手会回"一个都没有",甚至在新根里建一个重名的。
   310	    # ds_web 自己也会迁移一次(幂等),但它是**第二个**起来的,来不及。
   311	    try:
   312	        migration = core.prepare_data_root(user_home=str(home),
   313	                                           ds_root=str(install_root() / "ds"))
   314	    except ds_common.DataRootError as exc:
   315	        die(f"数据目录不可用({exc})。\n\n请重新运行安装程序。")
   316	    if migration["failed"]:
   317	        die(f"你的资料从旧位置搬过来时出错了,先没有继续启动:\n{migration['failed']}\n\n"
   318	            f"把这段发给我看看 —— 东西还在原处,没有丢。")
   319	
   320	    logs = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "Logs"
   321	
   322	    def gateway_service(e):
   323	        return core.Service(name="网关", argv=[str(python_exe()), "-m", "nanobot", "gateway"],
   324	                            env=e, ready_port=ws, log_path=logs / "网关.log",
   325	                            # 冷启动要连 3 个 MCP 子进程,S0 真机上见过接近 4 分钟
   326	                            ready_timeout=300)
   327	
   328	    def web_service(e):
   329	        return core.Service(name="工作台", argv=[str(python_exe()),
   330	                                                 str(install_root() / "ds" / "bin" / "ds_web.py")],
   331	                            env=e, ready_port=web, log_path=logs / "工作台.log",
   332	                            # 🔴 2026-08-30(判据 s11):就绪 = **它真的应答了**,
   333	                            #    不是"端口有人监听"。`ready_probe` 这个机制一直都在,
   334	                            #    只是工作台从没接上 ⇒ 时间线里的"后端就绪"是半真话,
   335	                            #    而整条启动耗时都建在这句话上面。
   336	                            ready_probe=web_ready_probe,
   337	                            ready_timeout=60)
   338	
   339	    # plan 里那两个名字是 core 的说法("ds-web"/"网关");Service 名是业主看得见的
   340	    # 中文名("工作台"),watchdog 和报错都用它。别把两套名字混着用。
   341	    services = (([gateway_service(envs["网关"])] if "网关" in plan["start"] else [])
   342	                + [web_service(envs["ds-web"])])
   343	
   344	    sup = core.Supervisor()
   345	    try:
   346	        sup.start(services)
   347	    except core.StartupFailed as e:
   348	        sup.shutdown()
   349	        die(f"{APP} 没能启动。\n\n{e}\n\n详细日志:{logs}")
   350	
   351	    def restart_gateway():
   352	        """业主在界面里填完 key ⇒ ds-web 通过锁通道叫到这里。
   353	
   354	        **现读**一遍 key 和配置(build_env 就是干这个的),把网关换成新进程;
   355	        界面那条腿一动不动 —— 他正看着的页面就是它发的。
   356	        """
   357	        k, fresh = build_env()      # fresh 是两条腿各自的 env,重启只换网关那条
   358	        if not k:
   359	            log("[重启网关] 收到请求,但 key.txt 还是空的 —— 不动")
   360	            return
   361	        try:
   362	            sup.restart([gateway_service(fresh["网关"])])
   363	            log("[重启网关] 完成")
   364	        except Exception as exc:      # 回调跑在锁的线程里:炸出去会把那条线程带走
   365	            log(f"[重启网关] 失败:{exc}")
   366	            alert(f"key 已经存好了,但后台没能自己重启:\n{exc}\n\n"
   367	                  f"请退出 {APP} 再打开一次。")
   368	
   369	    return sup, web, restart_gateway
   370	
   371	
   372	# ── winuser.h 的几个常量 ──────────────────────────────────────────────
   373	# 🔴 值抄错一位**不会报错**,只会安静地设成别的位 ⇒ 判据 s1 逐个对表 winuser.h。
   374	#    GWL_STYLE 是负数,别写成 0x10。
   375	GWL_STYLE = -16
  1100	        """
  1101	        accepted = DIAG.report_from_ui(str(event), str(detail))
  1102	        if event == "frontend.frame_submitted":
  1103	            self._shell.note_first_frame()
  1104	        return {"accepted": bool(accepted)}
  1105	
  1106	
  1107	class Shell:
  1108	    """把 core 的状态机接到 pywebview / pystray 上。"""
  1109	
  1110	    def __init__(self, sup, web_port: int, lock: core.InstanceLock):
  1111	        self.sup = sup
  1112	        self.web_port = web_port
  1113	        self.lock = lock
  1114	        self.window = None
  1115	        self.icon = None
  1116	        # 窗口按钮走它,`shown` 那条线也要再叫它一次(贴系统样式位)⇒ 存一份,
  1117	        # 别在 main 里往实例上动态挂一个属性。
  1118	        self.window_api = WindowApi(self)
  1119	        self.state = core.ShellState(ui=self, on_stop=self.stop_backend)
  1120	        self._frame_watch = None
  1121	
  1122	    # --- core.ShellState 要求的 UI 三件 -------------------------------
  1123	    # ⚠️ 这三个方法可能被**锁的监听线程**调到(第二次双击时)。pywebview 的
  1124	    # EdgeChromium 后端内部会把调用转到 UI 线程,但这一点我在 Linux 上验不了 ⇒
  1125	    # 已进 Windows 真机考卷(「开着的时候再双击一次图标」那一问)。
  1126	    def show_window(self):
  1127	        if not self.window:
  1128	            return
  1129	        # 🔴 先从最小化里捞出来,再 Show。pywebview 的 `show()` 是
  1130	        #    `Form.Show() + Activate()`,而 Activate 走的 `SetForegroundWindow`
  1131	        #    **对最小化的窗口不还原** ⇒ 业主点托盘图标、或再双击一次桌面图标,
  1132	        #    窗口都回不来(pywebview issue #1749 列的第三条,我们从没验过)。
  1133	        #    ⚠️ 2026-08-23(track opendesign-native-frame):这里原来写着
  1134	        #    「我们的最大化 WindowState 一直是 Normal ⇒ restore 幂等」——
  1135	        #    **D3 之后那句话不成立了**,最大化是真的,无条件 restore() 会把
  1136	        #    最大化的窗口打回小窗。所以先问一句它是不是真的最小化了。
  1137	        minimized = True
  1138	        try:
  1139	            from System.Windows.Forms import FormWindowState
  1140	
  1141	            form = getattr(self.window, "native", None)
  1142	            if form is not None:
  1143	                minimized = (form.WindowState == FormWindowState.Minimized)
  1144	        except Exception as exc:
  1145	            # 读不到状态时**按最小化处理**:多还原一次顶多丢掉最大化状态,
  1146	            # 而漏还原会让窗口彻底回不来 —— 那才是 0.92 修掉的那个 bug。
  1147	            log(f"[窗口] 读不到窗口状态,按最小化处理:{exc.__class__.__name__}")
  1148	        if minimized:
  1149	            try:
  1150	                self.window.restore()
  1151	            except Exception as exc:
  1152	                log(f"[窗口] 从最小化还原失败,仍然试着 Show:{exc.__class__.__name__}")
  1153	        self.window.show()
  1154	
  1155	    def hide_window(self):
  1156	        if self.window:
  1157	            self.window.hide()
  1158	
  1159	    def destroy(self):
  1160	        if self.icon:
  1161	            try:
  1162	                self.icon.stop()
  1163	            except Exception:
  1164	                pass
  1165	        if self.window:
  1166	            # 🔴 先把窗口过程还回去,再销毁窗口 —— 顺序反了的话,
  1167	            #    销毁过程中那几条消息会走进一个即将消失的 Python 回调。
  1168	            self.window_api.uninstall_wndproc()
  1169	            try:
  1170	                self.window.destroy()
  1171	            except Exception:
  1172	                pass
  1173	
  1174	    # --- 收摊 ---------------------------------------------------------
  1175	    def stop_backend(self):
  1176	        log("收摊:停两条腿")
  1177	        try:
  1178	            self.sup.shutdown()
  1179	        finally:
  1180	            self.lock.release()
  1181	
  1182	    # --- 托盘 ---------------------------------------------------------
  1183	    # --- 首帧看门 + 诊断导出 ------------------------------------------
  1184	    # 白屏那晚(0.98,08-25)我们手上一条线索都没有。这两件补的就是那笔账。
  1185	
  1186	    FIRST_FRAME_TIMEOUT = 90.0
  1187	    """多少秒没等到前端画出第一帧,就写一次诊断快照。
  1188	
  1189	    🔴 **这个数字不承重**(判据 s9):超时路径不弹框,定错了最多多写一段日志。
  1190	    取 90 是刻意取宽的 —— 已知唯一硬数据是云端冷启虚机 20~40 秒(08-25 分时段截图),
  1288	
  1289	def main() -> int:
  1290	    DIAG.mark("main.entered")
  1291	    log(f"==== {APP} 外壳启动 ====")
  1292	    # 版本清单先写 —— 万一后面炸了,至少知道是哪一版、哪个内核上炸的。
  1293	    # (08-25 白屏那晚我们连内核版本都得靠业主去翻文件夹。)
  1294	    log(DIAG.manifest())
  1295	    # manifest() 里会 import ds_web 拿版本号(唯一来源)。它是**我自己塞进这段窗口的
  1296	    # 成本**,所以必须单独计一笔 —— 免得将来查慢的时候查到自己头上还不知道。
  1297	    DIAG.mark("manifest.done")
  1298	    shell_holder: list[Shell] = []
  1299	
  1300	    # ① 单实例。第二次双击走到这里就退出了,窗口由第一份自己叫到前台。
  1301	    #    这把锁同时是 ds-web 回来找我们的**唯一通道**(填完 key 请求重启网关)——
  1302	    #    所以它必须在起后台之前就位:锁端口要随 env 交给 ds-web。
  1303	    restart_holder: list = []
  1304	    lock = core.InstanceLock(
  1305	        base_port=LOCK_PORT, span=5,
  1306	        on_show=lambda: shell_holder and shell_holder[0].state.on_show(),
  1307	        on_restart=lambda: restart_holder and restart_holder[0]())
  1308	    try:
  1309	        if not lock.acquire():
  1310	            log("已有一份在跑,把它叫到前台,自己退出")
  1311	            return 0
  1312	    except core.PortBusy as e:
  1313	        die(f"启动失败:{e}")
  1314	    # 花在哪、占了哪一格,由这把锁自己说 —— 2026-09-01 那一趟真机,业主的诊断里
  1315	    # 只有一个 +9094ms,是我拿它减前一条、再除以锁位数,才知道 6 次握手全部耗满。
  1316	    # 下一趟不该再靠人做除法。
  1317	    DIAG.mark("lock.acquired",
  1318	              f"port={lock.port} 扫了{lock.scanned}格 用时{lock.scan_ms:.0f}ms")
  1319	
  1320	    try:
  1321	        home = user_home()
  1322	        sup, web, restart_gateway = start_backend(home, lock_port=lock.port)
  1323	        DIAG.mark("backend.ready")
  1324	        restart_holder.append(restart_gateway)
  1325	        shell = Shell(sup, web, lock)
  1326	        shell_holder.append(shell)
  1327	
  1328	        import webview
  1329	
  1330	        shell.window = webview.create_window(
  1331	            # 地址带 SHELL_MARK = 外壳自报身份,前端第一帧就知道要画窗口栏
  1332	            # (window_url 是唯一来源,日志里印的也是它)。
  1333	            APP, window_url(web),
  1334	            width=1280, height=860, min_size=(960, 640),
  1335	            # 🔴 2026-08-16 业主:系统标题栏那个 "OpenDesign" 和我们前端自己的标题
  1336	            #    撞了 ⇒ 不要那个框,窗口按钮我们自己画在右上角(WindowChrome.tsx)。
  1337	            #    代价说清楚:frameless 之后 Windows 把"拖边缘改大小"也一起收走了,
  1338	            #    由 WindowApi 用原生窗口消息接回来。
  1339	            #    `easy_drag=False` 是关键:开着的话**整个页面**按哪儿都能拖窗口 ——
  1340	            #    选不了字、拖不动滚动条。拖动只认我们那条栏。
  1341	            frameless=True, easy_drag=False, js_api=shell.window_api,
  1342	        )
  1343	        # 关窗口 = 收进托盘。pywebview 的 closing 回调返回 False 表示"别关"。
  1344	        shell.window.events.closing += lambda: shell.state.on_close_requested()
  1345	        # 窗口一出来就把 frameless 拿走的那几个样式位贴回去(见
  1346	        # WindowApi._apply_native_styles)。挂 `shown` 而不是在这儿直接叫:
  1347	        # 这一刻窗口还没建出来,没有 Handle 可用。
  1348	        shell.window.events.shown += shell.window_api.ensure_native_styles
  1349	        # 🔴 2026-08-30(判据 s6):「窗口打开」这行原来写在 `webview.start()` **之前** ——
  1350	        #    它报的是"我要开了",不是"开了"。白屏那晚这行照样出现在日志里,
  1351	        #    于是它把"窗口真开了"这件根本没发生的事说成了既成事实。搬到 shown 里。
  1352	        shell.window.events.shown += lambda: DIAG.mark("window.shown")
  1353	        # 首帧看门:到点还没等到前端报"我画出来了",就写一次诊断快照。
  1354	        # **不弹框**(判据 s9)—— 阈值不承重,定错了最多多写一段日志。
  1355	        shell.window.events.shown += lambda: shell.start_first_frame_watch()
  1356	
  1357	        shell.run_tray()
  1358	        shell.run_watchdog()
  1359	        DIAG.mark("window.create_returned", window_url(web))
  1360	        log(f"准备进入图形循环:{window_url(web)}")
  1361	        DIAG.mark("webview.loop_entered")
  1362	        webview.start()          # 阻塞,直到窗口 destroy
  1363	        shell.state.on_quit()    # 走正常关闭时也要把后台收干净
  1364	        return 0
  1365	    except ImportError as e:
  1366	        # 少了 pywebview / pythonnet / PIL —— 包被装坏了
  1367	        die(f"{APP} 少了运行所需的组件:{e}\n\n请重新运行安装程序。")
  1368	    except Exception as e:
  1369	        # .NET 挂不上、WebView2 缺失都会落到这里。**不许只抛 CLR 栈**:
  1370	        # 业主看到一堆英文栈只会来问我。原始栈进日志,弹窗给人话。
  1371	        log(traceback.format_exc())
  1372	        die(f"{APP} 启动时出错:{e}\n\n"
  1373	            f"如果是第一次在这台电脑上打开,多半是缺少微软的 WebView2 运行时,\n"
  1374	            f"请重新运行安装程序(它会自动补装)。\n\n详细日志:{_log_path()}")
  1375	    finally:
  1376	        lock.release()
  1377	    return 1
  1378	
  1379	
  1380	# 🔴 模块体走完 = 所有 import 都办完了。这一条把"进程起来 → 拿到锁"那个
  1381	#    9.4 秒的黑块切开(判据 s17):云机器上它是全程最大的一块,而在 Linux 上
  1382	#    整条 import 链只要 130ms —— 差 70 倍,差的是 I/O 不是算力。
  1383	#    切开之后才知道到底是 import 慢、还是锁那一步慢。
  1384	DIAG.mark("shell.imports_done")
  1385	
  1386	if __name__ == "__main__":
  1387	    sys.exit(main())

 succeeded in 0ms:
    80	import ds_model
    81	import ds_openfolder
    82	import ds_organize  # 针孔④ approve+apply 直调核心(锁/复验/审计全在核心)
    83	import ds_refs
    84	import ds_shell_core     # 只取锁通道的协议常量与读行:帧格式两处各抄一份迟早对不上
    85	import ds_taxonomy
    86	import ds_update    # 查更新(track opendesign-in-app-update):只查不装
    87	import ds_todo
    88	import ds_tools
    89	import ds_workspace
    90	
    91	# 版本号约定(2026-08-25 业主亲口定):**从 0.98 起只往第三位加** —— 0.98.1、
    92	# 0.98.2、0.98.3……**中途不许跳到 0.99 或 1.x**。`1.0.0` 留给业主说"就它了"
    93	# 的那一版(他的原话:"我希望最后发行版是 1.0")。
    94	VERSION = "0.98.4"  # 应用内更新第一刀:软件自己发现新版并说一句(只查不装)
    95	                    # (track opendesign-in-app-update)
    96	                    # 业主装上去**感觉不到变化**,只多一个托盘菜单「导出本次启动诊断」;
    97	                    # 换来的是:每次启动有编号、有分阶段耗时、有网页内核版本,
    98	                    # 白屏时能把现场打包发回来 —— 08-25 那晚我们手上一条线索都没有。
    99	                    # 🔴 这一版还捎带修了一个**会让软件根本打不开**的新回归:
   100	                    # 我给"后端就绪"加的探针走了系统代理(urlopen 对 127.0.0.1 不绕代理),
   101	                    # 配了公司代理 / Clash 类 VPN 的机器上会死等 60s 然后判启动失败。
   102	                    # 怎么发现的:**四审孤腿 BLOCK,然后我自己造探针复现**——
   103	                    # 两条判 PASS 的腿都没看见(而且它们在读我的自审)。
   104	                    # 链条:ds_merge_config 把配置写好了 → 最后一句「已合并 4 段进…」
   105	                    # 在 cp1252 的 stdout 上 UnicodeEncodeError → rc≠0 →
   910	        # track opendesign-key-onboarding:前端不再手输口令之后补的纵深。
   911	        # 它挡"能被跨站触发的带副作用请求";浏览器同源策略与 _host_ok 各守另一面。
   912	        if not self._same_site_ok():
   913	            self._json(403, {"error": "cross-site"})
   914	            return
   915	        path = urlsplit(self.path).path
   916	        if path == "/api/health":
   917	            self._json(200, {"ok": True, "version": VERSION,
   918	                             "ds_root": self.server.ds_root,
   919	                             "model": _read_model(),
   920	                             # 文档转换器装没装:业主刷一下 /api/health 就看得见,
   921	                             # 不用开命令行(部署规矩:盘上有 ≠ 跑起来有)。
   922	                             "doc_reader": _doc_reader_status()})
   923	        elif path == "/api/update/check":
   924	            self._update_check()
   925	        elif path == "/api/todos":
   926	            self._todos()
   927	        elif path == "/api/llm/credential":
   928	            self._llm_credential_get()
   929	        elif path == "/api/chat/bootstrap":
   930	            self._proxy("/webui/bootstrap")
  1020	            self._method_not_allowed()
  1021	
  1022	    do_PUT = do_DELETE = do_PATCH = _method_not_allowed
  1023	
  1024	    def _update_check(self):
  1025	        """查更新:线上有没有比本机新的版本(track opendesign-in-app-update,第一刀)。
  1026	
  1027	        🔴 **任何失败都以 200 + error 字段回**(判据 t9b)。查更新失败是小事,
  1028	        而一个 500 会让前端的通用错误路径弹东西给业主 —— 他什么都没干、只是打开了软件,
  1029	        却看见"出错了"。**功能失败和软件坏了,在界面上不该长得一样。**
  1030	
  1031	        `?force=1` 是业主亲手点了「检查更新」:那一下不给缓存,真去问一次。
  1032	        本机版本号只有一个来源(VERSION),不另写一份 —— 抄第二份迟早对不上。
  1033	        """
  1034	        # 🔴 第三轮评审 F6:原来判的是"非空且非 0" ⇒ `?force=false` 也会强制刷新。
  1035	        #    没有危害(只多打一次 GitHub),但一个**反着读**的参数迟早会骗到下一个人。
  1036	        #    只认明确的"开"(判据 t9e)。
  1037	        raw_force = parse_qs(urlsplit(self.path).query).get("force", [""])[0]
  1038	        force = raw_force.strip().lower() in ("1", "true", "yes", "on")
  1039	        self._json(200, ds_update.check_cached(VERSION, force=force))
  1040	
  1041	    def _todos(self):
  1042	        try:
  1043	            data = ds_todo.collect(self.server.ds_root)
  1044	        except Exception:
  1045	            # M1 后:坏编码文件(F2)/读期 OSError(F3,Windows 写锁窗口)已在 collect
  2585	
  2586	def main() -> int:
  2587	    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
  2588	    dist = os.environ.get("DS_WEB_DIST", DEFAULT_DIST)
  2589	    port = int(os.environ.get("DS_WEB_PORT", str(DEFAULT_PORT)))
  2590	    nanobot_port = int(os.environ.get("DS_NANOBOT_PORT", str(DEFAULT_NANOBOT_PORT)))
  2591	    if not os.path.isfile(os.path.join(dist, "index.html")):
  2592	        print(f"ds-web: 前端产物缺失 {dist}/index.html —— 先在开发机构建"
  2593	              f"(cd web && npm run build)或 git pull 取最新", file=sys.stderr)
  2594	        return 2
  2595	    try:
  2596	        migration = ds_common.migrate_legacy_data(ds_root)
  2597	    except ds_common.DataRootError as exc:
  2598	        print(f"ds-web: 数据目录不可用({exc})", file=sys.stderr)
  2599	        return 2
  2600	    if migration["failed"]:
  2601	        print(f"ds-web: 遗留数据搬运失败: {migration['failed']}", file=sys.stderr)
  2602	        return 2
  2603	    try:
  2604	        httpd = make_server(ds_root, dist, port=port, nanobot_port=nanobot_port)
  2605	    except OSError as e:
  2606	        print(f"ds-web: 端口 {port} 起不来({e});被占用请设 DS_WEB_PORT 换端口",
  2607	              file=sys.stderr)
  2608	        return 2
  2609	    print(f"ds-web {VERSION}: http://127.0.0.1:{port}/  "
  2610	          f"(DS_DATA_ROOT={ds_common.data_root(ds_root)})")
  2611	    try:
  2612	        httpd.serve_forever()
  2613	    except KeyboardInterrupt:
  2614	        pass
  2615	    finally:
  2616	        httpd.server_close()
  2617	    return 0
  2618	
  2619	
  2620	if __name__ == "__main__":

 succeeded in 58ms:
    35	
    36	; 数据根 —— 与 bin/ds_shell.py 的 user_home() / _log_path() 是同一处约定。
    37	; 那边写的是 %LOCALAPPDATA%\OpenDesign\{UserData,Logs},这里只认它的父目录。
    38	!define DATA_ROOT  "$LOCALAPPDATA\${APP}"
    39	!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"
    40	!define RUN_KEY    "Software\Microsoft\Windows\CurrentVersion\Run"
    41	; 哨兵:递归删安装目录之前先确认"这确实是我们装的地方"。
    42	; NSIS 最出名的一次性事故就是 $INSTDIR 变成空串之后 RMDir /r 从当前目录往下删。
    43	!define SENTINEL   "ds\bin\ds_shell.py"
    44	; 微软官方的 WebView2 检测键(每机器装 / 每用户装两处)。
    45	!define WV2_GUID   "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    46	
    47	Name "${APP} ${APPVER}"
    48	OutFile "${APP}-Setup-${APPVER}.exe"
    49	InstallDir "$LOCALAPPDATA\Programs\${APP}"
    50	InstallDirRegKey HKCU "Software\${APP}" "InstallDir"
    51	RequestExecutionLevel user
    52	SetCompressor /SOLID lzma
    53	; 300MB 的树铺开要一会儿,让业主看得见在动,免得他以为卡死了去点叉。
    54	ShowInstDetails show
    55	ShowUnInstDetails show
    56	
    57	VIProductVersion "${APPVER}.0"
    58	VIAddVersionKey "ProductName"     "${APP}"
    59	VIAddVersionKey "FileDescription" "${APP} 安装程序"
    60	VIAddVersionKey "FileVersion"     "${APPVER}.0"
    61	VIAddVersionKey "ProductVersion"  "${APPVER}"
    62	VIAddVersionKey "LegalCopyright"  "OpenDesign"
    63	
    64	!define MUI_ICON   "opendesign.ico"
    65	!define MUI_UNICON "opendesign.ico"
    66	!define MUI_ABORTWARNING
    67	
    68	!define MUI_WELCOMEPAGE_TITLE "安装 ${APP} ${APPVER}"
    69	; 这段话要替业主回答两个他一定会遇到的问题,不然他会来问我:
    70	;   ① 没有代码签名 ⇒ Windows 会弹"未知发布者"(design 已记账,签名要花钱);
    71	;   ② 覆盖安装时如果程序正在跑,文件是锁着的。
    72	!define MUI_WELCOMEPAGE_TEXT "这个安装程序会把 ${APP} 装到你自己的用户目录里,\
    73	不需要管理员权限,也不会改动系统。$\r$\n$\r$\n\
    74	如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续安装。$\r$\n$\r$\n\
    75	你的资料(备忘、对话、工作区设置)存在安装目录之外,\
    76	更新和卸载都不会碰它。"
    77	
    78	!insertmacro MUI_PAGE_WELCOME
    79	!insertmacro MUI_PAGE_COMPONENTS
    80	; 目录页要有人守:卸载时会把安装目录**整棵**删掉,所以不能让业主随手指到一个
    81	; 本来就有东西的文件夹(见 CheckDirEmpty)。
    82	!define MUI_PAGE_CUSTOMFUNCTION_LEAVE CheckDirEmpty
    83	!insertmacro MUI_PAGE_DIRECTORY
    84	!insertmacro MUI_PAGE_INSTFILES
    85	
    86	!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP}.exe"
    87	!define MUI_FINISHPAGE_RUN_TEXT "现在就打开 ${APP}"
    88	!define MUI_FINISHPAGE_TEXT "装好了。开始菜单里可以找到 ${APP}。$\r$\n$\r$\n\
    89	第一次打开时,如果还没填过大模型的 API key,它会告诉你要把 key 放在哪个文件里。"
    90	!insertmacro MUI_PAGE_FINISH
    91	
    92	; 程序在跑的时候文件是锁着的,而 `RMDir /r` 删不掉会**悄悄**跳过 ——
    93	; 卸载器会显示"完成",盘上却剩半棵树。所以先提醒。
    94	; ⚠️ 这句话在 0.86.0 之前是**假的**:项目档案、客户备忘、共享参考图库、工作区设置
    95	; 当时都住在 $INSTDIR\ds 里,普通卸载(RMDir /r $INSTDIR)照样删。
    96	; track opendesign-data-outside-install 把它们搬到了 $LOCALAPPDATA\${APP}\Data 之后,
    97	; 这句才成立。**改这句之前先确认实现真的搬完了**(判据 tests/test_data_root.py)。
    98	!define MUI_UNCONFIRMPAGE_TEXT_TOP "如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续卸载。$\r$\n$\r$\n你的项目档案、参考图库、和助手的对话、工作区设置都放在别处,默认不会被删除。$\r$\n你自己的设计文件(CAD/SU/效果图)本来就在你自己的文件夹里,卸载完全不碰。"
    99	!insertmacro MUI_UNPAGE_CONFIRM
   100	!insertmacro MUI_UNPAGE_COMPONENTS
   101	!insertmacro MUI_UNPAGE_INSTFILES
   102	
   103	!insertmacro MUI_LANGUAGE "SimpChinese"
   104	
   105	; ─────────────────────────────────────────────────────────────── 安装
   106	
   107	Section "${APP} 主程序" SecMain
   108	  SectionIn RO
   109	  ; 每用户:$SMPROGRAMS / $DESKTOP 都要取当前用户的那一份,不是 All Users
   110	  ; (取错的话装的时候不报错,卸载时删不掉 —— 因为那需要管理员)。
   111	  SetShellVarContext current
   112	
   113	  SetOutPath "$INSTDIR"
   114	  ; 整棵树一次铺进去。**故意不逐个 File 点名**:点名清单会跟真实树漂移,
   115	  ; 而"少铺了半棵树"这种事编译期不报错。谁保证它全:成品闸 P4/P5
   116	  ; 逐个文件比对 makensis 自己打印的清单与 payload 树。
   117	  File /r "${PAYLOAD}\*"
   118	
   119	  WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"
   120	  WriteRegStr HKCU "Software\${APP}" "Version"    "${APPVER}"
   121	
   122	  ; 卸载条目("设置 → 应用"里那一条)。
   123	  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayName"     "${APP}"
   124	  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayVersion"  "${APPVER}"
   125	  WriteRegStr   HKCU "${UNINST_KEY}" "Publisher"       "OpenDesign"
   126	  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${APP}.exe"
   127	  WriteRegStr   HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
   128	  WriteRegStr   HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\卸载.exe"'
   129	  WriteRegStr   HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\卸载.exe" /S'
   130	  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
   131	  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
   132	  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
   133	  IntFmt $0 "0x%08X" $0
   134	  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"
   135	
   136	  WriteUninstaller "$INSTDIR\卸载.exe"
   137	
   138	  CreateDirectory "$SMPROGRAMS\${APP}"
   139	  CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\${APP}.exe"
   140	  CreateShortcut "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk" "$INSTDIR\卸载.exe"
   141	
   142	  Call EnsureWebView2
   143	  Call ProvisionConfig
   144	SectionEnd
   145	
   146	Section "在桌面上放一个图标" SecDesktop
   147	  SetShellVarContext current
   148	  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${APP}.exe"
   149	SectionEnd
   150	
   151	; `/o` = 默认不勾。业主拍板"开机自启做成选项";默认关还有第二个理由:
   152	; 常驻 + 自启会把底座的 dream(每 2 小时回顾对话、会写 SOUL.md)放大到 24 小时,
   153	; 那件事 design.md 记在 backlog 里、本单不动 —— 那就更不该默认替他打开。
   154	Section /o "开机时自动启动" SecAutorun
   155	  SetShellVarContext current
   156	  WriteRegStr HKCU "${RUN_KEY}" "${APP}" '"$INSTDIR\${APP}.exe"'
   157	SectionEnd
   158	
   159	!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
   160	  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}    "${APP} 本体(必装)。"
   161	  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "在桌面上放一个 ${APP} 图标。"
   162	  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutorun} "开机后自动把 ${APP} 挂到右下角托盘里。"
   163	!insertmacro MUI_FUNCTION_DESCRIPTION_END
   164	
   165	; ─────────────────────────────────────────────────────────────── 装机时的三件事
   166	
   167	Function CheckDirEmpty
   168	  ; 🔴 卸载时会 `RMDir /r "$INSTDIR"` —— 整棵删。所以"装到哪儿"这件事,
   169	  ; 一旦业主把路径改成一个本来就有东西的文件夹(`D:\文档` 这种),卸载就会把他的东西
   170	  ; 一起删光。**G6 那个哨兵挡不住这一种**:装完之后哨兵文件就在那儿了,它会说"是我们的"。
   171	  ;
   172	  ; 所以在这里拦:目录存在、非空、又不是上一次装的 OpenDesign ⇒ 让他确认一次。
   173	  ; 不直接禁止 —— 他可能真的想装回一个自己清理过的文件夹。
   174	  ; NSIS 的 `IfFileExists 文件 有则跳 [无则跳]`;`0` = "不跳,往下走"(标准惯用法)。
   175	  ; 把语义写在这儿是因为它属于"Linux 上验不了、写反了也没有闸看得出来"的那一类
   235	  ${EndIf}
   236	FunctionEnd
   237	
   238	Function ProvisionConfig
   239	  ; 把配置铺到"后台起得起来"的程度。**不问业主任何东西** —— 这一步是非交互的,
   240	  ; 而且幂等(已经装过一次的机器,他自己的设置原样留着)。细节全在
   241	  ; bin/ds_provision.py,那边有 15 条判据 + 12 条红检盯着。
   242	  DetailPrint "正在准备配置…"
   243	  ; **一行写完,不用续行**:NSIS 的续行拼出来到底是什么样,我在 Linux 上验不了,
   244	  ; 而"命令拼歪了"的表现是装机时静默失败 —— 少一个验不了的机制比省几个字重要。
   245	  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\ds\bin\ds_provision.py" --home "${DATA_ROOT}\UserData" --ds-root "$INSTDIR\ds"'
   246	  Pop $0
   247	  ${If} $0 != 0
   248	    ; 不 Abort:文件已经铺好了,而外壳自己会把"到底缺什么"说得比这里清楚
   249	    ; (那段话在业主真机上验过)。这里只负责别让它悄悄过去。
   250	    MessageBox MB_ICONEXCLAMATION "配置初始化没有成功(错误码 $0)。$\n$\n\
   251	${APP} 的文件已经装好了。第一次打开时它会告诉你还缺什么。" /SD IDOK
   252	  ${EndIf}
   253	FunctionEnd
   254	
   255	; ─────────────────────────────────────────────────────────────── 卸载
   256	
   257	Section "un.${APP}" SecUnMain
   258	  SectionIn RO
   259	  SetShellVarContext current
   260	
   261	  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"
   262	  DeleteRegKey   HKCU "${UNINST_KEY}"
   263	  DeleteRegKey   HKCU "Software\${APP}"
   264	
   265	  Delete "$DESKTOP\${APP}.lnk"
   266	  Delete "$SMPROGRAMS\${APP}\${APP}.lnk"
   267	  Delete "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk"
   268	  RMDir  "$SMPROGRAMS\${APP}"
   269	
   270	  ; 🔴 递归删之前先认门。$INSTDIR 可能因为注册表被人动过而变成空串或别的目录,
   271	  ; 那时候 `RMDir /r` 会从那里往下把东西删光。哨兵是这份闸(G6)要求的形状。
   272	  IfFileExists "$INSTDIR\${SENTINEL}" 0 not_ours
   273	    RMDir /r "$INSTDIR"
   274	    Goto done
   275	  not_ours:
   276	    MessageBox MB_ICONEXCLAMATION "这个目录看起来不是 ${APP} 装的地方,为安全起见没有删:$\n$INSTDIR" /SD IDOK
   277	  done:
   278	SectionEnd
   279	
   280	; `/o` = 默认不勾。业主两年的档案在这底下 —— 删掉不可恢复,必须是他主动勾的。
   281	Section /o "un.连我的资料一起删掉(不可恢复)" SecUnData
   282	  SetShellVarContext current
   283	  IfFileExists "${DATA_ROOT}\*.*" 0 no_data
   284	    RMDir /r "${DATA_ROOT}"
   285	    DetailPrint "资料目录已删除:${DATA_ROOT}"
   286	    Goto after
   287	  no_data:
   288	    DetailPrint "没有找到资料目录:${DATA_ROOT}"
   289	  after:
   290	SectionEnd
   291	
   292	!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
   293	  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnMain} "卸载 ${APP} 程序本体(你的资料不会被删)。"
   294	  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnData} "连同项目档案、参考图库、对话记录、工作区设置一起删掉。删了就找不回来了。(你自己的设计文件不在这儿,不受影响。)"
   295	!insertmacro MUI_UNFUNCTION_DESCRIPTION_END

codex
方案已经收敛为“安装目录外的稳定更新宿主 + 固定安装路径的整目录事务替换”。这比单纯让旧进程拉起 `/S` 更关键的一点，是断电或安装中崩溃后，快捷方式仍有一个不在被替换目录里的入口，可以按事务日志恢复旧目录；最终成功仍只由新实例的 health 回答裁决。现在在做最后一轮风险与测试判据对齐。
已完成只读梳理并形成独立方案；未运行构建、未联网、未修改仓库文件。
  ✓ 读取指定实现、安装器和工作流（排除 tracks/）
  ✓ 梳理现状约束、进程关系、版本来源与数据落点
  ✓ 形成更新/验收/回滚方案及备选方向
  ✓ 设计覆盖故障注入与业主视角的测试策略
codex
结论：采用“安装目录外的稳定 UpdateHost + NSIS 更新模式 + 整目录事务替换”。旧程序只负责下载和交棒；真正覆盖程序文件的是已经脱离旧进程、且不在被替换目录里的 UpdateHost。安装器退出码、文件是否落盘都只是中间证据，唯一成功判据是 UpdateHost 亲自请求新实例的 `/api/health`，并读到目标版本。

标记约定：

- 【读到】仓库里的现状。
- 【推论】基于现状做出的方案选择。

## 1. Approach

### 现状约束

- 【读到】当前 `ds_update.py` 明确“只查不装”，但已经拿到了安装包 URL、size 和 GitHub `digest`；代码也明确承认该 digest 能查损坏，不能防 GitHub 账号失陷。[ds_update.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_update.py:1)
- 【读到】程序安装在 `%LOCALAPPDATA%\Programs\OpenDesign`，业主资料位于安装目录外的 `%LOCALAPPDATA%\OpenDesign`。[OpenDesign.nsi](/root/.openclaw/workspace/projects/design-studio/installer/OpenDesign.nsi:35)
- 【读到】当前安装器直接向现有 `$INSTDIR` 铺整棵 payload，并且每次都会调用 `ProvisionConfig`；因此不能把当前 `/S` 原样当作“绝不碰数据”的更新模式。[OpenDesign.nsi](/root/.openclaw/workspace/projects/design-studio/installer/OpenDesign.nsi:107)
- 【读到】`OpenDesign.exe` 只是启动器：拉起安装目录中的 `pythonw.exe + ds_shell.py` 后立即退出。[launcher.nsi](/root/.openclaw/workspace/projects/design-studio/installer/launcher.nsi:1)
- 【读到】真正的桌面进程是 `ds_shell.py`；它能完整关闭受管后台进程并释放单实例锁。[ds_shell.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_shell.py:1174)
- 【读到】现有 health 返回 `ok、version、ds_root`，版本唯一来源是 `ds_web.VERSION`。[ds_web.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_web.py:916)

### 组件边界

【推论】增加一个很小的、每用户级的 `OpenDesign UpdateHost`，放在以下两棵树之外：

- 被替换的程序目录：`%LOCALAPPDATA%\Programs\OpenDesign`
- 业主数据目录：`%LOCALAPPDATA%\OpenDesign`

例如放在 `%LOCALAPPDATA%\Programs\OpenDesign.UpdateHost`。它不能依赖安装目录里的 Python，否则旧目录被换名或损坏后，回滚程序本身也会失效。

安装 UpdateHost 的“引导版”同时把桌面、开始菜单和开机启动入口改为指向稳定宿主。宿主平时只负责启动 `%LOCALAPPDATA%\Programs\OpenDesign\OpenDesign.exe`；存在未完成事务时先恢复，再启动。

【推论】当前 0.98.4 没有这个宿主，因此首个支持自更新的版本仍需最后一次人工安装。之后才具备一键更新能力；无法靠尚未安装的代码更新 0.98.4 自己。

### 更新事务

```text
旧版运行
  → 下载并校验完整安装包
  → UpdateHost 接棒
  → 旧版完整收摊
  → 数据快照
  → 旧安装目录原子换名为 rollback
  → NSIS 静默安装到原固定路径
  → 拉起目标版本
  → 新实例 /api/health 自报目标版本
  → 数据逐字节复核
  → COMMIT
             任一步失败
                  ↓
      停掉候选版本 → 恢复旧目录和数据
                  → 拉起旧版并验证旧版 health
```

具体协议：

1. **点击触发**

   【推论】新增 `POST /api/update/start`。请求不接受 URL、路径或版本等任意输入，只能安装服务端刚从固定仓库选出的 release。自动检查可以继续，但永远不能调用安装端点；只有业主点击“更新到 X”才创建事务。

2. **仍活着时下载**

   【推论】旧版在后台流式下载到 UpdateHost 的事务目录，先写 `.part`。要求：

   - `https` 且 host 在明确白名单内；
   - 名称符合 `OpenDesign-Setup-<version>.exe`；
   - size 为合理正数，实际字节数与 metadata 一致；
   - `digest` 必须严格是 `sha256:<64 hex>`；
   - 流关闭后 SHA-256 相等，才原子改名为可执行文件。

   缺 digest 时可以显示“发现新版，但该发布缺少可验证校验值”，不能提供自动安装按钮。

3. **交棒并收摊**

   【推论】校验完成后，由 `ds_web` 通过现有 shell IPC 请求主外壳启动 UpdateHost；不能让 `ds_web` 自己启动，因为它属于即将被 `Supervisor.shutdown()` 收掉的后台树。

   UpdateHost 启动成功并写下持久事务日志后，shell 才关闭网关、工作台、窗口并释放锁。UpdateHost等待旧 shell PID、子进程和锁全部消失；超时则不碰安装目录，重新拉起旧版。

4. **保护数据**

   【推论】“业主数据”的验收范围定为整棵 `Data`、整棵 `UserData`，以及更新器绝不接收路径的外部工作区。`Logs` 和 UpdateHost 事务日志属于运行证据，不作为业务数据。

   旧进程停止后，UpdateHost：

   - 生成路径、长度、SHA-256 清单；
   - 将 `Data`、`UserData` 完整复制到事务快照；
   - 再读一次确认源在复制期间未变化；
   - 不能得到稳定快照就中止更新。

   【读到→推论】当前 shell 启动会重写 `UserData` 中的 nanobot 配置，当前安装器也会运行 provisioning。因此更新验证模式必须禁止迁移、provisioning及业务后台写入，直到事务提交；否则“一个字节不变”无法兑现。[ds_shell_core.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_shell_core.py:980)

5. **安装目录事务**

   【推论】把当前安装目录原子换名为同卷兄弟目录，例如 `.OpenDesign.rollback-<tx>`，而不是在旧树上覆盖。这样不会留下新旧版本混杂和已经从新版删除的旧文件。

   新安装器增加专用 `/S /UPDATE` 模式：

   - 只向空的固定安装路径铺完整 payload；
   - 不调用 `ProvisionConfig`；
   - 不调用数据迁移；
   - 不改桌面图标、开机自启选择或其他用户偏好；
   - 全局版本注册表值延迟到 health 成功后提交；
   - 安装器退出码只决定是否继续验证，不决定成功。

6. **新进程自证**

   【推论】UpdateHost生成一次性随机 nonce，通过启动环境交给新 shell。新 shell 将实际动态 web 端口通过受限 named pipe 告知 UpdateHost。

   `/api/health` 在更新启动时额外返回：

   - `update_tx`：必须来自进程启动环境，不能回显 HTTP 查询参数；
   - `pid` 或进程启动标识；
   - 现有的 `version、ds_root、ok`。

   UpdateHost直接、禁用系统代理地请求该端口，只有以下条件同时成立才成功：

   - HTTP 200，JSON 可解析；
   - `ok is true`；
   - `version` 规范化后严格等于安装包目标版本；
   - `ds_root` 是新安装目录下的 `ds`；
   - `update_tx` 等于本事务 nonce；
   - 回答进程属于刚拉起的候选进程树。

   named-pipe 收据、安装器退出码、注册表版本、磁盘文件均不能代替这次 HTTP 回答。

7. **提交与回滚**

   【推论】health 通过后仍要复算数据清单。只有 health 正确且数据逐字节相同，才写 `COMMITTED`、更新注册表版本并开放窗口和业务后台。

   失败时：

   - 停掉候选进程树；
   - 移走不完整的新目录；
   - 将 rollback 目录原子换回固定路径；
   - 如数据发生变化，用快照恢复并复核；
   - 恢复注册表快照；
   - 拉起旧版，并要求旧版 `/api/health` 自报旧版本。

   只有旧 health 也通过，才能告诉业主“更新失败，已恢复 vX”。旧目录恢复但旧 health 不通时，必须诚实显示“文件已恢复，但旧版没有成功启动”，并保留备份和诊断。

   【推论】每个状态转换都先把事务日志写入临时文件、落盘、再原子替换。断电后稳定宿主看到非 `COMMITTED` 状态时采取保守回滚，因此快捷方式不会指向一个已经被换走的目录。

## 2. Key trade-offs / risks

- 【读到→推论】没有代码签名证书。GitHub digest 能防传输损坏，但 digest 和安装包来自同一个 GitHub 信任域，不能防仓库账号失陷；SmartScreen、杀软也可能阻断或隔离安装包。
- 【推论】UpdateHost 成为高价值单点。它必须小、路径规则固定、拒绝任意 URL/安装目录，并专门防 junction/reparse-point 路径逃逸。
- 【推论】更新期间需要同时容纳旧程序树、新程序树、43MB 安装包及数据快照。磁盘预检必须在关闭旧版前完成；数据很多时，快照时间会明显增加。
- 【推论】杀软或残留子进程可能继续锁住文件。锁未完全释放时不能强装；应在旧目录仍完整的阶段中止。
- 【推论】UpdateHost 本身不能在自己运行时被同一事务覆盖。宿主升级应 side-by-side 落下，待本次进程退出后由下次启动激活。
- 【推论】“数据”范围必须在验收文档里钉死。若要求连 `%LOCALAPPDATA%\OpenDesign\Logs` 都一个字节不变，则与现实现“每次启动必写日志”冲突；这不是测试能补掉的，需要改变日志落点或调整定义。
- 【推论】health 是部署收口，不等于整个产品体验正确。窗口、WebView2、网关、聊天可能仍失败，必须作为额外质量门验证，但不能拿它们替代版本 health 判据。

## 3. Alternatives considered

- **让运行中的 Python 直接覆盖自己**

  【推论】不选。Windows 会锁住正在使用的解释器、DLL和程序文件；同时旧进程一退出，就失去了负责验证和回滚的观察者。

- **旧版直接启动当前 NSIS `/S` 后退出**

  【读到→推论】不选。当前安装器会覆盖现有树并调用 `ProvisionConfig`，没有数据不变契约、事务日志和 health 回滚；退出码 0 也无法证明新进程起来了。

- **A/B 版本槽位加 active pointer**

  【推论】回滚很漂亮，但改动更大。当前配置会写包内 Python 的绝对路径；槽位变化会改变 `UserData` 配置字节，与本需求的数据不变要求直接冲突。固定路径整目录替换更贴合现有结构。

- **MSIX、Squirrel、WinSparkle 等现成更新框架**

  【推论】暂不选。它们要求重做当前 NSIS/Python分发结构，部分路径依赖签名，而且仍不会自动满足“新进程 health 精确版本 + 数据逐字节不变 + 业务定制回滚”。

- **增量更新**

  【推论】按题面排除。全量包反而更适合做空目录安装和完整 payload 校验。

## 4. Test strategy

### 纯逻辑与协议

- release 选择、预发布、版本规范化、缺失/畸形 digest、错误 URL、截断下载、size 不符、hash 不符。
- 状态机每一状态的恢复幂等性；同一事务重复执行不能二次安装或二次回滚。
- health 裁决必须拒绝：旧版本、错误 nonce、错误 `ds_root`、无效 JSON、HTTP 500、陌生端口、回答一次后立即死亡。
- 变异测试：把裁决改成“安装器退出码 0”或“目标文件存在”时，测试必须转红。

### 安装器

- 静态检查 `/UPDATE` 分支不能引用 `DATA_ROOT`、`ProvisionConfig`、用户工作区、开机启动或可选快捷方式。
- 成品检查安装进空目录后的逐文件清单与 payload 完全相同。
- 故意造一个“退出码 0 但缺关键文件”的安装包，必须最终回滚。

### Windows 真机/CI 端到端

以真实旧版安装包作为 N-1，种入中文名、空文件、嵌套目录及随机二进制 canary，记录 `Data`、`UserData` 的完整 byte manifest，然后执行真实“一次点击更新”。

成功断言：

- 旧 shell 和所有子进程消失；
- 新实例 health 返回目标版本、正确 nonce 和新 `ds_root`；
- 数据 manifest 完全相同；
- 关闭新实例后，从桌面、开始菜单、开机入口重新启动，health仍是新版本；
- 截图确认主窗口存在且不是对话框或白屏。

失败注入：

- 下载中断、hash 错、磁盘满；
- 旧进程不退出、孤儿占端口、文件被杀软锁住；
- 安装器非零、安装器零但少文件；
- 新 health 超时、返回旧版本、答错 nonce、只成功一次便崩；
- 候选版本偷偷修改一个数据字节；
- 在每个持久状态写完后强杀 UpdateHost或模拟重启；
- 自定义安装路径、中文/空格路径、无 key、系统代理、普通用户权限。

每条失败用同一套收口：

1. 程序目录恢复为旧版 byte manifest；
2. 数据恢复为原 manifest；
3. 注册表和启动入口恢复；
4. 旧版新进程 `/api/health` 自报旧版本。

【读到】现有 `.github/workflows` 只有 Windows 探针，并且文件自身明确说不是回归判据。因此需要新增独立、强制的 N-1→N 更新工作流，不能只扩展现有“跑完即绿”的探针。[windows-package-probe.yml](/root/.openclaw/workspace/projects/design-studio/.github/workflows/windows-package-probe.yml:1)

### “断言全绿但业主眼里仍然失败，会失败成什么样？”

最可能的形态是：新 `ds-web` 的 health 精确报告了新版本，数据也没变，但 pywebview 主窗口没出现、只剩托盘，或者窗口整块白；业主看到的是“更新完以后软件打不开”。

【读到】仓库已有经验表明“后端活着/首帧已提交”不等于业主眼睛看见正常界面；当前 Windows 探针也明确要求最终看截图。

另外还有三种 oracle 盲区：

- health 通过一瞬间后进程崩溃；
- 工作台活着但网关/MCP没起来，界面能看却不能聊天；
- 当前新进程正常，但快捷方式仍指向旧入口，下次启动又回旧版。

因此 health 仍是部署成功的唯一终局判据，但其后必须附加短稳定窗口、窗口截图、聊天最小 smoke，以及“关闭后从真实快捷方式再启动一次”。这些附加项只能让质量门更严，不能把安装器退出码或盘上文件偷换成部署成功。

本次仅做了只读分析；未运行构建、未联网、未修改任何仓库文件，也未读取 `tracks/` 下的方案文件。
tokens used
236,703
结论：采用“安装目录外的稳定 UpdateHost + NSIS 更新模式 + 整目录事务替换”。旧程序只负责下载和交棒；真正覆盖程序文件的是已经脱离旧进程、且不在被替换目录里的 UpdateHost。安装器退出码、文件是否落盘都只是中间证据，唯一成功判据是 UpdateHost 亲自请求新实例的 `/api/health`，并读到目标版本。

标记约定：

- 【读到】仓库里的现状。
- 【推论】基于现状做出的方案选择。

## 1. Approach

### 现状约束

- 【读到】当前 `ds_update.py` 明确“只查不装”，但已经拿到了安装包 URL、size 和 GitHub `digest`；代码也明确承认该 digest 能查损坏，不能防 GitHub 账号失陷。[ds_update.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_update.py:1)
- 【读到】程序安装在 `%LOCALAPPDATA%\Programs\OpenDesign`，业主资料位于安装目录外的 `%LOCALAPPDATA%\OpenDesign`。[OpenDesign.nsi](/root/.openclaw/workspace/projects/design-studio/installer/OpenDesign.nsi:35)
- 【读到】当前安装器直接向现有 `$INSTDIR` 铺整棵 payload，并且每次都会调用 `ProvisionConfig`；因此不能把当前 `/S` 原样当作“绝不碰数据”的更新模式。[OpenDesign.nsi](/root/.openclaw/workspace/projects/design-studio/installer/OpenDesign.nsi:107)
- 【读到】`OpenDesign.exe` 只是启动器：拉起安装目录中的 `pythonw.exe + ds_shell.py` 后立即退出。[launcher.nsi](/root/.openclaw/workspace/projects/design-studio/installer/launcher.nsi:1)
- 【读到】真正的桌面进程是 `ds_shell.py`；它能完整关闭受管后台进程并释放单实例锁。[ds_shell.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_shell.py:1174)
- 【读到】现有 health 返回 `ok、version、ds_root`，版本唯一来源是 `ds_web.VERSION`。[ds_web.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_web.py:916)

### 组件边界

【推论】增加一个很小的、每用户级的 `OpenDesign UpdateHost`，放在以下两棵树之外：

- 被替换的程序目录：`%LOCALAPPDATA%\Programs\OpenDesign`
- 业主数据目录：`%LOCALAPPDATA%\OpenDesign`

例如放在 `%LOCALAPPDATA%\Programs\OpenDesign.UpdateHost`。它不能依赖安装目录里的 Python，否则旧目录被换名或损坏后，回滚程序本身也会失效。

安装 UpdateHost 的“引导版”同时把桌面、开始菜单和开机启动入口改为指向稳定宿主。宿主平时只负责启动 `%LOCALAPPDATA%\Programs\OpenDesign\OpenDesign.exe`；存在未完成事务时先恢复，再启动。

【推论】当前 0.98.4 没有这个宿主，因此首个支持自更新的版本仍需最后一次人工安装。之后才具备一键更新能力；无法靠尚未安装的代码更新 0.98.4 自己。

### 更新事务

```text
旧版运行
  → 下载并校验完整安装包
  → UpdateHost 接棒
  → 旧版完整收摊
  → 数据快照
  → 旧安装目录原子换名为 rollback
  → NSIS 静默安装到原固定路径
  → 拉起目标版本
  → 新实例 /api/health 自报目标版本
  → 数据逐字节复核
  → COMMIT
             任一步失败
                  ↓
      停掉候选版本 → 恢复旧目录和数据
                  → 拉起旧版并验证旧版 health
```

具体协议：

1. **点击触发**

   【推论】新增 `POST /api/update/start`。请求不接受 URL、路径或版本等任意输入，只能安装服务端刚从固定仓库选出的 release。自动检查可以继续，但永远不能调用安装端点；只有业主点击“更新到 X”才创建事务。

2. **仍活着时下载**

   【推论】旧版在后台流式下载到 UpdateHost 的事务目录，先写 `.part`。要求：

   - `https` 且 host 在明确白名单内；
   - 名称符合 `OpenDesign-Setup-<version>.exe`；
   - size 为合理正数，实际字节数与 metadata 一致；
   - `digest` 必须严格是 `sha256:<64 hex>`；
   - 流关闭后 SHA-256 相等，才原子改名为可执行文件。

   缺 digest 时可以显示“发现新版，但该发布缺少可验证校验值”，不能提供自动安装按钮。

3. **交棒并收摊**

   【推论】校验完成后，由 `ds_web` 通过现有 shell IPC 请求主外壳启动 UpdateHost；不能让 `ds_web` 自己启动，因为它属于即将被 `Supervisor.shutdown()` 收掉的后台树。

   UpdateHost 启动成功并写下持久事务日志后，shell 才关闭网关、工作台、窗口并释放锁。UpdateHost等待旧 shell PID、子进程和锁全部消失；超时则不碰安装目录，重新拉起旧版。

4. **保护数据**

   【推论】“业主数据”的验收范围定为整棵 `Data`、整棵 `UserData`，以及更新器绝不接收路径的外部工作区。`Logs` 和 UpdateHost 事务日志属于运行证据，不作为业务数据。

   旧进程停止后，UpdateHost：

   - 生成路径、长度、SHA-256 清单；
   - 将 `Data`、`UserData` 完整复制到事务快照；
   - 再读一次确认源在复制期间未变化；
   - 不能得到稳定快照就中止更新。

   【读到→推论】当前 shell 启动会重写 `UserData` 中的 nanobot 配置，当前安装器也会运行 provisioning。因此更新验证模式必须禁止迁移、provisioning及业务后台写入，直到事务提交；否则“一个字节不变”无法兑现。[ds_shell_core.py](/root/.openclaw/workspace/projects/design-studio/bin/ds_shell_core.py:980)

5. **安装目录事务**

   【推论】把当前安装目录原子换名为同卷兄弟目录，例如 `.OpenDesign.rollback-<tx>`，而不是在旧树上覆盖。这样不会留下新旧版本混杂和已经从新版删除的旧文件。

   新安装器增加专用 `/S /UPDATE` 模式：

   - 只向空的固定安装路径铺完整 payload；
   - 不调用 `ProvisionConfig`；
   - 不调用数据迁移；
   - 不改桌面图标、开机自启选择或其他用户偏好；
   - 全局版本注册表值延迟到 health 成功后提交；
   - 安装器退出码只决定是否继续验证，不决定成功。

6. **新进程自证**

   【推论】UpdateHost生成一次性随机 nonce，通过启动环境交给新 shell。新 shell 将实际动态 web 端口通过受限 named pipe 告知 UpdateHost。

   `/api/health` 在更新启动时额外返回：

   - `update_tx`：必须来自进程启动环境，不能回显 HTTP 查询参数；
   - `pid` 或进程启动标识；
   - 现有的 `version、ds_root、ok`。

   UpdateHost直接、禁用系统代理地请求该端口，只有以下条件同时成立才成功：

   - HTTP 200，JSON 可解析；
   - `ok is true`；
   - `version` 规范化后严格等于安装包目标版本；
   - `ds_root` 是新安装目录下的 `ds`；
   - `update_tx` 等于本事务 nonce；
   - 回答进程属于刚拉起的候选进程树。

   named-pipe 收据、安装器退出码、注册表版本、磁盘文件均不能代替这次 HTTP 回答。

7. **提交与回滚**

   【推论】health 通过后仍要复算数据清单。只有 health 正确且数据逐字节相同，才写 `COMMITTED`、更新注册表版本并开放窗口和业务后台。

   失败时：

   - 停掉候选进程树；
   - 移走不完整的新目录；
   - 将 rollback 目录原子换回固定路径；
   - 如数据发生变化，用快照恢复并复核；
   - 恢复注册表快照；
   - 拉起旧版，并要求旧版 `/api/health` 自报旧版本。

   只有旧 health 也通过，才能告诉业主“更新失败，已恢复 vX”。旧目录恢复但旧 health 不通时，必须诚实显示“文件已恢复，但旧版没有成功启动”，并保留备份和诊断。

   【推论】每个状态转换都先把事务日志写入临时文件、落盘、再原子替换。断电后稳定宿主看到非 `COMMITTED` 状态时采取保守回滚，因此快捷方式不会指向一个已经被换走的目录。

## 2. Key trade-offs / risks

- 【读到→推论】没有代码签名证书。GitHub digest 能防传输损坏，但 digest 和安装包来自同一个 GitHub 信任域，不能防仓库账号失陷；SmartScreen、杀软也可能阻断或隔离安装包。
- 【推论】UpdateHost 成为高价值单点。它必须小、路径规则固定、拒绝任意 URL/安装目录，并专门防 junction/reparse-point 路径逃逸。
- 【推论】更新期间需要同时容纳旧程序树、新程序树、43MB 安装包及数据快照。磁盘预检必须在关闭旧版前完成；数据很多时，快照时间会明显增加。
- 【推论】杀软或残留子进程可能继续锁住文件。锁未完全释放时不能强装；应在旧目录仍完整的阶段中止。
- 【推论】UpdateHost 本身不能在自己运行时被同一事务覆盖。宿主升级应 side-by-side 落下，待本次进程退出后由下次启动激活。
- 【推论】“数据”范围必须在验收文档里钉死。若要求连 `%LOCALAPPDATA%\OpenDesign\Logs` 都一个字节不变，则与现实现“每次启动必写日志”冲突；这不是测试能补掉的，需要改变日志落点或调整定义。
- 【推论】health 是部署收口，不等于整个产品体验正确。窗口、WebView2、网关、聊天可能仍失败，必须作为额外质量门验证，但不能拿它们替代版本 health 判据。

## 3. Alternatives considered

- **让运行中的 Python 直接覆盖自己**

  【推论】不选。Windows 会锁住正在使用的解释器、DLL和程序文件；同时旧进程一退出，就失去了负责验证和回滚的观察者。

- **旧版直接启动当前 NSIS `/S` 后退出**

  【读到→推论】不选。当前安装器会覆盖现有树并调用 `ProvisionConfig`，没有数据不变契约、事务日志和 health 回滚；退出码 0 也无法证明新进程起来了。

- **A/B 版本槽位加 active pointer**

  【推论】回滚很漂亮，但改动更大。当前配置会写包内 Python 的绝对路径；槽位变化会改变 `UserData` 配置字节，与本需求的数据不变要求直接冲突。固定路径整目录替换更贴合现有结构。

- **MSIX、Squirrel、WinSparkle 等现成更新框架**

  【推论】暂不选。它们要求重做当前 NSIS/Python分发结构，部分路径依赖签名，而且仍不会自动满足“新进程 health 精确版本 + 数据逐字节不变 + 业务定制回滚”。

- **增量更新**

  【推论】按题面排除。全量包反而更适合做空目录安装和完整 payload 校验。

## 4. Test strategy

### 纯逻辑与协议

- release 选择、预发布、版本规范化、缺失/畸形 digest、错误 URL、截断下载、size 不符、hash 不符。
- 状态机每一状态的恢复幂等性；同一事务重复执行不能二次安装或二次回滚。
- health 裁决必须拒绝：旧版本、错误 nonce、错误 `ds_root`、无效 JSON、HTTP 500、陌生端口、回答一次后立即死亡。
- 变异测试：把裁决改成“安装器退出码 0”或“目标文件存在”时，测试必须转红。

### 安装器

- 静态检查 `/UPDATE` 分支不能引用 `DATA_ROOT`、`ProvisionConfig`、用户工作区、开机启动或可选快捷方式。
- 成品检查安装进空目录后的逐文件清单与 payload 完全相同。
- 故意造一个“退出码 0 但缺关键文件”的安装包，必须最终回滚。

### Windows 真机/CI 端到端

以真实旧版安装包作为 N-1，种入中文名、空文件、嵌套目录及随机二进制 canary，记录 `Data`、`UserData` 的完整 byte manifest，然后执行真实“一次点击更新”。

成功断言：

- 旧 shell 和所有子进程消失；
- 新实例 health 返回目标版本、正确 nonce 和新 `ds_root`；
- 数据 manifest 完全相同；
- 关闭新实例后，从桌面、开始菜单、开机入口重新启动，health仍是新版本；
- 截图确认主窗口存在且不是对话框或白屏。

失败注入：

- 下载中断、hash 错、磁盘满；
- 旧进程不退出、孤儿占端口、文件被杀软锁住；
- 安装器非零、安装器零但少文件；
- 新 health 超时、返回旧版本、答错 nonce、只成功一次便崩；
- 候选版本偷偷修改一个数据字节；
- 在每个持久状态写完后强杀 UpdateHost或模拟重启；
- 自定义安装路径、中文/空格路径、无 key、系统代理、普通用户权限。

每条失败用同一套收口：

1. 程序目录恢复为旧版 byte manifest；
2. 数据恢复为原 manifest；
3. 注册表和启动入口恢复；
4. 旧版新进程 `/api/health` 自报旧版本。

【读到】现有 `.github/workflows` 只有 Windows 探针，并且文件自身明确说不是回归判据。因此需要新增独立、强制的 N-1→N 更新工作流，不能只扩展现有“跑完即绿”的探针。[windows-package-probe.yml](/root/.openclaw/workspace/projects/design-studio/.github/workflows/windows-package-probe.yml:1)

### “断言全绿但业主眼里仍然失败，会失败成什么样？”

最可能的形态是：新 `ds-web` 的 health 精确报告了新版本，数据也没变，但 pywebview 主窗口没出现、只剩托盘，或者窗口整块白；业主看到的是“更新完以后软件打不开”。

【读到】仓库已有经验表明“后端活着/首帧已提交”不等于业主眼睛看见正常界面；当前 Windows 探针也明确要求最终看截图。

另外还有三种 oracle 盲区：

- health 通过一瞬间后进程崩溃；
- 工作台活着但网关/MCP没起来，界面能看却不能聊天；
- 当前新进程正常，但快捷方式仍指向旧入口，下次启动又回旧版。

因此 health 仍是部署成功的唯一终局判据，但其后必须附加短稳定窗口、窗口截图、聊天最小 smoke，以及“关闭后从真实快捷方式再启动一次”。这些附加项只能让质量门更严，不能把安装器退出码或盘上文件偷换成部署成功。

本次仅做了只读分析；未运行构建、未联网、未修改任何仓库文件，也未读取 `tracks/` 下的方案文件。
