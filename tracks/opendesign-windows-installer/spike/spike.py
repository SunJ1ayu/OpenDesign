"""OpenDesign Windows 探路包 —— 判据本体(track opendesign-windows-installer,S0)。

回答一件事:**免装 Python(embeddable)能不能跑起 OpenDesign 这一整套。**
这个问题在 Linux 上验不了(embeddable 版的 sys.path 由 ._pth 写死、默认不加载
site-packages、不带 pip/venv),所以只能到真机上测量,而不是推理。

只读、不装、不改机器:所有东西都在本文件夹内(fakehome 当 HOME/USERPROFILE),
不写注册表、不进 PATH、不碰 %USERPROFILE%\\.nanobot。删掉文件夹 = 完全消失。

判据六问与七个防骗焊点见 design.md「Test strategy (oracle)」。收据写进 收据.txt。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

# Windows 的 cmd 默认不是 UTF-8,不焊这一下,打印中文会 UnicodeEncodeError 而假红。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
PYDIR = ROOT / "python"
DSDIR = ROOT / "ds"
FAKEHOME = ROOT / "fakehome"
RECEIPT = ROOT / "收据.txt"
LOGDIR = ROOT / "运行日志"

# 非常规端口:躲开业主自己可能正开着的 OpenDesign(网关 8765 / ds-web 8766)。
GATEWAY_PORT = 18795
WS_PORT = 18797
DSWEB_PORT = 18796

PYEXE = PYDIR / ("python.exe" if os.name == "nt" else "bin/python")

failures: list[str] = []
skipped: list[str] = []
_lines: list[str] = []


def emit(s: str = "") -> None:
    print(s)
    _lines.append(s)


def check(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    emit(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}" + (f" —— {detail}" if detail else ""))
    if not ok:
        failures.append(f"{cid} {name}" + (f"({detail})" if detail else ""))
    return ok


def blew_up(cid: str, name: str, exc: BaseException) -> None:
    """红了要说得出断在哪一句,否则拿到红也推进不了(焊点7)。"""
    tb = traceback.format_exc().splitlines()
    emit(f"  [FAIL] {cid} {name} —— 抛异常 {type(exc).__name__}: {exc}")
    emit("        ---- 原始报错(前 20 行)----")
    for line in tb[:20]:
        emit("        " + line)
    emit("        ---------------------------")
    failures.append(f"{cid} {name}(抛 {type(exc).__name__}: {exc})")


def skip(cid: str, name: str, why: str) -> None:
    """SKIP 不是 PASS —— 明账,不遮掩。"""
    emit(f"  [SKIP] {cid} {name} —— {why}")
    skipped.append(f"{cid} {name}({why})")


ROOT_RAW = Path(__file__).absolute().parent   # 不跟穿软链接的那一份


def inside_root(p: str | os.PathLike[str] | None) -> bool:
    """判"这个路径是不是本包里的",**两种写法命中一种就算**。

    只用 resolve() 会跟穿软链接 ⇒ **假红**:台架上 venv 的 `bin/python` 是指向系统
    解释器的软链,被判成"包外";Windows 上更现实的踩法是业主把包解压在 OneDrive
    重定向目录或映射盘下(路径经 junction),`__file__` 解析出的真路径和启动时的路径
    对不上,整包当场假红 —— 而我会据此得出"免装 Python 不行"这个完全错误的结论。
    **假报警和假绿一样坏**(08-11 变异脚本三次自己坏了那次的账)。

    反过来也不能因此把闸放空:机器上装的 `C:\\Python312\\python.exe` 两种写法都不在
    包内,照样红。这里放宽的只是"同一个东西的两种叫法",不是"别人家的东西"。
    """
    if not p:
        return False
    q = Path(p)
    try:
        cands = (Path(os.path.abspath(q)), q.resolve())
    except Exception:
        cands = (Path(os.path.abspath(q)), )
    for base in (ROOT_RAW, ROOT):
        for cand in cands:
            try:
                cand.relative_to(base)
                return True
            except ValueError:
                pass
    return False


def port_open(port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def http_get(port: int, path: str, timeout: float = 10.0) -> tuple[int, str]:
    """裸 socket 发一个 GET —— 不引第三方库,免得判据自己依赖被测对象。"""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(f"GET {path} HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n".encode())
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    head, _, body = raw.partition("\r\n\r\n")
    status = 0
    first = head.split("\r\n", 1)[0].split(" ")
    if len(first) >= 2 and first[1].isdigit():
        status = int(first[1])
    return status, body


def run(cid: str, name: str, argv: list[str], env: dict, timeout: int = 300) -> bool:
    """跑子进程并**显式判 returncode**。

    焊点4:任何命令都不接管道 —— 08-11 我一天两次把失败的 rc 喂给 `| tail` 吃掉,
    收据印着"通过"、正文写着失败。这里 rc 只从 CompletedProcess.returncode 来。
    """
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=timeout, cwd=str(ROOT))
    except Exception as exc:
        blew_up(cid, name, exc)
        return False
    out = (p.stdout or "").strip()
    if out:
        for line in out.splitlines()[:6]:
            emit("        > " + line)
    if p.returncode != 0:
        emit(f"  [FAIL] {cid} {name} —— 退出码 {p.returncode}")
        for line in (p.stderr or "").splitlines()[:20]:
            emit("        " + line)
        failures.append(f"{cid} {name}(退出码 {p.returncode})")
        return False
    emit(f"  [PASS] {cid} {name} —— 退出码 0")
    return True


def child_env() -> dict:
    env = dict(os.environ)
    env["HOME"] = str(FAKEHOME)
    env["USERPROFILE"] = str(FAKEHOME)
    env["DS_ROOT"] = str(DSDIR)
    env["DS_LLM_KEY"] = "sk-spike-not-a-real-key"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("PYTHONPATH", None)          # 别让机器上已有的 PYTHONPATH 混进来(焊点2)
    return env


# ===========================================================================
def gate_s0_identity() -> bool:
    """S0 我到底在用谁的 Python、谁的包(焊点1、焊点2)。

    业主机器上很可能本来就装着 Python。只要有一处走了机器上那个,整份收据就是假的 ——
    而且是最难看的那种假:它会绿。
    """
    emit("\n[S0] 我用的是谁的 Python、谁的包")
    emit(f"  sys.executable = {sys.executable}")
    emit(f"  sys.prefix     = {sys.prefix}")
    emit(f"  包根目录        = {ROOT}")
    ok = check("S0a", "解释器在本包内(不是机器上装的那个)", inside_root(sys.executable),
               f"{sys.executable}")
    emit("  sys.path:")
    for p in sys.path:
        emit(f"    - {p}{'' if inside_root(p) or not p else '   <<< 包外!'}")
    outside = [p for p in sys.path if p and not inside_root(p)]
    ok = check("S0b", "sys.path 没有指向包外的条目", not outside,
               f"包外条目 {outside}" if outside else "") and ok
    return ok


def gate_s1_python() -> bool:
    emit("\n[S1] 免装 Python 起得来")
    import platform
    v = platform.python_version()
    return check("S1", "版本 == 3.12.10", v == "3.12.10", f"实际 {v}")


def gate_s2_native() -> bool:
    """S2 25 个 native 扩展**真能用**,不是 import 成功就算(焊点5)。

    有些扩展 import 时不碰 DLL,真调用才炸 —— 只 import 的判据在 Windows 上最会骗人。
    """
    emit("\n[S2] native 扩展真能用(每个都真做一次运算)")
    ok = True

    try:
        from pydantic import BaseModel

        class _M(BaseModel):
            n: int

        got = _M(n="3").n            # pydantic_core:真跑一次校验+强制转换
        ok = check("S2a", "pydantic_core 真校验", got == 3, f"n={got!r}") and ok
    except Exception as exc:
        blew_up("S2a", "pydantic_core 真校验", exc); ok = False

    try:
        from cryptography.fernet import Fernet
        k = Fernet(Fernet.generate_key())
        ok = check("S2b", "cryptography 真加解密",
                   k.decrypt(k.encrypt(b"opendesign")) == b"opendesign") and ok
    except Exception as exc:
        blew_up("S2b", "cryptography 真加解密", exc); ok = False

    try:
        from lxml import etree
        ok = check("S2c", "lxml 真解析 XML",
                   etree.fromstring("<a><b>客厅</b></a>").findtext("b") == "客厅") and ok
    except Exception as exc:
        blew_up("S2c", "lxml 真解析 XML", exc); ok = False

    try:
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), (12, 34, 56)).save(buf, format="PNG")
        buf.seek(0)
        ok = check("S2d", "Pillow 真存真读一张图",
                   Image.open(buf).getpixel((1, 1)) == (12, 34, 56)) and ok
    except Exception as exc:
        blew_up("S2d", "Pillow 真存真读一张图", exc); ok = False

    try:
        import msgpack
        ok = check("S2e", "msgpack 真打包解包",
                   msgpack.unpackb(msgpack.packb({"a": 1})) == {"a": 1}) and ok
    except Exception as exc:
        blew_up("S2e", "msgpack 真打包解包", exc); ok = False

    # 焊点2:这些模块必须是从包里加载的,不是机器上已有的 site-packages。
    for name in ("nanobot", "mcp", "anydoc", "pydantic_core", "lxml", "PIL", "cryptography"):
        try:
            mod = __import__(name)
            f = getattr(mod, "__file__", None) or str(getattr(mod, "__path__", [""])[0])
            ok = check(f"S2-loc-{name}", f"{name} 从包内加载", inside_root(f), f"{f}") and ok
        except Exception as exc:
            blew_up(f"S2-loc-{name}", f"{name} 从包内加载", exc); ok = False
    return ok


def gate_s3_anydoc() -> bool:
    """S3 文档转换器真转一份文件 —— 它从来没在 Windows 上真跑过。

    断言直接搬 install.ps1:76 那条(CSV → markdown,结果里必须有「45天」)。
    """
    emit("\n[S3] 文档转换器真转一份 CSV(它没在 Windows 上真跑过)")
    try:
        import anydoc
        import importlib.metadata as md
        p = ROOT / "样例.csv"
        p.write_text("项目,工期\n王姐家,45天\n", encoding="utf-8")
        out = anydoc.to_markdown(str(p))
        return check("S3", "CSV 转出来的文字里有「45天」", "45天" in out,
                     f"firecrawl-anydoc {md.version('firecrawl-anydoc')};转出 {len(out)} 字")
    except Exception as exc:
        blew_up("S3", "CSV 转 markdown", exc)
        return False


def gate_s4_config() -> tuple[bool, Path | None]:
    """S4 脚本化配置成立 —— 装机不需要人答向导。

    原样跑 OpenDesign 自己的两个脚本(零改动),再用 nanobot 自己的加载器读回来。
    含 08-12 补强过的那两问:设了 key 解析出真值 / 没设当场 fail closed。
    """
    emit("\n[S4] 不跑向导,用脚本把配置生成出来")
    import shutil
    if FAKEHOME.exists():
        shutil.rmtree(FAKEHOME, ignore_errors=True)
    (FAKEHOME / ".nanobot").mkdir(parents=True, exist_ok=True)
    cfg = FAKEHOME / ".nanobot" / "config.json"
    env = child_env()

    try:
        from nanobot.config.schema import Config
        cfg.write_text(json.dumps(Config().model_dump(mode="json", by_alias=True,
                                                      exclude_none=True),
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        check("S4a", "生成 base config(替代 onboard 向导)", True, f"{cfg.stat().st_size} 字节")
    except Exception as exc:
        blew_up("S4a", "生成 base config", exc)
        return False, None

    ok = run("S4b", "enable_webui.py(原脚本零改动)",
             [str(PYEXE), str(DSDIR / "bin" / "enable_webui.py"), "spike-passwd"], env)
    ok = run("S4c", "ds_merge_config.py(原脚本零改动)",
             [str(PYEXE), str(DSDIR / "bin" / "ds_merge_config.py"),
              str(DSDIR / "config" / "nanobot.config.windows.jsonc"), str(cfg)], env) and ok

    # 端口改到非常规段 + MCP 命令改指包内 python。
    # 后者不是"为了让判据过":模板里写死的是 ${USERPROFILE}/.venvs/.../Scripts/python.exe,
    # 真安装器也**必须**改写这一处,这里测的就是那个真机制。
    try:
        d = json.loads(cfg.read_text(encoding="utf-8"))
        d.setdefault("gateway", {})["port"] = GATEWAY_PORT
        d.setdefault("channels", {}).setdefault("websocket", {})["port"] = WS_PORT
        servers = d.get("tools", {}).get("mcpServers", {}) or {}
        for _name, s in servers.items():
            s["command"] = str(PYEXE)
        cfg.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        check("S4d", "改写 MCP 启动命令指向包内 python", bool(servers),
              f"{len(servers)} 个:{sorted(servers)}")
    except Exception as exc:
        blew_up("S4d", "改写端口与 MCP 命令", exc)
        return False, None

    # 焊点:C 只问"非空"会被 ${DS_LLM_KEY} 这个占位符骗过(它本身就非空)。两向都问。
    try:
        from nanobot.config.loader import load_config, resolve_config_env_vars
        old = dict(os.environ)
        os.environ.update({k: env[k] for k in ("HOME", "USERPROFILE", "DS_ROOT")})
        os.environ["DS_LLM_KEY"] = "sk-real-value-42"
        c = resolve_config_env_vars(load_config(cfg))
        key = c.model_dump(mode="json", by_alias=True)["providers"]["custom"]["apiKey"]
        ok = check("S4e", "填了 key → 解析出真值(不是占位符)",
                   key == "sk-real-value-42", f"读回 {key!r}") and ok
        os.environ.pop("DS_LLM_KEY", None)
        try:
            resolve_config_env_vars(load_config(cfg))
            ok = check("S4f", "没填 key → 当场拒绝启动", False,
                       "竟然加载成功 ⇒ 会带着占位符去请求,业主看到的报错会很难懂") and ok
        except ValueError as e:
            ok = check("S4f", "没填 key → 当场拒绝启动(报错说人话)",
                       "DS_LLM_KEY" in str(e), f"{e}") and ok
        os.environ.clear(); os.environ.update(old)
    except Exception as exc:
        blew_up("S4e/f", "key 解析两向", exc); ok = False
    return ok, cfg


def gate_s5_running(cfg: Path) -> bool:
    """S5 网关 + ds-web 真起来了,而且是**我们这一份**(焊点3)。

    「在使用现场验证」那条规矩的落点:让运行中的目标自己打印身份。
    """
    emit("\n[S5] 真把它启起来,让它自己报身份")
    LOGDIR.mkdir(exist_ok=True)
    env = child_env()
    env["DS_WEB_PORT"] = str(DSWEB_PORT)
    env["DS_NANOBOT_PORT"] = str(GATEWAY_PORT)

    # ② 起之前先探:端口已被占就当场红,别把别人的应答当成我们的绿。
    busy = [p for p in (GATEWAY_PORT, DSWEB_PORT) if port_open(p, 0.4)]
    if busy:
        check("S5-pre", "开跑前端口是空的", False,
              f"{busy} 已经有人在听 —— 先关掉那个程序再跑一次,否则这份收据说明不了任何事")
        return False
    check("S5-pre", "开跑前端口是空的", True, f"{GATEWAY_PORT} / {DSWEB_PORT}")

    gw_out = LOGDIR / "gateway.out.log"
    gw_err = LOGDIR / "gateway.err.log"
    dw_out = LOGDIR / "dsweb.out.log"
    procs = []
    ok = True
    try:
        gw = subprocess.Popen([str(PYEXE), "-m", "nanobot", "gateway"],
                              stdout=gw_out.open("w", encoding="utf-8", errors="replace"),
                              stderr=gw_err.open("w", encoding="utf-8", errors="replace"),
                              env=env, cwd=str(ROOT))
        procs.append(("gateway", gw))

        # ③ 开机横幅从**我们自己子进程的管道**里读 —— 别的进程再怎么应答也进不了这根管子。
        banner = f"Starting nanobot gateway version 0.2.2 on port {GATEWAY_PORT}"
        deadline = time.time() + 240
        seen = ""
        while time.time() < deadline:
            if gw.poll() is not None:
                break
            seen = gw_out.read_text(encoding="utf-8", errors="replace")
            if banner in seen:
                break
            time.sleep(1)
        ok = check("S5a", "网关自己打印了版本和端口", banner in seen,
                   f"要找 {banner!r};进程{'已退出 rc=' + str(gw.poll()) if gw.poll() is not None else '还活着'}") and ok
        if gw.poll() is not None:
            emit("        ---- 网关 stderr 前 20 行 ----")
            for line in gw_err.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
                emit("        " + line)

        # 3 个 ds MCP 工具服务连上 + agent loop 起来
        deadline = time.time() + 240
        err = ""
        while time.time() < deadline:
            err = gw_err.read_text(encoding="utf-8", errors="replace")
            if err.count("connected,") >= 3 and "Agent loop started" in err:
                break
            time.sleep(1)
        ok = check("S5b", "3 个工具服务全连上 + agent loop 起来",
                   err.count("connected,") >= 3 and "Agent loop started" in err,
                   f"connected×{err.count('connected,')}") and ok

        deadline = time.time() + 60
        st, body = 0, ""
        while time.time() < deadline:
            if port_open(GATEWAY_PORT, 1.0):
                try:
                    st, body = http_get(GATEWAY_PORT, "/health")
                    break
                except OSError:
                    pass
            time.sleep(1)
        ok = check("S5c", "网关 /health 应答", st == 200 and '"ok"' in body, f"{st} {body[:80]}") and ok

        # ds-web:运行中的进程自己报版本号
        dw = subprocess.Popen([str(PYEXE), str(DSDIR / "bin" / "ds_web.py")],
                              stdout=dw_out.open("w", encoding="utf-8", errors="replace"),
                              stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
        procs.append(("ds-web", dw))
        deadline = time.time() + 90
        st, body = 0, ""
        while time.time() < deadline:
            if dw.poll() is not None:
                break
            if port_open(DSWEB_PORT, 1.0):
                try:
                    st, body = http_get(DSWEB_PORT, "/api/health")
                    break
                except OSError:
                    pass
            time.sleep(1)
        want = (DSDIR / "版本号.txt")
        expect = want.read_text(encoding="utf-8").strip() if want.exists() else None
        try:
            h = json.loads(body) if body else {}
        except Exception:
            h = {}
        ok = check("S5d", "ds-web 自己报出版本号",
                   st == 200 and bool(h.get("version")) and (expect is None or h.get("version") == expect),
                   f"回 {st};version={h.get('version')!r}"
                   + (f";应为 {expect!r}" if expect else "")) and ok
        ok = check("S5e", "ds-web 说文档转换器在位",
                   bool((h.get("doc_reader") or {}).get("available")),
                   f"doc_reader={h.get('doc_reader')}(弱证人:只看元数据;真证人是 S3)") and ok
    except Exception as exc:
        blew_up("S5", "启动阶段", exc); ok = False
    finally:
        emit("\n[S6] 关掉,并确认端口真的放开了")
        for name, p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for name, p in procs:
            try:
                p.wait(timeout=60)
                check(f"S6-{name}", f"{name} 已退出", True, f"rc={p.returncode}")
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
                check(f"S6-{name}", f"{name} 已退出", False, "60 秒没退,已强杀")
        time.sleep(3)
        still = [p for p in (GATEWAY_PORT, DSWEB_PORT) if port_open(p, 0.4)]
        check("S6-port", "端口已放开", not still, f"仍在听:{still}" if still else "")
    return ok


def main() -> int:
    emit("=" * 68)
    emit("OpenDesign Windows 探路包 —— 只回答一件事:免装 Python 跑不跑得动")
    emit(f"时间:{time.strftime('%Y-%m-%d %H:%M:%S')}   包根目录:{ROOT}")
    emit("这个包只读、不装、不改你的机器;删掉这个文件夹就等于没来过。")
    emit("=" * 68)

    for p, what in ((PYEXE, "包内 python"), (DSDIR, "ds 文件夹")):
        if not p.exists():
            emit(f"\n包不完整:找不到 {what}({p})。整个文件夹重新解压一次再跑。")
            return 2

    gate_s0_identity()
    gate_s1_python()
    gate_s2_native()
    gate_s3_anydoc()
    ok4, cfg = gate_s4_config()
    if ok4 and cfg:
        gate_s5_running(cfg)
    else:
        skip("S5/S6", "启动网关与 ds-web", "S4 没过,配置都没生成出来,起不了 —— 不是 PASS")

    emit("\n" + "=" * 68)
    if failures:
        emit(f"结论:红了 —— {len(failures)} 条没过:")
        for f in failures:
            emit("   - " + f)
        emit("")
        emit(f"最先断的那一关:{failures[0]}")
        emit("把这份 收据.txt 整个发回来就行,不用你判断是什么问题。")
    else:
        emit("结论:全绿 —— 免装 Python 能跑起 OpenDesign 这一整套。")
    if skipped:
        emit(f"\n另有 {len(skipped)} 条没跑(SKIP 不是通过):")
        for s in skipped:
            emit("   - " + s)
    emit("=" * 68)

    RECEIPT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print(f"\n收据已写到:{RECEIPT}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
