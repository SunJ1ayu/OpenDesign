# Proposal: opendesign-e2e-no-egress-browser-tmp

- Date: 2026-09-15
- Status: open

## Goal

两件 e2e 判据的卫生问题,业主 09-15 晚「开」:
1. **e2e 判据有外网出口**:默认 e2e 起的真 ds_web,页面一打开就调 `/api/update/check`,真去问 GitHub(没有替身)。
2. **浏览器临时目录偶发泄漏**:全量总跑的 e2e 段偶尔剩 1 个空前缀目录,泄漏闸红。

## 真问题(第一性)

- 不变量:**跑判据的进程不许有外网出口**(08-10 kimi 额度被判据烧光立的;aiwork 已机械化,design-studio 没有)。
  09-15 发 0.98.5 时,产品查更新被本机 GitHub 免登录额度 403 挡住 —— 疑似被 e2e 用光(归因没钉死),
  但「e2e 会真去问 GitHub」是代码路径上确定的:只有 `update_notice.e2e.mjs` 用 page.route 拦了,其余 37 条都没拦。
  不修的代价:判据结果依赖外网状态;判据替我花掉额度;下一个外呼口(比如某天界面加了别的联网请求)同样没人拦。
- 泄漏:探针坐实 Chromium 被硬杀一次就在 TMPDIR 留一个 `org.chromium.Chromium.XXXXXX`(5 次 → 5 个),
  与「剩 1 个、名字里没有 `-`/`_`」同形。哪条 e2e 的浏览器没走正常关闭**没钉住**(e2e 单跑 4 遍 0 残留)。
  真正要解决的是:**判据自己造的东西自己收**,并且下次再发生时**说得出是哪一条**。

## 实测(派活前)

- 默认 e2e 整套放进 `unshare -n`(只有回环):**40 PASS / 0 FAIL / 2 SKIP,159 秒**(平时约 170 秒)。隔离不打坏任何一条。

## Scope

- in:
  - e2e 无出口守卫:`tests/e2e/helpers.mjs` 导入即生效(全部 38 个 `.e2e.mjs` 都导入它);新增 `tests/e2e/_no_egress.py` 给 3 个 `.e2e.py`。
    做法照搬 aiwork `tests/_no-egress.sh` / `_no_egress.py`:发现自己在主网络命名空间 ⇒ `exec` 进 `unshare -n`(拉起 lo)重跑;做不到就拒跑(rc=78);
    进去后实测一次出口,还连得出去也拒跑;判定看 `/proc/*/ns/net`,不认环境变量。
  - 豁免:要活网关的两条(`new_chat` / `project-thread`)**明确豁免**,名单只在 helpers 里一份,run-all.sh 那份由判据钉成一致。
  - 浏览器临时目录:`launchBrowser()` 给 Chromium 一个测试自己拥有的 TMPDIR,进程退出时收掉;里面若有残留 ⇒ stderr 报一句并记进 `E2E_BROWSER_NOTES`,
    e2e 总跑在汇总里点名是哪条。
- 不改产品代码。

## Non-goals

- **要活网关的两条仍然真发聊天消息、花真 key 的额度** —— 它们本来就是 `--with-gateway` 才跑的活服务测试,豁免是明示的。要不要换成不花钱的形态另议(问业主)。
- python / node 单元判据(`tests/test_*.py`、`tests/*.mjs`)不在本单加守卫:它们有注入替身的惯例、未观测到出口。要不要机械化另议。
- 不治 e2e 遗孤进程(`opendesign-e2e-orphan-generation` 那单);不去猜是哪条 e2e 的浏览器没正常关 —— 本单让它下次自己报名。
- 不是安全边界:root 一行 `nsenter` 就出去。挡的是手滑。
