#!/usr/bin/env python3
"""装完之后把配置弄到位 —— 非交互、幂等(track opendesign-windows-installer S1c)。

    python ds_provision.py --home <数据目录> --ds-root <ds 目录> [--token 口令]

## 它解决的是哪个问题

安装器把文件铺到盘上只是一半。业主双击图标那一刻,外壳要读
`<数据目录>\\.nanobot\\config.json` 才起得来后台 —— **那份文件从来没人生成过**。
老装法(`bin/install.ps1`)靠三步人工问答产出它,而这一单的整个目标就是
「双击装完、不答向导」。所以这里把那三步做成一条非交互的路:

    nanobot 的默认配置  →  打开本地聊天通道(自动口令)  →  合并 Windows 模板

这条路**不是新发明的**:S1b 的考卷 `spike-shell2.py` 就是这么准备配置的,
而它已经在业主真机上跑绿过(10 PASS / 0 FAIL)。这里只是把它从考卷里提出来变成正式脚本,
并补上考卷不需要、但真装机需要的东西:幂等、不碰业主自己那份 nanobot、坏配置不覆盖。

## 两条硬规矩

**① 只写 `--home` 底下。** 业主机器上很可能**已经有一份他自己在用的**
`~/.nanobot/config.json`(openclaw 那套)。碰它 = 把他现有的东西弄坏,而且他不会知道
是我干的。所以这里全程用显式路径,一次都不走 `~` —— 也正因为这条,
本脚本**不复用** `bin/enable_webui.py`(它写死了 `~/.nanobot/config.json`,
是给老装法用的,那个场景下写 `~` 是对的)。

**② 凭据不进配置文件。** key 只走环境变量 `${DS_LLM_KEY}`(配置里只留引用),
由外壳从 `<数据目录>\\.openDesign\\key.txt` 读进来。配置文件是会进日志、进截图、
进收据的东西。

判据:`tests/test_ds_provision.py`(15 条)。
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

# 口令要业主**用眼睛抄**(在引导页做出来之前),所以把长得像的字符全剔掉:
# 0/O、1/l/I 抄错一次的代价是"口令不对",而他不会知道是抄错还是坏了。
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_TOKEN_LEN = 16

TEMPLATE_NAME = "nanobot.config.windows.jsonc"


class Trouble(RuntimeError):
    """给业主看的一句话。**不许把 Python 栈甩给他** —— 他没有终端,也不是程序员。"""


def new_token() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_TOKEN_LEN))


def check_token(token: str) -> str:
    """口令必须是浏览器发得出去的。

    前端把它放进 HTTP 头,而 fetch 的头值只收 Latin-1
    (`web/src/chat/connection.ts` 已经明确拒收)⇒ 中文口令会让两条腿全部正常起来、
    界面也正常,**唯独第一句话永远发不出去**。这是最难查的一种坏法,所以在这里 fail closed。
    与 `ds_shell_core.patch_config` 的那道闸是同一件事,两边都要有:
    那边挡的是"已经存在的坏口令",这边挡的是"刚被写进去的坏口令"。
    """
    token = token.strip()
    if not token:
        raise Trouble("口令不能是空的")
    try:
        token.encode("latin-1")
    except UnicodeEncodeError:
        raise Trouble("口令里有中文或特殊字符,浏览器发不出去 —— 请改成字母数字口令") from None
    return token


def write_json(path: Path, data: dict) -> None:
    """原子落盘。半份配置比没有配置更坏:外壳会拿着它去起后台,然后死在别处。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def default_config() -> dict:
    """nanobot 自己的默认配置。**不手抄一份** —— 手抄的那份会随它升级而过期。"""
    try:
        from nanobot.config.schema import Config
    except ImportError:
        raise Trouble(
            "这份安装包不完整:找不到 nanobot 组件。\n请重新运行安装程序。") from None
    return json.loads(json.dumps(
        Config().model_dump(mode="json", by_alias=True, exclude_none=True)))


def load_existing(cfg_path: Path) -> dict | None:
    """已有配置读出来;读不出来就**停下**,不许当成"没有配置"覆盖掉。

    覆盖的后果:业主用了一年的那份配置(他换过的大脑、加过的通道)一声不响没了。
    """
    if not cfg_path.exists():
        return None
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise Trouble(
            f"已有的配置读不出来,为安全起见没有动它:\n{cfg_path}\n({exc})\n"
            "请把这个文件发给我看看,或者把它改名后重新运行安装程序。") from None
    if not isinstance(data, dict):
        raise Trouble(f"已有的配置不是一份配置:{cfg_path}")
    # 合法 JSON ≠ 形状对。`{"channels": null}` 解析得动,但 setdefault 拿到 None
    # 再 .setdefault 就 AttributeError ⇒ 业主收到一个 Python 栈,而本模块承诺过不给他栈。
    # (四审 subdeepseek F2。低概率,但它盯的正是这句承诺。)
    for path in (("channels",), ("channels", "websocket"), ("tools",), ("providers",)):
        node = data
        for key in path:
            if key not in node:
                break
            node = node[key]
            if not isinstance(node, dict):
                raise Trouble(
                    f"已有的配置里 `{'.'.join(path)}` 不是一段配置(而是 {type(node).__name__}),"
                    f"为安全起见没有动它:\n{cfg_path}\n"
                    "请把这个文件发给我看看,或者把它改名后重新运行安装程序。")
    return data


def set_websocket(cfg: dict, token: str) -> None:
    """打开本地聊天通道并写上口令。

    这四行与 `bin/enable_webui.py` 做的是同一件事,**故意不复用它**:
    那个脚本写死了 `~/.nanobot/config.json`(老装法里那样是对的),而这里绝不能碰 `~`。
    真要合并,该合的是"两边都从一处读 websocket 段的形状",而不是让本脚本去改业主的家。
    """
    ws = cfg.setdefault("channels", {}).setdefault("websocket", {})
    ws["enabled"] = True
    ws["token"] = token
    ws.setdefault("host", "127.0.0.1")
    ws.setdefault("port", 8765)


def merge_template(python_exe: str, ds_root: Path, cfg_path: Path) -> None:
    """合并 Windows 模板的四段(providers / model_presets / agents.defaults / mcpServers)。

    起子进程而不是 import:`ds_merge_config.py` 里有一整套"别把机主选好的大脑重置回
    模板默认"的判断,那是它自己的正确性,不该被本脚本复制一份。
    """
    template = ds_root / "config" / TEMPLATE_NAME
    if not template.is_file():
        raise Trouble(f"这份安装包不完整:找不到配置模板\n{template}\n请重新运行安装程序。")
    merger = ds_root / "bin" / "ds_merge_config.py"
    if not merger.is_file():
        raise Trouble(f"这份安装包不完整:找不到 {merger.name}\n请重新运行安装程序。")
    # 🔴 两道保险都要:合并脚本自己会 `_talk_utf8()`,这里再把它的管道编码钉死。
    # 理由是这条链上"提示写不出中文"曾经害得全新的非中文 Windows 整个装不上
    # (2026-08-25 云机器实测)——而**盘上那份合并脚本不一定和这份一起更新**
    # (业主可能在旧安装目录上覆盖安装)。判据:tests/test_ds_provision.py f1/f2。
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    # no-console-exempt: 装机时由安装器的 nsExec 调用,跑在安装器自己的控制台里、
    # 装完就没了 —— 不是业主日常打开软件的路径。
    # (这一行必须**紧贴**下面那个调用:我 08-25 把说明插在中间,豁免当场失效、
    #  test_no_console_window 立刻红 —— 那道闸干得对,别把它挪开。)
    r = subprocess.run([python_exe, str(merger), str(template), str(cfg_path)],
                       capture_output=True, text=True, encoding="utf-8",
                       # 🔴 解码侧也要 replace(panel subglm 抓到,我自审两遍没看见)。
                       # 编码侧给了 replace、这里却还是 strict:盘上那份合并脚本
                       # 吐出非 UTF-8 字节时,UnicodeDecodeError 在**这一行**抛出 ——
                       # 那不是 Trouble,main 接不住 ⇒ 业主看到 Python 栈。
                       # 同一条管道两个方向,只修一个方向不算修完。判据 f3。
                       errors="replace", timeout=180, env=env)
    if r.returncode != 0:
        raise Trouble("配置合并失败:\n" + (r.stderr or r.stdout or "(没有输出)").strip()[:600])


def write_token_note(home: Path, token: str) -> Path:
    """把口令写到业主找得到的地方。

    口令是随机生成的 ⇒ **不告诉他,他就永远登不进聊天**。
    (引导页做出来之后这一步会退化成"以防万一还留一份",见 design.md 的 S1d 规格。)
    """
    note = home / ".openDesign" / "登录口令.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
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
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass   # 拿不到就算了:这一步是保险,不是功能


def main(argv: list[str]) -> int:
    _talk_utf8()
    ap = argparse.ArgumentParser(description="装完之后把配置弄到位(非交互、幂等)")
    ap.add_argument("--home", required=True, help="业主数据目录(%%LOCALAPPDATA%%\\OpenDesign\\UserData)")
    ap.add_argument("--ds-root", required=True, help="装好的 ds 目录(里面有 bin\\ 和 config\\)")
    ap.add_argument("--token", default=None, help="指定登录口令;不给就沿用已有的,再没有就自动生成")
    ap.add_argument("--python", default=sys.executable, help="跑合并脚本用的解释器")
    a = ap.parse_args(argv)
    try:
        provision(Path(a.home), Path(a.ds_root), a.token, a.python)
    except Trouble as exc:
        # 业主看到的就是这一段。**不带栈** —— 判据 d1 盯着这件事。
        print(f"\n{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
