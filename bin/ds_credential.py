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
"""
from __future__ import annotations

import json
import os
import re
import tempfile

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


PROVIDERS = {
    # 名字是给界面看的;端点/模型是给网关用的。
    "mimo": {"label": "MiMo(小米)", **_template_presets()},
    # 🔴 2026-08-15 现拉 `GET https://api.deepseek.com/models` 核过:
    #    只剩 v4-flash / v4-pro,老的 deepseek-chat / deepseek-reasoner 已下架。
    #    **这是一条会过期的事实**,判据 b4 把它钉住,过期时会红。
    "deepseek": {"label": "DeepSeek 官方", "apiBase": "https://api.deepseek.com/v1",
                 "model": "deepseek-v4-flash"},
}


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
    """
    key = read_key(home)
    provider = None
    env_key = None
    if cfg_path and os.path.isfile(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            base = (cfg.get("providers", {}).get("custom", {}) or {}).get("apiBase", "")
            for name, preset in PROVIDERS.items():
                if base and base == preset["apiBase"]:
                    provider = name
                    break
            env_key = _env_key(cfg)
        except (OSError, ValueError):
            provider = None
    # 启动脚本 env 优先 ⇒ **真正生效的是 env 那把**,hint 也必须报它,
    # 否则业主换完 key 会看见新的末四位、用着旧的 key,且无从发现。
    live = env_key or key
    return {"configured": live is not None, "provider": provider,
            "hint": _hint(live) if live else None,
            "source": "env" if env_key else ("file" if key else None),
            "writable": env_key is None}


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


def save(home: str, cfg_path: str, provider: str, key: str) -> dict:
    """写 key.txt + 把厂商写进配置。返回状态(**不含 key**)。

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
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # 🔴 报错里带路径可以,**带 key 不行**(判据 a4)。
        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None

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
