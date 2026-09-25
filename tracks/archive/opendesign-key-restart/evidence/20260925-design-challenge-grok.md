我先读快照 diff 和仓库里跟存 key、网关重启、配置解析相关的代码，再按业主目标核对拟议方案会在哪一步失败。
Direction: 已经连上的网关不要杀；key 仍只进文件，由网关子进程在解析 `${VAR}` 之前写进本进程的 `os.environ`，继续用 nanobot 自己的 `_env_replace`。网关没在听时只拉起一次。设置页模型行点击走已经有的 `select_model`。

Core bet: 业主看见的「连接不上」和右下角按钮消失，是 `restart_gateway` 把正在听的 websocket 拆掉，新进程在 Windows 上又进不了 Python。下一句要用新 key，靠活进程重读文件，不靠再起一个进程。

How it works: `save()` 把 key 文件和只含 `${VAR}` 的配置条目一起写上。网关那条子进程（`bin/ds_shell.py` 里 `python -m nanobot gateway`）在 `resolve_config_env_vars` 之前，用 `key.txt` / `keys/<厂商>.txt` 填本进程环境变量。websocket 已在听就不发重启帧。`startup_plan` 没起网关时才 start 一次。模型列表的行点击 `POST` 现成的选模型接口。

Best at: 聊天已经连着时换 key、换一家，连接和右下角按钮都不掉，下一句用文件里的 key。

Sacrifices: 网关入口仍要加一层进程内同步。第一次把网关拉起来，仍可能撞上「进程在、Python 一直不初始化」。定时任务和别的通道不在这次范围内。

Blind spots in the brief: 「完全不重启」盖不住第一次没有网关，也盖不住设置页模型行不能点。配置里一旦有条目，界面就把这家当成网关已经拿到 key。那次实验只走了 Linux 上的 websocket。

Smallest first step: 在已经连上的安装版上，存第二家 key 时不发重启帧，只在网关进程里把 key 文件写入 `os.environ`（不替换 `_env_replace`），马上发一条 websocket，看请求带的是文件里的新 key 还是启动时的旧环境变量。另一次：无 key 冷启动后只保存、不拉起，看聊天是否仍是连不上。

## 1. 完全照做之后，业主目标仍会失败

装好第一次打开时没有 key，外壳只起工作台、不起网关（`bin/ds_shell_core.py` 的 `startup_plan`，1128–1138 行）。业主在设置里保存 key 之后，拟议不再重启，于是没有任何东西去把网关拉起来。新对话一直显示「连接不上, gateway 可能没在跑」（`web/src/chat/ChatPage.tsx` 973 行），右下角换模型按钮只在 `connected` 时渲染（同文件 791–793 行），所以仍然没有。必须退出再打开。已经连着时，设置页保存走 `switch=False`，只写 key、不改当前模型（`bin/ds_credential.py` 771–778 行）；模型列表每一行仍只有「测试」「编辑」（`web/src/settings/ModelSettings.tsx` 427–433 行）。下一句还是原来那家，业主在这张列表上依然没有可点的切换。

## 2. 这个前提若为假，就得推倒重做

每条入站消息都会重新 `resolve_config_env_vars`，并且解析发生在模块全局 `_env_replace` 上，签名里带的是解析后的 `api_key`。这在现码里成立：`nanobot/agent/loop.py` 1255 行调用 `_refresh_provider_snapshot`，`nanobot/providers/factory.py` 251–260 行与 213 行，`nanobot/config/loader.py` 102 行与 143–150 行。若 nanobot 只在进程启动时解析一次，或签名里仍是未展开的 `${VAR}`，替换 `_env_replace` 对下一句无效，整条「不重启就能用」要重做。补丁必须打在网关子进程里；外壳是另一个进程（`bin/ds_shell.py` 251 行）。安装包里的启动器有没有接上这条 argv：未核实。

## 3. 更稳的方向，以及能把它和拟议方案分开的最小实验

上面的 Direction 更稳：活进程只刷新 `os.environ`，不替换 nanobot 的私有函数；没在听时负责拉起；设置页点模型行。分辨实验就是 Smallest first step 那两次。紧接着的 websocket 若已带文件里的新 key，私有函数替换就是多余的；冷启动只保存却仍连不上，就说明「一律不重启」留着业主现在的那块空白。

结论: 需改
