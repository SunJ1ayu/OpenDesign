#!/usr/bin/env python3
"""Windows 更新端到端 e1~e8 的判定器 —— "机器事实 → 这个场景过没过"。

track opendesign-in-app-update-install §3。结构照抄 `bin/probe_verdict.py` 付过学费的那一套:
`.github/scripts/windows-update-e2e.ps1` 本机跑不了(没有 pwsh),写在里面的判断谁都验不了
⇒ 那边**只采事实**,判定在这里,由 `tests/test_update_e2e_harness.py` 喂事实、断言裁决。

调用约定:

    python update_e2e_verdict.py e1|e2|e3|e4|e5|e6|e7|e8|e9 <facts.json>

stdout 一行;退出码 0=OK、1=FAIL、2=输入本身有问题(**也算红**,探针那边只认 0)。
输出**只用 ASCII**:runner 是英文 Windows,中文进管道会被代码页打成问号(windows-package-probe 栽过)。

事实的形状(字段缺了一律当 FAIL,不许当"没问题"):

    old_version / new_version          两个包的版本号
    reset      {installer_rc, health{port,version}}   场景开始前重装旧版的结果
    check      GET /api/update/check?force=1 的应答
    apply      POST /api/update/apply 的应答
    source     查更新走哪条来源:feed(订阅源 + 清单,替身 API 回 403)| api(订阅源 503,API 正常,e8)
    fake_log   替身记下的请求 [{kind: atom|manifest|releases|download, status, mode, ...}]
    live_before / live_after           活树清单摘要(排除 __pycache__)
    live_version_after                 活树 ds\\版本号.txt 的内容,活树不在则 null
    new_exists / old_exists            接力脚本结束后 .new / .old 在不在
    nested_old_exists                  活树里面有没有被塞进一个 OpenDesign.old(e5 那个怀疑)
    relay      {seen, ended, seconds}  接力脚本进程看见过没有、结束了没有
    health_after {port, version} | null   接力脚本结束后是谁在答(不手动拉起)
    relaunch   {health{...}}           e3:放手后手动拉起旧版的结果
    inject     {landed, detail}        e3/e4/e5 的注入打中没有
    markers_before / markers_after     档案标记文件 {相对路径: sha256}
    pointers   {live, install_dir, uninstall{InstallLocation,UninstallString,DisplayIcon}, shortcuts{lnk: target}}
               场景结束时业主"从哪儿打开它"的那几处指向(t26 的真机半)
    window     {wins, procs}           e1/e6:屏幕上的窗口(交给 bin/probe_verdict.window_verdict)
    health_final {port, version} | null   e1/e6:截完 20 秒那张图之后**再问一次**(新版起来又退出,前面那次看不出来)
    cmdline    e7:交给新版安装器的参数串(修 t33 之前 python 真正发出去的那个形态)
    installer_rc  e7:那次安装器的退出码
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "bin"))

import probe_verdict  # noqa: E402  (窗口在不在沿用它那套:报错框和真窗口按窗口类分)


class Facts:
    """带缺字段即记账的读取器。缺一个字段 = 一条 problem,不是 KeyError 崩掉、也不是当成 None 放过。"""

    def __init__(self, raw):
        self.raw = raw if isinstance(raw, dict) else {}
        self.missing = []

    def get(self, key):
        if key not in self.raw:
            self.missing.append(key)
            return None
        return self.raw[key]


def _version(health):
    return str((health or {}).get("version") or "") if isinstance(health, dict) else ""


def _baseline(f, problems):
    """每个场景都先问:场景摆好了吗、替身被软件认出来了吗。摆不好的场景一律红,不许当"产品没问题"。"""
    old, new = str(f.get("old_version") or ""), str(f.get("new_version") or "")
    reset = f.get("reset") or {}
    if reset.get("installer_rc") != 0:
        problems.append("setup: old installer rc=%r" % reset.get("installer_rc"))
    if _version(reset.get("health")) != old or not old:
        problems.append("setup: old app not answering as %s (got %r)" % (old, _version(reset.get("health"))))
    check = f.get("check") or {}
    if check.get("update_available") is not True or str(check.get("latest")) != new:
        problems.append("setup: app did not see the stand-in release (update_available=%r latest=%r error=%r)"
                        % (check.get("update_available"), check.get("latest"), check.get("error")))
    log = [e for e in (f.get("fake_log") or []) if isinstance(e, dict)]

    def first(pred, after=-1):
        return next((i for i, e in enumerate(log) if i > after and pred(e)), None)

    def kind_is(k, status=None):
        return lambda e: e.get("kind") == k and (status is None or status(e.get("status")))

    ok = lambda s: s == 200          # noqa: E731
    # 判据 rl12c(评审 整份 DeepSeek):产品在订阅源**任何**失败时都回落 API,
    # 这里原来只认 >=500 ⇒ 替身换个状态码(404/403/429)就会"产品完全正确却判红"。
    # 200 仍然不算失败 —— 反例 "feed did not actually fail" 守着这一边。
    failed = lambda s: isinstance(s, int) and s != 200   # noqa: E731
    download = first(kind_is("download"))
    # 查更新走哪条来源(track opendesign-update-check-rate-limit,rl12):
    #   feed —— 替身的 API 回 403 限流 ⇒ 订阅源 200、清单 200 且在下载之前,**一次都不许问 API**(rl4 的真机版);
    #   api  —— 替身的订阅源回 503 ⇒ 先有失败的订阅源请求、之后才有成功的 API 请求、下载在 API 应答之后。
    # 🔴 评审(overall GPT #2 / 切片 e2e Kimi #2,均复现):原来只看 kind 出没出现 —— 顺序反了、状态不对、清单只有 404 都判 OK。
    source = f.get("source")
    if source == "feed":
        if first(kind_is("atom", ok)) is None:
            problems.append("setup: stand-in never answered a release-feed request with 200")
        manifest_ok = first(kind_is("manifest", ok))
        if manifest_ok is None:
            problems.append("feed path: app never fetched the update manifest successfully")
        if first(kind_is("releases")) is not None:
            problems.append("feed path worked but the app still asked the rate-limited API")
        if download is not None and (manifest_ok is None or download < manifest_ok):
            problems.append("feed path: download happened before the manifest was fetched")
    elif source == "api":
        feed_failed = first(kind_is("atom", failed))
        if feed_failed is None:
            problems.append("fallback: the release feed never failed first (scenario untested)")
        early_api = first(kind_is("releases"))
        if feed_failed is not None and early_api is not None and early_api < feed_failed:
            problems.append("fallback: app asked the API before the release feed failed")
        api_ok = first(kind_is("releases", ok), after=feed_failed if feed_failed is not None else -1)
        if api_ok is None:
            problems.append("fallback: app never got an API answer after the feed failed")
        if download is not None and (api_ok is None or download < api_ok):
            problems.append("fallback: download happened before the API answered")
    else:
        problems.append("setup: unknown update source mode %r" % (source,))
    return old, new


def _downloads(f):
    return [e for e in (f.get("fake_log") or []) if isinstance(e, dict) and e.get("kind") == "download"]


def _markers(f, problems):
    before, after = f.get("markers_before"), f.get("markers_after")
    if not before:
        problems.append("deadline: no archive markers were seeded")
    elif before != after:
        problems.append("deadline: archive markers changed (Data/UserData touched)")


def _norm(path):
    return str(path or "").strip().strip('"').rstrip("\\").lower()


def _pointers(f, problems):
    """注册表"装在哪"、卸载条目、开始菜单/桌面快捷方式,**全都必须指着活树**(t26)。

    更新档装进的是 `.new`;改名之后那个路径就不存在了。指过去 = 业主的图标打不开、卸载点不动、
    下次手动安装装进 `.new`。每个场景都查:失败/回滚的路上 `.new` 也已经装过一遍了。
    """
    p = f.get("pointers") or {}
    live = _norm(p.get("live"))
    if not live:
        problems.append("pointers: no live path recorded")
        return
    under = live + "\\"
    un = p.get("uninstall") or {}
    checks = [("InstallDir", p.get("install_dir"), "eq"),
              ("uninstall.InstallLocation", un.get("InstallLocation"), "eq"),
              ("uninstall.UninstallString", un.get("UninstallString"), "under"),
              ("uninstall.DisplayIcon", un.get("DisplayIcon"), "under")]
    shortcuts = p.get("shortcuts") or {}
    if not shortcuts:
        problems.append("pointers: no start-menu/desktop shortcut found")
    checks += [("shortcut " + str(k).rsplit("\\", 1)[-1], v, "under") for k, v in sorted(shortcuts.items())]
    for name, value, how in checks:
        got = _norm(value)
        ok = got == live if how == "eq" else got.startswith(under)
        if not ok:
            problems.append("pointers: %s -> %r, expected %s live tree" % (name, value, "the" if how == "eq" else "inside the"))


def _started(f, problems):
    apply = f.get("apply") or {}
    if apply.get("ok") is not True or apply.get("stage") != "started":
        problems.append("apply did not start (ok=%r stage=%r error=%r)"
                        % (apply.get("ok"), apply.get("stage"), apply.get("error")))
        return False
    relay = f.get("relay") or {}
    if not relay.get("seen"):
        problems.append("relay script process was never seen")
    if not relay.get("ended"):
        problems.append("relay script still running at deadline (%rs)" % relay.get("seconds"))
    return True


def _injected(f, problems):
    inject = f.get("inject") or {}
    if inject.get("landed") is not True:
        # 注入打晚了,更新就会走成功路径 —— 那不是"回滚正常",是这个场景没测到。
        problems.append("injection did not land, scenario untested (%s)" % inject.get("detail"))


def _live_same(f, problems, what):
    before, after = f.get("live_before"), f.get("live_after")
    if not before or before != after:
        problems.append("%s: live tree changed (before=%s after=%s)" % (what, str(before)[:12], str(after)[:12]))


def _finish(kind, f, problems, ok_text):
    if f.missing:
        problems.insert(0, "facts missing: " + ",".join(sorted(set(f.missing))))
    if problems:
        return False, "FAIL %s - %s" % (kind, "; ".join(problems))
    return True, "OK %s - %s" % (kind, ok_text)


def verdict_e2(raw):
    """下回来的包坏了一个字节 ⇒ 拒装,活树不动,旧版照常在答。"""
    f, problems = Facts(raw), []
    old, _ = _baseline(f, problems)
    apply = f.get("apply") or {}
    if apply.get("ok") is not False or apply.get("stage") != "verify":
        problems.append("expected refusal at stage=verify, got ok=%r stage=%r" % (apply.get("ok"), apply.get("stage")))
    if not any(d.get("mode") == "corrupt" for d in _downloads(f)):
        problems.append("no corrupted download was served")
    _live_same(f, problems, "refused update")
    if f.get("new_exists"):
        problems.append(".new left behind")
    if f.get("old_exists"):
        problems.append(".old exists")
    if _version(f.get("health_after")) != old:
        problems.append("old app not answering after refusal (got %r)" % _version(f.get("health_after")))
    _pointers(f, problems)
    _markers(f, problems)
    return _finish("e2", f, problems, "corrupt download refused at verify, live tree untouched, %s still up" % old)


def verdict_e3(raw):
    """活树里有东西被占着 ⇒ 接力脚本放弃:不换名、删 .new、放手后旧版起得来。"""
    f, problems = Facts(raw), []
    old, _ = _baseline(f, problems)
    _injected(f, problems)
    _started(f, problems)
    _live_same(f, problems, "teardown gate")
    if f.get("new_exists"):
        problems.append(".new not deleted after giving up")
    if f.get("old_exists"):
        problems.append(".old exists: a rename happened although teardown was not clean")
    relaunch = f.get("relaunch") or {}
    if _version(relaunch.get("health")) != old:
        problems.append("old app does not start after release (got %r)" % _version(relaunch.get("health")))
    _pointers(f, problems)
    _markers(f, problems)
    auto = _version(f.get("health_after")) or "nobody"
    return _finish("e3", f, problems,
                   "relay gave up without renaming, .new removed, old relaunches (auto-reopened: %s)" % auto)


def _auto_update_disabled_by_the_harness(f, problems):
    """aw1(track opendesign-auto-update-countdown):e1/e6/e8 里**装出来的真桌面版**查更新,
    `why_not` 必须恰好是 `disabled`(脚本用 OPENDESIGN_AUTO_UPDATE=off 关掉了自动更新,免得产品自己抢跑)。

    `disabled` 排在全部条件的**最后**判 ⇒ 看到它 = 前面 no_update / asset / no_shell / not_installed /
    path_unsupported / attempted 在真机上全都成立。Linux 判据全在替身环境里,任何一条在真机上误判,
    启动更新就永远不出现而其余判据全绿 —— 这里是 e9 之外唯一问得到的地方。
    看到 eligible=true ⇒ 关不掉 ⇒ 场景被产品自己的启动更新污染,同样算红。
    """
    auto = (f.get("check") or {}).get("auto_update")
    if not isinstance(auto, dict) or auto.get("eligible") is not False or auto.get("why_not") != "disabled":
        problems.append("auto update gate in the real app is not exactly 'disabled by the harness' (auto_update=%r)" % (auto,))


def _rolled_back(kind, f, problems, old):
    _live_same(f, problems, "rollback")
    if str(f.get("live_version_after") or "") != old:
        problems.append("live tree version is %r, expected old %s" % (f.get("live_version_after"), old))
    if f.get("old_exists"):
        problems.append(".old still exists: rollback did not move it back")
    if f.get("nested_old_exists"):
        problems.append("old tree was moved INSIDE the live tree (move into existing dir)")
    if _version(f.get("health_after")) != old:
        problems.append("relay did not bring the old app back (answering: %r)" % (_version(f.get("health_after")) or None))


def _reached_rollback(f, problems):
    """回滚场景必须**真的做成了第一次改名**:否则走的是"改名一直失败、放弃"那条路,
    终态(活树是旧版、旧版被拉起、没有 .old)和回滚一模一样,而回滚一行都没执行过。
    run 34860373658 的 e4 就是这么假绿的。"""
    if (f.get("relay") or {}).get("old_seen") is not True:
        problems.append("first rename never happened (.old never seen): rollback path untested")


def verdict_e4(raw):
    """第二次改名失败 ⇒ 回滚:活树换回旧版、没有 .old、旧版由接力脚本自己拉起来。"""
    f, problems = Facts(raw), []
    old, _ = _baseline(f, problems)
    _injected(f, problems)
    if _started(f, problems):
        _reached_rollback(f, problems)
        _rolled_back("e4", f, problems, old)
    _pointers(f, problems)
    _markers(f, problems)
    return _finish("e4", f, problems, "second rename failed, relay rolled back and relaunched %s" % old)


def verdict_e5(raw):
    """新版起得来、但收口认不出它 ⇒ 回滚:活树是旧版、在答的是旧版、旧树没被塞进新树。"""
    f, problems = Facts(raw), []
    old, _ = _baseline(f, problems)
    _injected(f, problems)
    if _started(f, problems):
        # 这个场景问的是"**跑着的**坏新版怎么换回去"。坏新版要是压根没起来,回滚面对的是一棵没人占着的树,
        # 那是 e4 已经问过的另一件事 ⇒ 没看见它答过 = 场景没测到,算红。
        bad = str((f.get("inject") or {}).get("version") or "")
        if not bad or bad not in (f.get("seen_versions") or []):
            problems.append("the unhealthy new version (%r) never answered, scenario untested" % (bad or None))
        _reached_rollback(f, problems)
        _rolled_back("e5", f, problems, old)
    _pointers(f, problems)
    _markers(f, problems)
    return _finish("e5", f, problems, "unhealthy new version rolled back to %s" % old)


def _full_update(kind, raw, extra=None):
    """完整更新:在答的是新版、活树是新版、.old/.new 清掉、窗口在、档案逐字节不变。

    失败时要分得清"没装成"(停在哪一步)和"装错了"(装上了但不对)——
    业主那边两种都长成"软件关了没回来"(design「这个 oracle 能被什么骗过」第 4 条)。
    """
    f, problems = Facts(raw), []
    old, new = _baseline(f, problems)
    if extra is not None:
        extra(f, problems)
    _auto_update_disabled_by_the_harness(f, problems)
    if not any(d.get("mode") == "normal" for d in _downloads(f)):
        problems.append("no normal download was served")
    if _started(f, problems):
        answering = _version(f.get("health_after"))
        live_ver = str(f.get("live_version_after") or "")
        if answering != new:
            if live_ver == new:
                problems.append("installed but not answering: live tree is %s, health says %r" % (new, answering or None))
            elif live_ver == old:
                problems.append("not installed: live tree still/again %s, health says %r" % (old, answering or None))
            else:
                problems.append("live tree version %r, health says %r" % (live_ver or None, answering or None))
        elif live_ver != new:
            problems.append("health says %s but live tree version file is %r" % (new, live_ver or None))
        if f.get("old_exists"):
            problems.append(".old not cleaned up")
        if f.get("new_exists"):
            problems.append(".new still exists")
        window = f.get("window") or {}
        w = probe_verdict.window_verdict(window.get("wins") or [], window.get("procs") or [])
        if not w.ok:
            problems.append("window: no OpenDesign main window after update")
        # 切片评审 GPT 腿 #9:health_after 与窗口只采一次,新版起来之后又退出 ⇒ 前面的事实全是过时的。
        if _version(f.get("health_final")) != new:
            problems.append("new version no longer answering at the end (got %r)" % (_version(f.get("health_final")) or None))
    _pointers(f, problems)
    _markers(f, problems)
    return _finish(kind, f, problems, "updated %s -> %s, window up, archive markers intact" % (old, new))


def verdict_e1(raw):
    return _full_update("e1", raw)


def _api_mode(f, problems):
    """e8 问的就是"订阅源坏了靠 API 还能更新" —— 不在 api 模式下跑 = 场景没摆好。"""
    if f.get("source") != "api":
        problems.append("setup: e8 ran with update source %r, not api (scenario untested)" % (f.get("source"),))


def verdict_e8(raw):
    """rl12 的备路半:替身订阅源回 503、API 正常 ⇒ 先试订阅源、再问 API,照样完整更新(e1 的全部断言)。"""
    return _full_update("e8", raw, extra=_api_mode)


def verdict_e9(raw):
    """真 WebView 里的启动更新整条链(track opendesign-auto-update-countdown,aw2)。

    脚本一次 apply 都没发:页面自己查到新版、启动更新、自己发自动更新 ⇒ 注入让新版认不出 ⇒ 回滚 ⇒ 旧版被重新拉起、
    页面再加载一次 ⇒ **不许再下载、不许再起接力脚本**;查更新 attempted + recent_failure。
    """
    f, problems = Facts(raw), []
    # 复位时故意不拉起(页面一起来就会启动更新,注入得先摆好)⇒ 没有「复位后健康」和「脚本自己查一次」这两个事实。
    # _baseline 要问的那两件事由拉起后的健康(launch_health)和回滚后的查更新(check_after)顶上。
    shadow = dict(f.raw)
    shadow["reset"] = dict(shadow.get("reset") or {}, health=f.get("launch_health"))
    shadow["check"] = f.get("check_after")
    old, _ = _baseline(Facts(shadow), problems)
    if "apply" in f.raw:
        problems.append("setup: the harness sent an apply itself, the page's own startup update is untested")
    knob = f.get("auto_knob_at_launch")
    if knob != "":
        problems.append("setup: auto update was still switched off when the app launched (%r)" % (knob,))
    _injected(f, problems)
    if f.get("relay_started_after") is None:
        problems.append("no relay ever started: the page never auto-updated (startup update missing in the real app?)")
    else:
        relay = f.get("relay") or {}
        if not relay.get("seen"):
            problems.append("relay script process was never seen")
        if not relay.get("ended"):
            problems.append("relay script still running at deadline (%rs)" % relay.get("seconds"))
        bad = str((f.get("inject") or {}).get("version") or "")
        if not bad or bad not in (f.get("seen_versions") or []):
            problems.append("the unhealthy new version (%r) never answered, scenario untested" % (bad or None))
        _reached_rollback(f, problems)
        _rolled_back("e9", f, problems, old)
    downloads = [d for d in _downloads(f) if d.get("mode") == "normal"]
    if len(downloads) != 1:
        problems.append("expected exactly one download (the automatic one), got %d: auto update retried after rollback?"
                        % len(downloads))
    else:
        # 攻题二 #4:证明是**页面启动更新**发起的,不是后端查完就自己开装。
        # 页面那次查更新拿到清单 → 立即 POST → (缓存命中,不再拉清单)→ 下载。
        log = [e for e in (f.get("fake_log") or []) if isinstance(e, dict)]
        first_dl = next((e for e in log if e.get("kind") == "download"), None)
        before = [e for e in log[:log.index(first_dl)] if e.get("kind") == "manifest" and e.get("status") == 200]
        gap = (first_dl.get("t") - before[-1].get("t")) if before and isinstance(first_dl.get("t"), (int, float)) \
            and isinstance(before[-1].get("t"), (int, float)) else None
        if gap is None:
            problems.append("cannot time the immediate update: no timestamped manifest before the download")
        elif not 0 <= gap < 8.5:
            problems.append("manifest -> download took %.1fs, expected immediate startup update (<8.5s)" % gap)
    if f.get("relay_again") is not False:
        problems.append("a relay script was running again after the rollback (relay_again=%r)" % (f.get("relay_again"),))
    window = f.get("window_final") or {}
    if not probe_verdict.window_verdict(window.get("wins") or [], window.get("procs") or []).ok:
        problems.append("window: no OpenDesign main window at the end of the observation")
    if _version(f.get("health_final")) != old:
        problems.append("old app no longer answering at the end of the observation (got %r)" % (_version(f.get("health_final")) or None))
    waited = f.get("check_after_s")
    if not isinstance(waited, (int, float)):
        problems.append("check_after_s missing: cannot tell whether the 10-minute window was still open")
    elif waited >= 570:
        problems.append("setup: rollback came back %.0fs after launch, the 600s recent-failure window is untestable" % waited)
    auto = (f.get("check_after") or {}).get("auto_update")
    if (not isinstance(auto, dict) or auto.get("eligible") is not False or auto.get("why_not") != "attempted"
            or auto.get("recent_failure") is not True):
        problems.append("after rollback the version is not reported as a recent failed auto attempt (auto_update=%r)" % (auto,))
    _pointers(f, problems)
    _markers(f, problems)
    return _finish("e9", f, problems, "page auto-updated on its own, rolled back to %s, not retried" % old)


def _live_has_space(f, problems):
    """e6/e7 问的就是"安装路径带空格"—— 路径里没空格 = 场景没摆好,不许当产品没问题。"""
    live = str((f.get("pointers") or {}).get("live") or "")
    if " " not in live:
        problems.append("setup: install path %r has no space, scenario untested" % live)


def verdict_e6(raw):
    """t33 的真机半:装在**带空格**的目录里,点更新照样完整更新(e1 的全部断言 + 路径真的带空格)。"""
    return _full_update("e6", raw, extra=_live_has_space)


def verdict_e7(raw):
    """t33/t34 的真 NSIS 半:把修 t33 之前 python 真正发出去的那条参数(带空格的 /D= 被加了引号 + /UPDATE)
    交给新版安装器 ⇒ 必须拒装(t34 的 rc=3),活树一个字节不动、`.new` 不出现、旧版照常在答。

    `.new` 出现了 = NSIS 其实认了带引号的 /D=(t33 的前提读错了)或守卫把它放了进来;
    活树变了 = /D= 没被认、守卫也没拦 ⇒ 装进了正在运行的活树,正是 t33 要防的那件事。
    """
    f, problems = Facts(raw), []
    old = str(f.get("old_version") or "")
    reset = f.get("reset") or {}
    if reset.get("installer_rc") != 0:
        problems.append("setup: old installer rc=%r" % reset.get("installer_rc"))
    if _version(reset.get("health")) != old or not old:
        problems.append("setup: old app not answering as %s (got %r)" % (old, _version(reset.get("health"))))
    _live_has_space(f, problems)
    cmd = str(f.get("cmdline") or "")
    quoted = cmd.split('"/D=', 1)
    if "/UPDATE" not in cmd or len(quoted) != 2 or " " not in quoted[1]:
        problems.append("setup: not the quoted-/D= update command line, scenario untested (%r)" % cmd)
    rc = f.get("installer_rc")
    if rc != 3:
        problems.append("installer rc=%r, expected 3 (update mode must refuse a target that is not .new)" % (rc,))
    _live_same(f, problems, "quoted /D=")
    if f.get("new_exists"):
        problems.append(".new was created: NSIS honoured the quoted /D= or the guard let it through")
    if _version(f.get("health_after")) != old:
        problems.append("old app not answering afterwards (got %r)" % (_version(f.get("health_after")) or None))
    _pointers(f, problems)
    _markers(f, problems)
    return _finish("e7", f, problems, "quoted /D= in update mode refused by the real installer (rc=3), live tree untouched")


KINDS = {"e1": verdict_e1, "e2": verdict_e2, "e3": verdict_e3, "e4": verdict_e4, "e5": verdict_e5,
         "e6": verdict_e6, "e7": verdict_e7, "e8": verdict_e8, "e9": verdict_e9}


def main(argv):
    if len(argv) != 3 or argv[1] not in KINDS:
        sys.stdout.write("FAIL - usage: update_e2e_verdict.py %s <facts.json>\n" % "|".join(KINDS))
        return 2
    try:
        with open(argv[2], encoding="utf-8-sig") as fh:
            raw = json.load(fh)
        ok, text = KINDS[argv[1]](raw)
    except Exception as exc:  # noqa: BLE001 —— 判定器自己坏了要说出来,且算红
        sys.stdout.write("FAIL %s - judge could not read facts (%s: %s)\n" % (argv[1], type(exc).__name__, exc))
        return 2
    sys.stdout.write(text.encode("ascii", "replace").decode("ascii") + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
