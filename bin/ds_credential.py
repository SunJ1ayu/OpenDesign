#!/usr/bin/env python3
"""业主的大模型 key:存、读状态、换厂商(track opendesign-key-onboarding)。

装完第一次打开,业主在界面里填这把 key。**它是凭据**,所以这个模块的规矩是:

1. **只收不读**:任何返回值里都不许出现 key 原文,只回"已配置 + 一个提示片段"。
2. **只落一个地方**:`<home>/.openDesign/key.txt`,原子写(temp + replace),
   一行、不带别的。配置里永远只有 `${VAR}` 引用形态(判据 a3 / 与
   `test_ds_provision.a6` 同一条不变量:配置会进日志、截图、收据)。
3. **变量名从配置读,不许写死** —— Windows 那份引用 `${DS_LLM_KEY}`,
   **Linux 那份引用 `${MIMO_TP_KEY}`**。写死就等于在两台 git-pull 机器上把网关搞死。
   (这条是规划双出 B 卷替我抓到的,我原本要写死。)
4. **报错不许带入参**:坏路径是最容易把 key 回显出去的地方。

## 🔴 这个模块管得到哪儿(2026-08-16 四审 deepseek 腿 BLOCK 的那条)

它只看得见**两层**:`<home>/.openDesign/key.txt`,以及**ds-web 自己进程的环境变量**。

**看不见的**:网关的 key 若来自别处,这里一无所知。现实中就有这么一条 ——
Linux 的 `bin/ds-nanobot` 从 `~/.local/share/mimocode/auth.json` 读 key、
`export MIMO_TP_KEY` **只给它 exec 出来的 nanobot 子进程**,既不进 ds-web 的环境、
也从不碰 key.txt。在那台机器上:

- 网关明明能聊天,`status()` 却报 `configured=False` ⇒ 界面催业主填一把他不需要的 key;
- 业主若真填了,`save()` 照写 key.txt(遮蔽检查看不到 auth.json,不会拒绝),
  界面显示「已配置」和新 key 的末四位,**而网关继续用 auth.json 里那把旧的**。

**这是已知边界,本单不修**,理由:业主的机器是 Windows(装好的形态走 `ds_shell`
注入、或 git-pull 那两台走 `ds-nanobot.ps1` 的 env/key.txt 两层),两条路都在本模块
管辖内;而为 Linux 开发机引入平台特化的探测(去读 auth.json)会把平台判断塞进凭据
模块,风险大于收益。**已记 docs/backlog.md。**

⚠️ 别把这条读成"Linux 不支持":ds-web 在 Linux 上照常跑,只是**界面上的 key 状态
在那台机器上不可信**。谁将来要在 Linux 上支持界面配 key,得先给 `status()` 一个
"这把 key 由启动器管理、我看不见"的第三种回答,而不是让它在 `configured` 上撒谎。
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import ds_model  # 「当前大脑」preset 优先规则的唯一真相源(与 ds_web / set_model.py 同源)

# 出货模板是这两份的**唯一出处**:预设值不在本文件里第二次硬编码。
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
WINDOWS_TEMPLATE = os.path.join(_REPO, "config", "nanobot.config.windows.jsonc")

_ENV_REF_RE = re.compile(r"^\$\{([^}]+)\}$")
_JSONC_LINE_COMMENT = re.compile(r"^\s*//")


class CredentialError(Exception):
    """凭据面出错。**报错文本里永远不许带 key。**"""


def load_jsonc(path: str) -> dict:
    """读带 `//` 注释的 jsonc。只剥整行注释 —— 行内 `//` 可能是 URL 里的那两个斜杠。"""
    with open(path, encoding="utf-8") as fh:
        body = "".join("" if _JSONC_LINE_COMMENT.match(ln) else ln for ln in fh)
    return json.loads(body)


def _template_presets() -> dict:
    """MiMo 的端点/模型:**从出货模板里读**,不在这儿抄第二遍(判据 b3 咬着)。"""
    tpl = load_jsonc(WINDOWS_TEMPLATE)
    api_base = tpl.get("providers", {}).get("custom", {}).get("apiBase", "")
    presets = tpl.get("model_presets", {})
    default = tpl.get("agents", {}).get("defaults", {}).get("modelPreset", "")
    model = presets.get(default, {}).get("model") or default
    return {"apiBase": api_base, "model": model}


def _template_models() -> list:
    """MiMo 能选哪些模型:**从出货模板的 model_presets 里读**(判据 lm8:这里不许再抄一份模型名)。"""
    tpl = load_jsonc(WINDOWS_TEMPLATE)
    return [name for name, p in (tpl.get("model_presets") or {}).items()
            if isinstance(p, dict) and p.get("provider") == "custom"]


PROVIDERS = {
    # 名字是给界面看的;端点/模型是给网关用的。
    # `models` = 这家的 key 能用哪些模型(输入框里那颗模型按钮的菜单,track opendesign-composer-model-picker)。
    # `keyUrl` = key 卡片上「获取 API Key」链到哪(track opendesign-kimi-glm-vendors)。
    # MiMo 接的是**套餐**端点,套餐 key 只在套餐订阅页建 ⇒ 链套餐页,不照 ZCode 链平台首页。
    "mimo": {"label": "MiMo(小米)", **_template_presets(), "models": _template_models(),
             "keyUrl": "https://platform.xiaomimimo.com/token-plan"},
    # 🔴 2026-08-15 现拉 `GET https://api.deepseek.com/models` 核过:
    #    只剩 v4-flash / v4-pro,老的 deepseek-chat / deepseek-reasoner 已下架。
    #    **这是一条会过期的事实**,判据 b4 把它钉住,过期时会红。
    "deepseek": {"label": "DeepSeek 官方", "apiBase": "https://api.deepseek.com/v1",
                 "model": "deepseek-v4-flash", "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
                 "keyUrl": "https://platform.deepseek.com/api_keys"},
    # 🔴 下面三家 2026-09-23 照 ZCode 内置目录(config/provider/zcode-builtin.json)+ 官方文档 + 无 key 探测(401)填,
    #    **没用真 key 验过模型名**(业主手上没有);会过期,判据 k1 钉住。
    #    Kimi 只接按量(开放平台);Kimi 会员(Kimi Code)业主定不加 —— 官方只给编程工具、禁改 User-Agent。
    # `presetParams` = 这家每个预设必须带的生成参数。Kimi K2.5+ 拒收 temperature<1.0 ——
    #    nanobot 只在它自己的 moonshot 规格里覆盖(registry.py model_overrides),我们走 custom/od_kimi 通道吃不到,
    #    预设默认 0.1 ⇒ 每句被拒(判据 k7 问的是真发出去的参数)。
    "kimi": {"label": "Kimi 按量", "apiBase": "https://api.moonshot.cn/v1",
             "model": "kimi-k3", "models": ["kimi-k3", "kimi-k2.7-code", "kimi-k2.6"],
             "keyUrl": "https://platform.kimi.com/console/api-keys",
             "presetParams": {"temperature": 1.0}},
    # GLM 两家有同名模型(glm-5.3):菜单按「厂商+模型」打勾(pv3),换模型按厂商所在槽改预设(判据 k4 用 nanobot 加载器验)。
    "glm_plan": {"label": "GLM 套餐(Coding Plan)", "apiBase": "https://open.bigmodel.cn/api/coding/paas/v4",
                 "model": "glm-5.3", "models": ["glm-5.3", "glm-5.3-flash"],
                 "keyUrl": "https://bigmodel.cn/coding-plan/personal/overview"},
    "glm": {"label": "GLM 按量", "apiBase": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-5.3", "models": ["glm-5.3", "glm-5.3-flash", "glm-5v-turbo", "glm-5.1"],
            "keyUrl": "https://bigmodel.cn/usercenter/proj-mgmt/apikeys"},
}


# ── 目录 = 内置 ⊕ 用户登记(track opendesign-zcode-model-settings)──────────────────
# 业主 09-24:「严格按照zcode做」。ZCode 每家一张模型列表:内置几个 + 用户「添加模型」手填;还能加自定义供应商。
# 4c 挑战(Grok)核实:下面这些路由/清扫规矩**只认目录** —— 用户加的模型、自定义供应商不进目录,
# 菜单看不见、select_model 拒、起网关/合并时被当成手写预设删。所以目录不再是常量,而是
# **内置 PROVIDERS ⊕ `<home>/.openDesign/models.json`**,由入口函数进门时算一次(catalog_scope),
# 本次调用内所有助手经 `_P()` 读同一张;出门自动恢复。**不改全局 PROVIDERS**(测试与多 home 会互相串)。
# 没进范围的调用(老测试直接调助手)看到的就是内置目录 —— 与改动前逐字节同一行为。
_CATALOG: contextvars.ContextVar = contextvars.ContextVar("ds_credential_catalog", default=None)
CUSTOM_PREFIX = "c_"
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}$")  # 不许 @:那是预设名里的厂商分隔符


def _P() -> dict:
    """当前范围里的目录(没进范围 ⇒ 内置)。"""
    return _CATALOG.get() or PROVIDERS


def registry_path(home: str) -> str:
    return os.path.join(home, ".openDesign", "models.json")


def _empty_registry() -> dict:
    return {"version": 1, "extraModels": {}, "customProviders": [], "disabled": [], "contextWindow": {}}


def _load_registry(home: str | None) -> dict:
    """读登记;没有 / 读不出 / 形状不对 ⇒ 空登记(0.98.11 的机器没有这个文件,照常用)。"""
    reg = _empty_registry()
    if not home:
        return reg
    try:
        with open(registry_path(home), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return reg
    if not isinstance(raw, dict):
        return reg
    em = raw.get("extraModels")
    if isinstance(em, dict):
        reg["extraModels"] = {v: [m for m in ms if isinstance(m, str) and _MODEL_ID_RE.match(m)]
                              for v, ms in em.items() if isinstance(v, str) and isinstance(ms, list)}
    cps = raw.get("customProviders")
    if isinstance(cps, list):
        for cp in cps:
            if (isinstance(cp, dict) and isinstance(cp.get("id"), str) and cp["id"].startswith(CUSTOM_PREFIX)
                    and isinstance(cp.get("label"), str) and isinstance(cp.get("apiBase"), str)
                    and isinstance(cp.get("models"), list)):
                models = [m for m in cp["models"] if isinstance(m, str) and _MODEL_ID_RE.match(m)]
                if models:
                    reg["customProviders"].append({"id": cp["id"], "label": cp["label"],
                                                   "apiBase": cp["apiBase"], "models": models})
    if isinstance(raw.get("disabled"), list):
        reg["disabled"] = [v for v in raw["disabled"] if isinstance(v, str)]
    if isinstance(raw.get("contextWindow"), dict):
        reg["contextWindow"] = {k: v for k, v in raw["contextWindow"].items()
                                if isinstance(k, str) and type(v) is int and v > 0}
    return reg


def _save_registry(home: str, reg: dict) -> None:
    try:
        _atomic_write(registry_path(home), json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        raise CredentialError(f"写不进去({exc.__class__.__name__}),请确认这台机器上这个文件夹可写") from None


def catalog(home: str | None) -> dict:
    """内置五家 ⊕ 登记。每家:label / apiBase / model(默认)/ models(内置 + 用户加的)/ builtinModels /
    enabled / custom / keyUrl / presetParams / contextWindow{模型: tokens}。"""
    reg = _load_registry(home)
    disabled = set(reg["disabled"])
    out = {}
    for vendor, meta in PROVIDERS.items():
        m = dict(meta)
        extra = [x for x in reg["extraModels"].get(vendor, []) if x not in meta["models"]]
        m["models"] = list(meta["models"]) + extra
        m["builtinModels"] = list(meta["models"])
        m["enabled"] = vendor not in disabled
        m["custom"] = False
        out[vendor] = m
    for cp in reg["customProviders"]:
        if cp["id"] in out:
            continue
        out[cp["id"]] = {"label": cp["label"], "apiBase": cp["apiBase"], "model": cp["models"][0],
                         "models": list(cp["models"]), "builtinModels": [], "enabled": cp["id"] not in disabled,
                         "custom": True, "keyUrl": None}
    for key, tokens in reg["contextWindow"].items():
        vendor, _, model = key.partition("/")
        if vendor in out:
            out[vendor].setdefault("contextWindow", {})[model] = tokens
    return out


def home_of(cfg_path: str | None) -> str | None:
    """配置在 `<home>/.nanobot/config.json` ⇒ home(与 key.txt / keys/ 同根);别的布局 ⇒ None(只用内置目录)。"""
    if not cfg_path:
        return None
    d = os.path.dirname(os.path.abspath(cfg_path))
    return os.path.dirname(d) if os.path.basename(d) == ".nanobot" else None


@contextlib.contextmanager
def catalog_scope(home: str | None):
    """本次调用内的目录 = catalog(home)。可嵌套;出门恢复。"""
    token = _CATALOG.set(catalog(home) if home else None)
    try:
        yield _P()
    finally:
        _CATALOG.reset(token)


def _scoped(fn):
    """公开入口进门时按 `home`(没给 ⇒ 从 cfg_path 推)建目录范围;已在范围里(入口套入口)⇒ 沿用外层。
    🔴 P4:漏包一个入口,那个入口就只认内置目录 —— 判据 z2/z4 走完 存 key → 起网关 → 选中 → 合并 咬着。"""
    import functools
    import inspect
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _CATALOG.get() is not None:
            return fn(*args, **kwargs)
        bound = sig.bind_partial(*args, **kwargs).arguments
        home = bound.get("home") or home_of(bound.get("cfg_path"))
        with catalog_scope(home):
            return fn(*args, **kwargs)
    return wrapper


def _norm_base(base) -> str:
    """端点比较前去掉首尾空白与尾斜杠:`…/v1/` 和 `…/v1` 是同一家(挑战腿指出的 F5)。"""
    return str(base or "").strip().rstrip("/")


def _vendor_by_base(base):
    b = _norm_base(base)
    if not b:
        return None
    for name, preset in _P().items():
        if b == _norm_base(preset["apiBase"]):
            return name
    return None


def _current_provider(cfg: dict):
    """**主槽**是哪一家:按 providers.custom.apiBase 认(与 status() 同一个判法)。认不出返回 None。"""
    base = ((cfg.get("providers") or {}).get("custom") or {}).get("apiBase", "")
    return _vendor_by_base(base)


# ── 额外槽(track opendesign-per-vendor-keys)────────────────────────────────
# 主槽 = `providers.custom` + 它引用的变量 + key.txt,**格式与语义一个字不改**:
# 老启动器(ds-nanobot.ps1、Linux 的 ds-nanobot)只认它,老用户也不用迁移。
# 第二家起放「额外槽」:key 在 `keys/<厂商>.txt`,配置条目 `providers.od_<厂商>`。
#
# 🔴 额外条目**只由 prepare_gateway 写**(外壳起网关那一刻,与注入 key 同一处)。
#    实验 p2(真网关)证实:配置引用了网关 env 里没有的变量,每句前的重读会抛错被吞、
#    **悄悄保留旧厂商**,而界面说换了。条目与 key 同一处产生 ⇒「引用 ⊆ 网关手里的 key」由结构保证。
EXTRA_PREFIX = "od_"
_VAR_UNSAFE = re.compile(r"[^A-Z0-9_]")


def extra_provider_name(vendor: str) -> str:
    return EXTRA_PREFIX + vendor


def extra_var_name(vendor: str) -> str:
    """额外槽的变量名。以 `DS_` 开头是刻意的:外壳 `child_env` 会剥掉继承来的 `DS_*`,
    业主自己环境里的同名变量就漏不进网关(只有外壳注入的那份算数)。"""
    return "DS_LLM_KEY_" + _VAR_UNSAFE.sub("_", vendor.upper())


def keys_dir(home: str) -> str:
    return os.path.join(home, ".openDesign", "keys")


def extra_key_path(home: str, vendor: str) -> str:
    return os.path.join(keys_dir(home), f"{vendor}.txt")


def _switch_marker_path(home: str) -> str:
    """「存了这家的 key,想换过去」—— 只有一个厂商 id,**不含 key**。
    存 key 的那一下网关还没拿到它,不能立刻切(会撞上前提 3);由 prepare_gateway 在注入之后兑现。"""
    return os.path.join(keys_dir(home), "switch-to")


def read_extra_key(home: str, vendor: str) -> str | None:
    try:
        with open(extra_key_path(home, vendor), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def _extra_entries(cfg: dict) -> dict:
    """配置里现有的额外槽条目:{厂商: 条目}。只认 `od_<目录里的厂商>`。"""
    out = {}
    for name, entry in ((cfg.get("providers") or {}).items()):
        if isinstance(name, str) and name.startswith(EXTRA_PREFIX) and isinstance(entry, dict):
            vendor = name[len(EXTRA_PREFIX):]
            if vendor in _P():
                out[vendor] = entry
    return out


def _live_vendors(cfg: dict) -> list:
    """网关手里有 key 的厂商(按配置判):主槽那家 + 每个额外条目。

    额外条目只由 prepare_gateway 在注入 key 的同时写,所以"条目在"就等于"网关拿到了"。"""
    primary = _current_provider(cfg)
    out = [primary] if primary else []
    for vendor in _extra_entries(cfg):
        if vendor not in out:
            out.append(vendor)
    return out


def _preset_vendor(cfg: dict, preset_name) -> str | None:
    """某个预设实际发往哪一家:看它的 `provider` 字段(nanobot 按它路由,预设里没有端点字段)。"""
    preset = (cfg.get("model_presets") or {}).get(preset_name) if preset_name else None
    if not isinstance(preset, dict):
        return None
    prov = preset.get("provider")
    if isinstance(prov, str) and prov.startswith(EXTRA_PREFIX):
        vendor = prov[len(EXTRA_PREFIX):]
        return vendor if vendor in _P() else None
    return _current_provider(cfg)


def _slot_of(cfg: dict, vendor: str) -> str:
    return "custom" if vendor == _current_provider(cfg) else extra_provider_name(vendor)


PRESET_VENDOR_SEP = "@"


def preset_name(vendor: str, model: str) -> str:
    """某家某模型的预设名。**同名模型按厂商各存一份**(两家 GLM 都有 glm-5.3 ⇒ `glm-5.3@glm_plan` / `glm-5.3@glm`),
    谁也改不动谁的归属 —— 共用一份时连打了五次补丁(k4b/k4c/k8/k8b/k9),第 3 轮评审后回头改成这样(k10)。
    不重名的模型照旧就用模型名:老配置、nanobot `/model` 列表一个字不变。"""
    shared = any(v != vendor and model in p["models"] for v, p in _P().items())
    return f"{model}{PRESET_VENDOR_SEP}{vendor}" if shared else model


def _apply_params(preset: dict, vendor: str) -> dict:
    """把这家必带的生成参数(presetParams)盖到预设上;其余字段不动。"""
    meta = _P()[vendor]
    preset.update(meta.get("presetParams") or {})
    cw = (meta.get("contextWindow") or {}).get(preset.get("model"))
    if cw:                                   # 设置页「编辑模型配置 → 上下文窗口」(ZCode);配置里字段是驼峰
        preset.pop("context_window_tokens", None)
        preset["contextWindowTokens"] = cw
    return preset


def _custom_preset(vendor: str, model: str) -> dict:
    # 主槽预设沿用老形状(含 apiBase —— nanobot 不读它,但 lm5 与老配置都是这个样子)
    return _apply_params({"label": model, "provider": "custom", "model": model,
                          "apiBase": _P()[vendor]["apiBase"]}, vendor)


def _extra_preset(vendor: str, model: str) -> dict:
    return _apply_params({"label": model, "provider": extra_provider_name(vendor), "model": model}, vendor)


def _preset_owner(name, preset: dict) -> str | None:
    """这份预设是不是**我们替某家起的**:模型在那家目录里,且名字正是 `preset_name(那家, 模型)` ⇒ 那家;
    其余一律 None(业主手写的,哪怕名字碰巧以 `@kimi` 结尾、或名字和模型对不上 —— 第 5 轮 #20)。"""
    model = preset.get("model")
    for v, p in _P().items():
        if model in p["models"] and name == preset_name(v, model):
            return v
    return None


def _route_presets(cfg: dict, *, endpoint_changed: bool = False) -> None:
    """**目录里的模型,只许以那家的正式名字挂在那家的槽上**(原地改;k11、d3~d8)。

    根因(第 4 轮两家 BLOCK):主槽 `custom` 的厂商会变,而指向它的预设不带厂商 ⇒ 主槽一换人,
    旧主槽留下的预设(`glm-5.3@glm_plan`、`mimo-v2.5`)就跟着发到新主槽,名字说一家、扣另一家的钱。
    第 9 轮后照 ZCode 收成一条**稳态**规矩(不等端点变,盘上已有的错配也扫;方案挑战 Grok 指出):
    只看指向我们自己槽位(custom / od_*)的预设;主槽端点认不出(机主自配)时指向 custom 的一律不碰。
      · 我们起的名字(见 _preset_owner)⇒ 主人是主槽 ⇒ custom;主人有额外槽 ⇒ od_<主人>;都不是 ⇒ 删。
        留下的补齐那家必带的参数(Kimi 的 temperature)。
      · 模型在目录里、名字却不是我们起的(老安装写的裸共享名 `glm-5.3-flash`、名模不一致):
        它所在那格的厂商有这个模型 ⇒ **原地改成那家的正式名**,不换格、不换模型,当前模型跟着改名
        (删了回落默认 = 把业主选好的模型换掉,第 10 轮 #37,d7b);那格厂商没有这个模型 ⇒ 删。
        **永不改指到别的格** —— 说不清它属于哪家,改指会把套餐的账记到按量(方案挑战 Grok,d8)。
      · 目录外的模型(机主手写)⇒ 不碰;只有 `endpoint_changed`(save 刚把主槽端点换掉)时,
        指向 custom 的删掉 —— 它们绑的是旧端点(d3/d4)。
    没写 provider 的(nanobot 的 auto)不是我们的槽,不碰(第 5 轮 #21)。
    """
    primary = _current_provider(cfg)
    providers = cfg.get("providers") or {}
    presets = cfg.get("model_presets")
    if not isinstance(presets, dict):
        return
    catalog = {m for p in _P().values() for m in p["models"]}
    for name in list(presets):
        p = presets[name]
        if not isinstance(p, dict):
            continue
        prov = p.get("provider")
        ours = prov == "custom" or (isinstance(prov, str) and prov.startswith(EXTRA_PREFIX))
        if not ours or (prov == "custom" and primary is None):
            continue
        if prov != "custom" and not isinstance(providers.get(prov), dict):
            presets.pop(name)                    # 指向已经没有的额外格:nanobot 加载不了,留着就是悬空
            continue
        owner = _preset_owner(name, p)
        if owner is None:
            model = p.get("model")
            if model in catalog:
                here = primary if prov == "custom" else prov[len(EXTRA_PREFIX):]
                if here in _P() and model in _P()[here]["models"]:
                    _rename_preset(cfg, name, preset_name(here, model))
                    _apply_params(presets[preset_name(here, model)], here)
                else:
                    presets.pop(name)
            elif prov == "custom" and endpoint_changed:
                presets.pop(name)
            continue
        if owner == primary:
            slot = "custom"
        elif isinstance(providers.get(extra_provider_name(owner)), dict):
            slot = extra_provider_name(owner)
        else:
            presets.pop(name)
            continue
        if prov != slot:
            p["provider"] = slot
        _apply_params(p, owner)


def _rename_preset(cfg: dict, old: str, new: str) -> None:
    """把预设 `old` 改名成 `new`(同一格、同一个模型);`new` 已在 ⇒ 丢掉 `old`、留已有的那份。当前模型指着它就跟着改。"""
    presets = cfg["model_presets"]
    p = presets.pop(old)
    presets.setdefault(new, p)
    defaults = (cfg.get("agents") or {}).get("defaults")
    if isinstance(defaults, dict) and defaults.get("modelPreset") == old:
        defaults["modelPreset"] = new


@_scoped
def models_status(cfg_path: str, home: str | None = None) -> dict:
    """输入框里模型按钮要的东西:当前厂商、当前模型、这把 key 能选的模型(判据 lm1/lm5/lm6)。

    🔴 模型列表按**厂商目录**给,不按配置里的 model_presets 给:换到 DeepSeek 之后,
       MiMo 的预设还留在配置里,照配置列就会把它们列成"能用"—— 选了会被发到 DeepSeek 的地址(判据 lm5)。
    配置缺失 / 读不出 / 认不出厂商 ⇒ provider=None、models=[](界面只剩「换厂商 / 换 key…」)。

    多厂商(track opendesign-per-vendor-keys):`groups` = 每个**网关手里有 key**的厂商一组;
    顶层 `provider/label/models` 仍是当前在用那一家(老前端照旧能用)。
    """
    out = {"provider": None, "label": None, "current": None, "models": [], "groups": []}
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return out
    if not isinstance(cfg, dict):
        return out
    live = _live_vendors(cfg)
    if not live:
        return out
    active = _preset_vendor(cfg, ds_model.active_preset_name(cfg))
    if active not in live:
        active = live[0]
    # 禁用的厂商只在菜单里藏(D3:路由与 key 不动)。正在用的那家不许禁用,所以 active 总在菜单里。
    shown = [v for v in live if _P()[v].get("enabled", True) or v == active]
    groups = [{"provider": v, "label": _P()[v]["label"],
               "models": [{"id": m, "label": m} for m in _P()[v]["models"]]} for v in shown]
    out.update(provider=active, label=_P()[active]["label"], current=ds_model.resolve_model(cfg),
               models=groups[shown.index(active)]["models"], groups=groups)
    return out


@_scoped
def select_model(cfg_path: str, model, provider=None, home: str | None = None) -> dict:
    """把当前模型换成 `model`:写 agents.defaults.modelPreset(判据 lm2~lm6、v8)。

    - 只许**网关手里有 key 的厂商**目录里的 id(别家的 / 随便的串 / 空 ⇒ CredentialError,配置不动);
      `provider` 给了就只在那一家里找(前端点哪一行就带哪一家,不靠模型名反查);
    - 目录里有、配置里还没有这个预设 ⇒ 按该厂商所在的槽补建(DeepSeek 的 v4-pro 就是这样);
    - 其余字段一个不碰,key 文件不碰,不重启网关:nanobot 每条入站消息前重读配置
      (agent/loop.py _refresh_provider_snapshot → providers/factory.py load_provider_snapshot),下一句起生效。
      跨厂商也一样 —— 真网关实验 p2 / 判据 l1 证实下一句就换到另一家的端点和 key。
    配置读不出 ⇒ 拒绝,**不替业主建一份配置**。
    给了 `home`(ds_web 总会给):业主亲手选的模型盖过之前留下的「想换过去」(第 2 轮 v18)——
    否则自动重启没成、他手选了 MiMo,之后一重启又被旧标记拽回 DeepSeek。
    """
    if not isinstance(model, str) or not model.strip():
        raise CredentialError("没有指定要换成哪个模型")
    if provider is not None and not isinstance(provider, str):
        raise CredentialError("厂商参数不对")
    model = model.strip()
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None
    if not isinstance(cfg, dict):
        raise CredentialError(f"配置读不出来:{cfg_path}")
    live = _live_vendors(cfg)
    if not live:
        raise CredentialError("认不出现在用的是哪家的 key,请先在「AI 模型 key」里选厂商")
    enabled = [v for v in live if _P()[v].get("enabled", True)]
    if provider is not None:
        if provider not in _P():
            raise CredentialError(f"不认识的厂商:{provider}")
        if not _P()[provider].get("enabled", True):
            raise CredentialError(f"{_P()[provider]['label']} 已禁用,先在「模型设置」里启用")
        if provider not in live:
            raise CredentialError(f"{_P()[provider]['label']} 的 key 后台还没拿到,"
                                  "等后台重启好再选(或先在「AI 模型 key」里填)")
        vendor = provider
    else:
        hits = [v for v in enabled if model in _P()[v]["models"]]
        if not hits:
            waiting = [v for v in _P() if v not in live and model in _P()[v]["models"]]
            if waiting:
                raise CredentialError(f"{_P()[waiting[0]]['label']} 的 key 后台还没拿到,"
                                      "等后台重启好再选(或先在「AI 模型 key」里填)")
            raise CredentialError(f"{_P()[live[0]]['label']} 这把 key 用不了 {model}")
        # 两家都能用同名模型(两家 GLM 的 glm-5.3)时不许按表序猜 —— 猜错就换端点、换 key、换账单(判据 k8/k8b):
        # 当前在用的那家有这个模型 ⇒ 就是它(老菜单只列当前这家的目录,不带厂商 = 这家里的那个模型);
        # 否则说不清 ⇒ 拒绝,要调用方指明厂商。
        active = _preset_vendor(cfg, ds_model.active_preset_name(cfg))
        if active in hits:
            vendor = active
        elif len(hits) > 1:
            names = "、".join(_P()[v]["label"] for v in hits)
            raise CredentialError(f"{model} 在 {names} 都有,请指明要用哪一家")
        else:
            vendor = hits[0]
    p = _P()[vendor]
    if model not in p["models"]:
        raise CredentialError(f"{p['label']} 这把 key 用不了 {model}")
    slot = _slot_of(cfg, vendor)
    presets = cfg.setdefault("model_presets", {})
    name = preset_name(vendor, model)
    existing = presets.get(name)
    if not isinstance(existing, dict):
        presets[name] = (_custom_preset(vendor, model) if slot == "custom"
                         else _extra_preset(vendor, model))
    else:
        if existing.get("provider", "custom") != slot:
            existing["provider"] = slot      # 手改过的错指预设:按厂商所在的槽纠正,否则会发到别家端点
        existing["model"] = model            # 正式名底下的 model 被手改过也纠正:选的是什么就发什么(#44,d11)
        _apply_params(existing, vendor)
    cfg.setdefault("agents", {}).setdefault("defaults", {})["modelPreset"] = name
    try:
        _atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        raise CredentialError(f"写不进去({exc.__class__.__name__}),请确认这台机器上这个文件夹可写") from None
    if home:
        try:
            os.remove(_switch_marker_path(home))
        except OSError:
            pass
    return models_status(cfg_path)


def key_path(home: str) -> str:
    return os.path.join(home, ".openDesign", "key.txt")


def env_var_name(cfg: dict) -> str:
    """配置里的 apiKey 引用的是哪个环境变量。

    写死变量名 = 两台 git-pull 机器上网关必死(它们引用的名字不一样)。
    """
    raw = (cfg.get("providers", {}).get("custom", {}) or {}).get("apiKey")
    m = _ENV_REF_RE.match(str(raw or "").strip())
    if not m:
        raise CredentialError("配置里的 apiKey 不是 ${变量} 形态,不知道该设哪个环境变量")
    return m.group(1)


def _hint(key: str) -> str:
    """给业主一个"确实是我那把"的凭证,而不是 key 本身。首尾各留一点。"""
    k = key.strip()
    if len(k) <= 12:
        return "已配置"
    return f"{k[:4]}…{k[-4:]}"


def read_key(home: str) -> str | None:
    try:
        with open(key_path(home), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _env_key(cfg: dict) -> str | None:
    """配置引用的那个环境变量**当前有没有值**。空串视为没有。

    为什么 status 必须看这一层:`bin/ds-nanobot.ps1` 是 **env 优先**
    (`if (-not $env:DS_LLM_KEY) { 读 key.txt }`),只看 key.txt 会让界面报告的状态
    和**真正生效的 key** 变成两回事 —— 业主要么被催填一把他不需要的 key,要么
    填完看见"新的末四位"而网关还在用旧那把。

    形状抄自 DeepSeek Harness 的 credentials seam(`docs/subsystems/credentials.zh.md`):
    `describe()` 报告**来源层**与 `writable`,且**空的存储值在任何地方都视为不存在**。
    """
    try:
        var = env_var_name(cfg)
    except CredentialError:
        return None                              # 配置里没有 ${引用} —— C 组管这件事
    return (os.environ.get(var) or "").strip() or None


@_scoped
def status(home: str, cfg_path: str | None = None) -> dict:
    """业主视角的当前状态。**永远不含 key 原文。**

    `source` / `writable` 回答的是"这把 key 从哪来、在这儿改得动吗",让界面能提前
    把被遮蔽的那一格渲染成只读,而不是让业主白填一次(见 `_env_key` 的说明)。
    这几个老字段只讲**主槽**(语义不变);每家一行的状态在 `vendors` 里(v11)。
    """
    key = read_key(home)
    provider = None
    env_key = None
    cfg = None
    if cfg_path and os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
            if not isinstance(cfg, dict):
                cfg = None
        except (OSError, ValueError):
            cfg = None
    if cfg is not None:
        provider = _current_provider(cfg)
        env_key = _env_key(cfg)
    # 启动脚本 env 优先 ⇒ **真正生效的是 env 那把**,hint 也必须报它,
    # 否则业主换完 key 会看见新的末四位、用着旧的 key,且无从发现。
    live = env_key or key
    return {"configured": live is not None, "provider": provider,
            "hint": _hint(live) if live else None,
            "source": "env" if env_key else ("file" if key else None),
            "writable": env_key is None,
            "vendors": _vendor_rows(home, cfg, provider, live)}


def _vendor_rows(home: str, cfg, primary, primary_key) -> list:
    """卡片上每家一行:configured(存了 key)/ live(网关手里有)/ active(正在用)/ pending(存了、等重启)。"""
    live_vendors = _live_vendors(cfg) if cfg is not None else []
    active = _preset_vendor(cfg, ds_model.active_preset_name(cfg)) if cfg is not None else None
    rows = []
    for vendor, meta in _P().items():
        if vendor == primary:
            k = primary_key
            is_live = k is not None
        else:
            k = read_extra_key(home, vendor)
            is_live = k is not None and vendor in live_vendors
        rows.append({"id": vendor, "label": meta["label"], "configured": k is not None,
                     "hint": _hint(k) if k else None, "live": is_live,
                     "active": bool(is_live and vendor == active),
                     "pending": bool(k is not None and not is_live)})
    return rows


def _atomic_write(path: str, body: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".key.", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp, 0o600)   # POSIX 上有意义;Windows 上真正管事的是 ACL(不声称)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@_scoped
def save(home: str, cfg_path: str, provider: str, key: str, *, multi: bool = False,
         switch: bool = True) -> dict:
    """存一家的 key。返回状态(**不含 key**)。

    `multi=False`(没有外壳:git-pull / Linux 开发机):**与今天逐字节相同** —— 主槽覆盖、
    改 apiBase/预设、写 key.txt。那两种启动器只认一个变量,配置里不许出现额外引用(v3)。

    `multi=True`(有外壳,ds_web 按 DS_SHELL_LOCK_PORT 判):
      · 主槽还没有 key(全新装机)或这家就是主槽那家 ⇒ 同上(主槽);
      · 否则 ⇒ 写 `keys/<厂商>.txt` + 「想换过去」标记,**配置一个字节不动**(v1)——
        此刻网关还没拿到这把 key,往配置里加引用就是"界面说换了、后台没换"。
        条目由外壳起网关时的 prepare_gateway 写,与注入 key 同一处。

    顺序是**先改配置、再写 key**:配置改坏了就整个失败,不留下"key 在但端点还是旧的"
    那种半成品(业主会拿着一把对的 key 连到错的地方,而报错长得像 key 不对)。
    """
    if provider not in _P():
        raise CredentialError(f"不认识的厂商:{provider}")
    k = (key or "").strip()
    if not k:
        raise CredentialError("API key 是空的")
    try:
        k.encode("latin-1")
    except UnicodeEncodeError:
        # 与登录口令那条同源:非 latin-1 的东西过不了 HTTP 头/环境变量这一路,
        # 现在说清楚,好过装完聊天时炸一句英文。
        raise CredentialError("API key 里有中文或特殊字符,请检查是不是复制多了") from None

    preset = _P()[provider]
    is_custom = bool(preset.get("custom"))
    if is_custom and not multi:
        # 自定义供应商只进额外槽(D2);没外壳的启动器只认主槽那一个变量
        raise CredentialError("这台机器是老装法(没有外壳),只能用内置厂商")
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        # 🔴 报错里带路径可以,**带 key 不行**(判据 a4)。
        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None

    if multi and isinstance(cfg, dict):
        primary = _current_provider(cfg)
        primary_has_key = (_env_key(cfg) or read_key(home)) is not None
        if is_custom or (primary_has_key and provider != primary):
            if not switch:
                # 设置页存 key(照 ZCode):不写「想换过去」、不换当前模型(D4,z7;顺带收掉 kimi-glm #60)
                try:
                    _atomic_write(extra_key_path(home, provider), k + "\n")
                except OSError as exc:
                    raise CredentialError(f"写不进去({exc.__class__.__name__}),"
                                          f"请确认这台机器上这个文件夹可写") from None
                return status(home, cfg_path)
            # 先写「想换过去」、再写 key;key 写不进去就把标记撤掉 ⇒ 失败的保存两样都不留
            # (第 1 轮 K3:反过来的话,标记写失败会留下一把业主以为没存上的 key,下次起网关悄悄激活)。
            marker = _switch_marker_path(home)
            try:
                _atomic_write(marker, provider + "\n")
            except OSError as exc:
                raise CredentialError(f"写不进去({exc.__class__.__name__}),"
                                      f"请确认这台机器上这个文件夹可写") from None
            try:
                _atomic_write(extra_key_path(home, provider), k + "\n")
            except OSError as exc:
                try:
                    os.remove(marker)
                except OSError:
                    pass
                raise CredentialError(f"写不进去({exc.__class__.__name__}),"
                                      f"请确认这台机器上这个文件夹可写") from None
            return status(home, cfg_path)

    var = env_var_name(cfg)                      # 会抛 CredentialError,由调用方翻译

    # 🔴 被环境变量遮蔽时**直接拒绝**,不许"表面成功":启动脚本 env 优先,
    #    写进 key.txt 根本不会生效,而界面会显示新 key 的末四位 —— 业主以为换好了。
    #    DSH 的 credentials seam 也是这么选的(那样的写入"表面成功而解析持续返回
    #    遮蔽值",所以直接拒绝)。放在改配置**之前**:拒绝就不该留下任何痕迹。
    if _env_key(cfg):
        raise CredentialError(
            f"当前的 key 由环境变量 {var} 提供,写在这里不会生效"
            f"(启动脚本读 {var} 优先于 key.txt)。要在界面里改,请先清掉那个环境变量。")

    custom = cfg.setdefault("providers", {}).setdefault("custom", {})
    endpoint_changed = _norm_base(custom.get("apiBase")) != _norm_base(preset["apiBase"])
    custom["apiBase"] = preset["apiBase"]
    custom["apiKey"] = "${%s}" % var             # 只留引用形态,原文永不进配置
    presets = cfg.setdefault("model_presets", {})
    name = preset_name(provider, preset["model"])
    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    # 主槽可能刚换了厂商:旧主槽的预设不许跟着发到新主槽(k11);端点真换了 ⇒ 绑在旧端点上的手写预设也不留(d3)。
    # 先对齐、再补这家的默认预设:反过来会把占着默认名、装着别的模型的那份先盖掉,当前模型就丢了(d7b)。
    _route_presets(cfg, endpoint_changed=endpoint_changed)
    ex = presets.get(name)
    if not (isinstance(ex, dict) and ex.get("provider") == "custom" and ex.get("model") == preset["model"]):
        presets[name] = _custom_preset(provider, preset["model"])
    # 当前模型能不动就不动(照 ZCode:不改用户原来的选择)。对齐之后还挂在主槽上的,一定是这家的模型 ⇒ 不动
    # (同一家换 key #38、这家从额外格挪进主槽 #52);当前写在 model 字段、端点没换 ⇒ 不替他设 modelPreset(#47)。
    # 当前没了(属于别家、被对齐删掉)或在别的格 ⇒ 存进主槽就是要用这家,切到这家默认(第 1 轮 K2)。
    cur = defaults.get("modelPreset")
    if cur is None and not endpoint_changed:
        pass
    elif not switch and isinstance(presets.get(cur), dict):
        pass                                     # 设置页存 key 不换当前模型(D4);当前还在就不动
    elif not (isinstance(presets.get(cur), dict) and presets[cur].get("provider") == "custom"):
        defaults["modelPreset"] = name

    try:
        _atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        _atomic_write(key_path(home), k + "\n")
    except OSError as exc:
        raise CredentialError(f"写不进去({exc.__class__.__name__}),"
                              f"请确认这台机器上这个文件夹可写") from None

    # 存进主槽 = 这一次就是要用这家:之前留下的「想换过去」作废,最后一次保存为准(第 1 轮 K2)
    try:
        os.remove(_switch_marker_path(home))
    except OSError:
        pass
    out = status(home, cfg_path)
    out["env_var"] = var                         # 给外壳重启时用;**不是凭据**
    return out


# ── 外壳起网关的那一刻(track opendesign-per-vendor-keys)────────────────────────
@_scoped
def prepare_gateway(home: str, cfg_path: str) -> dict:
    """外壳每次起/重启网关前调一次(`ds_shell.build_env`):让配置里的额外厂商条目
    与 key 文件对齐,返回**要注入网关的额外变量 → key**(主槽 key 仍走原来那条路)。

    这是额外条目**唯一的写入口**,而且与注入在同一处 ⇒ 配置引用的每个变量,网关都拿得到
    (判据 v4 把配置交给 nanobot 自己的加载器来答)。

    - 只有主槽一把 key 的老家:一个字节都不动(v12/v12b,零迁移);
    - 有第二家的 key:补条目、补齐每家有 key 的厂商目录里的预设;**挂在哪格只由 _route_presets 决定**;
    - 条目没有对应 key 了:删条目、删指向它的预设;当前模型悬空就回落主槽默认(v5);
    - 「想换过去」标记:那家此刻真有 key 才兑现,兑现后才删(v6/v6b);
    - **任何出错都不抛**(外壳不能因为这一步起不来):不写配置,只返回盘上配置里已引用、且读得到 key 的那些(v10)。
    """
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(cfg, dict):
        return {}
    try:
        new, marker_done = _synced_config(home, cfg)
    except Exception:          # 🔴 这一步坏了也不许拖垮启动:退回今天的单厂商
        return _extra_env(home, cfg)
    if new != cfg:
        try:
            _atomic_write(cfg_path, json.dumps(new, ensure_ascii=False, indent=2) + "\n")
        except OSError:
            return _extra_env(home, cfg)
        cfg = new
    if marker_done:
        try:
            os.remove(_switch_marker_path(home))
        except OSError:
            pass
    return _extra_env(home, cfg)


def _extra_env(home: str, cfg: dict) -> dict:
    """配置里每个额外条目引用的变量 → 它的 key。读不到 key 的不给(那种条目本不该在)。"""
    out = {}
    for vendor, entry in _extra_entries(cfg).items():
        m = _ENV_REF_RE.match(str(entry.get("apiKey") or "").strip())
        k = read_extra_key(home, vendor)
        if m and k:
            out[m.group(1)] = k
    return out


def _read_marker(home: str) -> str | None:
    try:
        with open(_switch_marker_path(home), encoding="utf-8") as fh:
            v = fh.read().strip()
    except (OSError, UnicodeDecodeError):
        return None
    return v if v in _P() else None


def _synced_config(home: str, cfg: dict):
    """算出对齐之后的配置(不写盘)。返回 (新配置, 标记是否兑现)。"""
    import copy
    primary = _current_provider(cfg)
    wanted = {v: k for v in _P() if v != primary for k in [read_extra_key(home, v)] if k}
    existing = {name for name in (cfg.get("providers") or {})
                if isinstance(name, str) and name.startswith(EXTRA_PREFIX)}
    marker = _read_marker(home)
    if not wanted and not existing and marker is None:
        # 只有主槽的老家:除了「预设发到自己那家」这一条,其余不碰;本来就对齐的配置一个字节不变(v12/v12b)
        new = copy.deepcopy(cfg)
        _route_presets(new)
        if new != cfg:
            _fallback_if_dangling(new)
        return new, False

    new = copy.deepcopy(cfg)
    providers = new.setdefault("providers", {})
    presets = new.setdefault("model_presets", {})

    # ① 没 key 的额外条目删掉(我们拥有 od_ 这个前缀);指向它的预设由下面的对齐删
    for name in list(existing):
        if name[len(EXTRA_PREFIX):] not in wanted:
            providers.pop(name, None)

    # ② 有 key 的额外厂商补条目
    for vendor in wanted:
        name = extra_provider_name(vendor)
        entry = dict(providers.get(name)) if isinstance(providers.get(name), dict) else {}
        entry["apiKey"] = "${%s}" % extra_var_name(vendor)
        entry["apiBase"] = _P()[vendor]["apiBase"]
        providers[name] = entry

    # ③ 每家有 key 的厂商(含主槽那家),目录里的模型都有预设(菜单里的每一项都能直接选);**挂在哪格不在这里管**
    for vendor in ([primary] if primary is not None else []) + list(wanted):
        for model in _P()[vendor]["models"]:
            presets.setdefault(preset_name(vendor, model),
                               _custom_preset(vendor, model) if vendor == primary else _extra_preset(vendor, model))

    # ④ 挂在哪只由这一处决定:每份预设只发到它主人那家,主人没格就删(见 _route_presets)
    _route_presets(new)

    # ⑤ 「想换过去」:那家此刻真有 key(额外槽有条目,或就是主槽且主槽有 key)才兑现
    defaults = new.setdefault("agents", {}).setdefault("defaults", {})
    marker_done = False
    if marker is not None:
        if marker in wanted or (marker == primary and read_key(home)):
            target = preset_name(marker, _P()[marker]["model"])
            if target in presets:
                defaults["modelPreset"] = target
                marker_done = True

    _fallback_if_dangling(new)
    return new, marker_done


def _fallback_if_dangling(cfg: dict) -> None:
    """⑥ 当前模型悬空(指向刚删的预设)⇒ 回落主槽默认;nanobot 对悬空的 modelPreset 直接拒绝加载。
    同名模型各家一份预设,丢了 key 的那家的预设在 _route_presets 删掉 ⇒ 这里回落,不会落到另一家同名预设上(k9)。"""
    defaults = (cfg.get("agents") or {}).get("defaults")
    presets = cfg.get("model_presets")
    if not isinstance(defaults, dict) or not isinstance(presets, dict):
        return
    if defaults.get("modelPreset") and defaults["modelPreset"] not in presets:
        primary = _current_provider(cfg)
        fallback = preset_name(primary, _P()[primary]["model"]) if primary else None
        if fallback and fallback not in presets:
            presets[fallback] = _custom_preset(primary, _P()[primary]["model"])
        if fallback:
            defaults["modelPreset"] = fallback
        elif defaults.get("model") or not presets:
            defaults.pop("modelPreset")          # 主槽认不出(机主自配端点):回到他自己的 model 字段,不替他挑一份(#48)
        else:
            defaults["modelPreset"] = next(iter(presets))


# ── 设置页(照 ZCode,track opendesign-zcode-model-settings)──────────────────────────
def _read_cfg(cfg_path: str) -> dict:
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None
    if not isinstance(cfg, dict):
        raise CredentialError(f"配置读不出来:{cfg_path}")
    return cfg


def _write_cfg(cfg_path: str, cfg: dict) -> None:
    try:
        _atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        raise CredentialError(f"写不进去({exc.__class__.__name__}),请确认这台机器上这个文件夹可写") from None


def _in_use(cfg: dict) -> tuple:
    """(正在用的厂商, 正在用的模型)。"""
    return _preset_vendor(cfg, ds_model.active_preset_name(cfg)), ds_model.resolve_model(cfg)


def _known(provider) -> dict:
    if not isinstance(provider, str) or provider not in _P():
        raise CredentialError(f"不认识的厂商:{provider}")
    return _P()[provider]


@_scoped
def providers_view(home: str, cfg_path: str, *, multi: bool = True) -> dict:
    """设置页要的一切(**永不含 key 原文**,只回末四位提示):每家一行 + 模型列表 + 当前在用。"""
    try:
        cfg = _read_cfg(cfg_path)
    except CredentialError:
        cfg = None
    rows = {r["id"]: r for r in status(home, cfg_path)["vendors"]}
    presets = (cfg or {}).get("model_presets") or {}
    out = []
    for vid, meta in _P().items():
        r = rows.get(vid, {})
        models = []
        for m in meta["models"]:
            cw = (meta.get("contextWindow") or {}).get(m)
            p = presets.get(preset_name(vid, m))
            if cw is None and isinstance(p, dict):
                cw = p.get("contextWindowTokens") or p.get("context_window_tokens")
            models.append({"id": m, "label": m, "builtin": m in meta.get("builtinModels", []),
                           "contextWindow": cw if type(cw) is int else None})
        out.append({"id": vid, "label": meta["label"], "kind": "custom" if meta.get("custom") else "builtin",
                    "apiBase": meta["apiBase"], "keyUrl": meta.get("keyUrl"),
                    "configured": bool(r.get("configured")), "hint": r.get("hint"),
                    "live": bool(r.get("live")), "active": bool(r.get("active")), "pending": bool(r.get("pending")),
                    "enabled": bool(meta.get("enabled", True)), "models": models})
    current = None
    if cfg is not None:
        vendor, model = _in_use(cfg)
        if vendor:
            current = {"provider": vendor, "model": model}
    return {"providers": out, "current": current, "multi": bool(multi)}


def _check_model_id(model) -> str:
    m = (model or "").strip() if isinstance(model, str) else ""
    if not _MODEL_ID_RE.match(m):
        raise CredentialError("模型 ID 不对:只能用字母、数字和 . _ - : / +,不超过 128 个字符")
    return m


def _check_tokens(tokens) -> int:
    if type(tokens) is not int or not 1024 <= tokens <= 10_000_000:
        raise CredentialError("上下文窗口要填 1024 到 10000000 之间的整数")
    return tokens


@_scoped
def add_model(home: str, cfg_path: str, provider: str, model: str, *, context_window=None) -> dict:
    """「添加模型」:进这家的目录(登记),菜单与路由从此认它。"""
    meta = _known(provider)
    model = _check_model_id(model)
    if model in meta["models"]:
        raise CredentialError(f"{meta['label']} 已经有 {model} 了")
    if context_window is not None:
        context_window = _check_tokens(context_window)
    reg = _load_registry(home)
    if meta.get("custom"):
        for cp in reg["customProviders"]:
            if cp["id"] == provider:
                cp["models"].append(model)
    else:
        reg["extraModels"].setdefault(provider, []).append(model)
    if context_window is not None:
        reg["contextWindow"][f"{provider}/{model}"] = context_window
    _save_registry(home, reg)
    with catalog_scope(home):
        return providers_view(home, cfg_path)


def _drop_presets(cfg: dict, provider: str, models) -> None:
    """删掉我们替 provider 起的、装着这些模型的预设(按**当前范围的目录**算名字 —— 调用方在改登记之前调)。"""
    presets = cfg.get("model_presets")
    if not isinstance(presets, dict):
        return
    slots = {extra_provider_name(provider)}
    if provider == _current_provider(cfg):
        slots.add("custom")
    names = {preset_name(provider, m) for m in models}
    for n in list(presets):
        p = presets[n]
        if isinstance(p, dict) and n in names and p.get("provider") in slots:
            presets.pop(n)


@_scoped
def remove_model(home: str, cfg_path: str, provider: str, model: str) -> dict:
    meta = _known(provider)
    if model not in meta["models"]:
        raise CredentialError(f"{meta['label']} 没有 {model}")
    if model in meta.get("builtinModels", []):
        raise CredentialError(f"{model} 是内置模型,不能删")
    cfg = _read_cfg(cfg_path)
    if _in_use(cfg) == (provider, model):
        raise CredentialError(f"{model} 正在用,先在聊天框里换一个模型再删")
    _drop_presets(cfg, provider, [model])
    reg = _load_registry(home)
    if meta.get("custom"):
        for cp in reg["customProviders"]:
            if cp["id"] == provider:
                if len(cp["models"]) <= 1:
                    raise CredentialError("自定义供应商至少要留一个模型")
                cp["models"] = [m for m in cp["models"] if m != model]
    else:
        reg["extraModels"][provider] = [m for m in reg["extraModels"].get(provider, []) if m != model]
    reg["contextWindow"].pop(f"{provider}/{model}", None)
    _save_registry(home, reg)
    _write_cfg(cfg_path, cfg)
    with catalog_scope(home):
        return providers_view(home, cfg_path)


@_scoped
def set_context_window(home: str, cfg_path: str, provider: str, model: str, tokens) -> dict:
    """「编辑模型配置 → 上下文窗口」:记进登记,已有的预设当场改(nanobot 每句前重读配置,下一句生效)。"""
    meta = _known(provider)
    if model not in meta["models"]:
        raise CredentialError(f"{meta['label']} 没有 {model}")
    tokens = _check_tokens(tokens)
    reg = _load_registry(home)
    reg["contextWindow"][f"{provider}/{model}"] = tokens
    _save_registry(home, reg)
    with catalog_scope(home):
        cfg = _read_cfg(cfg_path)
        p = (cfg.get("model_presets") or {}).get(preset_name(provider, model))
        if isinstance(p, dict):
            _apply_params(p, provider)
            _write_cfg(cfg_path, cfg)
        return providers_view(home, cfg_path)


@_scoped
def set_enabled(home: str, cfg_path: str, provider: str, enabled: bool) -> dict:
    """启用 / 禁用(D3):只管菜单里藏不藏、能不能选;路由与 key 一概不动。正在用的那家不许禁用。"""
    meta = _known(provider)
    if not enabled and _in_use(_read_cfg(cfg_path))[0] == provider:
        raise CredentialError(f"{meta['label']} 正在用,先在聊天框里换到别家的模型再禁用")
    reg = _load_registry(home)
    dis = [v for v in reg["disabled"] if v != provider]
    if not enabled:
        dis.append(provider)
    reg["disabled"] = dis
    _save_registry(home, reg)
    with catalog_scope(home):
        return providers_view(home, cfg_path)


def _check_base(api_base) -> str:
    base = _norm_base(api_base)
    u = urllib.parse.urlparse(base)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise CredentialError("Base URL 要以 http:// 或 https:// 开头,例如 https://api.example.com/v1")
    return base


@_scoped
def add_custom_provider(home: str, cfg_path: str, *, label: str, api_base: str, models, key=None,
                        multi: bool = True) -> str:
    """「添加供应商」(自定义端点):只走 OpenAI 兼容格式、只进额外槽(D2)。返回新厂商 id。"""
    if not multi:
        raise CredentialError("这台机器是老装法(没有外壳),加不了自定义供应商")
    label = (label or "").strip() if isinstance(label, str) else ""
    if not label or len(label) > 40:
        raise CredentialError("供应商名称要填,不超过 40 个字")
    base = _check_base(api_base)
    for v, meta in _P().items():
        if _norm_base(meta["apiBase"]) == base:
            raise CredentialError(f"这个地址已经是「{meta['label']}」了,直接在它那页配置")
    if not isinstance(models, list) or not models:
        raise CredentialError("添加供应商前,请至少添加一个模型")
    ids = []
    for m in models:
        m = _check_model_id(m)
        if m not in ids:
            ids.append(m)
    reg = _load_registry(home)
    used = {cp["id"] for cp in reg["customProviders"]}
    n = 1
    while f"{CUSTOM_PREFIX}{n}" in used or f"{CUSTOM_PREFIX}{n}" in PROVIDERS:
        n += 1
    pid = f"{CUSTOM_PREFIX}{n}"
    reg["customProviders"].append({"id": pid, "label": label, "apiBase": base, "models": ids})
    _save_registry(home, reg)
    if key:
        with catalog_scope(home):
            save(home, cfg_path, pid, key, multi=True, switch=False)
    return pid


@_scoped
def remove_custom_provider(home: str, cfg_path: str, provider: str) -> dict:
    meta = _known(provider)
    if not meta.get("custom"):
        raise CredentialError(f"{meta['label']} 是内置厂商,不能删")
    cfg = _read_cfg(cfg_path)
    if _in_use(cfg)[0] == provider:
        raise CredentialError(f"{meta['label']} 正在用,先在聊天框里换到别家的模型再删")
    slot = extra_provider_name(provider)
    (cfg.get("providers") or {}).pop(slot, None)
    presets = cfg.get("model_presets")
    if isinstance(presets, dict):
        for n in list(presets):
            if isinstance(presets[n], dict) and presets[n].get("provider") == slot:
                presets.pop(n)
    reg = _load_registry(home)
    reg["customProviders"] = [cp for cp in reg["customProviders"] if cp["id"] != provider]
    reg["disabled"] = [v for v in reg["disabled"] if v != provider]
    reg["contextWindow"] = {k: v for k, v in reg["contextWindow"].items() if not k.startswith(provider + "/")}
    _save_registry(home, reg)
    _write_cfg(cfg_path, cfg)
    try:
        os.remove(extra_key_path(home, provider))
    except OSError:
        pass
    with catalog_scope(home):
        return providers_view(home, cfg_path)


def _vendor_error(body: bytes) -> str:
    try:
        obj = json.loads(body or b"{}")
    except ValueError:
        return (body or b"")[:200].decode("utf-8", "replace").strip()
    err = obj.get("error") if isinstance(obj, dict) else None
    if isinstance(err, dict) and isinstance(err.get("message"), str):
        return err["message"]
    if isinstance(err, str):
        return err
    if isinstance(obj, dict) and isinstance(obj.get("message"), str):
        return obj["message"]
    return ""


@_scoped
def test_model(home: str, cfg_path: str, provider: str, model: str, *, timeout: float = 20) -> dict:
    """模型列表每行的「测试」:用这家的 key **直接**请求厂商一次最小对话(不经网关 ⇒ 存完 key 立刻能测)。
    返回 {ok, message};message 里**永不带 key**。"""
    meta = _known(provider)
    model = _check_model_id(model)
    try:
        cfg = _read_cfg(cfg_path)
    except CredentialError:
        cfg = {}
    if provider == _current_provider(cfg) and not meta.get("custom"):
        k = _env_key(cfg) or read_key(home)
    else:
        k = read_extra_key(home, provider)
    if not k:
        return {"ok": False, "message": "还没填 API Key"}
    base = _norm_base(meta["apiBase"])
    body = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16}
    body.update(meta.get("presetParams") or {})
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
    host = urllib.parse.urlparse(base).hostname or ""
    handlers = [urllib.request.ProxyHandler({})] if host in ("127.0.0.1", "localhost", "::1") else []
    opener = urllib.request.build_opener(*handlers)

    def scrub(text: str) -> str:
        return (text or "").replace(k, "***")

    try:
        with opener.open(req, timeout=timeout) as resp:
            resp.read(65536)
        return {"ok": True, "message": f"{model} 连接成功"}
    except urllib.error.HTTPError as exc:
        detail = scrub(_vendor_error(exc.read(65536)))
        return {"ok": False, "message": f"{exc.code} {detail}".strip()}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"ok": False, "message": scrub(f"连不上 {host}:{reason}")}
