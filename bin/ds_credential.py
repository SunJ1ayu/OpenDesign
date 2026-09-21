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

import json
import os
import re
import tempfile

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
    "mimo": {"label": "MiMo(小米)", **_template_presets(), "models": _template_models()},
    # 🔴 2026-08-15 现拉 `GET https://api.deepseek.com/models` 核过:
    #    只剩 v4-flash / v4-pro,老的 deepseek-chat / deepseek-reasoner 已下架。
    #    **这是一条会过期的事实**,判据 b4 把它钉住,过期时会红。
    "deepseek": {"label": "DeepSeek 官方", "apiBase": "https://api.deepseek.com/v1",
                 "model": "deepseek-v4-flash", "models": ["deepseek-v4-flash", "deepseek-v4-pro"]},
}


def _norm_base(base) -> str:
    """端点比较前去掉首尾空白与尾斜杠:`…/v1/` 和 `…/v1` 是同一家(挑战腿指出的 F5)。"""
    return str(base or "").strip().rstrip("/")


def _vendor_by_base(base):
    b = _norm_base(base)
    if not b:
        return None
    for name, preset in PROVIDERS.items():
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
            if vendor in PROVIDERS:
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
        return vendor if vendor in PROVIDERS else None
    return _current_provider(cfg)


def _slot_of(cfg: dict, vendor: str) -> str:
    return "custom" if vendor == _current_provider(cfg) else extra_provider_name(vendor)


def _custom_preset(vendor: str, model: str) -> dict:
    # 主槽预设沿用老形状(含 apiBase —— nanobot 不读它,但 lm5 与老配置都是这个样子)
    return {"label": model, "provider": "custom", "model": model, "apiBase": PROVIDERS[vendor]["apiBase"]}


def models_status(cfg_path: str) -> dict:
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
    groups = [{"provider": v, "label": PROVIDERS[v]["label"],
               "models": [{"id": m, "label": m} for m in PROVIDERS[v]["models"]]} for v in live]
    out.update(provider=active, label=PROVIDERS[active]["label"], current=ds_model.resolve_model(cfg),
               models=groups[live.index(active)]["models"], groups=groups)
    return out


def select_model(cfg_path: str, model, provider=None) -> dict:
    """把当前模型换成 `model`:写 agents.defaults.modelPreset(判据 lm2~lm6、v8)。

    - 只许**网关手里有 key 的厂商**目录里的 id(别家的 / 随便的串 / 空 ⇒ CredentialError,配置不动);
      `provider` 给了就只在那一家里找(前端点哪一行就带哪一家,不靠模型名反查);
    - 目录里有、配置里还没有这个预设 ⇒ 按该厂商所在的槽补建(DeepSeek 的 v4-pro 就是这样);
    - 其余字段一个不碰,key 文件不碰,不重启网关:nanobot 每条入站消息前重读配置
      (agent/loop.py _refresh_provider_snapshot → providers/factory.py load_provider_snapshot),下一句起生效。
      跨厂商也一样 —— 真网关实验 p2 / 判据 l1 证实下一句就换到另一家的端点和 key。
    配置读不出 ⇒ 拒绝,**不替业主建一份配置**。
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
    if provider is not None:
        if provider not in PROVIDERS:
            raise CredentialError(f"不认识的厂商:{provider}")
        if provider not in live:
            raise CredentialError(f"{PROVIDERS[provider]['label']} 的 key 后台还没拿到,"
                                  "等后台重启好再选(或先在「AI 模型 key」里填)")
        vendor = provider
    else:
        hits = [v for v in live if model in PROVIDERS[v]["models"]]
        if not hits:
            waiting = [v for v in PROVIDERS if v not in live and model in PROVIDERS[v]["models"]]
            if waiting:
                raise CredentialError(f"{PROVIDERS[waiting[0]]['label']} 的 key 后台还没拿到,"
                                      "等后台重启好再选(或先在「AI 模型 key」里填)")
            raise CredentialError(f"{PROVIDERS[live[0]]['label']} 这把 key 用不了 {model}")
        vendor = hits[0]
    p = PROVIDERS[vendor]
    if model not in p["models"]:
        raise CredentialError(f"{p['label']} 这把 key 用不了 {model}")
    slot = _slot_of(cfg, vendor)
    presets = cfg.setdefault("model_presets", {})
    existing = presets.get(model)
    if not isinstance(existing, dict):
        presets[model] = (_custom_preset(vendor, model) if slot == "custom"
                          else {"label": model, "provider": slot, "model": model})
    elif existing.get("provider", "custom") != slot:
        existing["provider"] = slot          # 手改过的错指预设:按厂商所在的槽纠正,否则会发到别家端点
    cfg.setdefault("agents", {}).setdefault("defaults", {})["modelPreset"] = model
    try:
        _atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        raise CredentialError(f"写不进去({exc.__class__.__name__}),请确认这台机器上这个文件夹可写") from None
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
    for vendor, meta in PROVIDERS.items():
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


def save(home: str, cfg_path: str, provider: str, key: str, *, multi: bool = False) -> dict:
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
    if provider not in PROVIDERS:
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

    preset = PROVIDERS[provider]
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        # 🔴 报错里带路径可以,**带 key 不行**(判据 a4)。
        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None

    if multi and isinstance(cfg, dict):
        primary = _current_provider(cfg)
        primary_has_key = (_env_key(cfg) or read_key(home)) is not None
        if primary_has_key and provider != primary:
            try:
                _atomic_write(extra_key_path(home, provider), k + "\n")
                _atomic_write(_switch_marker_path(home), provider + "\n")
            except OSError as exc:
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
    custom["apiBase"] = preset["apiBase"]
    custom["apiKey"] = "${%s}" % var             # 只留引用形态,原文永不进配置
    presets = cfg.setdefault("model_presets", {})
    presets[preset["model"]] = {"label": preset["model"], "provider": "custom",
                                "model": preset["model"], "apiBase": preset["apiBase"]}
    cfg.setdefault("agents", {}).setdefault("defaults", {})["modelPreset"] = preset["model"]

    try:
        _atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        _atomic_write(key_path(home), k + "\n")
    except OSError as exc:
        raise CredentialError(f"写不进去({exc.__class__.__name__}),"
                              f"请确认这台机器上这个文件夹可写") from None

    out = status(home, cfg_path)
    out["env_var"] = var                         # 给外壳重启时用;**不是凭据**
    return out


# ── 外壳起网关的那一刻(track opendesign-per-vendor-keys)────────────────────────
def prepare_gateway(home: str, cfg_path: str) -> dict:
    """外壳每次起/重启网关前调一次(`ds_shell.build_env`):让配置里的额外厂商条目
    与 key 文件对齐,返回**要注入网关的额外变量 → key**(主槽 key 仍走原来那条路)。

    这是额外条目**唯一的写入口**,而且与注入在同一处 ⇒ 配置引用的每个变量,网关都拿得到
    (判据 v4 把配置交给 nanobot 自己的加载器来答)。

    - 只有主槽一把 key 的老家:一个字节都不动(v12/v12b,零迁移);
    - 有第二家的 key:补条目、把那家目录里的模型预设指到它的条目;主槽那家的目录预设补齐并指回 custom;
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
    return v if v in PROVIDERS else None


def _synced_config(home: str, cfg: dict):
    """算出对齐之后的配置(不写盘)。返回 (新配置, 标记是否兑现)。"""
    import copy
    primary = _current_provider(cfg)
    wanted = {v: k for v in PROVIDERS if v != primary for k in [read_extra_key(home, v)] if k}
    existing = {name for name in (cfg.get("providers") or {})
                if isinstance(name, str) and name.startswith(EXTRA_PREFIX)}
    marker = _read_marker(home)
    if not wanted and not existing and marker is None:
        return cfg, False                       # 只有主槽的老家:不碰(零迁移)

    new = copy.deepcopy(cfg)
    providers = new.setdefault("providers", {})
    presets = new.setdefault("model_presets", {})

    # ① 没 key 的额外条目连同指向它的预设一起删(我们拥有 od_ 这个前缀)
    for name in list(existing):
        vendor = name[len(EXTRA_PREFIX):]
        if vendor not in wanted:
            providers.pop(name, None)
            for pname in [n for n, p in presets.items() if isinstance(p, dict) and p.get("provider") == name]:
                presets.pop(pname, None)

    # ② 有 key 的额外厂商:条目 + 目录里每个模型的预设都指向它
    for vendor in wanted:
        name = extra_provider_name(vendor)
        entry = providers.get(name) if isinstance(providers.get(name), dict) else {}
        entry = dict(entry)
        entry["apiKey"] = "${%s}" % extra_var_name(vendor)
        entry["apiBase"] = PROVIDERS[vendor]["apiBase"]
        providers[name] = entry
        for model in PROVIDERS[vendor]["models"]:
            p = presets.get(model)
            if isinstance(p, dict):
                p["provider"] = name
                p.pop("apiBase", None)          # 老形状残留的端点字段 nanobot 不读,留着只会误导人
            else:
                presets[model] = {"label": model, "provider": name, "model": model}

    # ③ 主槽那家:目录里的模型都有预设、且都指回 custom(修掉换过厂商后留下的错指)
    if primary is not None and wanted:
        for model in PROVIDERS[primary]["models"]:
            p = presets.get(model)
            if isinstance(p, dict):
                if p.get("provider", "custom") != "custom":
                    p["provider"] = "custom"
            else:
                presets[model] = _custom_preset(primary, model)

    # ④ 「想换过去」:那家此刻真有 key(额外槽有条目,或就是主槽且主槽有 key)才兑现
    defaults = new.setdefault("agents", {}).setdefault("defaults", {})
    marker_done = False
    if marker is not None:
        if marker in wanted or (marker == primary and read_key(home)):
            target = PROVIDERS[marker]["model"]
            if target in presets:
                defaults["modelPreset"] = target
                marker_done = True

    # ⑤ 当前模型悬空(指向刚删的预设)⇒ 回落主槽默认;nanobot 对悬空的 modelPreset 直接拒绝加载
    if defaults.get("modelPreset") and defaults["modelPreset"] not in presets:
        fallback = PROVIDERS[primary]["model"] if primary else None
        if fallback and fallback not in presets:
            presets[fallback] = _custom_preset(primary, fallback)
        if fallback:
            defaults["modelPreset"] = fallback
        elif presets:
            defaults["modelPreset"] = next(iter(presets))
    return new, marker_done
