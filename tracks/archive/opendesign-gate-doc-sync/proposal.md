# Proposal: opendesign-gate-doc-sync

- Date: 2026-08-24
- Status: open

## Goal

把 `opendesign-dist-freshness-gate` 改变的事实,同步到它被复制到的**每一处**;
并把查证过程中挖出的两个**实质问题**(不只是文档)钉住。

## Motivation

上一单只改了闸本身。业主问「第一性原理查一下有没有其他地方要一起改,比如说明用法」,
照着「**我搜过了 ≠ 我搜的范围盖住了**」把活文档扫了一遍(排除 logs / attack-logs /
tracks/archive 这些史料),结果挖出的比"改个说明"多:

1. **`tests/e2e/README.md` 没提新闸** —— 跑的人会看到一段没来由的 build 输出。
2. **README 自己打自己的脸**:它写着「⚠️ 这里**故意不写第几段**…按名字指,插多少段都不会漂」
   (2026-08-18 四审抓到的教训),**而下一行就写着「六段一条命令」** —— 同一段话里自相矛盾,
   那个数字同样会漂。
3. 🔴 **上层总跑 ⑤ 段跑的是 `npm run build` = `tsc -b && vite build`,
   而六段里没有任何独立的类型检查段** ⇒ **它是这个仓库里唯一跑 TypeScript 类型检查的地方,
   而它的名字只说「dist 新鲜度」。**
   ⇒ 下一个人看到「两道闸问同一个问题、重复了」,很可能顺手删掉它 ——
   **连带把类型检查一起删掉,而且不会有任何判据变红。**
   (同族:memory `guards-must-watch-the-right-door`。)
4. ⑤ 段用 `test -z "$(git status --porcelain -- web/dist)"` 判断 ⇒ **依赖 `web/dist` 入库**。
   实测现在没被 ignore(判得动);但哪天它被 gitignore,这道闸会**恒绿**(fail-open),
   而新闸不受影响(直接比文件)。
5. ⑤ 段 `npm run build` **直接覆盖 `web/dist`**,与新闸「只报告不修复、保留信号」的
   哲学相反。两者并存不是错,但**必须写明分工**,否则将来改一处忘另一处 ——
   那正是这个项目栽过多次的「同一个事实存在两处,只更新其中一处」。

## Scope

- in: `tests/e2e/README.md` 补新闸说明、去掉会漂的「六段」数字、耗时口径带上那次 build
- in: `tests/run-all.sh` ⑤ 段:把「它也是唯一的类型检查」写进注释与显示名(防未来误删)
- in: `tests/e2e/check-dist-fresh.sh`:注释写明与 ⑤ 段的分工
- in: ⑤ 段那条 fail-open(依赖 dist 入库)写进注释,并记 backlog

## Non-goals

- **不改任何行为**:不合并两道闸、不动 ⑤ 段的实现、不动新闸的实现。
  「两道闸要不要合并」是独立判断(⑤ 段还捎带着类型检查,合并会牵动它),单独一单。
- 不动 `/root/aiwork/refs/` 下的东西 —— 那是退役备份与史料(`claude-md-retired-*`、
  `ctxdiet-backup-*`),**故意保留当时的措辞**,改了反而毁掉史料价值。
  (已确认 `aiwork/bin/` 里提到 design-studio 的四处全是注释里的举例,不是硬编码流程。)
