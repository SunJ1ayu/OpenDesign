# Tasks: dead-assertion-gate

- base-ref: 954c823894db774291273d32632babf475b7024b

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。
> **这一单没有外包**(理由见 verify 的「派给」格)。

- [x] 判据先行:`tests/test_dead_assertions.py`(实现前 3 处红)—— `59a8024`
- [x] 判据补:它要**替代**总跑的 python 段,汇总行要原样透出(修复前 1 处红)—— `1c83b28`
- [x] 实现 `tests/dead_assertions.py` + `dead_assertions.allow` + 接进 `run-all.sh` —— `faf2344`
- [x] 评审(fast:主 + submimo + subdeepseek),DeepSeek 给 BLOCK,两条 HIGH
- [x] 判据补:评审那两个洞先红检(修复前 2 处红)—— `46f39e0`
- [x] 修那两条 HIGH:单行守卫当场报、跳过不再算死 —— `d407160`
- [x] 收口:亲跑总跑 + 亲读 diff + 落 verify + push + 归档
