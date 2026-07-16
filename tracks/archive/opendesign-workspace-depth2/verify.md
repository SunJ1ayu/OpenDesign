# Verify: opendesign-workspace-depth2

- Date: 2026-07-16
- Verdict: PASS

## Mechanical checks

- [x] build passes(npm run build 绿,dist 进仓)
- [x] tests pass(py 14 套件全绿;ws_protocol 冒烟 rc=3=无 gateway 诚实 SKIP;
      mjs 5 套件 76 pass/0 fail;red-check 突变三连全红后还原绿)
- [x] no secrets / unsafe ops(无新写面,405 铁律未动,key 不参与路径运算)

## Review

- lane: fast(主审 + submimo review;PANEL_DIFF_BASE=6b9fb69 喂全量已提交 diff——
  首次 dispatch 误用 GIT_DIFF_RANGE 已杀掉重发,防空 diff 盲评)
- 主审(先落盘 /root/aiwork/tasks/opendesign-workspace-depth2-my-review.md,
  后读 employee 报告):PASS,0 BLOCK/0 MUST;核过 key-不当路径用/两级同闸/
  bool-float 陷阱/消费集去重/跨组重名歧义/%3A URL 往返实测/depth=1 逐行等价。
- submimo:PASS,0 BLOCK/0 MUST/3 SHOULD/3 NIT。仲裁:
  - S1 已建档条目不带 group → **拒为改动**(design.md Non-goals:分组标签只服务
    未建档发现,已建档视觉组织归 #7 驾驶舱),记 deviation;
  - S2 缺空分组显式断言 → **证伪**(test_g01 对完整列表 assertEqual 精确相等,
    空分组哨兵条目必炸);
  - S3 缺分组内 symlink 项目用例 → **收**,已补(test_g03 加 2026/外链项目 拒断言),
    39 全绿;
  - N4(写读两侧 bool 闸重复=有意纵深)/N5(`:` 无转义=NTFS 禁字已注释)/
    N6(depth=1 清字段=文件最小化,w15 已测)→ 均不动。
- arbitrated verdict(主裁): **PASS**

## Accepted deviations

- 已建档(registered)条目不带 group 字段;显式映射进分组的项目在侧栏无分组标签
  (submimo S1)。范围=纯视觉;#7 驾驶舱重排 IA 时统一处理。
- e2e 无新剧本:无新聊天面,HTTP 层由 test_ds_web_api 真服务器覆盖(含 %3A 往返);
  真机验收=用户接真实两层结构(D:\G2 DESIGN GROUP)。
- workspace/AGENTS.md 话术更新须随 install 拷到 %USERPROFILE%\.nanobot\workspace
  才对运行中 agent 生效(git pull 不自动带过去);bin/ds_tools.py 是仓内路径,
  pull 即生效——工具能力先行,话术滞后无害(助手看到 folder_count=0 仍会问布局)。
- depth 1↔2 切换会改变未建档条目的 key(`名`↔`组:名`);未建档无档案无持久引用,
  已建档走显式映射不受影响(design.md 已记)。
