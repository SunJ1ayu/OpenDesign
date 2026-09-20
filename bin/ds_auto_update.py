#!/usr/bin/env python3
"""打开软件倒计时自动更新的本机记账。

只记录"这个版本自动试过":接力脚本回滚时界面已经没了,失败事实来不及补写,
所以必须在动手前预写。文件放在数据根 Logs 下,不碰用户数据目录。
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time

RECORD_NAME = "auto-update-attempts.json"
RECENT_FAILURE_SECONDS = 600


def record_path(data_root: str) -> str:
    return os.path.join(str(data_root), "Logs", RECORD_NAME)


def read_attempts(data_root: str) -> dict[str, float]:
    try:
        with open(record_path(data_root), encoding="utf-8") as fh:
            body = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}
    raw = body.get("attempts") if isinstance(body, dict) else None
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for version, ts in raw.items():
        if not isinstance(version, str):
            continue
        try:
            out[version] = float(ts)
        except (TypeError, ValueError):
            continue
    return out


def attempted_at(data_root: str, version: object) -> float | None:
    if not isinstance(version, str) or not version:
        return None
    attempts = read_attempts(data_root)
    return attempts.get(version)


def why_not_auto(paths: dict, version: object) -> str | None:
    """「这一版,在这台机器上,**现在**该不该自动装」—— 整条链**唯一**的资格判据。

    返回 `None` = 该装;否则返回 why_not 字符串(与 `ds_web._auto_update_status` 同一套枚举)。
    两维一起答:**账本**(这一版自动试过没有)+ **这台机器**(有没有外壳、装没装过、
    路径行不行、业主把开关关了没有)。三个决策点 —— `prepare`(要不要下 46MB)、
    `startup`(要不要弹更新界面)、`apply`(真装)—— 全部只问这一处。

    🔴 为什么有它(2026-09-20 第 3 轮外审 subdeepseek F1,我跑探针核实成立):
    第 2 轮我把资格判断"收成一处"时,**只收了账本那一维**(`auto_eligible`:试过没试过)。
    而完整的「该不该自动装」有 7 种否决,另外几种 —— `no_shell` / `not_installed` /
    `path_unsupported` / `disabled` —— **只在 apply 被问**,那时界面已经弹出来了,
    而 `auto_skipped` 在界面上是静默的。探针实测:

        [no_shell] STARTUP -> install ; APPLY -> auto_skipped/no_shell ; 包还在盘上
        [disabled] 同上

    ⇒ 闪一下、什么都不说、包留着、下次打开再来一遍,**永不收敛**。比 attempted 那条更糟
    (那条至少会清包),而且 `disabled` 就是业主「关掉自动更新」的开关 —— 关了照样弹、照样下。

    ⚠️ 顺序是产品契约,与 `_auto_update_status` 保持一致(Windows 真机判据靠 `disabled`
    排最后来证明前面条件全成立)。判据 el10~el14。

    🔴 **第 2 轮我只收了账本那一维,那不是收敛,是把同一个问题拆成了两半**:剩下几维
    还留在 apply,而 startup/prepare 各自只问半个问题 ⇒ F1 那条回归。所以这里答**整个**
    问题,调用方一个字都不许自己再拼一遍(第 3 轮外审 F2 打的就是 apply 侧那份重写)。
    """
    try:
        shell_port = os.environ.get("DS_SHELL_LOCK_PORT") or ""
        if re.fullmatch(r"[0-9]+", shell_port) is None:
            return "no_shell"
        # 放在函数里而不是模块顶:本模块是那本小账(记账 + 资格),别让它在 import 期
        # 就拖上整个安装器模块。两边**本来就没有**循环依赖(ds_update_apply 不认识本模块)
        # —— 这句话写准是有意的:本单立的规矩之一就是"注释不许说谎"。
        import ds_update_apply
        problem, _error = ds_update_apply.update_preflight_problem(paths)
        if problem:
            return problem
        if not auto_eligible(paths.get("data_root"), version):
            return "attempted"
        if (os.environ.get("OPENDESIGN_AUTO_UPDATE") or "").strip().lower() == "off":
            return "disabled"
        return None
    except Exception:  # noqa: BLE001 —— 资格算不出来时当"不能自动装",但绝不许抛
        return "error"


#: 永久性的否决:这一版在这台机器上**再也不会**自动装 ⇒ 留着那 46MB 没有意义。
#: 其余几种(no_shell / disabled / error)是临时的 —— 条件恢复后还能装,不许删业主的包
#: (判据 el4 / el13),但也不许让它走到弹界面那一步(判据 el10)。
PERMANENT_BLOCKERS = ("attempted", "not_installed", "path_unsupported")


def auto_eligible(data_root: str, version: object) -> bool:
    """这一版还够不够格**自动**更新 —— 链上三处共用的**唯一**判据。

    🔴 为什么要有这个函数(2026-09-20 第 2 轮外审,subcursor 与 subdeepseek 各自独立报):
    在它之前,这本账只有**真装那一刻**(`ds_web._auto_update_status`)在读。而"要不要
    自动装这一版"这个问题,链上其实有**三个**地方在答:

        prepare(后台要不要把 46MB 下下来)   —— 原来只问 check_cached
        startup(打开软件要不要弹更新界面装) —— 原来只看 update-state.json
        apply(真装)                          —— 原来唯一读账的一处

    于是出现这条不收敛的链:装失败 → 记账 + 删包 → 业主开着软件满 60s → 后台把**同一个
    装不上的包**重新下回来 → 下次打开又弹一次更新界面 → 又判 attempted → 又删……
    症状从"每次打开"变成"每两次打开",外加每轮 46MB 流量。**在末端删文件,永远追不上
    前端重新备货** —— 这是同一类问题的第二个补丁,所以改抽象:判断只写一处,三处共用。

    语义:**同一版自动只试一次**(永久,不是时效窗口)。
    - 拿 `recent_failure`(10 分钟窗口)冒充资格 ⇒ 过了窗口又重下一遍、又空演一次(判据 el1b)。
    - 账读不出来时当作"没试过" —— 与 `_auto_update_status` 一直以来的语义保持一致,
      不在这里制造第二种解释;账真写不进去时的防线是 apply 侧的 `auto_unrecorded`。
    - 只管**自动**更新。业主自己点「更新」永远不受它限制(判据 el6)。
    """
    return attempted_at(data_root, version) is None


def recent_failure(data_root: str, version: object, now: float | None = None) -> bool:
    ts = attempted_at(data_root, version)
    if ts is None:
        return False
    if now is None:
        now = time.time()
    return now - ts < RECENT_FAILURE_SECONDS


def record_attempt(data_root: str, version: object, now: float | None = None) -> tuple[bool, str | None]:
    """把一个版本的自动尝试原子写到账里;失败时旧账保持原样。"""
    if not isinstance(version, str) or not version:
        return False, "没有可记录的版本号"
    if now is None:
        now = time.time()
    logs = os.path.join(str(data_root), "Logs")
    try:
        os.makedirs(logs, exist_ok=True)
        attempts = read_attempts(data_root)
        attempts[version] = float(now)
        payload = {"attempts": attempts}
        fd, tmp = tempfile.mkstemp(prefix=".auto-update-attempts-", suffix=".tmp", dir=logs)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, record_path(data_root))
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:  # noqa: BLE001 —— 端点要把它变成 auto_unrecorded,不甩栈给业主
        return False, str(exc) or exc.__class__.__name__
    return True, None
