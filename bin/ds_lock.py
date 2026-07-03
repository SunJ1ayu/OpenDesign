#!/usr/bin/env python3
"""跨平台文件排他锁 — Linux/macOS 走 fcntl.flock,Windows 走 msvcrt.locking。

用法:
    with open(path, "r+") as fh, ds_lock.exclusive(fh):
        ...读改写...

语义差异(单用户本地机可接受):
  - fcntl.flock 锁整个文件且阻塞等待;
  - msvcrt.locking(LK_LOCK) 锁「当前位置起 1 字节」的范围,拿不到锁时每秒重试、
    约 10 次后抛 OSError(不是无限阻塞)。锁前后都 seek(0),保证加锁/解锁同一范围;
    锁范围允许超出文件末尾(空文件也能锁)。
"""
from __future__ import annotations

from contextlib import contextmanager

try:
    import fcntl

    def _lock(fh) -> None:
        fcntl.flock(fh, fcntl.LOCK_EX)

    def _unlock(fh) -> None:
        fcntl.flock(fh, fcntl.LOCK_UN)

except ImportError:  # Windows
    import msvcrt

    def _lock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def exclusive(fh):
    """对已打开的文件对象持排他锁;离开 with(含 return/异常)即释放。"""
    _lock(fh)
    try:
        yield fh
    finally:
        _unlock(fh)
