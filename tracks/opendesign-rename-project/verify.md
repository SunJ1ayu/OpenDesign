# Verify: opendesign-rename-project

- Date: 2026-07-16
- Verdict: PASS

## Mechanical checks

- [x] build passes;tests pass(RenameProjectOracle 10 例先红后绿;tools 89 绿;
      refs/todo/web/workspace 回归绿)
- [x] 突变红检:①去 name_taken 闸→r02 红 ②refs 精确项→子串替换→r01/r07 红
- [x] no secrets / unsafe ops(写域=projects/ 内改名+既有三个引用文件+
      workspace.json,均既有写面;organize 隔离未动)

## Review

- lane: full(panel-review,PANEL_DIFF_BASE=c4025ae)
- 主审(先落盘 tasks/opendesign-rename-project-review-my-review.md):PASS,
  0 BLOCK/0 MUST;崩溃窗口逐态推演(四种中断态全部重跑可达正确终态);自审
  在提交前已抓两处并修:body 预读 fail fast(否则坏编码留下不可自愈的半改态)、
  refs bump 最后更新(与 link_ref 同礼数)。
- **submimo(满血复活,610 行真审查)**:PASS,3 SHOULD(全是"行为对但测试
  没锁")+3 NIT。**subsense**:PASS,2 SHOULD+4 NIT。仲裁:
  - 测试缺口类(refs 头/尾/重复项、workspace 半迁移态、title 已写态、悬空
    new 键语义)→ **收**:r1 fixture 加 r3 行(尾位+重复)、r09 扩成最深中断态
    (引用+映射键+title 全改后崩)、新增 r10 锁死悬空键覆盖语义;
  - subsense SHOULD locked_rw 非原子写崩溃窗口 → **拒(移交)**:预存共享基建
    性质全工具同窗口,已在盲评队列⑤立为独立 track(M4/sidecar);
  - 悬空 new 映射键要加闸 → **拒改行为**(悬空键无档案=垃圾,新项目接管正确;
    r10 把语义锁进测试);
  - NIT 懒 import/行计数/clients 无锁/`:` 入 bad_name → 均拒(库内既有风格/
    审计按行有意义/单写者架构一致/NTFS 禁 `:` 真机不存在,`组:名` 形反而触发
    直等自动绑定=自洽)。
- subglm:缺席(百炼余额不足,同上一 track)。
- arbitrated verdict(主裁): **PASS**

## Accepted deviations

- 其他项目档案散文里的 [[old]] 不跟改(账本语义;schema 无结构性跨项目字段)。
- 跨文件无整体原子性:引用先改(幂等)+os.replace 提交点,中断重跑补齐
  (r09 最深中断态实测);locked_rw 写崩溃窗口=既有基建债(队列⑤)。
- 变更历史/沟通日志正文旧名不动;改名后历史读起来是当时的名字(AGENTS.md 已写)。
