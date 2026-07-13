#!/usr/bin/env python3
"""ds_web — OpenDesign 工作台本地服务(纯 stdlib,track opendesign-workbench)。

静态服务 web/dist(Vite 构建产物) + 只读 API:
  GET /api/todos   ds_todo.collect() 结构化 JSON(每请求现读 PKB,零缓存)
  GET /api/health  存活探针(version + ds_root)
聊天代理(P1,docs/nanobot-ws-protocol.md;8765 零 CORS → 同源转发,纯管道零秘密):
  GET /api/chat/bootstrap             → 127.0.0.1:<nanobot>/webui/bootstrap
  GET /api/chat/sessions              → …/api/sessions
  GET /api/chat/sessions/<key>/thread → …/api/sessions/<key>/webui-thread
  白名单仅此三条;<key> 先验 [A-Za-z0-9_:.-]{1,128} 且拒 './..'(不 unquote,
  %xx 直接非法 → 转发段永远改不了上游路径结构);查询串原样透传;请求头只
  透传 Authorization / X-Nanobot-Auth;上游状态码原样回传(401 不吞,前端
  靠它透明重签);上游连不上 → 502。
文件工作区只读视图(P5,ds_workspace + config/workspace.json):
  GET /api/files/overview/<key>    类目计数+最近文件(未配置/未映射诚实降级)
  GET /api/files/images/<key>      项目图片清单
  GET /api/files/file/<key>/<rel>  项目图片静态服务(三闸同 refs 先例)
  POST /api/open-folder            {"key","sub"?} → 本机资源管理器打开项目夹。
    这是"只读铁律"的首个受控例外(P5 design §3,用户拍板):不写任何数据,
    仅在 key 映射 + sub 白名单 + realpath within + isdir 全过后执行 OPEN_LAUNCHER;
    launcher 可注入(测试/e2e 永不真开)。
  POST /api/chat/sessions/<key>/delete  → …/api/sessions/<key>/delete(p7 第二针孔):
    删除历史对话 = 代理 nanobot 原生删除(上游自带"绑定自动化先拒"保护);上游
    不查方法,本服务只以 POST 暴露(GET 面保持纯只读);真正鉴权在上游 Bearer
    token,CT json 闸是 CSRF 纵深。本服务仍零 PKB 写面。
其余方法/其余 POST 路径一律 405 —— 写操作必须过 ds_tools 核心,本服务不直改 PKB。
项目列表(p7):/api/projects = PKB projects/*.md ∪ 工作区项目夹自动发现
(ds_workspace.project_folders,未被映射/绑定消费的文件夹以 unregistered:true 追加;
只读联合,不自动建档)。

约束(design.md D2):只绑 127.0.0.1;端口 DS_WEB_PORT(默认 8766),被占明确报错
退出不静默换口;JSON ensure_ascii=False + charset=utf-8;读期 OSError(Windows
msvcrt 强制锁窗口内并发读会瞬时报错)归入 500 路径,刷新自愈;静态路径
unquote → realpath → ds_common.within 防逃逸。
环境变量:DS_ROOT / DS_WEB_PORT / DS_WEB_DIST(测试注入用)/ DS_NANOBOT_PORT。
"""
import http.client
import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import ds_common
import ds_refs
import ds_todo
import ds_workspace

VERSION = "0.8.0"  # p7 历史对话删除 + 项目列表直读工作区;回显此号=运行中是新版的实证
DEFAULT_NANOBOT_PORT = 8765
# nanobot config 路径(model 回显用):env 可覆盖(测试/非常规安装),默认 ~/.nanobot/config.json
DEFAULT_NANOBOT_CONFIG = os.path.join(os.path.expanduser("~"), ".nanobot", "config.json")


def _read_model():
    """当前大脑,解析规则与 nanobot 一致(schema.py:AgentDefaults):modelPreset 设了
    就以它指向的预设为准,悬空/未设才回落 agents.defaults.model —— 只读 model 字段会
    在 preset 布局(install.ps1 合并模板后的真机形态)回显假值(07-13 的雷)。
    只读、每请求现读(零缓存,与 /api/todos 同哲学);任何读取失败 → None,
    健康探针本体不受牵连。"""
    try:
        cfg = os.environ.get("DS_NANOBOT_CONFIG", DEFAULT_NANOBOT_CONFIG)
        with open(cfg, encoding="utf-8") as fh:
            data = json.load(fh)
        defaults = data.get("agents", {}).get("defaults", {})
        preset_name = defaults.get("modelPreset")
        if isinstance(preset_name, str) and preset_name:
            preset = data.get("model_presets", {}).get(preset_name)
            if isinstance(preset, dict):
                m = preset.get("model")
                if isinstance(m, str) and m:
                    return m
        m = defaults.get("model")
        return m if isinstance(m, str) and m else None
    except Exception:
        return None
# 与上游 _decode_api_key 同字符集;不含 % 和 / ⇒ 原样转发也无路径走私
_KEY_RE = re.compile(r"^[A-Za-z0-9_:.-]{1,128}$")
_THREAD_RE = re.compile(r"^/api/chat/sessions/([^/]+)/thread$")
_SESSION_DELETE_RE = re.compile(r"^/api/chat/sessions/([^/]+)/delete$")  # p7 POST 针孔②

# P2 只读 API 路由(段捕获用 [^/]+,中文项目名在 wire 上是 %xx,故不含裸 /):
_CHANGES_RE = re.compile(r"^/api/projects/([^/]+)/changes$")
_PROJ_REFS_RE = re.compile(r"^/api/projects/([^/]+)/refs$")
_REFS_FILE_RE = re.compile(r"^/api/refs/file/(.+)$")
# P5 文件工作区路由
_FILES_OVERVIEW_RE = re.compile(r"^/api/files/overview/([^/]+)$")
_FILES_IMAGES_RE = re.compile(r"^/api/files/images/([^/]+)$")
_FILES_FILE_RE = re.compile(r"^/api/files/file/([^/]+)/(.+)$")
OPEN_FOLDER_PATH = "/api/open-folder"  # do_POST 唯一放行路径,精确匹配
OPEN_BODY_MAX = 4096  # open-folder 请求体上限(key+sub 远小于此)


def _default_open_launcher(path: str):
    """本机打开文件夹。Windows=资源管理器;其余平台 xdg-open(列表参数无 shell)。
    DS_OPEN_CMD 覆盖启动命令(e2e 在无桌面 Linux 上注入记录脚本),同样列表参数。"""
    cmd = os.environ.get("DS_OPEN_CMD")
    if cmd:
        import subprocess
        subprocess.Popen([cmd, path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    elif os.name == "nt":
        os.startfile(path)  # noqa: S606 —— 目录路径已过 realpath within 闸
    else:
        import subprocess
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


OPEN_LAUNCHER = _default_open_launcher  # 模块级可注入(测试/e2e 用 fake)

# 已交付 = 阶段词表(workspace/AGENTS.md)的收尾两档;仅用于侧栏淡化,读侧启发式。
# 阶段词表如扩展,这里同步。accepted deviation:词表本身不在本 track 定义。
DELIVERED_STAGES = ("竣工验收", "售后")

# 项目 key 字符集白名单:\w 已覆盖中文(Python re 默认 Unicode);另放行空格与
# 可读连接符,p7 起放行 `#`(工作区文件夹命名约定「楼栋#户号」,wire 上是 %23,
# unquote 后才进比较,不参与路径语义)。不含 / \ ⇒ 无路径分隔符;`.`/`..` 与含
# `..` 者显式拒(纵深防御,realpath+within 才是权威闸)。与 ds_workspace._FOLDER_RE
# 同集合。
_PROJ_KEY_RE = re.compile(r"^[\w .()#\-]+\Z")
# 参考图相对路径白名单(Gate A):同上但放行 / 支持子目录;`..` 走 Gate B(realpath)。
# 收尾用 \Z 不用 $:re 的 $ 在"结尾换行符之前"也匹配,`a.png\n` 会漏过字符集闸。
_REFS_PATH_RE = re.compile(r"^[\w /.()\-]+\Z")

# 图片扩展名白名单(Gate C)—— 唯一允许读出的类型;svg 排除(直开可执行脚本)。
_IMG_CTYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}


def _valid_proj_key(key: str) -> bool:
    """项目 key 合法性:非空、非 `.`/`..`、无 `/ \\ ..`、无控制字符、过字符集白名单。"""
    if not key or key in (".", "..") or ".." in key:
        return False
    if "/" in key or "\\" in key or any(ord(c) < 0x20 for c in key):
        return False
    return bool(_PROJ_KEY_RE.match(key))


def _field(text: str, name: str) -> str:
    """取项目头 `- <name>: <值>` 的值(半/全角冒号都认);无则空串。"""
    m = re.search(rf"^- {re.escape(name)}[:：]\s*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _title(text: str) -> str:
    """取首个 `# 标题` 作项目显示名;无则空串(调用方回落 key)。"""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""
DEFAULT_DS_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_DIST = os.path.join(DEFAULT_DS_ROOT, "web", "dist")
DEFAULT_PORT = 8766

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"ds-web/{VERSION}"

    # ---- helpers ----
    def _send(self, status: int, ctype: str, body: bytes, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):  # 请求日志走 stdout(design D2 运维面)
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- routes ----
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "version": VERSION,
                             "ds_root": self.server.ds_root,
                             "model": _read_model()})
        elif path == "/api/todos":
            self._todos()
        elif path == "/api/chat/bootstrap":
            self._proxy("/webui/bootstrap")
        elif path == "/api/chat/sessions":
            self._proxy("/api/sessions")
        elif (m := _THREAD_RE.match(path)):
            key = m.group(1)  # 原样段,不 unquote(见模块头契约)
            if _KEY_RE.match(key) and key not in (".", ".."):
                self._proxy(f"/api/sessions/{key}/webui-thread")
            else:
                self._json(404, {"error": "bad key"})
        elif path == "/api/projects":
            self._projects()
        elif (m := _CHANGES_RE.match(path)):
            self._changes(unquote(m.group(1)))
        elif (m := _PROJ_REFS_RE.match(path)):
            self._project_refs(unquote(m.group(1)))
        elif (m := _REFS_FILE_RE.match(path)):
            self._refs_file(unquote(m.group(1)))
        elif (m := _FILES_OVERVIEW_RE.match(path)):
            self._files_meta(unquote(m.group(1)), "overview")
        elif (m := _FILES_IMAGES_RE.match(path)):
            self._files_meta(unquote(m.group(1)), "images")
        elif (m := _FILES_FILE_RE.match(path)):
            self._files_file(unquote(m.group(1)), unquote(m.group(2)))
        elif path.startswith("/api/"):
            self._json(404, {"error": "unknown api"})
        else:
            self._static(path)

    def _method_not_allowed(self):  # P0 只读:写方法焊死 405(oracle #5)
        body = json.dumps({"error": "read-only"}, ensure_ascii=False).encode("utf-8")
        self._send(405, "application/json; charset=utf-8", body,
                   {"Allow": "GET"})  # RFC 7231 §6.5.5:405 必带 Allow

    def do_POST(self):
        # 只读铁律的受控针孔白名单(精确匹配,其余 POST 维持 405,oracle 锁死):
        # ① open-folder(P5)② 会话删除代理(p7,真正鉴权在上游 Bearer token)
        path = urlsplit(self.path).path
        if path == OPEN_FOLDER_PATH:
            self._open_folder()
        elif (m := _SESSION_DELETE_RE.match(path)):
            self._delete_session(m.group(1))
        else:
            self._method_not_allowed()

    do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    def _todos(self):
        try:
            data = ds_todo.collect(self.server.ds_root)
        except Exception:
            # 含 Windows 写锁窗口内的读期 OSError(F3)与坏编码文件(F2):
            # 500 自愈路径,trace 进日志不进响应体
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._json(200, data)

    def _project_file(self, key: str) -> str | None:
        """key → projects/<key>.md 的 realpath;非法 key / 逃逸 / 不存在 → None。
        字符集白名单先拦(纵深),realpath + within(projects) 是权威闸,零文件读走私。"""
        if not _valid_proj_key(key):
            return None
        base = os.path.realpath(os.path.join(self.server.ds_root, "projects"))
        target = os.path.realpath(os.path.join(base, key + ".md"))
        if not ds_common.within(base, target) or not os.path.isfile(target):
            return None
        return target

    def _projects(self):
        try:
            root = self.server.ds_root
            counts = {}  # 未办结计数单一真相源 = ds_todo.collect(与 /api/todos 同源)
            for it in ds_todo.collect(root)["open"]:
                counts[it["project"]] = counts.get(it["project"], 0) + 1
            proj_dir = os.path.realpath(os.path.join(root, "projects"))
            files = sorted(f for f in (os.listdir(proj_dir) if os.path.isdir(proj_dir)
                                       else []) if f.endswith(".md"))
            projects = []
            for f in files:
                key = f[:-3]
                # 与 _project_file 同一把闸:projects/ 里指向外部的 symlink .md
                # 不读不列(panel LOW:listdir 直读会把外部文件标题/阶段字段带出)
                target = os.path.realpath(os.path.join(proj_dir, f))
                if not ds_common.within(proj_dir, target) or not os.path.isfile(target):
                    continue
                with open(target, encoding="utf-8") as fh:
                    text = fh.read()
                stage = _field(text, "阶段")
                dates = ds_common.LASTUPD_DATE_RE.findall(text)
                projects.append({
                    "key": key,
                    "name": _title(text) or key,
                    "stage": stage,
                    "open_count": counts.get(key, 0),
                    "delivered": stage in DELIVERED_STAGES,
                    "last_update": dates[-1] if dates else None,
                    "unregistered": False,
                })
            # p7 design D2:联合工作区自动发现的项目夹(只读,不建档)。
            # 消费集合按 realpath 比对(不按 basename):显式映射目标 ∪ 各 PKB
            # key 的三级绑定解析结果;没被消费的文件夹以 unregistered 追加,
            # key=文件夹名 → 文件区/图墙/open-folder 经 project_dir ②直等可用。
            cfg = ds_workspace.load_config(root)
            folders = ds_workspace.project_folders(cfg)
            if folders:
                consumed = set()
                for p in projects:
                    pd = ds_workspace.project_dir(cfg, p["key"])
                    if pd:
                        consumed.add(pd)
                for rel in cfg["projects"].values():
                    if rel:
                        consumed.add(os.path.realpath(os.path.join(cfg["root"], rel)))
                for name, fpath in folders:
                    if fpath in consumed:
                        continue
                    projects.append({
                        "key": name, "name": name, "stage": "",
                        "open_count": 0, "delivered": False,
                        "last_update": None, "unregistered": True,
                    })
        except Exception:
            traceback.print_exc()  # 坏编码/写锁窗口读期 OSError:500 自愈,trace 进日志
            self._json(500, {"error": "internal"})
            return
        self._json(200, {"projects": projects})

    def _changes(self, key: str):
        target = self._project_file(key)
        if target is None:
            self._json(404, {"error": "not found"})  # 不回显 key/路径
            return
        try:
            with open(target, encoding="utf-8") as fh:
                text = fh.read()
            changes = []
            for ln in text.split("\n"):
                c = ds_todo.parse_change(ln)  # 四状态全量,单一真相源
                if c is None:
                    continue
                changes.append({
                    "cnum": c["cnum"], "status": c["status"],
                    "text": c["text"], "date": c["date"],
                    # space = 变更行可选【空间】前缀(p4 T1,parse 单一真相源);
                    # source 仍无字段 → 恒 None(读侧宽容,accepted deviation)
                    "space": c["space"], "source": None,
                })
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._json(200, {"key": key, "changes": changes})

    def _project_refs(self, key: str):
        if not _valid_proj_key(key):
            self._json(404, {"error": "not found"})
            return
        try:
            refs = ds_refs.list_project_refs(key, self.server.ds_root)
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        # 只回 UI 需要的字段(id/style/space/file/note),source/used 不外泄
        out = [{"id": r["id"], "style": r["style"], "space": r["space"],
                "file": r["file"], "note": r["note"]} for r in refs]
        self._json(200, {"key": key, "refs": out})

    def _refs_file(self, rel: str):
        """参考图静态服务 —— 本 track 唯一新增文件读出面。三闸串联,每闸独立可验红:
        Gate A 字符集白名单 → Gate B realpath 前缀(逃逸/symlink 权威闸)→ Gate C 扩展白名单。
        404 一律不回显路径;Content-Type 按扩展映射;禁目录列表(只 isfile)。"""
        # Gate A —— 字符集白名单(拒 % 残留 / 控制字符 / 反斜杠 / 其它非白名单字符)
        if not _REFS_PATH_RE.match(rel):
            self._json(404, {"error": "not found"})
            return
        base = os.path.realpath(os.path.join(self.server.ds_root, "refs"))
        target = os.path.realpath(os.path.join(base, rel))
        # Gate B —— realpath 前缀:裸 ../ 与 symlink 逃逸展开后必须仍落在 refs/ 内
        if not ds_common.within(base, target):
            self._json(404, {"error": "not found"})
            return
        # Gate C —— 扩展名白名单:只有图片类型可读出
        ctype = _IMG_CTYPES.get(os.path.splitext(target)[1].lower())
        if ctype is None:
            self._json(404, {"error": "not found"})
            return
        if not os.path.isfile(target):  # 禁目录列表 + 不存在
            self._json(404, {"error": "not found"})
            return
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body,
                   {"Cache-Control": "public, max-age=86400"})

    # ── P5 文件工作区 ────────────────────────────────────────────────────────

    def _ws_proj(self, key: str):
        """(状态, 项目夹) —— 状态 ∈ badkey/unconfigured/unmapped/ok。
        配置每请求现读(零缓存,与 /api/todos 同哲学,改 json 即生效)。"""
        if not _valid_proj_key(key):
            return "badkey", None
        cfg = ds_workspace.load_config(self.server.ds_root)
        if cfg is None:
            return "unconfigured", None
        pd = ds_workspace.project_dir(cfg, key)
        if pd is None:
            return "unmapped", None
        return "ok", pd

    def _files_meta(self, key: str, kind: str):
        """overview / images 共用外壳:降级态诚实回 JSON,不 404 糊弄前端。"""
        status, pd = self._ws_proj(key)
        if status == "badkey":
            self._json(404, {"error": "not found"})
            return
        if status == "unconfigured":
            self._json(200, {"configured": False})
            return
        if status == "unmapped":
            self._json(200, {"configured": True, "mapped": False})
            return
        try:
            if kind == "overview":
                data = ds_workspace.overview(pd)
            else:
                data = {"images": ds_workspace.images(pd)}
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._json(200, {"configured": True, "mapped": True, **data})

    def _files_file(self, key: str, rel: str):
        """项目图片静态服务。三闸同 _refs_file 先例(Gate A 字符集 → Gate B realpath
        within(项目夹) → Gate C 图片扩展白名单),外加 key 必须已映射;404 不回显路径。"""
        status, pd = self._ws_proj(key)
        if status != "ok" or not _REFS_PATH_RE.match(rel):
            self._json(404, {"error": "not found"})
            return
        target = os.path.realpath(os.path.join(pd, rel))
        if not ds_common.within(pd, target):
            self._json(404, {"error": "not found"})
            return
        ctype = _IMG_CTYPES.get(os.path.splitext(target)[1].lower())
        if ctype is None or not os.path.isfile(target):
            self._json(404, {"error": "not found"})
            return
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body, {"Cache-Control": "public, max-age=3600"})

    def _open_folder(self):
        """唯一非 GET 端点(P5 design §3)。闸序:body 尺寸/JSON → key 白名单+映射
        (_ws_proj)→ sub 单段白名单+realpath within+isdir(ds_workspace.resolve_sub)
        → 全过才调 OPEN_LAUNCHER;任何拒绝路径零执行(oracle 断言)。
        CSRF 硬化:强制 Content-Type application/json——跨站 fetch 带该类型必触发
        preflight,本服务无 OPTIONS 面 → 浏览器拦;text/plain 类 simple request 在此 400。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        key = body.get("key") if isinstance(body, dict) else None
        if not isinstance(key, str) or not key:
            self._json(400, {"error": "bad request"})
            return
        status, pd = self._ws_proj(key)
        if status != "ok":
            self._json(404, {"error": "not found"})
            return
        sub = body.get("sub")
        if sub is not None and not isinstance(sub, str):
            self._json(400, {"error": "bad request"})
            return
        target = ds_workspace.resolve_sub(pd, sub)
        if target is None:
            self._json(404, {"error": "not found"})
            return
        try:
            OPEN_LAUNCHER(target)
        except OSError:
            traceback.print_exc()  # 无桌面/启动器缺失:500,路径不回显
            self._json(500, {"error": "internal"})
            return
        self._json(200, {"ok": True})

    def _delete_session(self, key: str):
        """POST 针孔②(p7 design D1):删除历史对话 → 代理 nanobot 原生删除。
        闸序:CT application/json(CSRF 纵深:跨站带该类型必 preflight,本服务无
        OPTIONS 面)→ body ≤ OPEN_BODY_MAX 且读净丢弃(防 keep-alive 脱轨)→
        key 白名单(不 unquote,同 thread 代理:%xx 直接非法)→ _proxy 转发。
        真正鉴权在上游(无 Bearer token 上游 401 原样回传);上游若回
        blocked_by_automations 也原样透传给前端提示,不代理 delete_automations
        参数(OpenDesign 不暴露自动化面)。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 <= n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        if n:
            self.rfile.read(n)
        if not _KEY_RE.match(key) or key in (".", ".."):
            self._json(404, {"error": "bad key"})
            return
        self._proxy(f"/api/sessions/{key}/delete")

    def _proxy(self, up_path: str):
        """白名单 GET 转发到本机 nanobot gateway。纯管道:不读不存任何秘密。"""
        q = urlsplit(self.path).query
        if q:
            up_path += "?" + q
        hdrs = {}
        for h in ("Authorization", "X-Nanobot-Auth"):  # 请求头白名单,其余剥离
            v = self.headers.get(h)
            if v is not None:
                hdrs[h] = v
        try:
            conn = http.client.HTTPConnection(
                "127.0.0.1", self.server.nanobot_port, timeout=30)
            try:
                conn.request("GET", up_path, headers=hdrs)
                r = conn.getresponse()
                body = r.read()
                status = r.status
                ctype = r.getheader("Content-Type") or "application/json; charset=utf-8"
            finally:
                conn.close()
        except OSError:  # gateway 没起/端口错:502 可辨,进程不挂
            self._json(502, {"error": "nanobot gateway unreachable"})
            return
        self._send(status, ctype, body)  # 状态码原样透传(含 401)

    def _static(self, path: str):
        raw = unquote(path)
        if "\\" in raw or "\x00" in raw:  # ..%5c 等 Windows 分隔符变体直接拒
            self._json(400, {"error": "bad path"})
            return
        rel = raw.lstrip("/") or "index.html"
        dist = self.server.dist  # 已 realpath(make_server 保证)
        target = os.path.realpath(os.path.join(dist, rel))
        if not ds_common.within(dist, target) or not os.path.isfile(target):
            self._json(404, {"error": "not found"})
            return
        ext = os.path.splitext(target)[1].lower()
        ctype = _CTYPES.get(ext, "application/octet-stream")
        # 缓存策略:入口页永远现取,哈希资产长缓存(git pull 后刷新即新版)
        cache = ("no-cache" if os.path.basename(target) == "index.html"
                 else "public, max-age=31536000, immutable")
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:  # git pull 覆盖 dist 的瞬间并发读:同 _todos,500 自愈
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._send(200, ctype, body, {"Cache-Control": cache})


def make_server(ds_root: str, dist: str, host: str = "127.0.0.1",
                port: int = DEFAULT_PORT,
                nanobot_port: int = DEFAULT_NANOBOT_PORT) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)  # allow_reuse_address 已内建
    httpd.ds_root = ds_root
    httpd.dist = os.path.realpath(dist)
    httpd.nanobot_port = nanobot_port  # 代理上游恒 127.0.0.1,仅端口可配
    return httpd


def main() -> int:
    ds_root = os.environ.get("DS_ROOT", DEFAULT_DS_ROOT)
    dist = os.environ.get("DS_WEB_DIST", DEFAULT_DIST)
    port = int(os.environ.get("DS_WEB_PORT", str(DEFAULT_PORT)))
    nanobot_port = int(os.environ.get("DS_NANOBOT_PORT", str(DEFAULT_NANOBOT_PORT)))
    if not os.path.isfile(os.path.join(dist, "index.html")):
        print(f"ds-web: 前端产物缺失 {dist}/index.html —— 先在开发机构建"
              f"(cd web && npm run build)或 git pull 取最新", file=sys.stderr)
        return 2
    try:
        httpd = make_server(ds_root, dist, port=port, nanobot_port=nanobot_port)
    except OSError as e:
        print(f"ds-web: 端口 {port} 起不来({e});被占用请设 DS_WEB_PORT 换端口",
              file=sys.stderr)
        return 2
    print(f"ds-web {VERSION}: http://127.0.0.1:{port}/  (DS_ROOT={ds_root})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
