# verify: opendesign-release-0983

机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录 `decision.json`。

## Mechanical checks

- [x] build passes —— dist 新鲜度 + 类型检查段绿(`npm run build` 后 git 无差异)。
- [x] tests pass —— ⚠️ **口径**:六段 **5 绿 1 红**,总跑 `rc=1`。
      · **python 全量 1426 跑过 / 1 跳过,0 失败** ⇒ **bump 版本号没让任何判据变红**
        (开工前的疑虑:`tests/test_startup_diag.py` 里有 `"0.98.2"` 字面量,
         核过是 health 端点的**夹具假数据**,与 `bin/ds_web.py` 的 VERSION 无关)。
      · 红的唯一一条 `stage_timer.e2e.mjs`,**本轮又自己核了失败形状**:
        4 FAIL + `connect-modal-mask` 拦截 ×9,与上一单、与开工前 `d0840c1` 上量到的
        **逐条一致** ⇒ 既有红,非本单引入。
      · 3 条 SKIP 同一根因(本机无活 gateway)、都自标"不算通过"。
- [x] no secrets / unsafe ops(本单只动版本号字符串、CI 默认值字符串与工件;零行为代码)

**最终收据(全仓总跑)**:

```
runlog: run-all rc=1 commit=5589491 dirty=yes final=yes at=2026-09-02T08:31:51Z file=tracks/opendesign-release-0983/evidence/20260902T083151Z-01-run-all.txt
```

**release 资产往返比对**:

```
runlog: release-asset-roundtrip rc=0 commit=5589491 dirty=no at=2026-09-02T08:31:32Z file=tracks/opendesign-release-0983/evidence/20260902T083132Z-01-release-asset-roundtrip.txt
```

## 收口条件逐条对账(proposal 里写死的四条)

1. ✅ **exe 文件名含 0.98.3 且成品闸绿** —— 静态闸 23 条 0 不合格、成品闸 7 条 0 不合格
   (含 P4「编进去的文件==payload,不多不少」、P5「每个文件字节数逐个对得上」)。
2. ⚠️ **「从 exe 内容读回版本号」—— 降级了,如实说明。**
   本机**没有 NSIS 解包工具**(`7z`/`binwalk` 都没有),exe 内容是压缩的,
   字节流里搜不到 `VERSION = "0.98.3"`。**所以这一条不是直接读出来的**,
   是靠传递性:`payload/pkg/ds/bin/ds_web.py` = `0.98.3`(直接读的)
   × 成品闸 P4/P5 机械证明「exe 编进去的文件 == payload 树、字节数逐个对得上」。
   ⇒ **链条是机器验的,但最后一环是推的,不是读的。**
   真正的直接验证只有第 4 条(业主真机回显),这也是它必须存在的理由。
3. ✅ **release 上的 tag 与资产名都是 0.98.3**,且**下回来与本地造的那份逐字节一致**
   (sha256 `b1d40edf…d87982`,两边相同;`prerelease=true`,45836403 字节)。
4. ⏳ **业主真机装一趟并回显版本** —— **只有他能做,不装不算发完**。
   同一趟合并验上一单欠的那件:双击软件是不是真的不再干等十几秒。

## 我自己的两个顺序错误(都记账,不藏)

1. 🔴 **我先发了 release,才补跑最终判据。** 正确顺序是判据绿了再发。
   这次侥幸没出事(补跑结果证明零新增失败),但**"侥幸"不是方法** ——
   如果补跑红了,业主可能已经下载了一个没验过的包。
   ⇒ 自检句:**对外发布之前,判据跑完了吗?**(发布是不可逆的:链接一旦给出去,
   撤回也不知道谁已经下过了。)
2. **最终收据 `dirty=yes`** —— 我在跑 `--final` 之前没有先把上一份收据提交,
   于是 `evidence/`、`observations/` 两个未跟踪目录让工作树是脏的。
   核过 `source-stable: yes`、`head-before == head-after == 5589491`,
   **脏的只是收据文件自身、不是被测源码**,所以这遍有效;但严格说它削弱了
   "这份收据对应哪棵树"的可追溯性。⇒ 下次:**先提交收据,再跑 `--final`。**

## arbitrated verdict(主裁)

**PASS**。

依据:零行为代码改动(只动版本号与 CI 默认值字符串);python 全量 1426 条 0 失败
⇒ bump 没碰坏任何判据;唯一的红是既有的、本轮自核过失败形状;
release 资产与本地构建**逐字节一致**。

⚠️ **但"发完了"这句话现在还不能说** —— 收口条件第 4 条(业主真机回显)未完成。
按本机那条部署规矩:**没被装上、没回显出 0.98.3 的包,不算部署**。
这一单的 PASS 是"包造对了、发对了",**不是"业主用上了"**。
