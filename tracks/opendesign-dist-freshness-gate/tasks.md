# Tasks: opendesign-dist-freshness-gate

- base-ref: a433bf8df759b5c7be8a997c68c2194a79769412

## 0. 开工前必须过的闸

- [ ] **P0 前提探针:`vite build` 是确定性的吗?**
      连续两次 build 到两个不同的仓外临时目录,产物**逐字节**比对。
      **不一致 ⇒ 本方案作废**(闸会随机红 = 把报警器换成噪音源,比现状更坏),
      回头重新选方向。**P0 没绿之前不许写实现。**

## 1. 判据先行(单独 commit,先红后绿)

- [ ] `tests/test_dist_freshness_gate.py` 六条(见 design.md 的 oracle):
      O1 真过期咬得住(含一个落在 `index.html` 上的变异)/ O2 只改注释不误报 /
      O3 build 失败不静默放过且带得出报错原文 / O4 不污染工作树 /
      O5 build 确定性 / O6 闸红时 `run-all.sh` 整体 rc≠0 且不继续跑场景
- [ ] 判据此刻必须**红**(闸还不存在),把红收据留下 —— 先红后绿,单独 commit
- [ ] 红检 `tests/mutation-dist-gate.sh`:比对退回"只比文件名" / 调用改成 `;` 接吃 rc /
      build 失败吞掉 / 闸退回比 mtime(新旧闸**对照组**) —— 每条都要咬住

## 2. 实现(顺序不能换)

- [ ] `tests/e2e/check-dist-fresh.sh`:build 到仓外 mktemp 目录、逐字节比产物、
      trap 清理、失败时透出 build 报错原文、断言产物文件数 > 0
- [ ] `tests/e2e/run-all.sh` 入口调用它(**默认路径就跑**,不藏在 `--with-gateway` 分支里),
      **rc 必须传得出去**(不许 `;` 接、不许进管道)
- [ ] `tests/e2e/llm_key.e2e.mjs` 里那道比 mtime 的旧闸退场(连同它的注释一起删干净)

## 3. 收口

- [ ] 判据全绿 + 红检每条咬住(机器收据,不是我的转述)
- [ ] `tests/e2e/run-all.sh` 总跑:**这一单的验收是 36 PASS / 0 FAIL**
      (即 `llm_key` 由红转绿,且新闸没把别的场景带红)
- [ ] python 全量回归(venv 解释器,不是系统 python3)
- [ ] 四审 panel-review(impact=standard ⇒ 外部预算 1,可加证据不可减)
- [ ] `docs/backlog.md` 记一笔:8 个 `mutation-*.sh` 的 `cp` → `cp -p`(本单 non-goal,
      理由与实测要求一并写清)
- [ ] 归档(本单纯判据面、无产品改动、无真机依赖 ⇒ 绿了就能归档)
