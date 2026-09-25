# 方案挑战:OpenDesign「存 key 后不用重启就能用」

你是独立的方案挑战者。仓库在当前目录(design-studio,产品名 OpenDesign:室内设计师用的本地桌面助手,
Electron 窗口 + Python 管家 `bin/ds_host.py` 拉起两条子进程:nanobot 网关 与 工作台 `bin/ds_web.py`)。
业主不是程序员,Windows 11 上用安装版。**不要联网;不要改任何文件;不要读 `tracks/*/verify.md`、`tracks/*/design.md` 与任何 `*my-review*` / `*my-direction*` 文件。**

## 业主原话(09-25)

「我切换模型填入api key之后 新对话一直显示链接不上gateway」
「重启之后可以了」
「但是我换模型列表没有可以点击的地方，只有一个测试一个编辑。。你让我怎么换模型呢，聊天列表只要我填一次apikey之后就一直显示连接不上gateway 然后输入框右下角没有模型选择框了」
「zcode是怎么做到切换模型直接能用的」
「那就直接改成zcode那样不就好了吗哈哈哈」

## 现在的行为(已核实的事实)

- 设置页存某家的 key → `POST /api/llm/providers/key` → `ds_credential.save(multi=True, switch=False)`:
  第二家起写 `.openDesign/keys/<厂商>.txt`,**配置不动**;然后 `ds_web.ds_shell_bridge_restart()` 经单实例锁通道请外壳重启网关。
- 外壳 `ds_shell.restart_gateway()` → `build_env()` → `ds_credential.prepare_gateway()`(此刻才往 config 写 `providers.od_<厂商>` 条目,
  apiKey 只写 `${DS_LLM_KEY_<厂商>}` 引用)→ key 以环境变量注入 → `Supervisor.restart()` 杀旧网关、起新网关。
- nanobot 0.2.2(钉版本)只支持 `${VAR}` 从**进程环境变量**解析(`nanobot/config/loader.py` 的 `_ENV_REF_PATTERN` / `_env_replace`);
  它每条入站消息前重读配置(`agent/loop.py` `_refresh_provider_snapshot` → `providers/factory.py` `load_provider_snapshot`),
  `provider_signature` 里含解析后的 api_key。nanobot 源码在 `/root/.venvs/design-studio/lib/python3.12/site-packages/nanobot/`
  (读得到就读;读不到请明说,别猜)。
- 故障证据:业主真机存 key 后新网关 2.5 分钟零日志、始终没起来,聊天「连接不上」,输入框换模型按钮只在连上时显示所以消失;退出重开就好。
  云端 Windows 复现:新网关进程存在、300 秒都没进入 Python 初始化;Linux 上同一路径栽在另一处(外壳的端口空闲试探被 TIME_WAIT 挡)。
- ZCode(智谱开源桌面客户端)的做法:个人 provider 配置文件(含 key)由运行中的进程每 1 秒轮询重读,存了就能用,不重启任何进程。
- 约束:**key 原文永不写进配置文件**(配置会进日志、截图、收据;见 `bin/ds_credential.py` 模块头);key 不回显给浏览器;报错不带 key。

## 拟议的改变(被挑战的对象)

用户层:存完 key,不重启任何东西,下一句话就能用那家;换模型按钮一直在。
机制:网关改由一个小启动器拉起,启动器在 nanobot 读配置前替换 `nanobot.config.loader._env_replace`,
让 `${主槽变量}` / `${DS_LLM_KEY_<厂商>}` 每次解析都现读对应 key 文件(读不到才落回环境变量);
`save()` 当场把配置条目与 key 文件一起写好,不再请求重启。配置里仍只有 `${VAR}` 引用。
一次本机实验(Linux,真 nanobot 网关不重启,假厂商记录请求):换主槽 key、新加 DeepSeek 并切过去、切回,
每一句都带上了当时文件里的 key,网关日志无 `Failed to refresh provider config`。实验只走了 websocket 聊天这一条路径。

## 请回答(先从业主目标推演,再挑机制;没有就说没有,不必凑)

1. 这个改变**完全照做**之后,业主的目标仍会怎样失败?(具体到操作步骤与会看到什么)
2. 哪个前提若为假,就得推倒重做?请尽量读代码核实,给出 `文件:行` 证据;核实不了的标「未核实」。
3. 有没有更简单或更稳的方向?用什么**最小实验**能分辨它和拟议方案?

输出:按 1/2/3 分节,每条一句结论 + 证据;最后一行写 `结论: 可行 / 需改 / 不可行`。
