# Tasks: 安装包瘦身

## 0. 前提(已完成)

- [x] **P0 探针 + 对照组**:抹掉候选包之后 nanobot 启动路径 5 步全过;
      对照组 15 → 抹后 13,**正好少 feishu + telegram**,没波及第三个。
      (`matrix` 在对照组就加载不了 —— 本来就缺,不是本单造成的。)

## 1. 判据先行(**必须先单独 commit,此刻应为红**)

- [ ] g1 清单里的包**真的没进产物**(问 pkg 目录,不是问脚本里有没有那行)
- [ ] g2 **真在用的一个都没少**(白名单反向查:PIL / lxml / cryptography / mcp / nanobot / anydoc …)
- [ ] g3 **删完之后 nanobot 还起得来**(P0 探针的常驻版)
- [ ] g4 `dist-info` 与包**同生共死**
- [ ] g5 清单必须是**显式数组**,不许通配符/正则(一个 `*` 能把 PIL 一起带走)
- [ ] 红检:每条都要有变异咬得动

## 2. 实现

- [ ] `spike/build-package.sh`:`pip install --target` 之后按 `SLIM_DROP` 数组删目录 + dist-info
- [ ] 组包闸(`check-package.sh`)里加一句:被删的包不许出现在产物里

## 3. 收口

- [ ] 全量回归(venv 解释器)
- [ ] 重新打包,量**前后的文件数与体积**并记进 verify
- [ ] panel-review(impact=standard ⇒ 预算 1 条外部腿)
- [ ] 与 0.95 的窗口改动**打同一个包**,业主只装一次

## ⚠️ 一笔说不清的敞账(2026-08-24,别当成已解决)

写这一单时,`probes/` 里两个 `.py` **在我 cp 进去、并且成功跑过之后消失了**
(evidence/ 里的 .txt 好好的,同一分钟)。已从 scratchpad 恢复并**立即 commit**
(入库之后就动不了了)。

**已排除**:`track-record validate`(做了哨兵实验:放一个文件进去、跑一遍、文件还在);
`~/.openclaw/_scripts/cleanup-sessions.sh`(只扫 session 目录、凌晨 3 点跑);
`tmp-sweeper`(只扫 /tmp、3:25)。

🔴 **谁删的仍然不知道。** 不编原因。教训是可操作的那条:
**工件一落盘就 commit,别攒着** —— 未跟踪文件在这台机器上不安全。
