#!/usr/bin/env python3
"""查更新:问一次 GitHub,答"线上有没有比我新的版本"(track opendesign-in-app-update)。

这个模块**只查不装**。装是第二刀的事,住在别处。

🔴 **写这个文件的人必须知道的一件事**(2026-09-07 实测,判据 t1/t1b 钉着):

    GET /repos/SunJ1ayu/OpenDesign/releases/latest  →  404 Not Found

那个接口**按 GitHub 的设计跳过 prerelease**,而本仓至今 **20 个 release 全是 prerelease**。
所以这里必须用 `/releases`(列表,含预发布)**自己挑**。改回那个"标准接口"的后果不是报错,
是**功能永远查不到新版本、界面永远显示"已是最新"** —— 一条恒绿路径,比没有更新功能更坏。

🔴 **第二件必须知道的事**(2026-09-15 夜,业主 0.98.4 实测,track opendesign-update-check-rate-limit):
未登录的 API **每个出口 IP 每小时 60 次**。业主开着商用 VPN,出口很多人共用 ⇒
`HTTP Error 403: rate limit exceeded`,点多少次都「查不到更新」。所以现在**先问 github.com 的
发布页订阅源(releases.atom,网页端,不吃那个额度)+ 每版随包上传的清单 `OpenDesign-update.json`**,
订阅源这条走不通才问 API。两条都把结果拼成 API 的形状交给同一个 `decide()`。

信任根就一条:**HTTPS 到 github.com**。资产的 sha256 由 GitHub 在 `digest` 字段里给
(实测与我们发版时记的那串一致),它挡得住"下坏了/下了半截/被中间人换了包",
**挡不住"GitHub 账号被盗后换了资产"** —— 我们没有代码签名证书,这是明账,不假装有。
"""
from __future__ import annotations

import http.client
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

REPO = "SunJ1ayu/OpenDesign"
API_BASE = "https://api.github.com"
# 故意拼出来而不是写成一整串:t1b 那道结构闸扫的是本文件的源码。
RELEASES_PATH = "/repos/{repo}/releases"
# 版本号=**2~4 段数字**。单段不算(会撞上一堆随便的数字),形状必须整段吻合。
# 🔴 收两段是 S1 自审改的:原来只认三段,业主哪天宣布 1.0、tag 打成 `win-installer-1.0`,
#    那一版在更新检查里就**根本不存在,而且一声不吭** —— 和本单开头那个
#    /releases/latest 404 是同一种病。web/src/update.ts 的 releasePageUrl 与这里同口径。
_NUM = r"\d+(?:\.\d+){1,3}"
# 🔴 结尾用 \Z 不用 $(评审 overall GPT #1,我复现):`$` 配 match() 会放过末尾换行 ⇒
#    清单里 `OpenDesign-Setup-0.99.1.exe\n` 被当成合法安装包名,下载地址 / 本地文件名带换行,Windows 存不下。
ASSET_RE = re.compile(rf"^OpenDesign-Setup-({_NUM})\.exe\Z")
TAG_RE = re.compile(rf"^win-installer-({_NUM})\Z")
BARE_RE = re.compile(rf"^({_NUM})\Z")
TIMEOUT_S = 10
WEB_BASE = "https://github.com"
MANIFEST_NAME = "OpenDesign-update.json"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
FEED_LABEL = "发布页订阅源"
API_LABEL = "GitHub 接口"
UNVERIFIED_HUMAN = "新版缺少可核对的安装包信息"


class ManifestError(ValueError):
    """清单对不上。单独一类,好让 `explain` 说人话(判据 rl7e)。"""


class FeedUnverified(Exception):
    """订阅源里**看见了比本机新的版本**,但它的清单拿不到或对不上(判据 rl5d)。

    带着版本号往上抛:回落 API 之后若 API 说"没有更新",不许把这当成"已是最新" —— 线上明明有新版。
    """

    def __init__(self, version, cause):
        super().__init__(version)
        self.version = version
        self.cause = cause


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


def atom_url(repo=REPO):
    """发布页订阅源的地址(判据 rl8d 逐字节钉)。github.com 网页端,**不是** api.github.com。"""
    return "%s/%s/releases.atom" % (WEB_BASE, repo)


def manifest_url(repo, tag):
    """某一版随包上传的清单地址 —— 和安装包同一个下载通道(判据 rl8d)。"""
    return "%s/%s/releases/download/%s/%s" % (WEB_BASE, repo, tag, MANIFEST_NAME)


def _open(req, timeout):
    """🔴 代理在**请求那一刻**读(判据 rl8,t30b 同一个病):`urllib.request.urlopen` 复用进程级缓存的 opener,
    代理只在它第一次被建出来时读一次 ⇒ 业主先开软件、后开 VPN,查更新照样直连。
    `build_opener()` 不带参数 = 默认处理器 + 按此刻系统代理建的 ProxyHandler。"""
    return urllib.request.build_opener().open(req, timeout=timeout)


def _get_text(url, accept, timeout):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "OpenDesign-updater"})
    with _open(req, timeout) as resp:  # noqa: S310 (常量 https)
        return resp.read().decode("utf-8")


def fetch_releases(repo=REPO, timeout=TIMEOUT_S):
    """问 API(备路)。判据一律注入替身,不打真网(2026-08-10 那次事故立的规矩)。"""
    return json.loads(_get_text(releases_url(repo), "application/vnd.github+json", timeout))


def fetch_atom(repo=REPO, timeout=TIMEOUT_S):
    """取发布页订阅源(主路)。"""
    return _get_text(atom_url(repo), "application/atom+xml", timeout)


def fetch_manifest(tag, repo=REPO, timeout=TIMEOUT_S):
    """取某一版的清单(主路第二跳)。"""
    # 🔴 以文件身份去拿(判据 rl8e):真 GitHub 的下载地址带 `Accept: application/json` 回 404。
    return _get_text(manifest_url(repo, tag), "application/octet-stream", timeout)


def parse_atom(text, repo=REPO):
    """订阅源 → `[{tag, html_url}]`,只留 `win-installer-<版本>`,保持原顺序(挑最新交给调用方,**不按条目先后**)。

    tag 与链接都取 `<link href=".../releases/tag/<tag>">` 的**原文** —— 地址由 GitHub 给,不拼(F1)。
    链接必须是**本仓**的(判据 rl1d):别的仓库的 tag 链接不算本仓版本。不是 XML ⇒ ValueError。
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("订阅源不是 XML(%s)" % exc) from None
    link_re = re.compile(r"^%s/%s/releases/tag/([^/?#\s]+)\Z" % (re.escape(WEB_BASE), re.escape(repo)))
    out = []
    for entry in root.findall(_ATOM_NS + "entry"):
        for link in entry.findall(_ATOM_NS + "link"):
            m = link_re.match(link.get("href") or "")
            if m and TAG_RE.match(m.group(1)):
                out.append({"tag": m.group(1), "html_url": m.group(0)})
                break
    return out


def parse_manifest(text, tag, repo=REPO):
    """清单 → 与 API 同形的资产 `{name, browser_download_url, size, digest}`;**任一项对不上就 ValueError**(判据 rl3)。

    清单是新查法里"可信 sha256"的唯一来源,所以逐项核对:schema、来路 tag、version 与 tag 里的版本**同一段文字**、
    文件名是安装包且版本同文字、sha256 是 64 位小写十六进制、size 是正整数。
    下载地址用 tag 原文与文件名原文拼,**不用补零后的版本号**(F1:`win-installer-1.0` 不许变成 1.0.0)。
    """
    try:
        m = json.loads(text) if isinstance(text, (str, bytes, bytearray)) else text
    except ValueError:
        raise ManifestError("清单不是 JSON") from None
    if not isinstance(m, dict):
        raise ManifestError("清单不是对象")
    if type(m.get("schema")) is not int or m.get("schema") != 1:
        raise ManifestError("清单版本不认识")
    tag_m = TAG_RE.match(tag or "")
    if not tag_m or m.get("tag") != tag:
        raise ManifestError("清单写的版本标签与来路不一致")
    version = tag_m.group(1)
    if m.get("version") != version:
        raise ManifestError("清单里的版本号与标签不一致")
    asset = m.get("asset")
    if not isinstance(asset, dict):
        raise ManifestError("清单缺安装包信息")
    name = asset.get("name")
    name_m = ASSET_RE.match(name) if isinstance(name, str) else None
    if not name_m or name_m.group(1) != version:
        raise ManifestError("清单里的安装包文件名与版本不一致")
    sha = asset.get("sha256")
    if not isinstance(sha, str) or not _HEX64_RE.match(sha):
        raise ManifestError("清单里的 sha256 形状不对")
    size = asset.get("size")
    if type(size) is not int or size <= 0:
        raise ManifestError("清单里的安装包大小不对")
    return {
        "name": name,
        "browser_download_url": "%s/%s/releases/download/%s/%s" % (WEB_BASE, repo, tag, name),
        "size": size,
        "digest": "sha256:" + sha,
    }


def explain(exc):
    """把一次失败说成人话,技术细节留在括号里(判据 rl7)。业主看得懂前半句,排障看后半句。"""
    tech = "%s: %s" % (exc.__class__.__name__, exc)
    if isinstance(exc, urllib.error.HTTPError):
        said = ("%s %s" % (exc.reason, exc)).lower()
        headers = exc.headers if exc.headers is not None else {}
        # 判据 rl7d:GitHub 有时状态行只写 Forbidden,限流写在 X-RateLimit-Remaining: 0 里
        exhausted = str(headers.get("X-RateLimit-Remaining") or "").strip() == "0"
        if exc.code == 429 or (exc.code == 403 and ("rate limit" in said or exhausted)):
            human = "GitHub 限制了这个网络出口的查询次数(同一出口的人查得太多),换个网络或稍后再试"
        elif exc.code == 404:
            human = "线上没有找到要的文件"
        else:
            human = "GitHub 拒绝了这次请求"
    elif isinstance(exc, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError)):
        human = "连不上 GitHub(检查网络或 VPN)"
    elif isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError, http.client.HTTPException)):
        # 判据 rl7c:代理 / 门户把接口换成一张网页时是这句,别把「Expecting value」当人话甩给业主
        human = "线上返回的内容看不懂(可能被网络中间的代理或登录页换掉了)"
    elif isinstance(exc, ValueError):
        return str(exc)
    else:
        human = "出了意外"
    return "%s(%s)" % (human, tech)


def _failure(current, error):
    return {"current": current, "update_available": False, "latest": None,
            "asset": None, "notes": "", "release_url": None, "error": error}


def _via_releases(current, fetch):
    """API 形状的列表 → decide。"""
    releases = fetch()
    if isinstance(releases, str):
        try:
            releases = json.loads(releases)
        except Exception:  # noqa: BLE001
            raise ValueError("线上返回的不是 JSON") from None
    if not isinstance(releases, list):
        raise ValueError("线上返回的不是版本列表")
    return decide(current, releases)


def _via_feed(current):
    """订阅源 → 挑最大版本 →(比本机新才)拉清单 → 拼成 API 形状 → decide。任何一步不对就抛,让调用方回落 API。"""
    best, best_ver = None, None
    for entry in parse_atom(fetch_atom()):
        ver = parse_version(entry["tag"])
        if ver is not None and (best_ver is None or ver > best_ver):
            best, best_ver = entry, ver
    if best is None:
        raise ValueError("订阅源里没有安装包版本")
    here = parse_version(current)
    if here is not None and best_ver <= here:
        # 线上最新不比本机新:不拉清单(判据 rl6)—— 老版本没有清单,拉了只会误报失败
        out = _failure(current, None)
        out["latest"] = ".".join(str(n) for n in best_ver)
        return out
    try:
        text = fetch_manifest(best["tag"])
        asset = parse_manifest(text, best["tag"])
    except Exception as exc:  # noqa: BLE001 —— 带着"线上有新版"这件事往上抛(判据 rl5d)
        raise FeedUnverified(".".join(str(n) for n in best_ver), exc) from exc
    notes = json.loads(text).get("notes")
    release = {"tag_name": best["tag"], "html_url": best["html_url"], "draft": False,
               "body": notes if isinstance(notes, str) else "", "assets": [asset]}
    return decide(current, [release])


def check_for_update(current, fetch=None):
    """查一次。**任何异常都不许漏出去** —— 查更新失败是小事,把一坨栈甩给业主是大事。

    ⚠️ 名字不叫 `check`:`tests/dead_assertions.py` 把**任何叫 `check(` 的调用**当成断言
    (测试里常见的自定义断言助手),撞名会让那道闸对我的判据发出误报。
    2026-09-07 实测撞过一次,改名比削弱那道闸便宜得多。

    `fetch=None` 时到**调用那一刻**才去取 `fetch_releases`。默认参数在 def 那一刻就固化了,
    那样判据里替换 `ds_update.fetch_releases` 根本不生效,离线判据会悄悄变成真去打网
    (判据 t9d 钉的就是这件事)。

    来源:显式传了 `fetch` ⇒ **只用它**(判据 rl9;既有判据的注入方式)。
    不传 ⇒ 先 `发布页订阅源`,走不通再 `GitHub 接口`;两条都不通 ⇒ error 里两条原因都写(判据 rl5c)。
    每个来源函数都在调用那一刻按模块名取,判据替换 `ds_update.fetch_*` 才生效(t9d)。
    """
    if fetch is not None:
        try:
            return _via_releases(current, fetch)
        except Exception as exc:  # noqa: BLE001 —— 故意兜底,判据 t7d 就是钉它
            return _failure(current, "查更新失败:" + explain(exc))
    if parse_version(current) is None:
        # 判据 rl6b:读不出本机版本号就不联网(原来会白拉一次清单,错误还按两个来源重复两遍)
        return _failure(current, "读不出本机版本号,不提示更新")
    reasons = []
    unverified = None
    for label, attempt in ((FEED_LABEL, lambda: _via_feed(current)),
                           (API_LABEL, lambda: _via_releases(current, fetch_releases))):
        try:
            result = attempt()
        except FeedUnverified as exc:
            unverified = exc
            detail = str(exc.cause) if isinstance(exc.cause, ManifestError) else explain(exc.cause)
            reasons.append("%s:有新版 %s,但%s(%s)" % (label, exc.version, UNVERIFIED_HUMAN, detail))
            continue
        except Exception as exc:  # noqa: BLE001
            reasons.append("%s:%s" % (label, explain(exc)))
            continue
        if result.get("error"):
            reasons.append("%s:%s" % (label, result["error"]))
            continue
        if unverified is not None and not result.get("update_available"):
            # 判据 rl5d:订阅源看见了新版、API 却说没有更新 ⇒ 不许说"已是最新"(也就不进缓存)
            reasons.append("%s:没有比本机新的可安装版本" % label)
            break
        return result
    return _failure(current, "查更新失败:" + ";".join(reasons))


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
