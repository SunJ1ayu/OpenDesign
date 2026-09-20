# Tasks: opendesign-update-duplicate-facts

- base-ref: b688389efd2c231458e4c8c027a80e7bb9eb93b3

> 全程主 agent 自己做(见 decision.json:adapter=main)。理由:5 条里 3 条要改的是
> **判据本身**,而判据是对抗面 —— 不外包。

## 0. 开工前(已做)

- [x] T0 探针回答 D1:apply 作废分支 = B 档(纵深活着,正常链路走不到)
- [x] T6 改前基线:`mutants-prepare.py` 13/13 全咬住(并修好归档版失效的 4 条锚点)
- [x] T5 改前基线:资格卷变异 9/9 全咬住
- [x] 🔴 重采 T0(干净树):第二次采样与变异红检并发、读到被变异的代码 ⇒ 作废;第三次读数与第一次逐格相同

## 1. 判据(先单独 commit,再 commit 修复)

- [x] T1 el 新判据:`path_unsupported` 走到 apply auto 分支 ⇒ 包必须清;`no_shell`/`disabled` ⇒ 必须留
- [x] T2 prepare 新判据:① 不传 `paths` 必须**立刻报错**(不许静默少做检查);② 机器那一维在 prepare 里真被问到
- [x] T3 机械判据:`grep -rn machine_blocker bin/` 必须 0 命中
- [x] 判据红检:T1/T2/T3 在**修复之前**必须全红(收据进 evidence)
- [x] commit ①:只含判据

## 2. 修复

- [x] #24 `ds_web.py`:`== "attempted"` → `in ds_auto_update.PERMANENT_BLOCKERS`;那段注释整段重写(不再自带成员清单,明写"纵深")
- [x] #26 `ds_web.py:911`、`:1342` 旧名 `machine_blocker` → `why_not_auto`;全仓扫同类
- [x] #25 `ds_update_startup.py`:`prepare_update(info, paths, download=None, now=None)`,内部推导 `data_root`;删掉半维回退
- [x] #25 夹具:`tests/test_ds_update_startup.py` 与 `tests/test_ds_update_eligibility.py` 的调用点改传 `paths`,**行为断言一字不改**
- [x] T7 全仓扫:`grep -rn "prepare_update("` 0 个老签名调用点
- [x] commit ②:修复

## 3. 判据工具(#27 / #28)

- [x] #28 资格变异集补 E8b(只把 `error` 加进 `PERMANENT_BLOCKERS`),并给它一个**常驻位置**
      `tests/mutation-update-eligibility.py`(与 `tests/mutation-*.sh` 同处,便于下次找得到;
      **不承诺**它被 run-all 自动跑 —— 那一批本来就都是手跑的红检)
- [x] #27 b8 探针:span 从 `ds_shell_core.InstanceLock` 推导,不写死数字;重跑取正确读数
- [x] T4:探针自己断言 span 长度 == `InstanceLock._ports` 长度

## 4. 收口

- [x] T5 改后:资格变异整套(含 E8b)必须全部咬住
- [x] T6 改后:`mutants-prepare.py` 再跑一遍,与改前表**逐条 diff**;条数相同、0 error、无一条由红转绿
- [x] `tests/run-all.sh` 总跑
- [x] 真起一次 ds-web 走 `/api/update/prepare`(不是 mock),确认备货链路没被签名改动打断
- [ ] `track preflight`(🔴 **别经 runlog 跑**)→ 派 1 腿评审 → 处置 → 归档
