#!/usr/bin/env python3
"""track opendesign-workspace-health 的 oracle(一)—— workspace.json 读改写加锁。
主 agent 亲写,executor off-limits。

**这是本单的准入条件,不是 follow-up。** design.md「Key trade-offs / risks」第一条:
`_write_workspace_json` 只做原子替换(tmp + os.replace),**整个「读→改→写」全程无锁**。
四个写口(set_workspace / bind_project / rename_project / delete_project)都是
「读 raw → 改一个键 → 整份写回」,两个并发写互相覆盖,最后写的赢。体检卡再加一个
网页写口 = 又多一个并发来源,所以锁必须先落。

而且这不是"锦上添花":`ds_tools.py` 模块头自己写着「安全(spec §5):realpath
allowlist 防路径逃逸 + **排他锁写串行化**」—— workspace.json 这条路径从来没兑现过。
仓里现成的 `ds_common.locked_rw` 是给 markdown 账本用的(按行读写、就地截断),
JSON 配置不能直接套。

## 判据钉死的是行为,不是实现

1. **互斥必须活过 os.replace**(t03/t04)。执行腿最可能的写法是「flock 目标文件本身,
   然后 tmp + os.replace 盖上去」—— 锁留在了**被 unlink 的旧 inode** 上,下一个写者
   open 到的是**新文件**、拿到的是**新锁**,互斥当场失效而测试看起来全绿。
   所以 t03 打的是「持锁期间别人必须真的被挡住」。
2. **原子性不许为了加锁而丢**(t06)。反过来,把锁焊死在目标文件上、改成就地
   truncate+write 也能让 t03 过 —— 但读者会读到半截文件。t06 让读者在写者狂写时
   读 200 次,每次都必须是合法 JSON。t03 + t06 一起,才逼出「旁挂锁文件 + 原子替换」。
3. **四个写口一个都不许漏**(t04)。守卫的强度只等于清单本身;这里逐个点名,
   只给新写口加锁 = 红。
4. **丢更新是最终判据**(t05)。前三条都是机制,t05 打的是用户看得见的后果:
   并发跑完之后,该在的映射一条都不能少。
5. **红检实测:病比 design.md 记的重**(t05b)。`_write_workspace_json` 的 tmp 名是
   **固定的** `workspace.json.tmp`,两个并发写者共用同一个临时文件。实测三连跑出三种
   症状:① `set_workspace` 抛 `FileNotFoundError`(A 替换走了 tmp,B 的 replace 扑空);
   ② 24/25 条映射被盖掉;③ **配置被写成非法 JSON**。第③种最狠 —— `load_config`
   对坏 JSON 的反应是整份降级成 None,用户眼里就是"我的项目全没了"。
   **所以"原子替换"这四个字目前根本不成立**,修法不止是加锁:tmp 名必须唯一,
   或由锁本身保证独占。

## 这个 oracle 能被什么骗过?

**全局大锁式的假绿**:执行腿可能给整个 ds_tools 加一把进程内 `threading.Lock`。
本文件的阻塞判据用的是**同进程多线程**(fcntl.flock 按 open file description 计,
同进程两个 fd 照样互斥),所以进程内锁也能让 t03/t04/t05 变绿 —— 但真机是
**MCP server 进程 + ds-web 进程两个进程**在写同一份配置,进程内锁等于没锁。
t07 用 `subprocess` 起真子进程复核这一条;t07 绿了,前面几条才算数。

跑法: python3 -m pytest tests/test_ds_workspace_config_lock.py
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from unittest import mock
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
import ds_tools  # noqa: E402
import ds_workspace  # noqa: E402

HOLD = 0.6      # 持锁时长:够长到能判定"确实被挡住",够短到测试不磨蹭
GRACE = 8.0     # 释放后允许完成的宽限(CI 慢机留余量)


def _mkenv(projects=None, extra=None):
    """建 DS_ROOT + 工作区;返回 (ds_root, ws_root)。"""
    ds = tempfile.mkdtemp(prefix="wslock-ds-")
    ws = tempfile.mkdtemp(prefix="wslock-ws-")
    os.makedirs(os.path.join(ds, "config"), exist_ok=True)
    os.makedirs(os.path.join(ds, "projects"), exist_ok=True)
    # projectsDir="." → 项目夹直接在工作区根一级(用户真机就是这个布局,
    # 也是 excluded_structural / 体检卡唯一适用的布局)。不写这一行,
    # projects_root() 找不到候选目录 → project_folders 恒为 [],夹具假绿。
    cfg = {"root": ws, "projects": projects or {}, "projectsDir": "."}
    cfg.update(extra or {})
    _write_raw(ds, cfg)
    return ds, ws


def _cfg_path(ds):
    return os.path.join(ds, "config", "workspace.json")


def _write_raw(ds, obj):
    with open(_cfg_path(ds), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def _read_raw(ds):
    with open(_cfg_path(ds), encoding="utf-8") as fh:
        return json.load(fh)


def _mkproject(ds, key, body=None):
    """建一份档案(rename/delete 写口需要)。"""
    with open(os.path.join(ds, "projects", f"{key}.md"), "w", encoding="utf-8") as fh:
        fh.write(body or f"# {key}\n\n最后更新: 2026-07-26\n")


def _mkfolder(ws, name):
    os.makedirs(os.path.join(ws, name), exist_ok=True)
    return name


class LockedWorkspaceJson(unittest.TestCase):
    """加锁读改写的公共件本身:`ds_tools.locked_workspace_json(ds_root)`。

    契约(判据即规格):
      - contextmanager,yield 一个 box;`box["raw"]` = 已解析的 dict,
        文件缺失/坏 JSON/顶层非 dict → None(全仓"坏配置降级"同款,不抛)。
      - 调用方改 `box["raw"]`;置 `box["write"] = False` → 文件**一个字节都不碰**。
      - 退出时(write 为真)原子落盘;**锁从读之前一直握到替换之后**。
    """

    def setUp(self):
        self.tmps = []

    def tearDown(self):
        for p in self.tmps:
            shutil.rmtree(p, ignore_errors=True)

    def _env(self, **kw):
        ds, ws = _mkenv(**kw)
        self.tmps += [ds, ws]
        return ds, ws

    def test_t01_reads_and_writes_whole_object(self):
        """读出整份 raw,改完整份写回;未动的键逐字节保留。"""
        ds, ws = self._env(projects={"甲": "甲夹"},
                           extra={"projectsDir": "01-项目", "projectsDepth": 2,
                                  "galleryDepth": 4})
        with ds_tools.locked_workspace_json(ds) as box:
            self.assertIsInstance(box["raw"], dict)
            self.assertEqual(box["raw"]["projects"], {"甲": "甲夹"})
            box["raw"]["structuralDirs"] = ["00-收件箱"]
        after = _read_raw(ds)
        self.assertEqual(after["structuralDirs"], ["00-收件箱"])
        self.assertEqual(after["root"], ws)
        self.assertEqual(after["projects"], {"甲": "甲夹"})
        self.assertEqual(after["projectsDir"], "01-项目")
        self.assertEqual(after["projectsDepth"], 2)
        self.assertEqual(after["galleryDepth"], 4)

    def test_t02_write_false_leaves_file_untouched(self):
        """错误路径:置 write=False → 内容与 mtime 都不许变(ds_common.locked_rw 同款礼数)。"""
        ds, _ = self._env(projects={"甲": "甲夹"})
        with open(_cfg_path(ds), "rb") as fh:
            before = fh.read()
        st_before = os.stat(_cfg_path(ds))
        time.sleep(0.02)
        with ds_tools.locked_workspace_json(ds) as box:
            box["raw"]["projects"]["乙"] = "乙夹"   # 改了,但不落盘
            box["write"] = False
        with open(_cfg_path(ds), "rb") as fh:
            self.assertEqual(fh.read(), before, "write=False 不许改内容")
        self.assertEqual(os.stat(_cfg_path(ds)).st_mtime_ns, st_before.st_mtime_ns,
                         "write=False 连 mtime 都不许碰")

    def test_t02b_bad_config_degrades_to_none_and_is_not_clobbered(self):
        """坏 JSON → raw=None,**不抛**;调用方不写时,用户手写的原文一个字节不动。"""
        ds, _ = self._env()
        with open(_cfg_path(ds), "w", encoding="utf-8") as fh:
            fh.write("{ 这是用户手改坏的 json")
        with open(_cfg_path(ds), "rb") as fh:
            before = fh.read()
        with ds_tools.locked_workspace_json(ds) as box:
            self.assertIsNone(box["raw"], "坏配置必须降级成 None,不许抛")
            box["write"] = False
        with open(_cfg_path(ds), "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_t02c_missing_file_yields_none_and_can_be_created(self):
        """文件不存在 → raw=None(set_workspace 首次接入就是这条路);写得出来。"""
        ds, ws = self._env()
        os.remove(_cfg_path(ds))
        with ds_tools.locked_workspace_json(ds) as box:
            self.assertIsNone(box["raw"])
            box["raw"] = {"root": ws, "projects": {}}
        self.assertEqual(_read_raw(ds)["root"], ws)

    def test_t02e_never_writes_a_non_dict_over_the_users_config(self):
        """**闸③亲读 diff 时发现的地雷(GPT 腿实现通过了全部判卷,但漏了这个)。**

        调用方进了块、`raw` 保持 `None`(坏配置)、又忘了置 `write=False` ——
        实测会往 `workspace.json` 里写进字面量 **`null`**,把用户手写的配置**当场毁掉**。

        四个既有写口目前都各自守住了(所以判卷全绿),但**下一阶段的体检卡写口
        正是最容易踩这一脚的地方** —— 而「别悄悄毁掉用户的配置」恰恰是本单的立身之本。
        安全网放在公共件里,只要一行:`raw` 不是 dict 就不落盘。

        判据:块内什么都不做 → 原文一个字节不许变。
        """
        ds, _ = self._env()
        with open(_cfg_path(ds), "w", encoding="utf-8") as fh:
            fh.write("{ 用户手改坏的 json")
        with open(_cfg_path(ds), "rb") as fh:
            before = fh.read()
        with ds_tools.locked_workspace_json(ds):
            pass                      # raw=None,write 仍是 True
        with open(_cfg_path(ds), "rb") as fh:
            self.assertEqual(fh.read(), before,
                             "raw 不是 dict 时绝不许落盘(写 null = 毁掉用户的配置)")
        # 同款:调用方把 raw 换成了非 dict
        for junk in (None, [], "字符串", 5):
            with self.subTest(raw=junk):
                with ds_tools.locked_workspace_json(ds) as box:
                    box["raw"] = junk
                with open(_cfg_path(ds), "rb") as fh:
                    self.assertEqual(fh.read(), before, f"raw={junk!r} 不许落盘")

    def test_t02d_exception_inside_block_does_not_write(self):
        """块内抛异常 → 异常照常传出,但文件不许被写成半成品状态。"""
        ds, _ = self._env(projects={"甲": "甲夹"})
        with open(_cfg_path(ds), "rb") as fh:
            before = fh.read()

        class Boom(Exception):
            pass

        with self.assertRaises(Boom):
            with ds_tools.locked_workspace_json(ds) as box:
                box["raw"]["projects"]["乙"] = "乙夹"
                raise Boom()
        with open(_cfg_path(ds), "rb") as fh:
            self.assertEqual(fh.read(), before, "异常路径不许落盘")

    # ── 互斥:本单的核心判据 ──────────────────────────────────────────────
    def test_t03_mutual_exclusion_survives_atomic_replace(self):
        """**执行腿最可能翻车的那一条**:锁必须活过 os.replace。

        「flock 目标文件 → tmp → os.replace」把锁留在被 unlink 的旧 inode 上,
        第二个写者 open 到的是新文件、拿到的是新锁,互斥当场失效。
        判据:持锁期间另一个写者必须**真的被挡住**;释放后必须能完成。
        """
        ds, ws = self._env()
        done = threading.Event()

        def worker():
            with ds_tools.locked_workspace_json(ds) as box:
                box["raw"]["projects"]["乙"] = "乙夹"
            done.set()

        with ds_tools.locked_workspace_json(ds) as box:
            box["raw"]["projects"]["甲"] = "甲夹"   # 先写一份(替换过一次)
        # 第二轮:握着锁不放,看别人挡不挡得住 —— 此时文件已被 replace 过一次,
        # 锁若绑在旧 inode 上,worker 会畅通无阻
        with ds_tools.locked_workspace_json(ds) as box:
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            self.assertFalse(done.wait(HOLD),
                             "持锁期间另一个写者必须被挡住(锁没活过 os.replace)")
            box["raw"]["projects"]["丙"] = "丙夹"
        self.assertTrue(done.wait(GRACE), "释放后必须能完成,不许死锁")
        t.join(GRACE)
        after = _read_raw(ds)
        self.assertEqual(set(after["projects"]), {"甲", "丙", "乙"},
                         "串行化之后三条映射都该在")

    def test_t04_every_workspace_json_writer_takes_the_lock(self):
        """**四个写口一个都不许漏**。守卫的强度只等于这份清单。

        逐个点名:持锁期间调用该写口,它必须被挡住(= 它走了同一把锁)。
        只给新写口加锁、老写口照旧裸写 = 红。
        """
        cases = []

        # set_workspace:读旧配置保 projects → 写回
        ds1, ws1 = self._env()
        cases.append(("set_workspace",
                      lambda: ds_tools.set_workspace(ws1, ds_root=ds1), ds1))

        # bind_project:load_config → 读 raw → 改 projects[key] → 写回
        ds2, ws2 = self._env()
        _mkproject(ds2, "甲项目")
        _mkfolder(ws2, "甲项目")
        cases.append(("bind_project",
                      lambda: ds_tools.bind_project("甲项目", "甲项目", ds_root=ds2), ds2))

        # rename_project:映射键 old→new
        ds3, ws3 = self._env(projects={"老名": "老夹"})
        _mkproject(ds3, "老名")
        cases.append(("rename_project",
                      lambda: ds_tools.rename_project("老名", "新名", ds_root=ds3), ds3))

        # delete_project:摘映射
        ds4, ws4 = self._env(projects={"待删": "待删夹"})
        _mkproject(ds4, "待删")
        cases.append(("delete_project",
                      lambda: ds_tools.delete_project("待删", ds_root=ds4), ds4))

        for name, call, ds in cases:
            with self.subTest(writer=name):
                done = threading.Event()
                box_out = {}

                def worker():
                    box_out["r"] = call()
                    done.set()

                with ds_tools.locked_workspace_json(ds) as box:
                    box["write"] = False       # 只占锁,不改内容
                    t = threading.Thread(target=worker, daemon=True)
                    t.start()
                    blocked = not done.wait(HOLD)
                self.assertTrue(blocked,
                                f"{name} 写 workspace.json 时没走那把锁(裸写)")
                self.assertTrue(done.wait(GRACE), f"{name} 释放后必须能完成")
                t.join(GRACE)

    def test_t05_concurrent_writers_do_not_lose_updates(self):
        """**用户看得见的后果判据**:并发跑完,该在的映射一条都不能少。

        真机的经典交错:一边 bind_project 加映射,一边 set_workspace 改根/重存 ——
        后者「读旧 projects → 整份写回」会把前者刚加的那条盖掉。
        """
        n = 25
        ds, ws = self._env()
        for i in range(n):
            _mkproject(ds, f"项目{i}")
            _mkfolder(ws, f"项目{i}")
        errors, crashes = [], []

        def binder():
            for i in range(n):
                try:
                    r = ds_tools.bind_project(f"项目{i}", f"项目{i}", ds_root=ds)
                except Exception as e:                 # 见 t05b:真的会抛
                    crashes.append(("bind", i, repr(e)))
                    continue
                if not r.get("ok"):
                    errors.append(("bind", i, r))

        def setter():
            for _ in range(n):
                try:
                    r = ds_tools.set_workspace(ws, ds_root=ds)
                except Exception as e:
                    crashes.append(("set", repr(e)))
                    continue
                if not r.get("ok"):
                    errors.append(("set", r))

        ts = [threading.Thread(target=binder), threading.Thread(target=setter)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(60)
        self.assertEqual(crashes[:3], [], "并发期间写口不许抛异常")
        self.assertEqual(errors, [], "并发期间写口本身不许报错")
        after = _read_raw(ds)
        missing = [f"项目{i}" for i in range(n) if f"项目{i}" not in after["projects"]]
        self.assertEqual(missing, [], f"丢更新:{len(missing)} 条映射被并发写盖掉")

    def test_t05b_concurrent_writes_never_corrupt_the_config(self):
        """**红检时实测到的第三种症状,比 design.md 记的更严重。**

        `_write_workspace_json` 的 tmp 名是**固定的** `workspace.json.tmp` ——
        两个并发写者共用同一个临时文件:内容互相交错写进去,然后 A 替换走(tmp 没了)、
        B 的 `os.replace` 抛 `FileNotFoundError`。实测三连跑复现三种症状:
        ① set_workspace 抛 FileNotFoundError;② 24/25 条映射被盖掉;
        ③ **配置被写成非法 JSON**(`Extra data`)。

        ③ 是最狠的一种:`load_config` 对坏 JSON 的反应是**整份配置降级成 None**
        —— 用户眼里是"我的项目全没了"。所以"原子替换"这四个字目前根本不成立,
        修法不只是加锁,tmp 名也必须唯一(或干脆由锁来保证独占)。

        判据:并发跑完,配置**必须还是合法 JSON 且 root 正确**。
        """
        n = 20
        ds, ws = self._env()
        for i in range(n):
            _mkproject(ds, f"项目{i}")
            _mkfolder(ws, f"项目{i}")
        crashes = []

        def binder():
            for i in range(n):
                try:
                    ds_tools.bind_project(f"项目{i}", f"项目{i}", ds_root=ds)
                except Exception as e:
                    crashes.append(("bind", repr(e)))

        def setter():
            for _ in range(n):
                try:
                    ds_tools.set_workspace(ws, ds_root=ds)
                except Exception as e:
                    crashes.append(("set", repr(e)))

        ts = [threading.Thread(target=binder), threading.Thread(target=setter)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(60)
        self.assertEqual(crashes[:3], [], "并发写不许抛(共用 tmp 名的直接后果)")
        try:
            after = _read_raw(ds)
        except ValueError as e:
            self.fail(f"并发写把 workspace.json 写坏了({e})—— 读侧会整份降级,"
                      f"用户眼里=项目全没了")
        self.assertEqual(after.get("root"), ws)
        self.assertIsNotNone(ds_workspace.load_config(ds), "写坏的配置读侧直接下线")

    def test_t06_readers_never_observe_a_partial_file(self):
        """**别为了加锁把原子性丢了**。就地 truncate+write 也能让 t03 变绿,
        但读者会读到半截 JSON —— 而读侧(load_config)对坏 JSON 的反应是
        **整个工作区功能下线**,用户眼里就是"文件全没了"闪一下。

        判据:写者狂写期间,读者每一次读都必须是合法 JSON 且 root 正确。
        载荷放大到几百条映射,把"半截文件"的窗口撑开。

        **假绿闸(红检时真的踩到了)**:写者线程若自己挂了(比如助手还没实现那个
        contextmanager),读者读到的是一份纹丝不动的健康文件 → `bad` 为空 → 本条
        会"通过"。所以必须同时断言 **写者确实写成功过**(wrote > 0)且**没抛异常**。
        """
        ds, ws = self._env(projects={f"项目{i}": f"夹{i}" for i in range(400)})
        stop = threading.Event()
        bad, boom, wrote = [], [], []

        def writer():
            i = 0
            while not stop.is_set():
                try:
                    with ds_tools.locked_workspace_json(ds) as box:
                        box["raw"]["projects"][f"新{i}"] = f"新夹{i}"
                except Exception as e:
                    boom.append(repr(e))
                    return
                wrote.append(i)
                i += 1

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        try:
            for _ in range(200):
                try:
                    with open(_cfg_path(ds), encoding="utf-8") as fh:
                        obj = json.load(fh)
                except (OSError, ValueError) as e:
                    bad.append(repr(e))
                    continue
                if not isinstance(obj, dict) or obj.get("root") != ws:
                    bad.append(f"结构不对: {type(obj)} root={obj.get('root') if isinstance(obj, dict) else None}")
        finally:
            stop.set()
            t.join(GRACE)
        self.assertEqual(boom[:3], [], "写者线程自己挂了 —— 本条的绿不作数")
        self.assertGreater(len(wrote), 0, "写者一次都没写成 —— 本条的绿不作数")
        self.assertEqual(bad[:5], [], f"读者读到了半截/损坏的配置({len(bad)}/200 次)")

    def test_t07_lock_is_cross_process_not_just_cross_thread(self):
        """**防"进程内锁"假绿**:真机是 MCP server 进程 + ds-web 进程两个进程
        在写同一份配置。`threading.Lock` 能让 t03~t05 全绿,但真机等于没锁。

        判据:本进程持锁期间,**另起一个真子进程**去写,它必须被挡住。
        """
        ds, ws = self._env()
        code = (
            "import sys, json;"
            f"sys.path.insert(0, {os.path.join(ROOT, 'bin')!r});"
            "import ds_tools;"
            f"r = ds_tools.set_workspace({ws!r}, ds_root={ds!r});"
            "print(json.dumps(r))"
        )
        with ds_tools.locked_workspace_json(ds) as box:
            box["write"] = False
            p = subprocess.Popen([sys.executable, "-c", code],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                p.wait(timeout=HOLD)
                blocked = False
            except subprocess.TimeoutExpired:
                blocked = True
        try:
            out, err = p.communicate(timeout=GRACE)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            self.fail("释放后子进程仍未完成(跨进程死锁)")
        self.assertTrue(blocked,
                        "跨进程没被挡住 —— 用的是进程内锁,真机(MCP + ds-web 两进程)等于没锁")
        self.assertEqual(p.returncode, 0, err.decode("utf-8", "replace"))
        # 四审补(submimo #3 + subkimi):原来只断言"被挡住 + 退出码 0",
        # **没验证子进程的写到底落没落盘** —— 一个既被挡住、又静默写失败的实现
        # 也能让本条变绿。跨进程的"不丢更新"判据缺了这一半。
        self.assertTrue(json.loads(out.decode("utf-8")).get("ok"),
                        "子进程必须真的写成功,不是被挡住之后悄悄失败")
        self.assertEqual(_read_raw(ds)["root"], ws, "子进程释放后那次写必须真的落盘")

    def test_t08_lock_does_not_litter_the_user_workspace(self):
        """锁文件是**我们的**实现细节,不许落到用户的项目文件夹里。
        用户会在资源管理器里看着这个目录 —— 多一个 .lock 就是多一个"这什么?"。
        """
        ds, ws = self._env()
        _mkfolder(ws, "00-收件箱")
        _mkfolder(ws, "真项目")
        before = set(os.listdir(ws))
        for _ in range(3):
            with ds_tools.locked_workspace_json(ds) as box:
                box["raw"]["structuralDirs"] = ["00-收件箱"]
        self.assertEqual(set(os.listdir(ws)), before,
                         "工作区根下不许多出任何锁文件/临时文件")

    def test_t09_no_tmp_file_left_behind(self):
        """写完不许在 config/ 留 .tmp 残骸(崩溃不留半文件的另一半)。"""
        ds, _ = self._env()
        with ds_tools.locked_workspace_json(ds) as box:
            box["raw"]["structuralDirs"] = []
        leftovers = [f for f in os.listdir(os.path.join(ds, "config"))
                     if f.endswith(".tmp")]
        self.assertEqual(leftovers, [], "写完不许留 .tmp")

    def test_t11_nested_acquisition_fails_loudly_instead_of_hanging(self):
        """**四审顺出、主 agent 漏掉的(subdeepseek W1 + subkimi M1 两腿独立命中)。**

        `locked_workspace_json` 不可重入:同一线程嵌套进入同一 ds_root,
        `flock` 按 open file description 计,第二个 fd 的 `LOCK_EX` **永久阻塞**
        —— 实测 `timeout 8` 直接 124,无超时、无报错、无从恢复。
        真机表现:ds-web 那条线程整个挂死,用户点了按钮永远转圈。

        它已经被定位成「阶段二网页写口要接的公共件」,而网页写口最容易
        在锁内间接调到另一个已经接了锁的入口(比如卡片保存里顺手调 bind_project)。

        判据钉的是**响度不是可重入**:嵌套 = 编程错误,应当**当场炸给开发者**,
        而不是变成一个没有任何线索的挂起。修法不是让它可重入
        (那会让「锁内调另一个写口」这种真正危险的写法悄悄合法化)。
        """
        ds, _ = self._env()
        with ds_tools.locked_workspace_json(ds) as outer:
            outer["write"] = False
            with self.assertRaises(RuntimeError,
                                   msg="嵌套获取必须立刻抛,不许挂死"):
                with ds_tools.locked_workspace_json(ds) as inner:
                    inner["write"] = False
        # 外层正常退出后,锁必须已经彻底释放(别把嵌套失败变成锁泄漏)
        done = threading.Event()

        def worker():
            with ds_tools.locked_workspace_json(ds) as box:
                box["write"] = False
            done.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.assertTrue(done.wait(GRACE), "嵌套报错之后不许把锁泄漏掉")
        t.join(GRACE)

    def test_t12_write_preserves_the_files_permission_bits(self):
        """**四审顺出(subdeepseek BLOCK-1 + subkimi L2)。**

        `tempfile.NamedTemporaryFile` 建的临时文件是 0600,`os.replace` 之后
        整个继承过去 —— 于是每写一次,`workspace.json` 的权限就被**悄悄收紧**
        (实测 0644 → 0600)。这是修 tmp 名带来的**非预期副作用**,不是有意设计。

        本机单账号看不出问题,但「写文件顺手改掉它的权限」本身就不该发生:
        判据钉住「写前是什么,写后还是什么」。

        **Windows 上跳过(2026-07-27 用户真机实测,判据自己的错)**:
        Windows 没有 POSIX 权限位 —— `os.chmod` 只认只读标志,`os.stat` 对任何
        可写文件一律回 `0o666`(实测三个子条目全报 `438 != …`,438 就是 0o666)。
        在那儿断言「写前是什么写后还是什么」测的是操作系统,不是本仓的代码。
        **不是把判据放水**:POSIX 上照旧逐位钉死,只是这条断言在 Windows 上
        本来就没有可测的对象。
        """
        if os.name == "nt":
            self.skipTest("Windows 无 POSIX 权限位:os.stat 恒回 0o666,无从断言")
        ds, _ = self._env()
        for mode in (0o644, 0o600, 0o664):
            with self.subTest(mode=oct(mode)):
                os.chmod(_cfg_path(ds), mode)
                with ds_tools.locked_workspace_json(ds) as box:
                    box["raw"]["structuralDirs"] = ["00-收件箱"]
                self.assertEqual(stat.S_IMODE(os.stat(_cfg_path(ds)).st_mode), mode,
                                 "写入不许改动配置文件的权限位")

    def test_t13_replace_survives_a_windows_style_permission_error(self):
        """**Windows 真机抓到的真 bug**(2026-07-27,判据 t06 在用户机器上红)。

        POSIX 上 rename 覆盖一个"正被读的文件"完全合法,所以这条在 Linux 上
        **永远绿**;Windows 上只要有任何人把 `workspace.json` 打开着(哪怕只是
        `load_config` 那零点几毫秒),写者的 `os.replace` 就当场
        `PermissionError(13, '拒绝访问。')`。真机是 MCP server + ds-web 两进程、
        ds-web 自己还是多线程 —— 用户看到的现象是**保存莫名其妙失败**。

        本条在 Linux 上**注入**那个异常,把重试逻辑本身钉住:
        否则修复代码在开发机上一行都跑不到,等于又发一份没验过的东西上 Windows。
        """
        ds, _ = self._env()
        real_replace = os.replace
        calls = []

        def flaky(src, dst, *a, **kw):
            calls.append(1)
            if len(calls) <= 3:                      # 前 3 次模拟"目标被别人开着"
                raise PermissionError(13, "拒绝访问。")
            return real_replace(src, dst, *a, **kw)

        with mock.patch.object(os, "replace", flaky):
            with ds_tools.locked_workspace_json(ds) as box:
                box["raw"]["structuralDirs"] = ["00-收件箱"]
        self.assertGreater(len(calls), 3, "重试没发生")
        cfg = ds_workspace.load_config(ds)
        self.assertEqual(cfg["structuralDirs"], ["00-收件箱"], "重试后必须真的写进去")

    def test_t13b_replace_gives_up_loudly_instead_of_silently_losing_the_write(self):
        """一直失败就必须**照抛**。吞掉异常 = 用户以为存上了,其实没有 ——
        比直接报错坏得多(本 track 的立身之本就是"别悄悄动/悄悄不动用户的东西")。"""
        ds, _ = self._env()

        def always_denied(src, dst, *a, **kw):
            raise PermissionError(13, "拒绝访问。")

        with mock.patch.object(os, "replace", always_denied):
            with self.assertRaises(PermissionError):
                with ds_tools.locked_workspace_json(ds) as box:
                    box["raw"]["structuralDirs"] = ["00-收件箱"]

    def test_t10_written_config_is_immediately_usable(self):
        """落盘 ≠ 能用(test_ds_web_upload 第 1 条哲学):写完 load_config 立刻认得。"""
        ds, ws = self._env()
        _mkfolder(ws, "00-收件箱")
        _mkfolder(ws, "真项目")
        with ds_tools.locked_workspace_json(ds) as box:
            box["raw"]["structuralDirs"] = ["00-收件箱"]
        cfg = ds_workspace.load_config(ds)
        self.assertIsNotNone(cfg, "写完的配置必须读得回来")
        self.assertEqual(cfg["structuralDirs"], ["00-收件箱"])
        self.assertEqual([n for n, _ in ds_workspace.project_folders(cfg)], ["真项目"])


if __name__ == "__main__":
    unittest.main()
