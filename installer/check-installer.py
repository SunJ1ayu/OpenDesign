#!/usr/bin/env python3
r"""安装器判据 —— 静态闸(查 .nsi 源码)+ 成品闸(查编出来的 .exe)。

## 为什么是这一套闸,而不是"写的时候小心点"

安装器这东西的特点是:**它在业主的机器上以他的身份跑,而我一次也跑不了它**
(makensis 在 Linux 上能编,但编出来的 PE 只有 Windows 能执行)。所以本单的可验证性
全部压在两处:① 这份静态闸;② 业主真机装一趟。**中间没有第三种证据。**

于是这份闸的写法有一条硬规矩:**每一条都必须对应一种真会发生的事故**,
而不是"看着像个检查项"。逐条的事故在每个 check 的 docstring 里写着。

NSIS 的经典脚枪就那么几个,而且**全都是静态可判的**:
  · 卸载时 `RMDir /r "$INSTDIR"`,而 `$INSTDIR` 因为注册表被人删过而成了空串
    ⇒ 展开成 `RMDir /r ""` = 从当前目录开始递归删。这是 NSIS 最出名的一次性事故。
  · 卸载顺手把用户数据一起删了(数据目录在安装根之外也不保险 —— 只要有人手写了
    一条 `RMDir /r "$LOCALAPPDATA\OpenDesign"`)。
  · 要管理员权限(装到 Program Files)⇒ 业主每次更新都撞 UAC,应用内更新直接废掉。
  · 开机自启写进 HKLM ⇒ 要管理员,而且卸载后残留。

## 双向验(这一条是本机的旧账)

`win-deps-audit.py` 曾经因为剥后缀剥错,**把任何包都判成缺失** —— 一个永远红的闸和
一个永远绿的闸一样没用。所以:
  · 干净的 .nsi 必须**全绿**(这份脚本自己在流水线里跑);
  · 每条闸必须被 `mutation-test.sh` 的一个定点变异**咬住**。
两头都验过,这份闸才算数。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- NSIS 词法

_QUOTES = "\"'`"


def strip_comment(line: str) -> str:
    """去掉行尾注释。引号内的 ; # 不算注释 —— 路径里真的会有 `#`。"""
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in _QUOTES:
            quote = ch
            out.append(ch)
        elif ch in ";#":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def tokenize(line: str) -> list[str]:
    """按 NSIS 的规矩切词:引号成组,引号内的空格不切。"""
    toks: list[str] = []
    cur: list[str] = []
    quote = None
    for ch in line:
        if quote:
            if ch == quote:
                quote = None
            else:
                cur.append(ch)
        elif ch in _QUOTES:
            quote = ch
        elif ch.isspace():
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        toks.append("".join(cur))
    return toks


class Nsi:
    """一份 .nsi 的最小语义视图:行、词、以及每行属于安装侧还是卸载侧。

    卸载侧 = `Section "Uninstall"` / `Section un.xxx` / `Function un.xxx` 里面。
    这个区分是本文件一半闸的地基:**同一条 RMDir,在安装侧和卸载侧的意思完全不同**。
    """

    def __init__(self, path: Path):
        self.path = path
        self.raw = path.read_text(encoding="utf-8")
        self.lines: list[str] = []          # 去注释后的正文
        self.toks: list[list[str]] = []
        self.uninst: list[bool] = []        # 这一行在不在卸载侧
        self.block: list[str] = []          # 所属 Section/Function 的名字("" = 顶层)

        in_un = False
        block = ""
        in_block_comment = False
        for raw in self.raw.splitlines():
            text = raw
            # /* */ 块注释:NSIS 支持,别让藏在里面的东西被当成正文
            if in_block_comment:
                if "*/" in text:
                    text = text.split("*/", 1)[1]
                    in_block_comment = False
                else:
                    text = ""
            if "/*" in text:
                head, rest = text.split("/*", 1)
                if "*/" in rest:
                    text = head + rest.split("*/", 1)[1]
                else:
                    text = head
                    in_block_comment = True
            text = strip_comment(text)
            t = tokenize(text)
            if t:
                head = t[0].lower()
                if head == "section":
                    args = [a for a in t[1:] if not a.startswith("/")]
                    name = args[0] if args else ""
                    ident = args[1] if len(args) > 1 else ""
                    block = name
                    in_un = (name.strip().lower() == "uninstall"
                             or name.lower().startswith("un.")
                             or ident.lower().startswith("un."))
                elif head == "sectionend":
                    block, in_un = "", False
                elif head == "function":
                    name = t[1] if len(t) > 1 else ""
                    block = name
                    in_un = name.lower().startswith("un.")
                elif head == "functionend":
                    block, in_un = "", False
            self.lines.append(text)
            self.toks.append(t)
            self.uninst.append(in_un)
            self.block.append(block)

    def rows(self):
        for i, t in enumerate(self.toks):
            if t:
                yield i + 1, t, self.uninst[i], self.block[i]

    def cmd(self, name: str):
        """所有以 `name` 开头的行(大小写不敏感)。"""
        low = name.lower()
        for ln, t, un, blk in self.rows():
            if t[0].lower() == low:
                yield ln, t, un, blk

    def defines(self) -> dict[str, str]:
        d = {}
        for _ln, t, _un, _blk in self.cmd("!define"):
            if len(t) >= 3:
                d[t[1]] = t[2]
            elif len(t) == 2:
                d[t[1]] = ""
        return d

    def expand(self, s: str) -> str:
        """把 `${X}` 按本文件的 !define 展开(够用即可,循环三轮防自引用)。"""
        for _ in range(3):
            new = re.sub(r"\$\{(\w+)\}", lambda m: self.defines().get(m.group(1), m.group(0)), s)
            if new == s:
                break
            s = new
        return s


# ---------------------------------------------------------------- 闸

class Report:
    def __init__(self):
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = ""):
        self.rows.append((name, ok, detail))

    def print_and_exit(self, title: str) -> int:
        print(f"\n==== {title} ====")
        bad = 0
        for name, ok, detail in self.rows:
            mark = "PASS" if ok else "FAIL"
            if not ok:
                bad += 1
            print(f"[{mark}] {name}" + (f"\n        {detail}" if detail else ""))
        print(f"---- 合计 {len(self.rows)} 条,{bad} 条不合格 ----")
        return 1 if bad else 0


# 删除类指令:静态闸判"会不会删到不该删的东西"就看这几个
_DELETE_CMDS = {"rmdir", "delete"}
# 写注册表的指令(读的不算 —— 检测 WebView2 就要读 HKLM,读是允许的)
_REG_WRITE_CMDS = {"writeregstr", "writeregdword", "writeregbin", "writeregexpandstr",
                   "writeregmultistr", "deleteregkey", "deleteregvalue"}


def norm_path(p: str) -> str:
    return p.replace("/", "\\").rstrip("\\").lower()


def under(child: str, parent: str) -> bool:
    """child 是不是 parent 或它下面的东西(纯字符串判断,够静态闸用)。"""
    c, p = norm_path(child), norm_path(parent)
    return c == p or c.startswith(p + "\\")


def static_checks(nsi: Nsi, rep: Report) -> None:
    d = nsi.defines()
    install_dir = ""
    for _ln, t, _un, _blk in nsi.cmd("InstallDir"):
        install_dir = nsi.expand(t[1]) if len(t) > 1 else ""

    def resolve(s: str) -> str:
        """展开 `${...}` **并且**把 `$INSTDIR` 还原成它实际指的那个目录。

        🔴 少了后半句这份闸就有个洞:把数据目录写成 `$INSTDIR\\data` 时,
        纯字符串比较看不出它在安装根**里面**,G3/G4 会放行 —— 而那恰恰是这两条闸
        存在的理由(卸载时整棵删安装根 = 把业主的资料一起删了)。
        这个洞是红检 M3 找出来的,不是我看出来的。
        """
        return nsi.expand(s).replace("$INSTDIR", install_dir)

    data_root = resolve(d.get("DATA_ROOT", ""))

    # G1 ── 事故:装到 Program Files ⇒ 每次应用内更新都要管理员,业主的一键更新直接废掉。
    levels = [t[1].lower() for _ln, t, _un, _blk in nsi.cmd("RequestExecutionLevel") if len(t) > 1]
    rep.add("G1 不要管理员权限(RequestExecutionLevel user)",
            levels == ["user"], f"实际:{levels or '没写'}")

    # G2 ── 同上的另一半:装的位置本身必须是每用户可写的。
    rep.add("G2 装在 $LOCALAPPDATA\\Programs 下,且全文不出现 $PROGRAMFILES",
            bool(install_dir) and norm_path(install_dir).startswith("$localappdata\\programs")
            and "$programfiles" not in nsi.raw.lower(),
            f"InstallDir={install_dir or '没写'}")

    # G3 ── 数据必须在安装根之外。design A∪B 第 4 条:边界从"约定"变成"路径",
    #        卸载/更新逻辑就不必再为树里那个特殊目录开例外。
    rep.add("G3 数据目录在安装根之外",
            bool(data_root) and not under(data_root, install_dir),
            f"DATA_ROOT={data_root or '没定义'} / INSTALL={install_dir}")

    # G4 ── 事故:卸载顺手把两年的档案删了。默认卸载路径上**一条**碰数据根的删除都不许有;
    #        真要删,只能在一个默认不勾的可选段里(见 G5)。
    optional_un_sections = {name for _ln, t, un, name in nsi.rows()
                            if t[0].lower() == "section" and un and "/o" in [a.lower() for a in t]}
    offenders = []
    for ln, t, un, blk in nsi.rows():
        if not un or t[0].lower() not in _DELETE_CMDS:
            continue
        targets = [a for a in t[1:] if not a.startswith("/")]
        for tgt in targets:
            if data_root and under(resolve(tgt), data_root) and blk not in optional_un_sections:
                offenders.append(f"{ln}: {' '.join(t)}")
    rep.add("G4 默认卸载路径不碰业主数据", not offenders, "; ".join(offenders))

    # G5 ── "删数据"这个动作必须存在、必须在卸载侧、且必须默认不勾(`/o`)。
    #        B 卷原话:删数据必须是卸载器里单独的、默认不勾的选项。
    wipes = [blk for ln, t, un, blk in nsi.rows()
             if un and t[0].lower() in _DELETE_CMDS
             and any(data_root and under(resolve(a), data_root) for a in t[1:])]
    rep.add("G5 删数据是单独的、默认不勾的可选段",
            bool(wipes) and all(b in optional_un_sections for b in wipes),
            f"删数据的段={sorted(set(wipes)) or '没有'} / 默认不勾的段={sorted(optional_un_sections)}")

    # G6 ── 事故:`RMDir /r "$INSTDIR"` 而 $INSTDIR 是空串 ⇒ 从当前目录开始递归删。
    #        NSIS 官方文档自己把这条列为警告。防法:删之前先确认这确实是我们装的目录。
    ok_guard, detail = _check_instdir_guard(nsi)
    rep.add("G6 递归删安装目录之前先验哨兵文件", ok_guard, detail)

    # G7 ── 事故:开机自启写 HKLM ⇒ 要管理员;而且卸载时业主的账户删不掉,永久残留。
    #        注意:**读** HKLM 是允许的(检测 WebView2 就要读),这里只查写。
    hklm_writes = [f"{ln}: {' '.join(t)}" for ln, t, _un, _blk in nsi.rows()
                   if t[0].lower() in _REG_WRITE_CMDS and len(t) > 1 and t[1].upper() == "HKLM"]
    rep.add("G7 不往 HKLM 写任何东西(读可以)", not hklm_writes, "; ".join(hklm_writes))

    # G8 ── 事故:卸载后开机自启还在 ⇒ 每次开机弹一个"找不到文件"。
    run_key = nsi.expand(d.get("RUN_KEY", ""))
    un_del_run = any(un and t[0].lower() in {"deleteregvalue", "deleteregkey"}
                     and any(run_key and run_key.lower() in nsi.expand(a).lower() for a in t[1:])
                     for _ln, t, un, _blk in nsi.rows())
    rep.add("G8 卸载时删掉开机自启项", bool(run_key) and un_del_run, f"RUN_KEY={run_key}")

    # G9 ── 卸载条目本身:装了要出现在"应用和功能"里,卸载后要消失。
    unkey = nsi.expand(d.get("UNINST_KEY", ""))
    wrote = any(t[0].lower() == "writeregstr" and any(unkey and unkey.lower() in nsi.expand(a).lower()
                                                      for a in t[1:])
                for _ln, t, _un, _blk in nsi.rows())
    removed = any(un and t[0].lower() == "deleteregkey"
                  and any(unkey and unkey.lower() in nsi.expand(a).lower() for a in t[1:])
                  for _ln, t, un, _blk in nsi.rows())
    rep.add("G9 写卸载条目、卸载时删掉它", bool(unkey) and wrote and removed,
            f"UNINST_KEY={unkey} 写={wrote} 删={removed}")

    # G10 ── S1a 的账:WebView2 只证明了那两台机器上有。不许赌 —— 检测 + 官方引导程序兜底。
    #         查的是**机制**不是注释:既要读那个 GUID 的 pv,又要真去执行 bootstrapper。
    guid = "F3017226-FE2A-4295-8BDF-00C3A9A7E4C5"
    reads_guid = guid.lower() in nsi.raw.lower()
    runs_boot = any(t[0].lower() in {"exec", "execwait", "execshell"}
                    and "webview2setup" in " ".join(t).lower()
                    for _ln, t, _un, _blk in nsi.rows())
    rep.add("G10 检测 WebView2 并在缺失时跑官方引导程序",
            reads_guid and runs_boot, f"读注册表={reads_guid} 跑引导程序={runs_boot}")

    # G11 ── design 已拍板:安装器全程不经手凭据(key 与口令在首次打开时问)。
    #         这条闸的价值是**防止将来有人图省事**把 key 塞进安装器界面。
    banned = [w for w in ("DS_LLM_KEY", "apiKey", "sk-", "登录口令", "password")
              if w.lower() in nsi.raw.lower()]
    rep.add("G11 安装器不经手 key / 口令", not banned, f"出现了:{banned}")

    # G12 ── 中文路径与中文文案(业主的用户名可能是中文)。ANSI 版 NSIS 会当场乱码。
    rep.add("G12 Unicode true",
            any(len(t) > 1 and t[1].lower() == "true" for _ln, t, _un, _blk in nsi.cmd("Unicode")))

    # G13 ── 快捷方式必须指向启动器,不许直指 python.exe:
    #         直指的话业主看到的是 Python 的图标和名字,而且将来换启动方式要改三处。
    links = [(ln, t) for ln, t, _un, _blk in nsi.rows() if t[0].lower() == "createshortcut"]
    bad_links = [f"{ln}: {' '.join(t)}" for ln, t in links
                 if len(t) > 2 and "python" in t[2].lower()]
    rep.add("G13 快捷方式指向启动器而不是 python.exe",
            bool(links) and not bad_links, "; ".join(bad_links) or f"{len(links)} 个快捷方式")

    # G15 ── 装进一个本来就有别的东西的文件夹 ⇒ 卸载时把那些东西一起删掉。
    #         G6 的哨兵挡不住这一种(装完之后哨兵就在那儿了)。自审时补的。
    ok_dir, detail_dir = _check_dir_page_guard(nsi)
    rep.add("G15 装进非空目录时会拦一下", ok_dir, detail_dir)

    # G14 ── 业主自己拍的板:开机自启做成**选项**。所以它必须是可取消的段,
    #         而且默认不勾(常驻+自启会把 dream 放大到 24 小时,design 已记账)。
    autorun_sections = [name for _ln, t, un, name in nsi.rows()
                        if t[0].lower() == "section" and not un
                        and any(run_key and run_key.lower() in nsi.expand(a).lower()
                                for a in t[1:])]
    optional_sections = {name for _ln, t, un, name in nsi.rows()
                         if t[0].lower() == "section" and not un
                         and "/o" in [a.lower() for a in t]}
    autorun_blocks = {blk for _ln, t, un, blk in nsi.rows()
                      if not un and t[0].lower() in {"writeregstr", "writeregexpandstr"}
                      and any(run_key and run_key.lower() in nsi.expand(a).lower() for a in t[1:])}
    rep.add("G14 开机自启是默认不勾的可选段",
            bool(autorun_blocks) and autorun_blocks <= optional_sections,
            f"写自启的段={sorted(autorun_blocks)} / 默认不勾的段={sorted(optional_sections)}"
            + (f" / {autorun_sections}" if autorun_sections else ""))


def _check_dir_page_guard(nsi: Nsi) -> tuple[bool, str]:
    r"""装到一个**本来就有别的东西**的文件夹 ⇒ 卸载时把那些东西一起删掉。

    这条是自审时想出来的、G6 的哨兵**挡不住**的一种:哨兵问的是"这是不是我们装的地方",
    而业主要是把路径改成 `D:\文档`,装完之后哨兵文件就在那儿了 —— 哨兵会说"是我们的",
    然后 `RMDir /r` 把他的文档全删了。概率低,后果不可逆。

    ⇒ 要求存在一个**目录页的离开回调**,并且它真的去数了目录里有什么
    (FindFirst)。只查"有没有这个函数"不够:空壳函数照样过。
    """
    leave = [name for _ln, t, _un, name in nsi.rows()
             if t[0].lower() == "function" and len(t) > 1
             and t[1].lower() in {".ondirleave", "dirleave", "instdirleave"}]
    if not leave:
        # MUI 的目录页离开回调是靠 !define MUI_PAGE_CUSTOMFUNCTION_LEAVE 指定的
        for _ln, t, _un, _blk in nsi.cmd("!define"):
            if len(t) > 2 and t[1].upper() == "MUI_PAGE_CUSTOMFUNCTION_LEAVE":
                leave = [t[2]]
                break
    if not leave:
        return False, "没有目录页的离开回调 ⇒ 装进非空目录时没人拦"
    fn = leave[0].lower()
    counted = any(blk.lower() == fn and t[0].lower() in {"findfirst", "findnext"}
                  for _ln, t, _un, blk in nsi.rows())
    warned = any(blk.lower() == fn and t[0].lower() == "messagebox"
                 for _ln, t, _un, blk in nsi.rows())
    return (counted and warned,
            f"回调 {leave[0]}:数了目录内容={counted} 会提醒={warned}")


def _check_instdir_guard(nsi: Nsi) -> tuple[bool, str]:
    """`RMDir /r "$INSTDIR"` 之前,必须先确认这真是我们装的目录。

    判法要具体,否则就成了"有个 IfFileExists 就算数":
    要求在**同一个卸载段里、且在递归删之前**出现一条 IfFileExists,
    其目标位于 $INSTDIR 之下且不是 $INSTDIR 本身(= 哨兵文件)。
    """
    hits = [(ln, blk) for ln, t, un, blk in nsi.rows()
            if un and t[0].lower() == "rmdir" and "/r" in [a.lower() for a in t]
            and any(norm_path(nsi.expand(a)) == "$instdir" for a in t[1:])]
    if not hits:
        return True, "没有对 $INSTDIR 的递归删(不需要哨兵)"
    guards = [(ln, blk) for ln, t, un, blk in nsi.rows()
              if un and t[0].lower() == "iffileexists" and len(t) > 1
              and under(nsi.expand(t[1]), "$INSTDIR")
              and norm_path(nsi.expand(t[1])) != "$instdir"]
    for ln, blk in hits:
        if not any(g_ln < ln and g_blk == blk for g_ln, g_blk in guards):
            return False, f"第 {ln} 行 RMDir /r $INSTDIR 之前没有哨兵检查"
    return True, f"{len(hits)} 处递归删,每处之前都有哨兵"


def launcher_checks(nsi: Nsi, rep: Report) -> None:
    """启动器 stub 的闸。它很小,但它是业主每天双击的那个东西。"""
    rep.add("L1 静默启动(SilentInstall silent)",
            any(len(t) > 1 and t[1].lower() == "silent"
                for _ln, t, _un, _blk in nsi.cmd("SilentInstall")))
    rep.add("L2 不要管理员权限",
            [t[1].lower() for _ln, t, _un, _blk in nsi.cmd("RequestExecutionLevel")
             if len(t) > 1] == ["user"])
    rep.add("L3 有自己的图标", bool(list(nsi.cmd("Icon"))))
    # 用 pythonw 而不是 python:后者会常驻一个黑窗口在任务栏上,业主会以为是病毒。
    execs = [" ".join(t) for _ln, t, _un, _blk in nsi.rows()
             if t[0].lower() in {"exec", "execwait", "execshell"}]
    rep.add("L4 用 pythonw.exe 起(不留黑窗口)",
            bool(execs) and all("pythonw.exe" in e for e in execs), "; ".join(execs))
    # 不等它:等 = 启动器一直挂在任务管理器里,而且托盘退出后它才退,毫无意义。
    rep.add("L5 起完就退(Exec 不是 ExecWait)",
            not any(t[0].lower() == "execwait" for _ln, t, _un, _blk in nsi.rows()))
    # 装坏了要说人话 —— 这是 S1b 真机红教的:业主没有终端,不弹窗等于没报错。
    #
    # 🔴 第一版写的是"有 IfFileExists 且有 MessageBox",红检 M18 当场证明它太松:
    # 启动器里有**两处**存在性检查,拆掉其中一处的提示,这条照样绿 —— 而那一处正好是
    # 业主最可能遇到的(杀软吃掉 python\)。真正的契约是**每一处检查都要有对应的提示**,
    # 所以改成数量关系。同类账见 tasks.md「断言名比它问的强」。
    checks = [ln for ln, t, _un, _blk in nsi.rows() if t[0].lower() == "iffileexists"]
    alerts = [ln for ln, t, _un, _blk in nsi.rows() if t[0].lower() == "messagebox"]
    rep.add("L6 每一处组件检查都配一句中文提示",
            bool(checks) and len(alerts) >= len(checks),
            f"{len(checks)} 处检查 / {len(alerts)} 句提示")


# ---------------------------------------------------------------- 成品闸

# makensis -V4 的清单行有两种形态,**都要认**:
#   File: "x.py" 1511 bytes                 (整包压缩 /SOLID:只有原始大小)
#   File: "x.py" [compress] 640/1511 bytes  (逐文件压缩:压缩后/原始)
# 第一版只认第二种,于是清单解析出 0 个文件、P4 报"少了 21969 个" ——
# **闸红得对但理由是假的**,差点让我去查 File /r 而不是查自己的正则。
_FILE_RE = re.compile(
    r'^File: "(?P<name>[^"]+)"(?: \[(?:no )?compress\])?\s+(?:\d+/)?(?P<size>\d+) bytes')
# "Descending/Returning to" 给的是**完整相对路径**(不是一层层的名字),
# 所以直接记住"当前在哪个目录"就行,别拿栈去猜嵌套。
_DESC_RE = re.compile(r'^File: Descending to: "(?P<dir>[^"]+)"')
_RET_RE = re.compile(r'^File: Returning to: "(?P<dir>[^"]+)"')


def manifest_from_log(log_text: str, payload_name: str) -> dict[str, int]:
    """从 `makensis -V4` 的输出里还原"到底哪些文件被压进去了"。

    为什么不信"我写了 File /r 所以它进去了":`File /r` 的 glob 写歪一个字母,
    编译照样成功、包照样出得来,**少了半棵树**。编译器自己打印的清单是唯一
    不靠我复述的证据。
    """
    files: dict[str, int] = {}
    cur = payload_name
    for line in log_text.splitlines():
        line = line.strip()
        m = _DESC_RE.match(line) or _RET_RE.match(line)
        if m:
            cur = m.group("dir").replace("\\", "/").strip("/")
            continue
        m = _FILE_RE.match(line)
        if m:
            rel = f"{cur}/{m.group('name')}".replace("\\", "/")
            # 去掉 payload 根前缀,只留包内相对路径
            for prefix in (payload_name + "/", "./" + payload_name + "/"):
                if rel.startswith(prefix):
                    rel = rel[len(prefix):]
                    break
            files[rel] = int(m.group("size"))
    return files


def product_checks(exe: Path, log: Path, payload: Path, version: str, rep: Report) -> None:
    rep.add("P1 安装器 .exe 出得来", exe.is_file(), str(exe))
    if not exe.is_file():
        return
    head = exe.read_bytes()[:2]
    size = exe.stat().st_size
    rep.add("P2 是个 PE 可执行文件", head == b"MZ", f"头两字节={head!r}")
    # 区间是"sanity"不是精度:低于 40MB 说明 payload 整块没进去(最想抓的那种),
    # 高于 250MB 说明混进了不该带的东西。
    rep.add("P3 体积在合理区间(40MB–250MB)", 40 * 2**20 < size < 250 * 2**20,
            f"{size / 2**20:.1f} MB")

    got = manifest_from_log(log.read_text(encoding="utf-8", errors="replace"), payload.name)
    want = {str(p.relative_to(payload)).replace("\\", "/"): p.stat().st_size
            for p in payload.rglob("*") if p.is_file()}
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    rep.add("P4 编进去的文件 == payload 树(不多不少)",
            not missing and not extra,
            f"少了 {len(missing)} 个 {missing[:5]} / 多了 {len(extra)} 个 {extra[:5]}")
    mismatched = [k for k in set(want) & set(got) if want[k] != got[k]]
    rep.add("P5 每个文件的字节数逐个对得上", not mismatched,
            f"{len(mismatched)} 个对不上:{mismatched[:5]}")

    # 版本号锚:唯一来源是 bin/ds_web.py 的 VERSION。名字里印错版本 = 业主装完
    # 报的版本和我以为发的不是一回事,而这正是"在使用现场验证"那条规矩要防的。
    rep.add("P6 文件名里的版本号 == ds_web 的 VERSION",
            version in exe.name, f"{exe.name} 里应含 {version}")


# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="安装器判据")
    sub = ap.add_subparsers(dest="mode", required=True)

    s = sub.add_parser("static", help="查 .nsi 源码")
    s.add_argument("nsi")
    s.add_argument("--launcher", help="启动器 stub 的 .nsi")

    p = sub.add_parser("product", help="查编出来的成品")
    p.add_argument("--exe", required=True)
    p.add_argument("--log", required=True, help="makensis -V4 的完整输出")
    p.add_argument("--payload", required=True, help="被打进去的那棵树")
    p.add_argument("--version", required=True)

    a = ap.parse_args(argv)
    rep = Report()
    if a.mode == "static":
        nsi_path = Path(a.nsi)
        if not nsi_path.is_file():
            rep.add("安装器脚本存在", False, f"找不到 {nsi_path}")
            return rep.print_and_exit("静态闸")
        static_checks(Nsi(nsi_path), rep)
        if a.launcher:
            lp = Path(a.launcher)
            if not lp.is_file():
                rep.add("启动器脚本存在", False, f"找不到 {lp}")
            else:
                launcher_checks(Nsi(lp), rep)
        return rep.print_and_exit("静态闸")

    product_checks(Path(a.exe), Path(a.log), Path(a.payload), a.version, rep)
    return rep.print_and_exit("成品闸")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
