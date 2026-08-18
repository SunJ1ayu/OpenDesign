# 判据 ⑭ 的注入点:把 `mapfile` 这个内建关掉,模拟 bash<4 / 精简用户态。
# 走 BASH_ENV —— 闸脚本是 `#!/usr/bin/env bash` 起的**非交互** shell,bash 会读它,
# 于是关闭在闸自己的进程里生效(`enable -n` 不跨进程,在外面关是没用的)。
enable -n mapfile
