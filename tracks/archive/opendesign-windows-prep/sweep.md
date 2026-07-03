# T0 跨平台 sweep 清单(2026-07-03)

## 1. 硬编码路径(→ T1/T9 修)

| 位置 | 内容 | 处理 |
|---|---|---|
| ds_tools.py:29 / ds_organize.py:31 / ds_refs.py:21 | `DEFAULT_DS_ROOT="/root/..."` fallback | T9:Windows 上静默指向不存在路径;改为"env 缺失时基于 `__file__` 推导(bin/ 的父目录)",天然跨平台 |
| ds-todo:17 | 同上 fallback | T1 一并改 |
| config/nanobot.config.jsonc:41-62 | venv python ×3、脚本路径 ×3、DS_ROOT ×3 | T9:占位符化/Windows 变体 |
| bin/ds-nanobot:7-8 | venv + auth.json 路径(bash) | T8:ps1 不照抄,key 注入按 T7 方案 |

## 2. POSIX-only 调用(→ 零新发现)

- ds_lock.py 已是跨平台双实现(fcntl/msvcrt),7-02 换毕,31 测试绿。
- 其余脚本无 fcntl/fork/pwd/grp/signal/symlink 调用。
- shebang 不碍事:MCP 走 `sys.executable` 拉起,Windows 手动跑用 `python <script>`。

## 3. 编码(→ T1/T3 修)

| 位置 | 问题 | 处理 |
|---|---|---|
| ds_tools.py:174 | `subprocess.run(text=True)` 无 encoding;Windows 管道默认 cp936,子进程打 "▸"(非 GBK)即 UnicodeEncodeError | T3:改 import 直调,整个消灭 subprocess 面 |
| ds_tools.py:176 | 不查 returncode,子进程崩了照样 `ok:true`(Linux 上也是现存 bug) | T3:直调 + try/except 显式 error |
| ds-todo:32,53 | print "▸"(U+25B8,非 GBK)+ 中文 | T1:入口 `sys.stdout.reconfigure(errors="replace")` 防 Windows 控制台崩;核心逻辑改为返回字符串(供直调) |
| ds-approve:24-28 | print 中文(GBK 可编码,低危) | 同样加 reconfigure(errors="replace"),一行 |
| ds_organize.py:218 | 锁文件 `open(...,"a")` 无 encoding | **豁免**:无内容写入,无害(评审 F2 附注) |

其余 `open()` 均已带 encoding。
