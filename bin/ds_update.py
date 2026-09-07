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
ASSET_RE = re.compile(r"^OpenDesign-Setup-(\d+(?:\.\d+)*)\.exe$")
VERSION_RE = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")
TIMEOUT_S = 10


def parse_version(text):
    """从 "0.98.3" / "win-installer-0.98.3" / "OpenDesign-Setup-0.98.3.exe" 里取出 (0, 98, 3)。

    取不出来返回 None —— **绝不抛**。读不出版本号是"我不知道",不是"出事了":
    上层遇到 None 一律不提示更新(判据 t3d)。
    """
    if not isinstance(text, str):
        return None
    m = VERSION_RE.search(text)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


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
           "asset": None, "notes": "", "error": None}
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
    out["asset"] = {
        "name": asset.get("name"),
        "url": asset.get("browser_download_url"),
        "size": asset.get("size") or 0,
        # "sha256:<hex>" —— GitHub 自己给的,第二刀下载完拿它对。
        "digest": asset.get("digest"),
    }
    return out


def fetch_releases(repo=REPO, timeout=TIMEOUT_S):
    """唯一碰网络的函数。判据一律注入替身,不打真网(2026-08-10 那次事故立的规矩)。"""
    url = API_BASE + RELEASES_PATH.format(repo=repo) + "?per_page=100"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenDesign-updater",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (常量 https)
        return json.loads(resp.read().decode("utf-8"))


def check(current, fetch=fetch_releases):
    """查一次。**任何异常都不许漏出去** —— 查更新失败是小事,把一坨栈甩给业主是大事。"""
    try:
        releases = fetch()
    except Exception as exc:  # noqa: BLE001 —— 故意兜底,判据 t7d 就是钉它
        return {"current": current, "update_available": False, "latest": None,
                "asset": None, "notes": "", "error": f"查更新失败:{exc.__class__.__name__}: {exc}"}
    if isinstance(releases, str):
        try:
            releases = json.loads(releases)
        except Exception:  # noqa: BLE001
            return {"current": current, "update_available": False, "latest": None,
                    "asset": None, "notes": "", "error": "查更新失败:线上返回的不是 JSON"}
    if not isinstance(releases, list):
        return {"current": current, "update_available": False, "latest": None,
                "asset": None, "notes": "", "error": "查更新失败:线上返回的不是版本列表"}
    try:
        return decide(current, releases)
    except Exception as exc:  # noqa: BLE001
        return {"current": current, "update_available": False, "latest": None,
                "asset": None, "notes": "", "error": f"查更新失败:{exc.__class__.__name__}: {exc}"}


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


def check_cached(current, fetch=fetch_releases, now=time.time, force=False, ttl=None):
    """带缓存地查一次。`force=True` 是业主亲手点了「检查更新」—— 那一下必须真去问。"""
    ttl = CACHE_TTL_S if ttl is None else ttl
    t = now()
    if not force:
        with _cache_lock:
            hit = _cache.get(_cache_key(current))
        if hit and t - hit[0] < ttl:
            return hit[1]
    result = check(current, fetch=fetch)
    if not result.get("error"):
        with _cache_lock:
            _cache[_cache_key(current)] = (t, result)
    return result
