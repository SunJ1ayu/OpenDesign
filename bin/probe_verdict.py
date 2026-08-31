#!/usr/bin/env python3
"""探针的判定器 —— "机器事实 → 该不该 FAIL" 这件事,由**跑得动的代码**回答。

**为什么有这个文件**(2026-08-30 深夜,track `opendesign-startup-observability`):

Windows 探针 `.github/scripts/windows-package-probe.ps1` 本机跑不了(没有 pwsh),
于是它的判据只能**静态读源码**。今晚这条路被连打回十几次,最后一轮外部评审
(subdeepseek)自己动手变异了 8 种改法并逐条执行 —— **每一种静态判据都全绿**:

    if ($miss.Count)  →  if ($miss.Count -lt 1)     # 极性
    $required = @(外壳, 工作台)  →  加上 网关         # 喂给判定的**值**
    if (Test-Path $log)  →  if (-not (Test-Path))    # 极性
    $appTitle = 'OpenDesign'  →  ''                  # 不改过滤器,改它的输入
    -not $real.Count  →  $real.Count                 # 第二个操作数的极性
    while (… -and $box.Count -eq 0 …)  →  去掉这一项   # 循环为什么停
    $t -like "*$Match*"  →  -notlike                 # 匹配方向
    [W32]::Cls($h)  →  [W32]::Cls($l)                # 参数

形状是固定的:**字面断言天生够不着语义**。补一条字面规则,下一层字面就能绕过去。

⇒ 所以判定搬到这里:**纯函数,进去是事实,出来是裁决**。
探针只负责**采事实**(哪几份日志在、屏幕上有哪些窗口和它们的类、哪个端口应答),
把事实喂进来、把这里给的那句话原样 `Say` 出去。
于是"极性/取值/终止条件/参数"全变成输入输出问题 —— 判据(`tests/test_startup_diag.py`
的 `S19ProbeVerdictIsABehaviour`)喂一组真实事实、断言裁决,变异改哪一处都咬得住。

**调用约定**(探针那边用的就是这个):

    echo '<facts-json>' | python probe_verdict.py logs|window|health

stdout 是**一行**给 `Say` 的话;退出码 0=OK、1=FAIL、2=输入本身有问题。
`FAIL` 这个词只在真该红时出现 —— 探针末尾那道闸认的就是它。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass

# 三份日志:外壳/工作台**必须**有(进程只要被 spawn,文件在 Popen 之前就已落盘,
# 见 ds_shell_core._spawn),网关允许缺席 —— 没填 key 时网关本来就不起,
# 真机健康趟就是"网关缺席"这个形状。把它算成必须 = 每一趟健康的 run 都假红。
BUNDLE_LOGS = ("外壳.log", "工作台.log", "网关.log")
REQUIRED_LOGS = ("外壳.log", "工作台.log")

# MessageBoxW 弹出来的框,窗口类恒为 Windows 的对话框类 #32770;
# pywebview 的主窗口是动态注册的 WinForms 类,不可能是它。
# 而两者的**标题**都是 APP = OpenDesign(ds_shell.alert/die 用的就是 APP)⇒ 标题分不开。
DIALOG_CLASS = "#32770"

# 🔴 2026-08-31:**"哪个窗口是我们的"这件事搬到这里来判**(第六轮 panel)。
#    原来标题过滤写在 .ps1 里(`$appTitle = 'OpenDesign'` + `-like "*$appTitle*"`)。
#    外部评审实测:在它下面补一行 `$appTitle = ''`,50 条判据全绿,而屏幕上
#    **任何**窗口都算我们的 —— CI 机器上永远有个终端 ⇒「界面没画出来」整趟绿。
#    静态断言只看得见第一次赋值,天生够不着"这个变量最后是什么值"。
#    ⇒ 探针改成把**看见的所有窗口**原样交出来,挑窗口在这里做(s19 喂事实就能验)。
#    这个常量必须等于 ds_shell.APP(窗口标题的唯一来源),有跨文件判据钉着。
APP_TITLE = "OpenDesign"


@dataclass(frozen=True)
class Verdict:
    ok: bool
    text: str


def logs_verdict(present: dict) -> Verdict:
    """第 8 相:`present` = {日志名: 字节数 or None(缺席)}。"""
    got, miss = [], []
    for name in BUNDLE_LOGS:
        size = present.get(name)
        if size is None:
            got.append(f"{name} 缺席")
            if name in REQUIRED_LOGS:
                miss.append(name)
        else:
            got.append(f"{name} {size}B")
    detail = " | ".join(got)
    if miss:
        return Verdict(False, f"FAIL - 必须有的日志缺席:{', '.join(miss)} ⇒ 现场是空的。明细:{detail}")
    return Verdict(True, detail)


def _shown(w: dict) -> str:
    """一个窗口在读数里长什么样:「标题」[窗口类]·属主进程。"""
    owner = w.get("proc") or "属主未知"
    return f"「{w.get('title')}」[{w.get('cls')}]·{owner}"


def window_verdict(wins: list, procs: list) -> Verdict:
    """第 6 相。

    `wins`  = EnumWindows 看见的**所有**可见顶层窗口
              [{"title":…, "cls":…, "proc": 属主进程名}] —— 不是已经挑过的;
              挑哪些算我们的由这里做(见 APP_TITLE 那段注释)。

    🔴 **敞着的一条**(2026-08-31 自审量出来的,存量):现在只按**标题**挑。
    业主机器上资源管理器开着 `OpenDesign` 这个文件夹 ⇒ 标题 OpenDesign、
    类 CabinetWClass 的窗口 ⇒ 被算成"真窗口" ⇒ **应用只弹了报错框也报 OK**。
    `proc` 这个事实这一刀只**写进读数**(看到 OK 的人一眼能看出窗口是 explorer 的),
    还没拿它当闸 —— 我们那个窗口的属主进程真名要等真跑打印出来。见 verify.md。
    `procs` = 老口径的原始 dump:所有有主窗口标题的进程 `名字:「标题」`,同样没挑过。
              只在 `wins` 里一个我们的窗口都没有时兜底。
    """
    mine = [w for w in wins if APP_TITLE in str(w.get("title") or "")]
    ours = [t for t in procs if APP_TITLE in str(t)]
    boxes = [w for w in mine if w.get("cls") == DIALOG_CLASS]
    real = [w for w in mine if w.get("cls") != DIALOG_CLASS]
    if real:
        shown = " | ".join(_shown(w) for w in real)
        return Verdict(True, f"OK - {shown}(另有 {len(boxes)} 个报错框)")
    if boxes:
        # 只有框、没有真窗口 = 软件根本打不开(WebView2 缺失那类)。
        # 注意这一支要**先于**老口径判:框本身就是进程主窗口,老口径看得见它。
        shown = " | ".join(_shown(w) for w in boxes)
        return Verdict(False, f"FAIL - 屏幕上只有报错框(窗口类 {DIALOG_CLASS}):{shown} ⇒ 软件根本打不开")
    if ours:
        # 故意的 fail-open:一个都枚举不到时退回老口径,别造假红。
        # 代价(空枚举 + 只有报错框时这个洞会复活)写在读数里,不藏着。
        return Verdict(True, f"OK - {' | '.join(ours)}(EnumWindows 一个都没枚举到,退回老口径)")
    return Verdict(False, "FAIL - 没等到我们的窗口(EnumWindows 和进程主窗口标题都没有)")


def health_verdict(answers: dict, tried: list) -> Verdict:
    """第 5/10 相。

    `answers` = {端口: version} —— **只放真答上来的**(探针不再预填整段);
    `tried`   = 试过哪些端口,用来说清"没答上来时我们问过谁"。

    🔴 端口**会挪**:应用用 `pick_ports([8766,…], span=20)` 挑端口,8766 被占就往后找。
    探针原来把 8766 写死 ⇒ 应用在 8767 上健康启动、探针照样判 FAIL(健康假红)。

    🔴 `tried` 为什么是**单独一个事实**而不是 `answers` 的键(2026-08-31,第六轮 panel):
    原来探针先把整段端口预填成 `$null`、再让这里从键反推端口段。外部评审实测:
    把预填的值从 `$null` 改成 `"0"`(一个字符),整段端口就全"活着" ⇒ 后端死了也绿,
    50 条判据全绿。**能被预填造出来的东西,不能同时当"试过谁"的证据。**
    """
    alive = {int(p): v for p, v in answers.items() if v}
    if alive:
        port, ver = sorted(alive.items())[0]
        return Verdict(True, f"OK - /api/health 通(端口 {port},version={ver})")
    ports = sorted(int(p) for p in tried)
    span = f"{ports[0]}..{ports[-1]}" if ports else "(一个端口都没试)"
    return Verdict(False, f"FAIL - 端口段 {span} 全都不应答 ⇒ 后端没活过来")


_KINDS = {
    "logs": lambda f: logs_verdict(f["present"]),
    "window": lambda f: window_verdict(f.get("wins") or [], f.get("procs") or []),
    "health": lambda f: health_verdict(f["answers"], f.get("tried") or []),
}


def main(argv: list) -> int:
    if len(argv) != 2 or argv[1] not in _KINDS:
        sys.stderr.write(f"用法: probe_verdict.py {'|'.join(_KINDS)} < facts.json\n")
        return 2
    try:
        facts = json.load(sys.stdin)
        v = _KINDS[argv[1]](facts)
    except Exception as exc:                      # 判定器自己坏了要说出来,不许静默
        sys.stdout.write(f"FAIL - 判定器读不懂事实({type(exc).__name__}: {exc})\n")
        return 2
    sys.stdout.write(v.text + "\n")
    return 0 if v.ok else 1


if __name__ == "__main__":
    # 两头都不许赌编码:出去的话会被 Windows ANSI 代码页打炸(本单栽过一次),
    # 进来的事实同理 —— C locale 下 stdin 默认是 ASCII,中文键会全部解不出来。
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
