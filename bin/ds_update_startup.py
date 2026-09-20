"""打开软件时的更新决策 —— **只读盘,一次网络都不发**。

track opendesign-startup-not-blocked-by-update(2026-09-19)。

## 为什么有这个模块

0.98.7 把「查更新 + 下载 + 安装」整条链放在**启动路径**上,并用全屏卡片挡住界面。
实测最坏 **20.1 秒**干等(后端串行两跳 × 10s;收据见 track 的 evidence/)。
业主原话:「现在每次打开都会弹出正在检测更新,这严重拖慢了我们开软件的速度」。

## 这里的规矩

**启动只回答一个问题:盘上有没有一个已经下好、且校验得过的新版安装包?**
有 ⇒ 装(那时进度条是真的在装,不是在等网络);没有 ⇒ 立刻进工作区。
查更新和下载都挪到进入工作区**之后**的后台 —— 用户本来就开着软件,那时候慢不碍事。

🔴 **本模块的函数永远不许抛。** 它读的是**盘上的数据**,不是我们自己造的对象:
文件可能半写、可能是上一个版本写的、可能被人手改过、指向的安装包可能已经被删了。
本项目已经有四次"注入/时机"导致整页白或打不开的前科(0.94、0.98 两次白屏、
0.98.0 装不上、0.98.7 启动阻塞)——**"不更新"是小事,"打不开"是大事。**
判据 su13 钉这一条。
"""
import json
import os
import time
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds_update          # 只借 parse_version(避免两份版本比较逻辑漂移);**不调用它的任何取数函数**
import ds_update_apply    # 只借下载/校验(避免两份下载逻辑漂移)
import ds_auto_update     # 只借 why_not_auto + PERMANENT_BLOCKERS(资格判断只写一处,三处共用)

SCHEMA = 1
STATE_NAME = "update-state.json"


def state_path(data_root):
    """状态文件放数据根的 Logs 下,**和既有的 auto-update-attempts.json 同侧**。

    不进安装目录(更新会覆盖、卸载会删 —— 业主卸载丢资料那一单的教训),
    也不进用户数据目录(那是他的真实档案)。判据 sp1/sp2。
    """
    return os.path.join(str(data_root), "Logs", STATE_NAME)

# 🔴 这里原来有一整套后台轮询调度器(FIRST_CHECK_DELAY_S / BASE_INTERVAL_S /
# MAX_BACKOFF_S / JITTER / next_delay,配 sc1~sc4 四条判据),2026-09-20 整段删掉。
#
# 理由:**它一个调用方都没有**。真正决定"进工作区多久之后去查"的是前端那一个
# setTimeout(web/src/update.ts 的 BACKGROUND_FIRST_CHECK_MS,判据 sg9),
# 而"每 10 分钟轮询一次"根本没实现、也不该实现:
# 业主一次会话查一次足够(新版一周才有一个),而这个项目刚因为查得太勤被 GitHub
# 限过流(track opendesign-update-check-rate-limit)。
#
# 留着的代价不是占地方,是**它看起来像一条防线**:同一天前端 handleStartupAutoCheck
# 就是"以为还有人走、其实没人走",代价是回滚提示整条消失。
# 以后真要做长会话轮询,连调用方一起加回来,判据钉的是调用方,不是这个函数本身。


def read_state(path):
    """读盘上的状态。**任何读不出来的情况都返回 None,绝不抛**(判据 sw3/sw4)。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001 —— 文件不在/半写/非 JSON/权限/编码,一律当没有
        return None
    return data if isinstance(data, dict) else None


def write_state(path, state):
    """原子写:临时文件写满 + fsync,再 os.replace 换上去(判据 sw2)。

    半写的文件**绝不能出现在那个路径上** —— 启动路径会读它,
    而半写的 JSON 会让 read_state 返回 None、白白错过一次已经下好的更新。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".update-state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(p))
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _enter(reason):
    return {"action": "enter", "reason": reason}


def startup_decision(state, current_version, now=None):
    """打开软件时该干什么:装,还是直接进工作区。

    🔴 **这里只答事实,不答资格**(2026-09-20 第 3 轮外审 F1/F3 之后定的分工)。
    本函数问的是「盘上到底有没有一个校验得过、比当前新的包」—— 纯读盘,不看环境、不看账本。
    「该不该**自动**装它」是另一个问题,整条链只有一处答:`ds_auto_update.why_not_auto`
    (账本 + 这台机器两维一起),由 startup / prepare / apply 三个决策点共用。
    第 2 轮我曾把账本那一维塞进这里、拿一个可选的 `data_root` 控制,那不是收敛:
    ① 同一个问题两处答(端点那边还得再问一次机器维度);
    ② **忘传就静默失效**,而纯函数判据(su1~su15)不传它、自己测自己,永远是绿的。
    两条都是本单要消灭的形状,所以参数整个拿掉,让"忘传"不再是一种可能。

    **只有一条路通向 install**;其余一切 —— 包括任何我没预料到的输入 —— 都是 enter。
    reason 是稳定枚举(判据 su14),界面和判据都认它。

    🔴 整个函数包在一个 try 里:漏掉任何一种坏输入,代价是业主打不开软件。
    """
    try:
        if not isinstance(state, dict):
            return _enter("no_state")
        if state.get("schema") != SCHEMA:
            return _enter("unknown_schema")
        if state.get("phase") != "ready":
            return _enter("not_ready")

        version = state.get("version")
        current = ds_update.parse_version(current_version) if isinstance(current_version, str) else None
        target = ds_update.parse_version(version) if isinstance(version, str) else None
        if target is None or current is None:
            return _enter("unreadable_version")
        if target <= current:
            return _enter("not_newer")

        asset = state.get("asset")
        path = state.get("path")
        if not isinstance(asset, dict) or not isinstance(path, str) or not path:
            return _enter("incomplete_state")

        # 符号链接一律拒:那是"包被换掉"最省事的一条路(worktree 符号链接事故的同族)。
        if os.path.islink(path) or not os.path.isfile(path):
            return _enter("package_missing")

        want_size, want_sha = asset.get("size"), asset.get("sha256")
        if not isinstance(want_size, int) or not isinstance(want_sha, str) or len(want_sha) != 64:
            return _enter("incomplete_state")
        if os.path.getsize(path) != want_size:
            return _enter("size_mismatch")

        # 🔴 **这里不算 sha256**(判据 su15)。原来算 —— 那是 O(包大小) 的操作,
        #    而前端给这一步的上限是写死的 500ms,业主那台 Windows 还有 Defender
        #    正在实时扫这个刚下好的 46MB .exe。超时之后是**单向**的:前端 abort 进工作区、
        #    不重试;后台 already_ready 也不会重新备货 ⇒ 那一版从此永远装不上,而且悄无声息。
        #    (2026-09-20 第 1 轮外审 subcursor HIGH-1,我核实成立。本机实测热 37ms、
        #     丢缓存 117ms —— 没超,但余量未知,而失败是静默的。)
        #
        #    **字节校验没有消失,它在两头**:下好的那一刻(prepare,判据 pr3/pr9)、
        #    以及真装之前(apply_update 再算一遍,判据 t4:对不上就拒绝执行、活树零改动)。
        #    启动这一步只回答"盘上有没有一个看起来可装的东西"。
        return {"action": "install", "reason": "ready", "version": version, "path": path}
    except Exception:  # noqa: BLE001 —— 判据 su13:宁可不更新,绝不许打不开
        return _enter("decision_failed")


PENDING_DIR = "pending"


def _asset_facts(info):
    """从查更新的结果里挖出下载所需的四样;缺一样就不算数。"""
    if not isinstance(info, dict) or info.get("update_available") is not True:
        return None
    version = info.get("latest")
    asset = info.get("asset")
    if not isinstance(version, str) or not version or not isinstance(asset, dict):
        return None
    url, name, size = asset.get("url"), asset.get("name"), asset.get("size")
    digest = ds_update_apply.parse_digest(asset.get("digest"))
    if not isinstance(url, str) or not url or not isinstance(name, str) or not name:
        return None
    if not isinstance(size, int) or size <= 0 or not digest:
        return None
    return {"version": version, "url": url, "name": name, "size": size, "sha256": digest}


def _sweep_installed(state_file, info):
    """把"已经装上了"的那个备货包清掉。**永不抛**(调用它的也是后台任务)。

    只清确定没用的:状态里那一版 <= 现在跑着的版本。读不出版本就什么都不做 ——
    拿不准的时候宁可留着占盘,也不许删错(删掉的是业主等着装的那 46MB)。
    """
    try:
        current = info.get("current") if isinstance(info, dict) else None
        if not isinstance(current, str):
            return
        state = read_state(state_file)
        if not isinstance(state, dict):
            return
        here = ds_update.parse_version(current)
        there = ds_update.parse_version(state.get("version")) \
            if isinstance(state.get("version"), str) else None
        if here is None or there is None or there > here:
            return
        _discard(state.get("path"), state_file)
    except Exception:  # noqa: BLE001
        return


def _sweep_orphans(state_file, data_root):
    """`pending/` 下**没人指着**的文件一律清掉。**永不抛**。

    半截包(被杀在下载中途)、被跳过那一版的孤儿(备好 0.99.0 之后 0.99.1 上线,
    新的写成新文件名,旧那个 46MB 再没人提起)—— 每攒一个就是永久多占一份。
    判据 pr10。两条腿在第 1 轮各自报了这件事。

    判断"有没有人指着"只认状态文件里那一条 path:拿不准的时候不删是安全的,
    因为下一轮还会再来一次;而删错的代价是业主等着装的那 46MB 没了。
    """
    try:
        d = os.path.join(str(data_root), "Logs", PENDING_DIR)
        if not os.path.isdir(d):
            return
        state = read_state(state_file)
        keep = (state or {}).get("path") if isinstance(state, dict) else None
        keep = os.path.normcase(os.path.realpath(keep)) if isinstance(keep, str) and keep else None
        for name in os.listdir(d):
            p = os.path.join(d, name)
            try:
                if not os.path.isfile(p) or os.path.islink(p):
                    continue
                if keep is not None and os.path.normcase(os.path.realpath(p)) == keep:
                    continue
                os.unlink(p)
            except OSError:
                continue
    except Exception:  # noqa: BLE001
        return


def prepare_update(info, paths, download=None, now=None):
    """后台把新版下下来、校验、写状态 —— **只下不装**。

    装留到下一次打开软件:那时候装是最快的(东西已经在本地),而且本来就在启动,
    不额外打断业主。这正是 Chrome 那一路的做法。

    🔴 **永不抛**(判据 pr6):它跑在业主正在干活的时候,一个后台任务把主进程搞崩
    是不可接受的。失败就安静地不写 ready,下次再试。

    🔴 `paths` 是**必填**,而且 `data_root` 不再单独当形参(判据 el17,
    track opendesign-update-duplicate-facts)。原来的形状是
    `prepare_update(info, data_root, ..., paths=None)`:

    - 生产调用点两个都传,而 `root` 就是 `paths["data_root"]` ⇒ **同一个事实两个入口**,
      迟早有人传成两个不同的值,而且没有任何东西会报错;
    - `paths` 忘传时不报错,**静默退回"只问账本那一维"** —— 上一单第 3 轮刚在
      `startup_decision` 上删掉同一个形状(F3),这里漏网了。今天生产无洞
      (唯一调用点一定传,端点自己还有一道早闸),漏的是**判据**:既有 pr 卷全都不传它,
      于是机器那一维在这一层一条题都问不到(el18 补上了)。
    """
    fetch = ds_update_apply._default_download if download is None else download
    try:
        # data_root / state_file 都放进 try 里:上面那句"永不抛"包括 `paths` 被传成
        # 不是 dict 的东西(红检实测过一次 —— 旧签名会把它 str() 进路径、默默建出目录)。
        data_root = paths.get("data_root")
        # 🔴 拿不到 data_root 就**什么都别做**(判据 el20,2026-09-20 外审 subcursor+submimo
        #    各自独立碰到这一处)。没有这一句的话:`state_path(None)` 会算出相对路径
        #    `"None/Logs/update-state.json"`,于是打扫、写状态、下载**全都落在当前工作目录**
        #    ——业主机器上那就是安装目录。不报错、不抛、照常返回,**一声不响地写错地方**。
        #    生产走不到(端点用 paths_for_update 造 paths),但这正是本单在治的那个形状:
        #    宁可响亮地失败,也不要静默地做错事。
        if not isinstance(data_root, str) or not data_root:
            return {"ok": False, "reason": "prepare_failed"}
        state_file = state_path(data_root)
        # 🔴 先打扫:盘上留着的那个包如果**不比现在跑着的版本新**,它就是垃圾
        #    (多半是上一次更新装完之后剩下的)。不清 ⇒ 每更新一次永久多占 46MB。
        #    放在这里而不是启动路径上:那条路只许读盘,越少动作越好;这里业主已经在用软件了。
        #    判据 pr8 / pr8b(还没装的新版不许被清掉)。
        _sweep_installed(state_file, info)
        _sweep_orphans(state_file, data_root)

        facts = _asset_facts(info)
        if facts is None:
            return {"ok": False, "reason": "nothing_to_prepare"}

        # 🔴 **备货之前先问够不够格自动装**(判据 el1/el1b,2026-09-20 第 2 轮外审)。
        #    这一版已经自动试过一次(装不上)⇒ 下回来也只会被 apply 再拒一次,
        #    中间还要让业主看一次没有任何解释的更新界面。原来这里不问,于是删掉的包
        #    **每打开一次软件就被原样下回来一次**:末端删文件追不上前端重新备货。
        #    判断本身在 ds_auto_update.why_not_auto —— 与 startup / apply 同一处来源,
        #    **整个问题问一次**(账本那一维 + 机器那几维),调用方不许自己再拼一遍。
        blocker = ds_auto_update.why_not_auto(paths, facts["version"])
        if blocker:
            if blocker in ds_auto_update.PERMANENT_BLOCKERS:
                # 永久否决(试过 / 不是装出来的 / 路径不支持)⇒ 这一版**再也不会**自动装,
                # 顺手清掉它的残留备货(判据 el9 我自审补的、el14 第 3 轮外审 F4)。
                # 资格闸装上之后这一版的链路是 prepare 拒 → startup 回 enter ⇒ **apply 再也不跑**,
                # 而清包的动作原本只挂在 apply 那一侧。没有这一下,一份没走完正常流程的
                # ready 备货三处都没人碰:`_sweep_installed` 嫌它新、`_sweep_orphans` 见状态
                # 正指着它、apply 不跑 ⇒ 业主盘上永久白占 46MB。
                # prepare 每次打开软件后 60 秒跑一趟(前端 setTimeout 单次,不是轮询),
                # 本来就是打扫 + 备货的地方,是这条链自然的收敛点。
                # 零风险:这个包永远不会再被自动装,手动更新走真下载、不碰它(判据 el6)。
                current = read_state(state_file)
                if isinstance(current, dict) and current.get("version") == facts["version"]:
                    _discard(current.get("path"), state_file)
            # 临时否决(没外壳 / 开关关着 / 算不出来)照旧**不删包**:条件恢复就还能装(判据 el4/el13)。
            return {"ok": False, "reason": blocker}

        # 同一版已经下好了就别再下一遍(判据 pr7:省业主的流量和磁盘)。
        # 🔴 但"已经下好"必须**验到字节**(判据 pr9):启动那一步已经不算哈希了(su15),
        #    这里再只比大小的话,一个等长坏包就会被两边一起放过 —— 后台说"不用下"、
        #    安装侧每次拒,**死循环,永不自愈**。这一趟跑在业主用软件的时候,慢不要紧。
        current = read_state(state_file)
        if (isinstance(current, dict) and current.get("phase") == "ready"
                and current.get("version") == facts["version"]):
            path = current.get("path")
            if isinstance(path, str) and os.path.isfile(path) \
                    and os.path.getsize(path) == facts["size"] \
                    and ds_update_apply.sha256_file(path).lower() == facts["sha256"].lower():
                return {"ok": True, "reason": "already_ready"}

        dest_dir = os.path.join(str(data_root), "Logs", PENDING_DIR)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, facts["name"])

        # 动手之前先把 downloading 写上(判据 pr5):下载中途断电/被杀,
        # 下次启动读到的是 downloading 而不是一个指向半个文件的 ready。
        write_state(state_file, {"schema": SCHEMA, "phase": "downloading",
                                 "version": facts["version"],
                                 "asset": {"name": facts["name"], "size": facts["size"],
                                           "sha256": facts["sha256"], "url": facts["url"]},
                                 "path": dest,
                                 "updated_at": time.time() if now is None else now})
        try:
            fetch(facts["url"], dest)
        except Exception:  # noqa: BLE001
            _discard(dest, state_file)
            return {"ok": False, "reason": "download_failed"}

        if not os.path.isfile(dest) or os.path.getsize(dest) != facts["size"]:
            _discard(dest, state_file)
            return {"ok": False, "reason": "size_mismatch"}
        if ds_update_apply.sha256_file(dest).lower() != facts["sha256"].lower():
            # 判据 pr3:坏包必须删掉 —— 留着只会占盘,而且哪天有人放宽校验就会装上去。
            _discard(dest, state_file)
            return {"ok": False, "reason": "digest_mismatch"}

        write_state(state_file, {"schema": SCHEMA, "phase": "ready",
                                 "version": facts["version"],
                                 # url 也记下来:下次打开要装的时候,安装那一侧需要一个
                                 # **真的**下载地址塞进决定里(它自己不去下,但会校验形状)。
                                 # 不记的话就只能现编一个,或者回去联网查 —— 两条都不行。
                                 "asset": {"name": facts["name"], "size": facts["size"],
                                           "sha256": facts["sha256"], "url": facts["url"]},
                                 "path": dest,
                                 "updated_at": time.time() if now is None else now})
        return {"ok": True, "reason": "ready", "version": facts["version"]}
    except Exception:  # noqa: BLE001 —— 判据 pr6
        return {"ok": False, "reason": "prepare_failed"}


def discard_ready(data_root):
    """把盘上那份备货作废(连包带状态)。**永不抛**。

    🔴 谁用它:自动安装被拒或没装成的时候(ds_web)。这一版从此只能手动
    (同一版自动只试一次),留着那份 `ready` 只会让**每次打开**都空演一遍更新界面,
    而 `auto_skipped` 在界面上是**静默**的 —— 业主看到的是"闪一下,然后什么都没说"。
    判据 ai7/ai8(2026-09-20 第 1 轮外审 subcursor HIGH-2)。
    """
    try:
        state_file = state_path(data_root)
        state = read_state(state_file)
        _discard((state or {}).get("path"), state_file)
    except Exception:  # noqa: BLE001
        return


def _discard(dest, state_file):
    """把没通过校验的包和 ready 状态一起清掉。自己也不许抛。

    🔴 `except Exception` 不是偷懒:`dest` 来自盘上的状态文件,可能是 `None`
    (`os.path.isfile(None)` 抛的是 `TypeError`,不是 `OSError`)。写着"自己也不许抛"
    却只兜 `OSError`,靠的是三个调用方各自包了更宽的 except —— 下一个调用方不包就漏。
    判据 el8(2026-09-20 第 2 轮外审 subdeepseek 实测)。
    """
    try:
        if os.path.isfile(dest):
            os.unlink(dest)
    except Exception:  # noqa: BLE001
        pass
    try:
        write_state(state_file, {"schema": SCHEMA, "phase": "idle",
                                 "version": None, "asset": None,
                                 "path": None, "updated_at": time.time()})
    except Exception:  # noqa: BLE001
        pass
