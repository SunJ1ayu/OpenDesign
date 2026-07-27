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
  POST /api/open-folder            {"key","sub"?} → 本机资源管理器打开项目夹;
    或 {"key","rel"?}(track p3-polish §I4)→ 用系统默认程序打开单个文件。
    这是"只读铁律"的首个受控例外(P5 design §3,用户拍板):不写任何数据,
    sub 分支仅在 key 映射 + sub 白名单 + realpath within + isdir 全过后执行
    OPEN_LAUNCHER;rel 分支仅在 key 映射 + relpath_ok + realpath within +
    扩展名白名单(_OPEN_EXTS)+ isfile 全过后执行;rel/sub 同给 → 400。
    launcher 可注入(测试/e2e 永不真开)。
  POST /api/chat/sessions/<key>/delete  → …/api/sessions/<key>/delete(p7 第二针孔):
    删除历史对话 = 代理 nanobot 原生删除(上游自带"绑定自动化先拒"保护);上游
    不查方法,本服务只以 POST 暴露(GET 面保持纯只读);真正鉴权在上游 Bearer
    token,CT json 闸是 CSRF 纵深。本服务仍零 PKB 写面。
收件箱认领(track opendesign-intake,聊天驱动+面板确认):
  GET /api/intake                  收件箱清单+确定性建议+待确认 plans(只读,
                                   未配置降级 configured:false)
  POST /api/intake/approve         {"plan_id"} 针孔④:卡片「确认执行」= 人工批准
    本体(替代终端 ds-approve,仅限 root 在工作区根内的 intake plan;工作区外
    plan 维持 CLI 批准)→ approve+apply 一气,apply 整体快照复验兜 TOCTOU。
  POST /api/intake/amend           {"plan_id","drop"} 针孔⑧(track opendesign-
    frontend-p1):卡片单条「跳过」纠偏 → ds_intake.amend_plan(剩余行经
    stage_plan 全套复验重新暂存;旧 plan 标 superseded_at,不删文件)。
其余方法/其余 POST 路径一律 405 —— 写操作必须过 ds_tools 核心,本服务不直改 PKB。
项目列表(p7):/api/projects = PKB projects/*.md ∪ 工作区项目夹自动发现
(ds_workspace.project_folders,未被映射/绑定消费的文件夹以 unregistered:true 追加;
只读联合,不自动建档)。
  POST /api/projects/bind          {"project","folder"} 针孔⑨(同上 track):
    项目↔工作区文件夹关联薄壳,直调 ds_tools.bind_project(名字闸/两级匹配/
    原子写全在核心)。
切阶段/参考图标签就地改/变更历史(track opendesign-stage-history,P2 队列 #7#8#9):
  POST /api/projects/stage         {"project","stage"} 针孔⑩:薄壳直调
    ds_tools.set_stage(词表精确匹配/名字闸/锁/页脚 bump 全在核心);GET /api/projects
    顶层加 stages 词表(单一真相源)。
  POST /api/refs/update            {"ref_id","style","space","note"} 针孔⑪:薄壳直调
    ds_refs.update_ref(词表校验/分段重写/锁/页脚 bump 全在核心,只重写头段与备注段,
    来源/文件/用于逐字节不变);GET /api/projects/<key>/refs 加 vocab 词表。
  #9 纯前端:/api/projects/<key>/changes 早就返回 history/note,UI 侧渲染。

约束(design.md D2):只绑 127.0.0.1;端口 DS_WEB_PORT(默认 8766),被占明确报错
退出不静默换口;JSON ensure_ascii=False + charset=utf-8;读期 OSError(Windows
msvcrt 强制锁窗口内并发读会瞬时报错)归入 500 路径,刷新自愈;静态路径
unquote → realpath → ds_common.within 防逃逸。
环境变量:DS_ROOT / DS_WEB_PORT / DS_WEB_DIST(测试注入用)/ DS_NANOBOT_PORT。
"""
import http.client
import base64
import binascii
import hashlib
import json
import os
import re
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import ds_common
import ds_intake    # 收件箱清单/建议(track opendesign-intake)
import ds_model
import ds_organize  # 针孔④ approve+apply 直调核心(锁/复验/审计全在核心)
import ds_refs
import ds_todo
import ds_tools  # parse_history:`## 变更历史` 段读侧解析(与写侧 edit_change 同源)
import ds_workspace

VERSION = "0.51.1"  # Windows 真机修复:workspace.json 原子替换撞上"文件正被读"时重试(否则保存莫名失败)
DEFAULT_NANOBOT_PORT = 8765
# nanobot config 路径(model 回显用):env 可覆盖(测试/非常规安装),默认 ~/.nanobot/config.json
DEFAULT_NANOBOT_CONFIG = os.path.join(os.path.expanduser("~"), ".nanobot", "config.json")


def _ensure_inbox_dir(root_real: str, name: str):
    """在工作区根下建收件箱夹 → ("created"|"already_exists", None) | (None, err)。

    抽成函数是为了让两条**只在竞态之后才看得见**的路径可判据(修复轮,四审 F1/F3):
    - **F1(subdeepseek + subglm 独立提出)**:候选名是 Windows 保留设备名(CON/NUL/
      COM1…)→ 在建之前就拒,给明确的 `bad_inbox_name`。真机上 `mkdir CON` 到底怎么
      失败我在 Linux 上验不了,但"提前拒"与平台无关。复用上传口那道 `_WIN_RESERVED`
      (不动 ds_workspace._SEG_RE:那是全仓共用的枚举闸)。
    - **F3(subdeepseek)**:**连点两次「帮我建收件箱」**。第二个请求在 lexists 之后、
      mkdir 之前被第一个抢先 → FileExistsError。此前一律回 `name_taken`("根目录下有个
      同名文件"),**对用户撒谎**。现在 EEXIST 之后复查一次:真是目录就回 already_exists。
    符号链接始终不跟随:`os.mkdir` 对最终段是链接时抛 EEXIST(不会顺着链接在外面
    建目录,已实测),复查发现是链接 → inbox_outside_root。
    """
    if not ds_workspace._SEG_RE.match(name) or _WIN_RESERVED.match(name):
        return None, "bad_inbox_name"
    target = os.path.join(root_real, name)
    if not ds_common.within(root_real, os.path.realpath(target)):
        return None, "inbox_outside_root"
    # 顺序要紧:islink 必须在 isdir 之前(指向目录的链接 isdir 也为真)。
    # 已经是目录 → already_exists 而不是 name_taken:处理器那边虽然有 _find_inbox
    # 先兜住,但本函数单独也必须诚实(c15/c16 就是分开锁这两种"名字被占")。
    if os.path.islink(target):
        return None, "inbox_outside_root"
    if os.path.isdir(target):
        return "already_exists", None
    if os.path.lexists(target):
        return None, "name_taken"
    try:
        os.mkdir(target)                      # 只一层;父目录 = 工作区根
    except FileExistsError:
        # 竞态输了或名字刚被占:复查一次再判,别把"别人先建好了"说成"被文件占了"
        if os.path.islink(target):
            return None, "inbox_outside_root"
        if os.path.isdir(target):
            return "already_exists", None
        return None, "name_taken"
    return "created", None


def _read_model():
    """当前大脑,解析规则与 nanobot 一致(schema.py:AgentDefaults):modelPreset 设了
    就以它指向的预设为准,悬空/未设才回落 agents.defaults.model —— 只读 model 字段会
    在 preset 布局(install.ps1 合并模板后的真机形态)回显假值(07-13 的雷)。
    只读、每请求现读(零缓存,与 /api/todos 同哲学);任何读取失败 → None,
    健康探针本体不受牵连。解析规则抽到 ds_model(与 set_model.py 同一真相源,L1)。"""
    try:
        cfg = os.environ.get("DS_NANOBOT_CONFIG", DEFAULT_NANOBOT_CONFIG)
        with open(cfg, encoding="utf-8") as fh:
            return ds_model.resolve_model(json.load(fh))
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
# 上传针孔(track opendesign-image-upload)——**本服务第一个"网页给字节、服务端落盘"的口**。
# 信封上限比图片上限宽:base64 膨胀 4/3 + JSON 信封,8MB 图 ≈ 10.7MB 编码后。
UPLOAD_BODY_MAX = 14 * 1024 * 1024   # 请求体上限(Content-Length 闸,读 body 之前判)
UPLOAD_MAX_BYTES = 8 * 1024 * 1024   # 解码后图片字节上限(与 nanobot 单图上限同档)
UPLOAD_NAME_MAX = 80                 # 去扩展名后的名字长度上限(Windows 260 全路径预算)
EDIT_CHANGE_PATH = "/api/changes/edit"  # do_POST 写针孔③(track opendesign-todo-edit),精确匹配
INTAKE_APPROVE_PATH = "/api/intake/approve"  # do_POST 针孔④(track opendesign-intake),精确匹配
ADD_CHANGE_PATH = "/api/changes/add"  # do_POST 写针孔⑤(track opendesign-clickable-actions),精确匹配
CREATE_PROJECT_PATH = "/api/projects/create"  # do_POST 写针孔⑥(同上 track),精确匹配
INTAKE_SCAN_PATH = "/api/intake/scan"  # do_POST 写针孔⑦(track opendesign-inbox-scan),精确匹配
INTAKE_AMEND_PATH = "/api/intake/amend"  # do_POST 写针孔⑧(track opendesign-frontend-p1),精确匹配
UPLOAD_PATH = "/api/upload"  # do_POST 写针孔⑬(track opendesign-image-upload),精确匹配
INBOX_CREATE_PATH = "/api/inbox/create"  # do_POST 写针孔⑭(track opendesign-chat-image),精确匹配
BIND_PROJECT_PATH = "/api/projects/bind"  # do_POST 写针孔⑨(同上 track),精确匹配
FOLDER_VISIBILITY_PATH = "/api/workspace/folder-visibility"  # 阶段二:整份存结构目录声明
STAGE_PATH = "/api/projects/stage"  # do_POST 写针孔⑩(track opendesign-stage-history §7),精确匹配
REFS_UPDATE_PATH = "/api/refs/update"  # do_POST 写针孔⑪(同上 track §8),精确匹配
DUE_DATE_PATH = "/api/changes/due"  # do_POST 写针孔⑫(track opendesign-todo-duedate),精确匹配
_INTAKE_ALLOWED_KEYS = {"plan_id"}
_INTAKE_AMEND_ALLOWED_KEYS = {"plan_id", "drop"}
# 收件箱确认的错误→HTTP 映射:格式/参数错 400,不存在 404,越界 403,状态冲突 409
_INTAKE_ERR_STATUS = {
    "bad_plan_id": 400, "plan_not_found": 404, "not_intake_plan": 403,
    "already_applied": 409, "not_approved": 409, "root_not_allowed": 403,
    "plan_drift": 409, "would_overwrite": 409, "src_missing": 409,
    "conflict": 409, "path_escape": 403, "dst_parent_not_dir": 409,
    "apply_failed": 500,
    # amend_plan 专属(track opendesign-frontend-p1):废案二次纠偏 409 /
    # drop 参数闸 400 / 畸形 plan(手工改坏)400 / 剩余行 stage 复验拒绝
    # (理论上不会撞,防御性兜底)400
    "plan_superseded": 409, "bad_drop": 400, "bad_plan": 400, "empty_plan": 400,
}
# bind_project 错误→HTTP 映射(track opendesign-frontend-p1):校验/资源类 404,
# 状态冲突 409;folder_not_found/folder_ambiguous 时核心回传的 folders 候选
# 名单原样透传(前端提示用)。
_BIND_ALLOWED_KEYS = {"project", "folder"}
_FOLDER_VISIBILITY_ALLOWED_KEYS = {"review_id", "hidden"}
# 体检卡写口是「一次存整份清单」(A2),请求体与**已声明目录数**线性相关 ——
# 不能复用 OPEN_BODY_MAX(那是给 open-folder 的两个短字段定的 4096:中文长目录名
# 约 34 字节,120 个就爆,用户从此存不进去)。两条闸各管一件事:
#   数量闸  —— 显式封顶,与名字长度无关(design.md:39 明写的两条之一)
#   请求体闸 —— 500 个名字即使全是长中文名也放得下,再大就是异常流量
_FOLDER_VISIBILITY_MAX_NAMES = 500
_FOLDER_VISIBILITY_BODY_MAX = 64 * 1024
_BIND_ERR_STATUS = {
    "bad_name": 400, "project_not_found": 404,
    "workspace_not_configured": 409, "folder_not_found": 404,
    "folder_ambiguous": 409,
}
# body 键白名单(空 body {} 针孔:白名单=空集,任何键即拒)
_SCAN_ALLOWED_KEYS = frozenset()
# stage_inbox_auto 错误→HTTP 映射:配置/规则表坏或收件箱不可读 409,不存在 404,其余 400
_SCAN_ERR_STATUS = {
    "workspace_not_configured": 409, "inbox_not_found": 404,
    "taxonomy_bad": 409, "inbox_unreadable": 409,
    # stage_inbox_auto 内部会调 stage_intake,其错误码沿用 intake 映射(subglm 四审 LOW:
    # 否则 bad_assignment/conflict/path_escape 等会降级成默认 400)
    "bad_assignment": 400, "bad_name": 400, "unknown_category": 400,
    "project_required": 400, "project_not_found": 404, "empty_plan": 400,
    "file_not_in_inbox": 409, "conflict": 409, "path_escape": 403,
    "would_overwrite": 409, "dst_parent_not_dir": 409,
}
# body 键白名单(多余键即拒:防夹带 ds_root/today 等内部参数走私)
_EDIT_ALLOWED_KEYS = {"project", "cnum", "new_status", "new_text", "note"}
# edit_change error code → HTTP status(校验类 400,资源类 404,重复 409;名字/逃逸闸不回显细节)
_EDIT_ERR_STATUS = {
    "invalid_status": 400, "empty_text": 400,
    "change_not_found": 404, "project_not_found": 404, "ambiguous_change": 409,
    "bad_name": 404, "path_escape": 404,
}
# body 键白名单(同上例:多余键即拒)
_ADD_ALLOWED_KEYS = {"project", "content", "space"}
# append_change error code → HTTP status(校验类 400,资源类 404,段缺失 409)
_ADD_ERR_STATUS = {
    "empty_content": 400, "project_not_found": 404, "no_change_section": 409,
    "bad_name": 404, "path_escape": 404,
}
_CREATE_ALLOWED_KEYS = {"project", "client", "stage", "address"}
_UPLOAD_ALLOWED_KEYS = {"name", "data_url"}
# 扩展名 → 允许的 data URL mime(防"名叫 .png、内容声明成别的")。
# 扩展名白名单**取 ds_workspace.IMG_EXTS**(与图墙读出面同源),不从 taxonomy 推导
# —— taxonomy.json 是用户可改的数据配置,推导等于让它变成安全配置。
_UPLOAD_MIME_BY_EXT = {
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
}
# Windows 保留设备名:写过去不是文件而是设备 → 表现为"上传成功但文件不见了"。
# 不改 ds_workspace._SEG_RE(那是全仓共用的枚举闸),只在上传口加这一道。
_WIN_RESERVED = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)", re.IGNORECASE)
_DATA_URL_HEAD = re.compile(r"^data:([\w.+-]+/[\w.+-]+);base64,", re.ASCII)
# create_project error code → HTTP status(校验类 400,重复 409)
_CREATE_ERR_STATUS = {
    "empty_name": 400, "bad_stage": 400, "project_exists": 409,
    "bad_name": 404, "path_escape": 404,
}
# body 键白名单(写针孔⑩:多余键即拒,防夹带 ds_root/today 走私)
_STAGE_ALLOWED_KEYS = {"project", "stage"}
# set_stage error code → HTTP status(词表外 400,项目/名字/逃逸类 404)
_STAGE_ERR_STATUS = {
    "bad_stage": 400, "project_not_found": 404,
    "bad_name": 404, "path_escape": 404,
}
# body 键白名单(写针孔⑪:多余键即拒,防夹带 ds_root/today/file/source/used 走私)
_REFS_UPDATE_ALLOWED_KEYS = {"ref_id", "style", "space", "note"}
# update_ref error code → HTTP status(校验类 400,资源不存在 404,状态冲突 409)
_REFS_UPDATE_ERR_STATUS = {
    "no_fields": 400, "style_unknown": 400, "space_unknown": 400,
    "ref_not_found": 404, "ambiguous_ref": 409, "malformed_entry": 409,
}
# body 键白名单(写针孔⑫:多余键即拒,防夹带 ds_root/today 走私)
_DUE_ALLOWED_KEYS = {"project", "cnum", "due"}
# set_due_date error code → HTTP status(格式/日期非法 400,项目/变更不存在 404,歧义 409)
_DUE_ERR_STATUS = {
    "invalid_due": 400, "change_not_found": 404, "project_not_found": 404,
    "ambiguous_change": 409, "bad_name": 404, "path_escape": 404,
}


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
    os.startfile(path)  # noqa: S606 —— 目录路径已过 realpath within 闸
    if os.path.isdir(path):
        _WIN_FOCUS(path)


def _safe_upload_name(name: str) -> str | None:
    """上传文件名闸(纯函数,便于表驱动 oracle)。放行 → 返回**真正要落盘的名字**
    (可能被截短);拒绝 → None。

    设计要点(每条都有来由,别随手放宽):
    - 先 `basename` 剥目录成分,再过 `ds_workspace.PROJECT_NAME_RE`(= 全仓单段名闸)。
      **复用而不是自研黑名单**:收件箱列举(ds_intake)、指派校验、图墙扫描都用它过滤,
      不复用就会造出"落盘成功但整条链路看不见"的黑洞(`%` 就是这么漏的)。
    - 额外四条(上传口专有,不动共用闸):
      `:` = NTFS 备用数据流面(`evil.exe:x.png` 过扩展名闸却造出 evil.exe);
      `.` 开头 = 收件箱列举会跳过(同样看不见);
      尾部 `.`/空格 = Windows 静默剥掉 → 名字对不上;
      保留设备名 = 写到设备而不是文件。
    - 扩展名必须在 `ds_workspace.IMG_EXTS`(png/jpg/jpeg/webp/gif;**svg 排除**)。
    - 超长**截短而不是拒**:不截的话炸点在 apply_plan 移动那一步,用户看到的是
      "确认执行失败"而不是"名字太长"。
    """
    if not isinstance(name, str):
        return None
    # **不做 basename 改写**:带目录成分的名字直接拒。悄悄把 `../evil.png` 改写成
    # `evil.png` 会把"对方想干什么"这条信息抹掉;PROJECT_NAME_RE 本就禁 / 与 \,
    # 这里只负责不给它"被洗白"的机会。同理不 strip:尾空格要拒,不是要修。
    if not name or name in (".", ".."):
        return None
    if name.startswith("."):
        return None
    if name != name.rstrip(". "):          # 尾点/尾空格
        return None
    if ":" in name:
        return None
    if not ds_workspace.PROJECT_NAME_RE.match(name):
        return None
    if _WIN_RESERVED.match(name):
        return None
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in ds_workspace.IMG_EXTS or not stem:
        return None
    if len(stem) > UPLOAD_NAME_MAX:
        stem = stem[:UPLOAD_NAME_MAX].rstrip(". ")
        if not stem:
            return None
    return stem + ext


def _decode_upload_data_url(data_url: str, ext: str) -> bytes | None:
    """data URL → 字节。mime 必须与扩展名同族,base64 严格解码,超限即拒。"""
    if not isinstance(data_url, str):
        return None
    m = _DATA_URL_HEAD.match(data_url)
    if not m:
        return None
    if m.group(1).lower() not in _UPLOAD_MIME_BY_EXT.get(ext, set()):
        return None
    b64 = data_url[m.end():]
    # 先按编码长度粗筛(4/3 膨胀),避免为超大串真去解码
    if len(b64) > UPLOAD_MAX_BYTES // 3 * 4 + 8:
        return None
    try:
        blob = base64.b64decode(b64, validate=True)
    except (ValueError, binascii.Error):
        return None
    if not blob or len(blob) > UPLOAD_MAX_BYTES:
        return None
    return blob


def _default_open_launcher(path: str):
    """本机打开文件夹。Windows=资源管理器(+尽力提到前台);其余平台 xdg-open(列表参数无 shell)。
    DS_OPEN_CMD 覆盖启动命令(e2e 在无桌面 Linux 上注入记录脚本),同样列表参数。"""
    cmd = os.environ.get("DS_OPEN_CMD")
    if cmd:
        import subprocess
        subprocess.Popen([cmd, path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    elif os.name == "nt":
        _open_windows(path)
    else:
        import subprocess
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


OPEN_LAUNCHER = _default_open_launcher  # 模块级可注入(测试/e2e 用 fake)

# 已交付 = 阶段词表(workspace/AGENTS.md)的收尾两档;仅用于侧栏淡化,读侧启发式。
# 阶段词表如扩展,这里同步。accepted deviation:词表本身不在本 track 定义。
DELIVERED_STAGES = ("竣工验收", "售后")

# 项目 key 字符集白名单 = ds_workspace.PROJECT_NAME_RE(单一真相源:p7 起文件夹名
# 就是路由 key,"能列出"与"能寻址"必须同集合)。不含 / \ ⇒ 无路径分隔符;
# `.`/`..` 与含 `..` 者 _valid_proj_key 显式拒(纵深防御,realpath+within 才是权威闸)。
_PROJ_KEY_RE = ds_workspace.PROJECT_NAME_RE
# 相对路径闸(Gate A)= ds_workspace.relpath_ok:逐段过单段黑名单(禁 / \ % 控制符、
# 非 ./..),允许 / 连接子目录。单一真相源(M2,07-13 盲评 + 07-14 v2 黑名单化):枚举侧
# (ds_workspace._SEG_RE)列得出的每段,服务侧必认得,否则列出即 404 裂图。逃逸权威闸=
# realpath+within(Gate B);此处 .. 段亦被 relpath_ok 提前拒(纵深防御)。

# 图片扩展名白名单(Gate C)—— 唯一允许读出的类型;svg 排除(直开可执行脚本)。
_IMG_CTYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}

# open-folder rel 分支的「开文件」扩展名白名单(Gate C,track p3-polish §I4)——
# 设计师会双击的文档/图纸/图片类型,**无任何可执行/脚本/快捷方式**(design.md §I4,
# 与 web/src/workspace/projectName.ts 的 OPEN_FILE_EXTS 同集合,前后端各自维护同一份
# 常量;修改任一份必须同步另一份,否则前端分流与后端安全闸会漂移)。
_OPEN_EXTS = {
    ".dwg", ".dxf", ".skp", ".3ds", ".max", ".rvt", ".obj", ".fbx", ".stl",
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf",
}


def _servable_ref_file(file: str) -> bool:
    """索引行的 file 字段是否 refs/ 下且能过 _refs_file Gate A(M2:列出=可服务)。"""
    if not isinstance(file, str) or not file.startswith("refs/"):
        return False
    return ds_workspace.relpath_ok(file[len("refs/"):])


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


def _workspace_config_bytes(ds_root: str) -> bytes:
    """workspace.json 原文字节;缺失/不可读按空串进 reviewId。"""
    try:
        with open(os.path.join(ds_root, ds_workspace.CONFIG_REL), "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _workspace_top_dirs(root: str) -> list[str]:
    """工作区根下可由网页声明的一层目录名:非点号、非符号链接、过单段名闸。

    **刻意复用 `ds_workspace._dir_entries`(项目列表用的同一个函数)**:体检卡的
    下发集合与项目列表必须同源,否则漏算一个目录 = 用户的真项目从列表里永久消失,
    而接口层测试会全绿。改 `_dir_entries` 的语义时,这里是第二个调用方。
    """
    return [name for name, _ent in ds_workspace._dir_entries(root)]


def _workspace_review_id(config_bytes: bytes, top_dirs: list[str]) -> str:
    """reviewId 绑定配置原文 + 根目录一层快照;任一侧变化都会过期。"""
    payload = {
        "config": hashlib.sha256(config_bytes).hexdigest(),
        "topDirs": sorted(top_dirs),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _workspace_health_state(ds_root: str) -> dict:
    """GET /api/workspace/health 的领域数据;不写盘、不自动修配置。"""
    config_bytes = _workspace_config_bytes(ds_root)
    cfg = ds_workspace.load_config(ds_root)
    if cfg is None:
        return {
            "configured": False,
            "applicable": False,
            "folders": [],
            "projectCount": 0,
            "reviewId": _workspace_review_id(config_bytes, []),
        }
    proot = ds_workspace.projects_root(cfg)
    root_real = os.path.realpath(cfg["root"])
    projects_real = os.path.realpath(proot) if proot else ""
    applicable = bool(projects_real and root_real == projects_real)
    top_dirs = _workspace_top_dirs(root_real) if applicable else []
    declared = isinstance(cfg.get("structuralDirs"), list)
    declared_names = set(cfg.get("structuralDirs") or []) if declared else set()
    guessed_names = set()
    if applicable and not declared:
        guessed_names = ds_workspace.structural_dirs(
            cfg, ds_intake.load_taxonomy(ds_root) or {})
    current = set(top_dirs)
    folders = []
    if applicable:
        for name in sorted(current | declared_names):
            if name in declared_names:
                reason = "declared"
            elif name in guessed_names:
                reason = "guessed"
            else:
                reason = "default"
            folders.append({
                "name": name,
                "reason": reason,
                "currentlyHidden": reason in ("declared", "guessed"),
                "preselect": reason == "declared",
                "missing": name not in current,
            })
    return {
        "configured": True,
        "applicable": applicable,
        "declared": declared,
        "root": root_real,
        "projectsRoot": projects_real,
        "projectCount": len(ds_workspace.project_folders(cfg)),
        "folders": folders,
        "reviewId": _workspace_review_id(config_bytes, top_dirs),
    }
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
        # 浏览器别自作主张嗅探类型:声明 image/png 就当图,不会被当 HTML 跑。
        # (上传口开放后,盘上可能出现"名叫 .png、内容不是图"的文件;读出面按扩展名
        #  发类型,加这一行把嗅探那半条路也焊死。)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    # 连接级超时(track opendesign-image-upload):上传口的体积上限抬到 14MB 后,
    # "Content-Length 说 14MB 却只发 1 字节"的连接会把一个工作线程挂死。
    timeout = 30

    def log_message(self, fmt, *args):  # 请求日志走 stdout(design D2 运维面)
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _host_ok(self) -> bool:
        """H2(07-13 盲评):Host 白名单,拒 DNS rebinding。

        rebinding 下 TCP 连的是 127.0.0.1 但浏览器带的 Host 是恶意域名——绑 loopback
        与 CORS 都不挡它,Host 头是唯一可辨信号。只认本机形态(带不带端口都认:
        非标准端口浏览器必带,留裸形态兜 80 端口边缘);比较不区分大小写。
        """
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}",
                        "127.0.0.1", "localhost", "[::1]"}

    # ---- routes ----
    def do_GET(self):
        if not self._host_ok():
            self._json(403, {"error": "bad host"})
            return
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
        elif path == "/api/intake":
            self._intake()
        elif path == "/api/projects":
            self._projects()
        elif path == "/api/workspace/health":
            self._workspace_health()
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
        if not self._host_ok():  # H2:针孔与 405 之前先验 Host(同 do_GET)
            self._json(403, {"error": "bad host"})
            return
        # 只读铁律的受控针孔白名单(精确匹配,其余 POST 维持 405,oracle 锁死):
        # ① open-folder(P5)② 会话删除代理(p7,真正鉴权在上游 Bearer token)
        path = urlsplit(self.path).path
        if path == OPEN_FOLDER_PATH:
            self._open_folder()
        elif path == EDIT_CHANGE_PATH:
            self._edit_change()
        elif path == INTAKE_APPROVE_PATH:
            self._intake_approve()
        elif path == ADD_CHANGE_PATH:
            self._add_change()
        elif path == CREATE_PROJECT_PATH:
            self._create_project()
        elif path == INTAKE_SCAN_PATH:
            self._intake_scan()
        elif path == INTAKE_AMEND_PATH:
            self._intake_amend()
        elif path == UPLOAD_PATH:
            self._upload()
        elif path == INBOX_CREATE_PATH:
            self._inbox_create()
        elif path == BIND_PROJECT_PATH:
            self._bind_project()
        elif path == FOLDER_VISIBILITY_PATH:
            self._folder_visibility()
        elif path == STAGE_PATH:
            self._set_stage()
        elif path == REFS_UPDATE_PATH:
            self._refs_update()
        elif path == DUE_DATE_PATH:
            self._set_due_date()
        elif (m := _SESSION_DELETE_RE.match(path)):
            self._delete_session(m.group(1))
        else:
            self._method_not_allowed()

    do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    def _todos(self):
        try:
            data = ds_todo.collect(self.server.ds_root)
        except Exception:
            # M1 后:坏编码文件(F2)/读期 OSError(F3,Windows 写锁窗口)已在 collect
            # 内逐文件隔离进 errors 字段;这层降为兜底(projects 目录本身不可列等意外),
            # 仍 500 但不再被单个坏文件触发。trace 进日志不进响应体。
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
                try:  # M1:坏编码/读失败的单个文件跳过,不 500 整个列表
                    with open(target, encoding="utf-8") as fh:
                        text = fh.read()
                except (OSError, UnicodeDecodeError):
                    continue
                stage = _field(text, "阶段")
                dates = ds_common.LASTUPD_DATE_RE.findall(text)
                # cockpit 速览:业主剥 [[ ]](链接语法是档案内部事,不外泄给 UI)
                owner = _field(text, "业主")
                if owner.startswith("[[") and owner.endswith("]]"):
                    owner = owner[2:-2]
                projects.append({
                    "key": key,
                    "name": _title(text) or key,
                    "stage": stage,
                    "owner": owner,
                    "status_note": _field(text, "当前状态"),
                    "open_count": counts.get(key, 0),
                    "delivered": stage in DELIVERED_STAGES,
                    "last_update": dates[-1] if dates else None,
                    "unregistered": False,
                    "group": "",
                })
            # p7 design D2:联合工作区自动发现的项目夹(只读,不建档)。
            # 消费集合按 realpath 比对(不按 basename):显式映射目标 ∪ 各 PKB
            # key 的三级绑定解析结果;没被消费的文件夹以 unregistered 追加,
            # key=文件夹名 → 文件区/图墙/open-folder 经 project_dir ②直等可用。
            cfg = ds_workspace.load_config(root)
            folders = ds_workspace.project_folders(cfg)
            if folders:
                # depth2 track:projectsDepth=2 时 key=`分组:项目名`,拆出
                # group 供前端标签、name 只留纯项目名;depth=1 恒 group=""
                grouped = cfg.get("projectsDepth", 1) == 2
                # cockpit(偿 depth2 deviation):文件夹 realpath → 分组名反查表,
                # 已建档条目经三级绑定命中的夹子也带上 group 标签
                path_group = {fp: n.split(":", 1)[0]
                              for n, fp in folders if grouped and ":" in n}
                consumed = set()
                for p in projects:
                    pd = ds_workspace.project_dir(cfg, p["key"])
                    if pd:
                        consumed.add(pd)
                        g = path_group.get(pd)
                        if g:
                            p["group"] = g
                for rel in cfg["projects"].values():
                    if rel:
                        consumed.add(os.path.realpath(os.path.join(cfg["root"], rel)))
                for name, fpath in folders:
                    if fpath in consumed:
                        continue
                    group = ""
                    disp = name
                    if grouped and ":" in name:
                        group, disp = name.split(":", 1)
                    projects.append({
                        "key": name, "name": disp, "stage": "",
                        "open_count": 0, "delivered": False,
                        "last_update": None, "unregistered": True,
                        "group": group,
                    })
        except Exception:
            traceback.print_exc()  # 坏编码/写锁窗口读期 OSError:500 自愈,trace 进日志
            self._json(500, {"error": "internal"})
            return
        # 阶段词表(track opendesign-stage-history §7):单一真相源 = ds_tools.PROJECT_STAGES,
        # 前端 stage-chip 下拉不许硬编码副本;写口不回显词表(少一条外泄面)。
        # excludedStructural:**被"猜"排掉的目录名**,让前端能说一句"这几个当结构目录了"
        # —— 静默排除正是"用户觉得项目不见了"的成因(-p2 四审)。
        try:
            excluded = ds_workspace.excluded_structural(
                ds_workspace.load_config(self.server.ds_root))
        except Exception:
            excluded = []
        self._json(200, {"projects": projects, "stages": list(ds_tools.PROJECT_STAGES),
                         "excludedStructural": excluded})

    def _workspace_health(self):
        """GET /api/workspace/health:工作区体检卡当前事实 + 本轮 reviewId。

        **刻意不拿锁**(主 agent 仲裁,panel 四审 subdeepseek 提出锁范围过大):
        ① 读不到半截文件已由写侧的原子替换保证(阶段一 `_write_workspace_json`
           唯一 tmp 名 + `os.replace`),锁在这里不再买到防撕裂;
        ② 「配置字节与目录快照同一瞬间」本来就不成立 —— 目录不受这把锁保护;
           真正的保证是写口在锁内**复核 reviewId**,快照过期就 409。
        ③ 而代价在 Windows 上是实的:`ds_lock` 是重试式锁,约 10 次重试后
           **抛 OSError 而非排队**(阶段一四审记录),读口持锁跑一遍目录扫描 +
           taxonomy 读取,会实打实抬高并发保存直接失败的概率。真机就是 Windows。
        """
        try:
            data = _workspace_health_state(self.server.ds_root)
            self._json(200, data)
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})

    def _changes(self, key: str):
        target = self._project_file(key)
        if target is None:
            self._json(404, {"error": "not found"})  # 不回显 key/路径
            return
        try:
            with open(target, encoding="utf-8") as fh:
                text = fh.read()
            hist = ds_tools.parse_history(text)  # {cnum: {note, history[]}},按 cnum 分桶
            changes = []
            for ln in text.split("\n"):
                c = ds_todo.parse_change(ln)  # 四状态全量,单一真相源
                if c is None:
                    continue
                h = hist.get(c["cnum"]) if c["cnum"] is not None else None
                item = {
                    "cnum": c["cnum"], "status": c["status"],
                    "text": c["text"], "date": c["date"],
                    # space = 变更行可选【空间】前缀(p4 T1,parse 单一真相源);
                    # source 仍无字段 → 恒 None(读侧宽容,accepted deviation)
                    "space": c["space"], "source": None,
                    "due": c["due"],  # 截止日(track opendesign-todo-duedate,读侧宽容,旧行=None)
                    "history": h["history"] if h else [],  # 留痕(时序),无则空列表
                }
                if h and h["note"] is not None:
                    item["note"] = h["note"]  # 备注可选:有才带该键
                changes.append(item)
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
        # 只回 UI 需要的字段(id/style/space/file/note),source/used 不外泄。
        # M2 不变量:列出=可服务——file 必须是 refs/ 下、剩余段过 Gate A 的路径,
        # 否则前端渲染即裂图(索引里手写了服务端认不出的字符)。跳过不列。
        out = [{"id": r["id"], "style": r["style"], "space": r["space"],
                "file": r["file"], "note": r["note"]}
               for r in refs if _servable_ref_file(r["file"])]
        # 词表(track opendesign-stage-history §8):单一真相源 = ds_refs._load_styles /
        # ds_refs.SPACES,前端 lightbox 编辑区不许硬编码副本。
        vocab = {"style": ds_refs._load_styles(self.server.ds_root),
                 "space": list(ds_refs.SPACES)}
        self._json(200, {"key": key, "refs": out, "vocab": vocab})

    def _refs_file(self, rel: str):
        """参考图静态服务 —— 本 track 唯一新增文件读出面。三闸串联,每闸独立可验红:
        Gate A 段黑名单 → Gate B realpath 前缀(逃逸/symlink 权威闸)→ Gate C 扩展白名单。
        404 一律不回显路径;Content-Type 按扩展映射;禁目录列表(只 isfile)。"""
        # Gate A —— relpath_ok:拒 % 残留 / 控制字符 / 反斜杠 / 空段 / . .. 段
        if not ds_workspace.relpath_ok(rel):
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
        """(状态, 项目夹, 扫描深度) —— 状态 ∈ badkey/unconfigured/unmapped/ok。
        配置每请求现读(零缓存,与 /api/todos 同哲学,改 json 即生效)。"""
        if not _valid_proj_key(key):
            return "badkey", None, ds_workspace.DEFAULT_MAX_DEPTH
        cfg = ds_workspace.load_config(self.server.ds_root)
        if cfg is None:
            return "unconfigured", None, ds_workspace.DEFAULT_MAX_DEPTH
        pd = ds_workspace.project_dir(cfg, key)
        if pd is None:
            return "unmapped", None, cfg["galleryDepth"]
        return "ok", pd, cfg["galleryDepth"]

    def _files_meta(self, key: str, kind: str):
        """overview / images 共用外壳:降级态诚实回 JSON,不 404 糊弄前端。"""
        status, pd, depth = self._ws_proj(key)
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
                data = ds_workspace.overview(pd, max_depth=depth)
            else:
                data = {"images": ds_workspace.images(pd, max_depth=depth)}
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})
            return
        self._json(200, {"configured": True, "mapped": True, **data})

    def _files_file(self, key: str, rel: str):
        """项目图片静态服务。三闸同 _refs_file 先例(Gate A relpath_ok → Gate B realpath
        within(项目夹) → Gate C 图片扩展白名单),外加 key 必须已映射;404 不回显路径。"""
        status, pd, depth = self._ws_proj(key)
        if status != "ok" or not ds_workspace.relpath_ok(rel):
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
        """唯一非 GET 端点(P5 design §3;track p3-polish §I4 拓宽为可选 rel)。
        闸序:body 尺寸/JSON → key 白名单+映射(_ws_proj)→ 分流:
          - 无 rel(老行为,不回归):sub 单段白名单+realpath within+isdir
            (ds_workspace.resolve_sub)
          - 有 rel(新增,开单个文件):Gate A ds_workspace.relpath_ok(rel) →
            Gate B realpath+ds_common.within(项目夹)→ Gate D os.path.isfile
            (目录/不存在 → 404,开目录走 sub 不走 rel)→ Gate C 扩展名 ∈
            _OPEN_EXTS 白名单(只有真文件才谈得上"扩展名被拒" 415)
        rel 与 sub 同给(body 同时含两个键)→ 400,不猜意图。
        全过才调 OPEN_LAUNCHER;任何拒绝路径零执行(oracle 断言)。
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
        if not isinstance(body, dict):
            self._json(400, {"error": "bad request"})
            return
        # inbox 分支(track opendesign-chat-image-p2 D2):「打开收件箱」。
        # **路径由服务端 _find_inbox 解析,调用方给不了路径** —— 否则这条口就成了
        # "网页能让 Windows 打开任意目录"。与 key/sub/rel 互斥,同给即 400(不猜意图)。
        if "inbox" in body:
            if body.get("inbox") is not True or set(body) != {"inbox"}:
                self._json(400, {"error": "bad request"})
                return
            cfg = ds_workspace.load_config(self.server.ds_root)
            if not cfg or not cfg.get("root"):
                self._json(404, {"error": "not found"})
                return
            taxonomy = ds_intake.load_taxonomy(self.server.ds_root)
            found = ds_intake._find_inbox(cfg, taxonomy) if taxonomy else None
            if not found:
                self._json(404, {"error": "not found"})
                return
            try:
                OPEN_LAUNCHER(found[1])
            except OSError:
                traceback.print_exc()
                self._json(500, {"error": "internal"})
                return
            self._json(200, {"ok": True})
            return
        key = body.get("key")
        if not isinstance(key, str) or not key:
            self._json(400, {"error": "bad request"})
            return
        status, pd, depth = self._ws_proj(key)
        if status != "ok":
            self._json(404, {"error": "not found"})
            return
        has_rel = "rel" in body
        has_sub = "sub" in body
        if has_rel and has_sub:
            self._json(400, {"error": "bad request"})
            return
        if has_rel:
            rel = body.get("rel")
            if not isinstance(rel, str) or not rel:
                self._json(400, {"error": "bad request"})
                return
            if not ds_workspace.relpath_ok(rel):
                self._json(404, {"error": "not found"})
                return
            target = os.path.realpath(os.path.join(pd, rel))
            if not ds_common.within(pd, target):
                self._json(404, {"error": "not found"})
                return
            # isfile 先于扩展名闸:目录/不存在一律 404(开目录走 sub,不走 rel),
            # 只有真文件才谈得上"扩展名被拒"(415)。
            if not os.path.isfile(target):
                self._json(404, {"error": "not found"})
                return
            if os.path.splitext(target)[1].lower() not in _OPEN_EXTS:
                self._json(415, {"error": "ext_not_allowed"})
                return
        else:
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
        blocked_by_automations 原样透传给前端提示。查询串按 _proxy 契约原样
        透传——已鉴权的机主显式带 ?delete_automations=1 属上游本就给他的能力,
        不是越权面;OpenDesign 前端不带此参数。"""
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

    def _intake(self):
        """GET /api/intake(只读):收件箱清单+确定性建议 + 待确认 plans。
        未配置工作区/坏规则表/没有收件箱夹 → 200 + configured:false(+reason),
        卡片按提示态渲染,不 404(files/overview 同款降级哲学)。
        pending 只列「root 落在工作区根内且未 applied」的 plan —— 桌面清理等
        工作区外 plan 不进收件箱卡片(那些走 ds-approve CLI)。"""
        try:
            r = ds_intake.list_inbox(self.server.ds_root)
            cfg = ds_workspace.load_config(self.server.ds_root)
            if not r.get("ok"):
                out = {"configured": False, "reason": r.get("error", "unknown"),
                       "entries": [], "pending": []}
                # 没有收件箱夹 → 顺带回**将要建在哪**,「帮我建收件箱」按钮才能在
                # 点之前就把路径写在提示里(用户按下去之前就知道会发生什么)。
                if out["reason"] == "inbox_not_found" and cfg and cfg.get("root"):
                    tax = ds_intake.load_taxonomy(self.server.ds_root)
                    cands = (tax or {}).get("inboxDirs") or []
                    if cands and ds_workspace._SEG_RE.match(cands[0]):
                        out["wouldCreate"] = os.path.join(
                            os.path.realpath(cfg["root"]), cands[0])
                self._json(200, out)
                return
            # `path` = 收件箱绝对路径,只给网页显示(用户原话「收件箱是在我电脑哪个
            # 文件夹」)。**刻意只在这一层拼**:ds_intake.list_inbox 同时是 MCP 工具
            # (list_inbox_tool),往它的返回里塞绝对路径 = 把本机路径喂给 LLM 并上云,
            # 无谓拓宽模型能看到的内容(ds_tools.py 的铁律)。网页要显示 ≠ 模型要知道。
            self._json(200, {"configured": True, "inbox": r["inbox"],
                             "path": os.path.join(
                                 os.path.realpath(cfg["root"]), r["inbox"])
                             if cfg and cfg.get("root") else None,
                             "entries": r["entries"],
                             "truncated": r["truncated"],
                             "pending": self._pending_plans(cfg)})
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})

    def _pending_plans(self, cfg):
        """organize/plans/ 里未 applied 且 root 在工作区根内的 plan,按 created 序。
        单个坏 plan 文件跳过不拖死清单(只读视图宁缺勿炸)。"""
        out = []
        plans_dir = os.path.join(self.server.ds_root, "organize", "plans")
        try:
            names = sorted(os.listdir(plans_dir))
        except OSError:
            return out
        for name in names:
            if not (name.startswith("plan_") and name.endswith(".json")):
                continue
            try:
                with open(os.path.join(plans_dir, name), encoding="utf-8") as fh:
                    plan = json.load(fh)
                if plan.get("applied_at") or plan.get("superseded_at"):
                    continue
                # root 缺失/非串直接跳过:realpath("") 会解析成本进程 cwd,
                # 万一 cwd 落在工作区内,坏 plan 就被误判成 intake plan
                proot = plan.get("root")
                if not isinstance(proot, str) or not proot:
                    continue
                if cfg is None or not ds_common.within(
                        cfg["root"], os.path.realpath(proot)):
                    continue
                out.append({"plan_id": plan["plan_id"],
                            "created": plan.get("created"),
                            "ops": [{"op": op["op"], "src_rel": op["src_rel"],
                                     "dst_rel": op["dst_rel"]}
                                    for op in plan.get("operations", [])]})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return out

    def _intake_approve(self):
        """POST 针孔④(track opendesign-intake design D1):收件箱卡片「确认执行」。
        浏览器里人点按钮 = 人工确认本体,替代终端 ds-approve —— 仅限工作区内的
        intake plan(工作区外的 plan 维持 CLI 批准,面越窄越好)。posture 逐条同
        edit-change:CT json → body 上限 → 键白名单 → plan_id 格式闸 →
        plan root 必须落工作区根内 → approve_plan + apply_plan(allowed_roots=
        [工作区根],apply 的整体快照复验兜 TOCTOU,audit 照记)。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _INTAKE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})
            return
        plan_id = body.get("plan_id")
        if not ds_organize.is_valid_plan_id(plan_id):
            self._json(400, {"error": "bad_plan_id"})
            return
        try:
            cfg = ds_workspace.load_config(self.server.ds_root)
            if cfg is None:
                self._json(403, {"error": "not_intake_plan"})
                return
            plan_path = os.path.join(self.server.ds_root, "organize", "plans",
                                     f"plan_{plan_id}.json")
            if not os.path.exists(plan_path):
                self._json(404, {"error": "plan_not_found"})
                return
            with open(plan_path, encoding="utf-8") as fh:
                plan = json.load(fh)
            # root 缺失守卫与 _pending_plans 对称(GLM panel 抓的不对称):
            # realpath("") = 本进程 cwd,坏 plan 不能靠 cwd 落点混进工作区判定
            proot = plan.get("root")
            if (not isinstance(proot, str) or not proot
                    or not ds_common.within(cfg["root"], os.path.realpath(proot))):
                self._json(403, {"error": "not_intake_plan"})
                return
            if plan.get("applied_at"):
                self._json(409, {"error": "already_applied"})
                return
            r = ds_organize.approve_plan(plan_id, ds_root=self.server.ds_root)
            if not r.get("ok"):
                err = r.get("error", "internal")
                self._json(_INTAKE_ERR_STATUS.get(err, 400), {"error": err})
                return
            r = ds_organize.apply_plan(plan_id, [cfg["root"]],
                                       ds_root=self.server.ds_root)
            if not r.get("ok"):
                err = r.get("error", "internal")
                out = {"error": err}
                if "executed" in r:  # 部分执行如实回传(audit 有全量)
                    out["executed"] = r["executed"]
                self._json(_INTAKE_ERR_STATUS.get(err, 400), out)
                return
            self._json(200, r)
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})

    def _intake_scan(self):
        """POST 针孔⑦(track opendesign-inbox-scan):收件箱卡片「扫描整理」。
        触发 ds_intake.stage_inbox_auto——把「00-收件箱里丢了什么」的确定性建议
        自动采纳为一个待确认 plan,歧义/未知留 skipped 交人工。posture 逐条同
        _intake_approve/_edit_change:CT json → body 上限 → 空 body 键白名单
        (任何键即拒,无参数可传)。allowed_roots=[工作区根]。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _SCAN_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})
            return
        try:
            cfg = ds_workspace.load_config(self.server.ds_root)
            if cfg is None:
                self._json(409, {"error": "workspace_not_configured"})
                return
            r = ds_intake.stage_inbox_auto([cfg["root"]], self.server.ds_root)
            if not r.get("ok"):
                err = r.get("error", "internal")
                self._json(_SCAN_ERR_STATUS.get(err, 400), {"error": err})
                return
            self._json(200, r)
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})

    def _intake_amend(self):
        """POST 针孔⑧(track opendesign-frontend-p1 design §②):收件箱卡片单条
        「跳过」纠偏。posture 逐条同 _intake_approve:CT json → body 上限 →
        键白名单 {plan_id, drop} → plan_id 格式闸 → plan root 必须落工作区根内
        (403 not_intake_plan)→ ds_intake.amend_plan(allowed_roots=[工作区根])。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _INTAKE_AMEND_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})
            return
        plan_id = body.get("plan_id")
        if not ds_organize.is_valid_plan_id(plan_id):
            self._json(400, {"error": "bad_plan_id"})
            return
        try:
            cfg = ds_workspace.load_config(self.server.ds_root)
            if cfg is None:
                self._json(403, {"error": "not_intake_plan"})
                return
            plan_path = os.path.join(self.server.ds_root, "organize", "plans",
                                     f"plan_{plan_id}.json")
            if not os.path.exists(plan_path):
                self._json(404, {"error": "plan_not_found"})
                return
            with open(plan_path, encoding="utf-8") as fh:
                plan = json.load(fh)
            # root 缺失守卫与 _intake_approve/_pending_plans 对称
            proot = plan.get("root")
            if (not isinstance(proot, str) or not proot
                    or not ds_common.within(cfg["root"], os.path.realpath(proot))):
                self._json(403, {"error": "not_intake_plan"})
                return
            r = ds_intake.amend_plan(plan_id, body.get("drop"), [cfg["root"]],
                                     self.server.ds_root)
            if not r.get("ok"):
                err = r.get("error", "internal")
                self._json(_INTAKE_ERR_STATUS.get(err, 400), {"error": err})
                return
            self._json(200, r)
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "internal"})

    def _edit_change(self):
        """POST 写针孔③(track opendesign-todo-edit design §Approach):待办行内编辑。
        只读铁律的又一受控开口,posture 同 open-folder/session-delete:
          CT application/json(CSRF 纵深:跨站带该类型必 preflight,本服务无 OPTIONS 面)
          → body 0<n≤OPEN_BODY_MAX → JSON dict → 键白名单(多余键即拒,防夹带 ds_root/today
          走私)→ 类型闸 → ds_tools.edit_change(名字闸/realpath/锁/保格式全在核心)。
        Host 闸由 do_POST 入口继承。精确匹配(非前缀)防路径走私。trace 不进响应体。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _EDIT_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        if not isinstance(project, str) or not project:
            self._json(400, {"error": "bad request"})
            return
        new_status = body.get("new_status")
        new_text = body.get("new_text")
        note = body.get("note")
        if any(v is not None and not isinstance(v, str)
               for v in (new_status, new_text, note)):
            self._json(400, {"error": "bad request"})
            return
        # cnum 原样交核心:缺失/非数 → edit_change 判 change_not_found(design test 12)
        r = ds_tools.edit_change(
            project, body.get("cnum"), new_status=new_status,
            new_text=new_text, note=note, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_EDIT_ERR_STATUS.get(err, 400), {"error": err})

    def _add_change(self):
        """POST 写针孔⑤(track opendesign-clickable-actions):变更记录「+ 记一条」。
        posture 逐条同 _edit_change:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单(多余键即拒,防夹带 ds_root/today 走私)→ 类型闸 →
        ds_tools.append_change(名字闸/realpath/锁/编号全在核心)。Host 闸由 do_POST
        入口继承。精确匹配(非前缀)防路径走私。trace 不进响应体。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _ADD_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        if not isinstance(project, str) or not project:
            self._json(400, {"error": "bad request"})
            return
        content = body.get("content")
        space = body.get("space")
        if any(v is not None and not isinstance(v, str) for v in (content, space)):
            self._json(400, {"error": "bad request"})
            return
        r = ds_tools.append_change(
            project, content or "", space=space or "", ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_ADD_ERR_STATUS.get(err, 400), {"error": err})

    def _create_project(self):
        """POST 写针孔⑥(track opendesign-clickable-actions):未建档文件夹「一键建档」。
        posture 逐条同 _edit_change/_add_change:CT application/json →
        body 0<n≤OPEN_BODY_MAX → JSON dict → 键白名单 → 类型闸 →
        ds_tools.create_project(名字闸/realpath/业主 stub 全在核心)。Host 闸由 do_POST
        入口继承。精确匹配(非前缀)防路径走私。trace 不进响应体。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _CREATE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        # 写门对齐读门(subkimi 四审 Low):create_project 核心 PROJECT_NAME_RE 会放行含 `..`
        # 的名字(如 a..b),但读侧 _valid_proj_key 拒之 → 建出来的项目 GET changes/refs 恒 404
        # (07-13 H1 同类"写成功即丢活")。这里先按读门 _valid_proj_key 拦,不造不可读的项目。
        if not isinstance(project, str) or not _valid_proj_key(project):
            self._json(400, {"error": "bad request"})
            return
        client = body.get("client")
        stage = body.get("stage")
        address = body.get("address")
        if any(v is not None and not isinstance(v, str) for v in (client, stage, address)):
            self._json(400, {"error": "bad request"})
            return
        r = ds_tools.create_project(
            project, client or "", stage=stage or "洽谈", address=address or "",
            ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_CREATE_ERR_STATUS.get(err, 400), {"error": err})

    def _upload(self):
        """POST 写针孔⑬(track opendesign-image-upload):网页拖拽上传图片 → 收件箱。

        **本服务第一个"网页给字节、服务端落盘"的口**,所以闸序写全:
          CT=application/json(**不收 multipart**:它是 simple content-type、不触发
          preflight,而本服务全部写针孔的 CSRF 纵深正是"json → 必 preflight → 无
          do_OPTIONS 面 → 浏览器拦";收 multipart 等于给这个口开 CSRF 洞)
          → Content-Length ∈ (0, UPLOAD_BODY_MAX](读 body 之前判)
          → JSON dict → 键白名单 {name,data_url} → 类型闸
          → _safe_upload_name(名字闸,复用全仓单段闸 + 上传口四条额外闸 + 截长)
          → 扩展名 ∈ IMG_EXTS(svg 排除)+ data URL mime 与扩展名同族 + 严格 base64
          → 解码后 ≤ UPLOAD_MAX_BYTES
          → 收件箱由 ds_intake._find_inbox 解析(taxonomy 四候选、用户可覆盖;
            自带 islink 拒绝 + within 闸)——**不硬编码 00-收件箱**;缺则 409,
            且**不自己造目录**(网页在用户工作区凭空建文件夹 = 越权)
          → realpath + within(纵深)
          → 落盘:先写 `.upload-<rand>.tmp`(点号开头 → 收件箱列举天然跳过),
            最终名用 O_EXCL 占位(撞名 `名字 (2).png` 递增,**不覆盖**),再 os.replace;
            任何异常 finally 清临时文件(半截文件会被「扫描整理」当正常文件归档)
        响应回显**真正落盘的名字**(可能被截短/换名),前端据此显示"已存为 xxx"。
        """
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        # 超限单独给码:前端要能说"图太大",不能只说"上传失败(bad request)"
        # (四审 subkimi F4)。体积闸仍在**读 body 之前**,不先收 20MB 再拒。
        if n > UPLOAD_BODY_MAX:
            self._json(413, {"error": "too_large"})
            return
        if n <= 0:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _UPLOAD_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})
            return
        raw_name, data_url = body.get("name"), body.get("data_url")
        if not isinstance(raw_name, str) or not isinstance(data_url, str):
            self._json(400, {"error": "bad request"})
            return
        # 类型与名字分两个码:svg/bmp/dwg 是"类型不收",回 bad_name 的话前端会建议
        # "改个名再试" —— 改名根本没用(四审 subkimi F4)。
        if os.path.splitext(raw_name)[1].lower() not in ds_workspace.IMG_EXTS:
            self._json(400, {"error": "bad_type"})
            return
        safe = _safe_upload_name(raw_name)
        if not safe:
            self._json(400, {"error": "bad_name"})
            return
        blob = _decode_upload_data_url(data_url, os.path.splitext(safe)[1].lower())
        if blob is None:
            self._json(400, {"error": "bad_image"})
            return

        cfg = ds_workspace.load_config(self.server.ds_root)
        if not cfg or not cfg.get("root"):
            self._json(409, {"error": "workspace_not_configured"})
            return
        # 坏/缺 taxonomy → load_taxonomy 返回 None,直接喂给 _find_inbox 会
        # `taxonomy["inboxDirs"]` 抛 TypeError → 连接被掐、浏览器只看到 Failed to fetch。
        # 兄弟端点(list_inbox / stage)一律降级成 taxonomy_bad,这里对齐(四审 subkimi F1)。
        taxonomy = ds_intake.load_taxonomy(self.server.ds_root)
        if taxonomy is None:
            self._json(409, {"error": "taxonomy_bad"})
            return
        found = ds_intake._find_inbox(cfg, taxonomy)
        if not found:
            self._json(409, {"error": "inbox_not_found"})
            return
        inbox_name, inbox_real = found
        if not ds_common.within(os.path.realpath(cfg["root"]), inbox_real):
            self._json(409, {"error": "inbox_not_found"})
            return

        tmp = os.path.join(inbox_real, f".upload-{uuid.uuid4().hex}.tmp")
        final = None
        try:
            with open(tmp, "xb") as fh:
                fh.write(blob)
            stem, ext = os.path.splitext(safe)
            for i in range(1, 100):
                cand = safe if i == 1 else f"{stem} ({i}){ext}"
                target = os.path.join(inbox_real, cand)
                try:
                    with open(target, "xb"):      # O_EXCL 占位:撞名不覆盖,无 TOCTOU
                        pass
                except FileExistsError:
                    continue
                final = (cand, target)
                break
            if final is None:
                self._json(409, {"error": "too_many_duplicates"})
                return
            os.replace(tmp, final[1])
            tmp = None
        except OSError:
            traceback.print_exc()            # 磁盘满/权限等:trace 进日志不进响应体
            if final is not None:
                try:
                    os.unlink(final[1])
                except OSError:
                    pass
            self._json(500, {"error": "internal"})
            return
        finally:
            if tmp is not None and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        # `path` = 绝对落盘路径。用户原话「收件箱是在我电脑哪个文件夹」——0.48.0 只回
        # name/inbox,前端只能说"已存进收件箱",他被迫来问人 = 提示不合格。
        # 不是新的泄漏类:/api/health 早就回 ds_root,且这是 localhost 单机工具、
        # 路径本来就是机主自己填的。**只给网页 UI,不进任何喂模型的通道。**
        self._json(200, {"ok": True, "name": final[0], "inbox": inbox_name,
                         "path": final[1]})

    def _inbox_create(self):
        """POST 写针孔⑭(track opendesign-chat-image design D3):建收件箱夹。

        为什么有这个口:0.48.0 缺收件箱只回一句"先建一个",把活推回给一个**不是
        程序员**的用户(他连收件箱在哪个文件夹都得来问)。但 `_upload` 的注释同时
        钉死了"网页不自己造目录 = 越权",那条过了四腿评审 —— 于是本口的形状是
        **人工点一下才建**,而不是"上传时顺手建":悄悄造目录和用户按下"帮我建"
        是两件事,后者与本仓既有规矩(写盘一律人工触发)同源。

        闸序照⑬:
          CT=application/json(CSRF 纵深:必触发 preflight,本服务无 do_OPTIONS 面)
          → Content-Length ∈ (0, OPEN_BODY_MAX] → JSON dict → **键白名单 = 空集**
            (无参可传:名字由规则表定、不由调用方点名,否则等于"网页可任意建目录")
          → workspace 已配置 → taxonomy 可用(坏表降级 409,同 _upload/list_inbox)
          → 已经有收件箱 → already_exists(**不重建、不动里面一根头发**)
          → 候选名必须是**单段**(ds_workspace._SEG_RE:禁 / \\ % 与控制符)——
            规则表的 _safe_rel_dir 允许多段,但本口只许在工作区根下建**一层**
          → realpath + within(root) 纵深
          → 名字被占:符号链接 → inbox_outside_root(不跟随,worktree 链接事故同源
            教训:链接不是目录);普通文件 → name_taken(不覆盖不删)
          → os.mkdir(**不是 makedirs**:父目录必须是 root 本身)
        """
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or body:      # 任何键即拒(无参数可传)
            self._json(400, {"error": "bad request"})
            return

        cfg = ds_workspace.load_config(self.server.ds_root)
        if not cfg or not cfg.get("root"):
            self._json(409, {"error": "workspace_not_configured"})
            return
        taxonomy = ds_intake.load_taxonomy(self.server.ds_root)
        if taxonomy is None:
            self._json(409, {"error": "taxonomy_bad"})
            return

        found = ds_intake._find_inbox(cfg, taxonomy)
        if found:
            name, real = found
            self._json(200, {"ok": True, "status": "already_exists",
                             "inbox": name, "path": real})
            return

        cands = taxonomy["inboxDirs"]
        if not cands:
            self._json(409, {"error": "bad_inbox_name"})
            return
        name = cands[0]
        root_real = os.path.realpath(cfg["root"])
        try:
            status, err = _ensure_inbox_dir(root_real, name)
        except OSError:
            traceback.print_exc()                  # 权限/磁盘满:trace 不进响应体
            self._json(500, {"error": "internal"})
            return
        if err:
            self._json(409, {"error": err})
            return
        self._json(200, {"ok": True, "status": status,
                         "inbox": name, "path": os.path.join(root_real, name)})

    def _bind_project(self):
        """POST 写针孔⑨(track opendesign-frontend-p1):项目↔工作区文件夹关联。
        薄壳,posture 同 _create_project:CT application/json →
        body 0<n≤OPEN_BODY_MAX → JSON dict → 键白名单 {project, folder} →
        双非空 str → ds_tools.bind_project(名字闸/已发现文件夹两级匹配/原子写
        全在核心,零新面)。folder_not_found/folder_ambiguous 时核心回传的
        folders 候选名单原样透传(前端提示用)。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _BIND_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        folder = body.get("folder")
        if (not isinstance(project, str) or not project
                or not isinstance(folder, str) or not folder):
            self._json(400, {"error": "bad request"})
            return
        # 写门对齐读门(四审 subkimi L3,同 _create_project 针孔的先例):核心
        # PROJECT_NAME_RE 放行含 `..` 的名字(如 a..b),但读侧 _valid_proj_key
        # 拒之 → 绑出来的映射键读侧永远寻址不到。不造读不到的映射。
        if not _valid_proj_key(project):
            self._json(400, {"error": "bad request"})
            return
        r = ds_tools.bind_project(project, folder, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        out = {"error": err}
        if "folders" in r:  # folder_not_found/folder_ambiguous 候选名单透传
            out["folders"] = r["folders"]
        self._json(_BIND_ERR_STATUS.get(err, 400), out)

    def _folder_visibility(self):
        """POST /api/workspace/folder-visibility:一次存整份「不显示」清单。

        posture 照抄写针孔⑨:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {review_id, hidden} → 类型/值域闸。写盘只在
        locked_workspace_json 内进行,且只改 raw["structuralDirs"] 一个键。
        """
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= _FOLDER_VISIBILITY_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _FOLDER_VISIBILITY_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})
            return
        review_id = body.get("review_id")
        hidden = body.get("hidden")
        if not isinstance(review_id, str) or not review_id:
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(hidden, list) or len(hidden) > _FOLDER_VISIBILITY_MAX_NAMES:
            self._json(400, {"error": "bad request"})
            return
        seen = set()
        for name in hidden:
            if (not isinstance(name, str) or not name
                    or not ds_workspace._SEG_RE.match(name) or name in seen):
                self._json(400, {"error": "bad request"})
                return
            seen.add(name)

        # 锁内**只算出**要回什么,出锁再发 —— 响应虽小,但在锁内写 socket 等于
        # 让一个慢客户端占住 workspace.json 的排他锁,而该锁在 Windows 上争用
        # 会抛 OSError 而非排队(阶段一四审记录)。
        try:
            with ds_tools.locked_workspace_json(self.server.ds_root) as box:
                box["write"] = False
                raw = box["raw"]
                cfg = ds_workspace.load_config(self.server.ds_root)
                if raw is None or cfg is None:
                    reply = (409, {"error": "workspace_not_configured"})
                else:
                    reply = self._folder_visibility_apply(box, cfg, review_id, hidden)
        except Exception:
            traceback.print_exc()
            reply = (500, {"error": "internal"})
        self._json(*reply)

    def _folder_visibility_apply(self, box, cfg, review_id, hidden):
        """在已持锁的前提下复核快照并落盘;→ (status, payload),不自己发响应。"""
        proot = ds_workspace.projects_root(cfg)
        if not proot or os.path.realpath(cfg["root"]) != os.path.realpath(proot):
            return 409, {"error": "not_applicable"}
        top_dirs = _workspace_top_dirs(os.path.realpath(cfg["root"]))
        current_rid = _workspace_review_id(
            _workspace_config_bytes(self.server.ds_root), top_dirs)
        if review_id != current_rid:
            return 409, {"error": "stale_review"}
        declared = (cfg.get("structuralDirs")
                    if isinstance(cfg.get("structuralDirs"), list) else [])
        issued = set(top_dirs) | set(declared)
        if any(name not in issued for name in hidden):
            return 400, {"error": "bad request"}
        box["raw"]["structuralDirs"] = list(hidden)
        box["write"] = True
        return 200, {"ok": True}

    def _set_stage(self):
        """POST 写针孔⑩(track opendesign-stage-history §7):切阶段。
        薄壳,posture 逐条照抄 _edit_change:CT application/json →
        body 0<n≤OPEN_BODY_MAX → JSON dict → 键白名单 {project, stage}(多余键即拒,
        防夹带 ds_root/today 走私)→ 两键都必须非空 str → ds_tools.set_stage(
        名字闸/词表精确匹配/锁/页脚 bump 全在核心)。响应体不回显词表(词表走
        GET /api/projects 的 stages,写口少一条外泄面)。Host 闸由 do_POST 入口继承。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _STAGE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        stage = body.get("stage")
        if (not isinstance(project, str) or not project
                or not isinstance(stage, str) or not stage):
            self._json(400, {"error": "bad request"})
            return
        r = ds_tools.set_stage(project, stage, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_STAGE_ERR_STATUS.get(err, 400), {"error": err})

    def _refs_update(self):
        """POST 写针孔⑪(track opendesign-stage-history §8):参考图标签/备注就地改。
        薄壳,posture 同 ⑩:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {ref_id, style, space, note}(多余键即拒,防夹带
        file/source/used 走私)→ ref_id 必须 str → style/space/note 给了必须是 str
        (缺省=不动,原样交核心区分)→ ds_refs.update_ref(词表/分段重写/锁/页脚 bump
        全在核心)。Host 闸由 do_POST 入口继承。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _REFS_UPDATE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        ref_id = body.get("ref_id")
        if not isinstance(ref_id, str):
            self._json(400, {"error": "bad request"})
            return
        if any(k in body and not isinstance(body[k], str)
               for k in ("style", "space", "note")):
            self._json(400, {"error": "bad request"})
            return
        r = ds_refs.update_ref(
            ref_id,
            style=body.get("style") if "style" in body else None,
            space=body.get("space") if "space" in body else None,
            note=body.get("note") if "note" in body else None,
            ds_root=self.server.ds_root)
        if r.get("ok"):
            # 只回 {ok, ref_id}:核心的 r["line"] 是整行,含读口刻意不外泄的
            # `来源:`/`用于:`(见 _project_refs 注释)。同一份数据两个口径必须一致。
            self._json(200, {"ok": True, "ref_id": r.get("ref_id")})
            return
        err = r.get("error", "internal")
        self._json(_REFS_UPDATE_ERR_STATUS.get(err, 400), {"error": err})

    def _set_due_date(self):
        """POST 写针孔⑫(track opendesign-todo-duedate design.md):设/清一条变更的截止日。
        posture 逐条照抄 _edit_change:CT application/json → body 0<n≤OPEN_BODY_MAX →
        JSON dict → 键白名单 {project, cnum, due}(多余键即拒,防夹带 ds_root/today 走私)→
        类型闸(due 可为 null/字符串)→ ds_tools.set_due_date(格式校验/定位/锁/页脚 bump
        全在核心)。Host 闸由 do_POST 入口继承。精确匹配(非前缀)防路径走私。"""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json(400, {"error": "bad request"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= OPEN_BODY_MAX:
            self._json(400, {"error": "bad request"})
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "bad request"})
            return
        if not isinstance(body, dict) or set(body) - _DUE_ALLOWED_KEYS:
            self._json(400, {"error": "bad request"})  # 非对象/多余键 → 拒
            return
        project = body.get("project")
        if not isinstance(project, str) or not project:
            self._json(400, {"error": "bad request"})
            return
        due = body.get("due")
        if due is not None and not isinstance(due, str):
            self._json(400, {"error": "bad request"})
            return
        # cnum 原样交核心:缺失/非数 → set_due_date 判 change_not_found(同 edit_change 口径)
        r = ds_tools.set_due_date(project, body.get("cnum"), due, ds_root=self.server.ds_root)
        if r.get("ok"):
            self._json(200, r)
            return
        err = r.get("error", "internal")
        self._json(_DUE_ERR_STATUS.get(err, 400), {"error": err})

    def _proxy(self, up_path: str):
        """白名单转发到本机 nanobot gateway。纯管道:不读不存任何秘密。
        上游方法恒为 GET(nanobot ws_http 路由不查方法;delete 针孔也走这条,
        POST 语义只存在于本服务的暴露面)——将来若有上游要求真 POST 的端点,
        这里要加 method 参数,别隐式复用。"""
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
