# Verify: opendesign-fresh-install-fix

- Date: 2026-08-25

## Mechanical checks

**机器打印的收据**(`evidence/20260825T031425Z-01-run-all.txt`,最后一次编辑之后跑的那一遍):

```
runlog: run-all rc=1 commit=ae72029 dirty=yes at=2026-08-25T03:14:25Z file=tracks/opendesign-fresh-install-fix/evidence/20260825T031425Z-01-run-all.txt
  PASS  泄漏闸自测                14 条全过
  PASS  node 单测                 376 通过 / 0 跳过 / 0 todo
  FAIL  python 全量 + 死断言闸    1336 跑过 / 1 跳过 / ⚠️ 1 条死断言
  PASS  MCP 契约闸                三条闸全绿
  PASS  dist 新鲜度 + 类型检查    与源码同步
  PASS  e2e 总跑                  36 PASS / 0 FAIL / 2 SKIP
```

**那一条红不是本单改出来的,证据在下面 —— 但也不许拿它当"绿"用。**

- python 用例本身 **`OK (skipped=1)`**(1336 条),红的是**死断言闸**:
  `tests/test_installer_slim.py:216 self.fail("SLIM_DROP 是空的 …")` 一次都没执行过。
- 溯源:`git log -S` ⇒ 该断言来自 **`393ab8f`(track `opendesign-installer-slim`,08-24)**,
  本单一个字都没碰过那个文件。而那一单**至今没有任何 run-all 收据**
  (`tracks/opendesign-installer-slim/evidence/` 只有一份 import 图)——
  **它是"加了一段没人跑的判据"留下的账,归它。**
- 形状上它和 allow 清单里已有的 5 条一样(防御分支,正常跑不到),
  修法应是"带理由写进 `tests/dead_assertions.allow`",**但那是另一单的事,本单不代改。**

**前一遍收据(`20260825T030259Z`)是真红**:`test_no_console_window` 逮到我把
`# no-console-exempt:` 注释和它守的 `subprocess.run` 之间插了说明 ⇒ 豁免当场失效。
**闸干得对**,已修(注释挪回紧贴调用,并在那儿写明这一行必须紧贴)。两份收据都留着。

**本单自己的判据(逐条亲跑,`ae72029`)**:

- `tests/test_ds_provision.py TestNonChineseWindows` f1/f2 —— 2 条,绿(修之前红,见 `da50f39`)
- `tests/test_installer_silent.py` s1/s2/s3 —— 3 条,绿(修之前 s2/s3 红)
- 邻近回归:`test_ds_provision` 21 条、`test_ds_merge_config` 9 条、
  `test_no_console_window` 3 条,全绿

## Review

- **规格自查**(在任何外部评审之前):这一单的规格如果错了,最可能错在
  **"把输出编码改成永不失败"会不会掩盖真正的失败**。我的判断是不会:
  `errors="replace"` 只作用在**打印**上,合并/写盘的成败仍由返回码和文件本身决定;
  而原来的行为是**成功的合并被一句提示判成失败**,方向正好相反。
  第二个可能错的地方:`/SD IDCANCEL` 让"目录非空"这条在静默安装下**直接中止安装** ——
  无人值守时这是保守侧,但如果将来有人指望"静默安装能覆盖装进非空目录",会被它拦住。
  **这是有意的**,写在判据 s3 的注释里。
- **腿的花名册**:<未跑 —— impact=high 需要 2 条不同家族的成功外部腿,尚未派发>
- **findings**:<待 panel>
- **arbitrated verdict(主裁)**:<待评审后下;本单**未归档**>

## Accepted deviations

- **端到端未验**:云机器那支探针是**下载已发布的安装包**,而本单的修复还没进任何发布版。
  ⇒ 真正的"装得上了"要等下一次发版(0.98.0)之后再跑一遍
  `windows-package-probe` 才算数。**本机判据绿 ≠ 业主机器装得上**,这一条不许含糊。
