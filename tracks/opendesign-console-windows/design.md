# Design: 子进程创建的平台标志只有一个所有者

## 现状:每个调用点各自决定

`bin/` 下现在的 `subprocess` 创建点(机械数出来的):

| 位置 | 干什么 | 现在带的标志 | 该不该无窗口 |
|---|---|---|---|
| `ds_shell_core._spawn` | 起网关 / 工作台 | 只有 `CREATE_NEW_PROCESS_GROUP` | **该,漏了** |
| `ds_shell_core._kill_tree` | 兜底 `taskkill /T /F` | 无 | **该,漏了** |
| `ds_openfolder` ×2 | `xdg-open` / Linux 文件管理器 | 无 | 不该 —— 那两行在 `os.name != "nt"` 的分支里,Windows 走 `os.startfile` |
| `ds_provision` | 装机时合并配置 | 无 | 不该 —— 由安装器的 `nsExec` 调,跑在安装器自己的控制台里,装完就没了 |

**这张表本身就是问题**:它只在我此刻的脑子里。下一个人加第五行时没有任何东西提醒他。

## 改成什么样

### 1. 一个所有者

`ds_shell_core` 顶部:

```python
# Windows 创建子进程时的标志 —— **唯一来源**,调用点不许自己拼。
#
# 🔴 为什么写死数值而不用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)`:
#    Linux 的 subprocess **没有**这两个常量,getattr 会退化成 0,
#    而 0 和"没设"一模一样 ⇒ 本机的判据永远问不出东西(假绿)。
#    数值出自 Windows SDK,和 CPython 在 Windows 上的定义一致。
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW         = 0x08000000
WINDOWS_SPAWN_FLAGS      = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
```

`_spawn` 和 `_kill_tree` 都取这一个。

### 2. 一道机械闸(`tests/test_no_console_window.py`)

照 `test_win_ctypes_decls.py` 的形状:静态扫源码,不看谁写得对,只问**带没带**。

> ⚠ **下面这三条是 08-17 上午的设计稿,落地时全被推翻了**(四审 subkimi 点出
> design.md 与实现脱节)。留着是因为**每一条被推翻的理由都比它本身值钱**,
> 真正的形状见本节末尾「落地成了什么」。

- ~~扫 `bin/*.py` 里所有 `subprocess.Popen(` / `.run(` / `.call(` / `.check_output(` /
  `.check_call(`~~;
- ~~每个调用点要么在同一个语句里出现 `creationflags=`~~,要么名字在**豁免名单**里
  且名单上写着理由;
- ~~**豁免名单要双向验**~~:名单上有、源码里已经没有的条目 ⇒ 也红
  (否则名单会变成一张过期的免死金牌 —— ctypes 那道闸就是这么写的)。

**落地成了什么(以代码为准,这段是事后补写的)**

1. **不问"带没带 `creationflags=`",问"走没走唯一来源"。** 前者红在了已经写对的
   代码上(`_spawn` 把参数塞进 dict 再 `**kwargs` 展开)—— 那是在规定代码长什么样。
2. **豁免不做名单,写在调用点旁边。** 按序号索引的名单会在有人插入新调用时
   **静静地错位**,把豁免盖到不该豁免的那个头上;"双向验"查得出多余条目,查不出错位。
3. **闸问的是"这一次调用",不是"包住它的函数里提过没有"**(四审三条腿独立命中):
   否则同一函数里再加一个裸调用就白拿豁免。实现改用 `ast`,`**名字` 要回函数里追一步。
4. **还有一条闸守这道闸自己的射程**:换个写法起进程(`from subprocess import Popen`、
   `os.system`、`subprocess.getoutput`…)扫描器就瞎了,**而瞎的表现是全绿**。
5. 豁免只认调用点自己那行、或紧贴其上的连续注释块,且理由不许空
   —— 老实现两条都漏(`.strip()` 把下一行代码当成了理由)。

**这道闸问得出 `_spawn` 的病吗?** 问得出:它现在的 `creationflags=` 是
`CREATE_NEW_PROCESS_GROUP`,静态闸只看"带没带"就会放行。⇒ **所以静态闸不够**,
必须配一条行为判据(下)。两条一起才咬得住。

### 3. 两条行为判据(替身 Popen,在 Linux 上问得出)

- **c23**:把 `os.name` 顶成 `"nt"`,替身 `Popen` 记下 kwargs,
  断言 `creationflags & 0x08000000` 和 `& 0x200` **都**成立。
  数值写死在判据里(不从被测模块导入)—— 否则实现把常量改成 0,判据跟着改成 0,
  两边一起错还全绿(08-12 栽过这个形状)。
- **c24**:走 `_kill_tree` 的 `taskkill` 兜底路(`job_handle` 为空、进程还活着),
  断言那次 `subprocess.run` 也带了 `CREATE_NO_WINDOW`。

## 这一版仍然验不了什么(说在前面)

**"真机上到底还弹不弹窗口",Linux 上一条判据也答不了。** 上面三条闸问的都是
"标志有没有传对",不是"Windows 有没有听我的"。⇒ 真机清单必须有一条:
**打开软件,一个黑窗口都不许有**。这一条红了,上面全绿也不算修好。

## 版本

bump **0.90.0**。理由是可验证性:业主要能从 `/api/health` 分辨自己装的是哪一版
(0.89.0 有黑窗口、0.90.0 没有),否则真机反馈没法归因。
