#!/usr/bin/env python3
"""ds_openfolder —— 「在资源管理器里打开这个文件夹」的平台实现(track opendesign-structure-debt)。

从 ds_web 搬出:这是**唯一一段真正碰操作系统窗口**的代码(Windows 下还要 ctypes 枚举
顶层窗口、把窗口提到前台),混在 HTTP 处理里既看不清边界,也让 oracle 咬不住。
边界:它只管"把某个已存在的目录交给系统打开、尽力提到前台";**不管**路径合不合法、
用户有没有权限看这个目录 —— 那些闸在 ds_web 的调用点(越权判断不能下放到平台层)。

⚠️ 主路径只在 Windows 真机上跑得到(Linux 上连 ctypes.WINFUNCTYPE 都没有),
所以这里的判据是"注入替身测决策逻辑",真行为要靠真机验收 —— 改这个文件,
verify 的 UNTESTED 清单就得跟着更新。
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time



# ── Windows「把资源管理器窗口提到前台」(真机反馈 2026-07-24 #4)──────────────
# 用户:点「打开文件夹」,窗口开在浏览器后面,新用户以为没反应。
# os.startfile 只把请求丢给 shell,z-order 归系统管;而 ds_web 是后台进程、不持前台权,
# **Windows 的前台权规则可能拒绝它抢焦点**(表现为任务栏闪一下)。所以这里是
# 「尽力而为 + 永不阻塞 + 失败静默退化」:提不上来就是今天的行为,绝不倒退,
# 更不用抢焦点的脏招(会被杀软当异常行为)。
# 结构 = 决策与平台 glue 分离,让 oracle 咬得住(tests/test_ds_web_open_front.py):
#   _pick_folder_window  纯逻辑:窗口三元组 → 该激活哪个句柄
#   _win_focus_folder    等窗口出现→激活,注入 enumerator/activator,异常一律吞
#   _win_folder_windows / _win_activate   Windows-only glue(Linux 上连
#                        ctypes.WINFUNCTYPE 都没有 → 只能真机验,见 verify UNTESTED 清单)
_FOLDER_WIN_CLASSES = ("CabinetWClass", "ExploreWClass")


def _pick_folder_window(windows, path: str):
    """windows = [(hwnd, 类名, 标题)] → 目标文件夹那扇窗的 hwnd,没有则 None。
    判据:类名 ∈ 资源管理器窗口类,且标题命中文件夹名 —— 默认标题就是文件夹名,
    用户开了"标题栏显示完整路径"时标题是整条路径,两种都要认。
    命中两种:①标题 == 文件夹名(默认标题);②标题**整条等于目标路径**(完整路径模式,
    分隔符/大小写/尾分隔符归一化后比)。不用"标题含这几个字"(文件夹叫「图」会把
    「施工图」「图片」全认了),也不用"标题以 \\名字 结尾"(panel subdeepseek 提的真问题:
    那样 `E:\\work` 的窗口会被当成 `D:\\work` 的)。标题只有裸文件夹名时确实分不出
    同名不同盘 —— 那是信息不足,只能认;真开错窗口的代价也只是"提错了一扇",不写不删。
    多个命中不断言"选哪个"(EnumWindows 的 z-order 不足以判断"刚开的是哪扇"),
    但返回值必须来自命中集合。"""
    # 反斜杠与正斜杠都要认:os.path.basename 在 Linux 上拆不开 Windows 路径
    # (整条路径原样返回 → 判据恒不命中),而本函数的 oracle 就跑在 Linux 上。
    base = re.split(r"[\\/]", path.rstrip("\\/"))[-1]
    if not base:
        return None
    base_l = base.lower()

    def _norm(p: str) -> str:   # 分隔符/尾分隔符/大小写归一,好比整条路径
        return p.replace("/", "\\").rstrip("\\").lower()

    path_n = _norm(path)
    # 真机日志(2026-07-25)实证:Windows 给的标题是 `3MDAX - 文件资源管理器`,
    # 不是裸文件夹名 —— 第一版要求"标题 == 名字"才命中,于是找到了窗口却擦肩而过
    # (日志原文:no-match … seen=['3MDAX - 文件资源管理器'])。所以标题允许带
    # ` - <后缀>`(中文"文件资源管理器"/英文"File Explorer"/其它本地化名一律照收),
    # 但**必须落在 " - " 这个边界上**:`3MDAXX - …` 不算 `3MDAX`,
    # `施工图 - …` 也不算文件夹「图」(p05b/p05c 两条教训不能被这次放宽推翻)。
    _SUFFIX = " - "

    def _head(t: str) -> str:
        """标题去掉资源管理器后缀:只切**最后一个** " - ",文件夹名里自带 " - " 也安全。"""
        i = t.rfind(_SUFFIX)
        return t[:i] if i > 0 else t

    exact, byname = [], []
    for hwnd, cls, title in windows:
        if cls not in _FOLDER_WIN_CLASSES:
            continue
        t = (title or "").strip()
        for cand in (t, _head(t)):      # 原样 + 去后缀,两种都试
            if _norm(cand) == path_n:
                exact.append(hwnd)      # 完整路径模式:整条对上,最可信
                break
            if cand.lower() == base_l:
                byname.append(hwnd)     # 只有裸文件夹名:信息不足,认它
                break
    if exact:
        return exact[-1]
    return byname[-1] if byname else None


def _win_folder_windows():
    """Windows-only:枚举顶层窗口 → [(hwnd, 类名, 标题)]。Linux 上 ctypes.WINFUNCTYPE
    不存在,所以整段在函数内构造(导入期不碰),测试用注入的 enumerator 替身。"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    out = []
    cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        cls = buf.value
        n = user32.GetWindowTextLengthW(hwnd)
        tbuf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, tbuf, n + 1)
        out.append((hwnd, cls, tbuf.value))
        return True

    user32.EnumWindows(cb_type(_cb), 0)
    return out


def _win_activate(hwnd, *, user32=None, kernel32=None) -> bool:
    """把窗口拿到前台;**返回是否真的在前台**(不是"调用过了")。

    真机反馈 2026-07-25:0.44.0 装上后仍然没置顶。第一版只做温和三连,
    而 Windows 的前台权规则本来就会拒绝后台进程 —— 拒绝了也没人知道,因为
    旧版既不检查结果也不记日志。这版:
      ① 温和档:SW_RESTORE + SwitchToThisWindow(alt-tab 用的那个)。够了就收手。
      ② 升级档:仍不在前台 → `AttachThreadInput` 把本线程输入队列绑到**当前前台
         窗口的线程**上,借它的前台权 BringWindowToTop + SetForegroundWindow。
         这是 Windows 上的标准做法(不伪造按键、不改系统设置),但**必须成对解绑**
         ——不解绑会把两个线程的输入队列绑死,那才是真事故。
      ③ 最后以 `GetForegroundWindow() == hwnd` 为准回报成败,绝不谎报。
    """
    if user32 is None or kernel32 is None:
        import ctypes
        user32 = user32 or ctypes.windll.user32
        kernel32 = kernel32 or ctypes.windll.kernel32
    user32.ShowWindow(hwnd, 9)              # SW_RESTORE:最小化的先还原
    try:
        user32.SwitchToThisWindow(hwnd, True)
    except AttributeError:                  # 极老系统没这个导出
        pass
    if user32.GetForegroundWindow() == hwnd:
        return True
    fg = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    cur_tid = kernel32.GetCurrentThreadId()
    attached = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(fg_tid, cur_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(fg_tid, cur_tid, False)
    return user32.GetForegroundWindow() == hwnd


def _win_focus_folder(path: str, *, enumerator=None, activator=None,
                      attempts: int = 20, delay: float = 0.1, sleep=None,
                      log=None) -> bool:
    """等目标文件夹窗口出现(窗口是异步创建的)→ 激活它。成功 True,放弃/失败 False。
    **任何异常都吞掉**:置顶失败绝不能连带把"打开文件夹"这件事搞失败。
    轮询有上限(默认 20×0.1s=2s),不会因为窗口永不出现就无限转。

    **每次尝试都留一行诊断**(真机反馈 2026-07-25 的直接教训:0.44.0 失败后
    日志里一个字都没有,只能靠猜)。三种结局各自可辨:
      `hwnd=… activate=True/False` = 找到了窗口,系统给不给焦点看 activate;
      `no-match seen=[标题…]`      = 压根没找到 —— 标题对不上/Win11 标签页;
      `error …`                    = 枚举或激活抛了。
    """
    enumerator = enumerator or _win_folder_windows
    activator = activator or _win_activate
    sleep = sleep or time.sleep
    log = log or (lambda msg: print(f"[open-front] {msg}", file=sys.stderr, flush=True))
    seen = []
    for i in range(attempts):
        try:
            windows = list(enumerator())
            seen = [t for _h, cls, t in windows if cls in _FOLDER_WIN_CLASSES]
            hwnd = _pick_folder_window(windows, path)
            if hwnd is not None:
                ok = bool(activator(hwnd))
                log(f"{path!r}: hwnd={hwnd} activate={ok} (第 {i + 1} 轮)")
                return ok
        except Exception as e:                     # noqa: BLE001 —— 尽力而为,不炸
            log(f"{path!r}: error {e!r}(第 {i + 1} 轮)")
            return False
        if i < attempts - 1:
            sleep(delay)
    log(f"{path!r}: no-match 轮询 {attempts} 次未找到资源管理器窗口 seen={seen!r}")
    return False


def _spawn_win_focus(path: str):
    """把置顶丢进 daemon 线程 —— 同步等 2 秒会把 POST /api/open-folder 的响应拖 2 秒
    (ThreadingHTTPServer 不至于卡死别的请求,但按钮会转 2 秒,用户以为又没反应)。
    返回 Thread(仅供 oracle 断言 daemon 属性;调用方不消费)。"""
    t = threading.Thread(target=_win_focus_folder, args=(path,), daemon=True)
    t.start()
    return t


_WIN_FOCUS = _spawn_win_focus  # 模块级可注入(oracle 用替身断时序)


def _open_windows(path: str):
    """Windows 分支:先照旧打开(失败照旧向上抛 → 前端看得见),再异步尝试提到前台。
    **只对目录**做置顶:同一个启动器也用于"用默认程序开单个文件"(rel 分支),那时
    前台窗口是 CAD/PDF 阅读器,找资源管理器窗口既无意义、又可能认错同名的那扇。"""
    # no-console-exempt: os.startfile 不创建进程,它把请求交给 shell(ShellExecute),
    # 由资源管理器/关联程序自己以 GUI 形态打开 —— 没有控制台可弹。
    os.startfile(path)  # noqa: S606 —— 目录路径已过 realpath within 闸
    if os.path.isdir(path):
        _WIN_FOCUS(path)


def _default_open_launcher(path: str):
    """本机打开文件夹。Windows=资源管理器(+尽力提到前台);其余平台 xdg-open(列表参数无 shell)。
    DS_OPEN_CMD 覆盖启动命令(e2e 在无桌面 Linux 上注入记录脚本),同样列表参数。"""
    cmd = os.environ.get("DS_OPEN_CMD")
    if cmd:
        import subprocess
        # no-console-exempt: 只给 e2e 在无桌面 Linux 上注入记录脚本用,业主机器上
        # 根本没有 DS_OPEN_CMD 这个变量(取到的是 None),这条路走不到。
        subprocess.Popen([cmd, path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    elif os.name == "nt":
        _open_windows(path)
    else:
        import subprocess
        # no-console-exempt: Linux 分支。Windows 走上面的 `_open_windows`(os.startfile),
        # 到不了这儿 —— 而 Linux 上根本没有"控制台窗口"这回事。
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

