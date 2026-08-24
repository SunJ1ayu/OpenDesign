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
