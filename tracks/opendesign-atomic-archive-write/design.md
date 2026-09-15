# Design: opendesign-atomic-archive-write

- Change: opendesign-atomic-archive-write
- Status: draft(主 agent,落盘于任何外部意见之前)

## Approach(不是开放分叉:仓里已有真机验过的先例)

`ds_tools.locked_workspace_json` + `_write_workspace_json`(2026-07-27 Windows 真机 t06 抓过一次)已经是这套形状:
**锁落在稳定的旁路文件上 + 同目录唯一临时文件 + `os.replace`(Windows 上目标被别人开着时重试)+ 保留权限位**。
那段注释写明了为什么锁不能落在目标本体上:被 `os.replace` 之后锁挂在旧 inode,下一个写者绕过互斥;
**而且在 Windows 上,持着目标文件的句柄时 `os.replace` 根本换不掉它**。本单把这套推广到档案写入口。

```
archive_lock(path)            <dir>/.locks/<文件名>.lock,open("a+b") + ds_lock.exclusive
atomic_write_text(path, text) realpath → 同目录 NamedTemporaryFile(".<名>.*.tmp",text 模式、utf-8、newline 默认)
                              → write → flush → os.fsync → close → chmod(原权限位)→ replace_with_retry → 失败删 tmp
locked_rw(path)               with archive_lock(path): 读(文件不在照旧抛)→ yield box → write=True 才 atomic_write_text
```

- **刷盘(fsync)是断电那一半**:只 replace 不刷盘,断电后可能是"改名已落盘、数据块还没落"的空文件。
- **换行/编码与原来逐字节一致**:原实现是 text 模式 `newline=None`(Windows 上写 CRLF),临时文件用同样的打开方式。
- **符号链接**:按 realpath 写,链接本身不被替换成普通文件。
- **`.locks/` 放每个目录下**(projects/、clients/、数据根):项目目录已有 `.trash/` 先例;所有列表代码只认 `.md` 结尾(已核:
  `ds_web.py:1186`、`ds_tools.py:709/1158/1275`)。锁文件**永不删除**(删一个别人正持着的锁文件 = 互斥失效)。
- `_replace_with_retry` 挪到 `ds_common` 作唯一来源;档案这边重试窗口放宽到约 2 秒(见风险 1)。
- `ds_refs.add_style`:原来锁词表本体 + r+ 截断写 → 改走 `archive_lock` + `atomic_write_text`。
- `ds_tools.rename_project`:客户备忘 / index 的原地改写改走 `locked_rw`(顺带补上锁);
  档案正文先 `atomic_write_text(old_path)` 再 `os.replace(old, new)`(提交点顺序不变),两步放在 `archive_lock(old_path)` 里。

## Key trade-offs / risks

1. **Windows 上的新失败方式**:原地写只要对方的共享模式允许写就能成;替换要求**没人开着目标**(Python/多数程序打开文件不带 FILE_SHARE_DELETE)。
   应用内的读者都是毫秒级开关;外部编辑器(记事本/VS Code/Typora)读完即关。长期占着文件的程序会让写入**重试约 2 秒后失败并报错**
   —— 不做"失败就退回原地写"的降级:那会让 Windows 上的原子性在判据全绿的情况下悄悄失效。**这一条要 Windows 探针量。**
2. 每次档案写入多一次 fsync:档案是小 markdown,单次毫秒级。
3. 文件身份变了(inode / 创建时间 / NTFS 备用数据流):对 markdown 档案无意义;编辑器会提示"文件已在外部更改",与原来一样。
4. msvcrt 锁在 Windows 上约 10 秒拿不到就抛(`ds_lock` 模块头)—— 锁换到旁路文件不改变这个语义。

## Alternatives considered

- **锁目标本体 + 替换后比对 inode 重试**(POSIX 常见做法):Windows 上持着句柄换不掉目标,走不通。
- **全局一把档案锁**:实现最简,但把不相干档案的写入串行化,且 Windows 上长持锁会把"约 10 秒后抛"的面放大。
- **临时 `.lock` 放在系统 TEMP**:不同进程的 TEMP 可能不同(判据里就会改 TMPDIR)⇒ 互斥悄悄失效。
- **写失败时退回原地写**:见风险 1,否掉。

## Test strategy (oracle)

主 agent 拥有,先行落盘、单独 commit。编号前缀 `aw`(`tests/mutation-*.sh` 按名字选靶子,别和 t*/m*/u* 撞)。
判据文件 `tests/test_ds_atomic_write.py`。

| id | 断言 | 备注 |
|---|---|---|
| `aw1` | **写到一半出错,原档案逐字节不变**:把 `io.TextIOWrapper.write` 换成"写一半就抛 OSError",对 `locked_rw` 做一次改写 ⇒ 原文件内容与 mtime 原封不动;替身必须真的被触发过(计数 > 0,防空转) | 模拟强杀/盘满在"截断之后、写完之前"。原实现:截断后写一半 ⇒ 半截文件 |
| `aw2` | **真强杀**:子进程对大档案反复 `locked_rw` 改写,父进程在它进入写之前/之中随机 SIGKILL 若干轮;每轮之后文件要么是完整旧内容、要么是完整新内容 | 回归护栏(对新实现恒绿);对旧实现是概率红 |
| `aw3` | 写失败之后**不留 `.tmp` 残骸**;成功之后也不留 | |
| `aw4` | `box["write"] = False` ⇒ 文件字节与 mtime 不变 | 保留原语义 |
| `aw5` | **跨进程不丢更新**:两个子进程各做 N 次"读数字 +1 写回" ⇒ 终值 2N | 锁换到旁路文件后仍互斥(防 inode 陷阱) |
| `aw6` | **读者永远读到完整文件**:写者反复改写时,另一进程并发读,每次读到的都带完整页脚标记 | 原实现的截断窗口里读者会读到空/半截 |
| `aw7` | 换行/编码/权限位与原实现逐字节一致(同一组编辑,新旧产物字节相同;0644 不被收紧成 0600) | |
| `aw8` | 目标是符号链接 ⇒ 写进真实文件,链接仍是链接 | |
| `aw9` | `ds_refs.add_style` 写一半出错 ⇒ 词表原封不动 | |
| `aw10` | `rename_project` 改写客户备忘 / index / 档案正文时写一半出错 ⇒ 这三类文件都原封不动(不出现空/半截) | |
| `aw11` | 写过之后,项目列表 / 客户列表不出现 `.locks` 之类的东西 | |
| `aw12` | **Windows 语义(本机恒绿,Windows 探针上才真问)**:另一句柄短暂开着目标(< 重试窗口)⇒ 写成功;一直开着 ⇒ 写抛错且原文件原封不动、无 `.tmp` 残骸 | `.github/workflows/windows-atomic-probe.yml` |
| `aw13` | `_replace_with_retry` 只有一处定义(ds_common),ds_tools 引用它 | 结构钉,防第二来源 |

### 这个 oracle 能被什么骗过?

1. `aw1` 的替身只拦 `TextIOWrapper.write`:实现若改用 `os.write`/二进制写,替身不触发 ⇒ 靠"触发计数 > 0"那条断言兜住(不触发即红)。
2. Linux 上的 `os.replace` 永远成功,**Windows 上"目标被开着换不掉"本机结构上照不出** ⇒ `aw12` 必须在 Windows runner 上跑过才算数。
3. `aw2`/`aw6` 是概率性的:它们证明不了旧实现一定红,只做回归护栏;**红检以 `aw1` 为准**。
