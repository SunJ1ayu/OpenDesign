# Verify: 启动可观测性(第一刀)

- Date: 2026-08-30

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`;这里保留检查、理由、发现与主 Agent 仲裁说明,不复制枚举。

## Mechanical checks

- [x] 判据先行,先红后绿(红收据 3 份、绿收据 2 份,见下)
- [x] 红检 `tests/mutation-startup-diag.sh`:**咬 18 漏 0**
- [x] e2e `startup_report.e2e.mjs`:全部通过,**且用控制变异证明它不是恒真的**
- [x] 全量回归:1357 项 rc=0
- [x] no secrets / unsafe ops(不碰网络、不加对外出口 —— 业主 08-30 定"先做 C")
- [ ] 四审 panel-review(impact=high ⇒ 预算 2)—— **未跑**
- [ ] Windows CI 端到端 —— 未跑
- [ ] 业主真机 —— 只有他答得了

## 机器打印的收据(逐字节,别改数)

判据先红:
```
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:38:48Z file=tracks/opendesign-startup-observability/evidence/20260830T073848Z-01-python.txt
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:39:33Z file=tracks/opendesign-startup-observability/evidence/20260830T073933Z-01-python.txt
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:40:01Z file=tracks/opendesign-startup-observability/evidence/20260830T074001Z-01-python.txt
```
转绿:
```
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:41:14Z file=tracks/opendesign-startup-observability/evidence/20260830T074114Z-01-python.txt
runlog: python rc=0 commit=95369a9 dirty=yes at=2026-08-30T07:41:40Z file=tracks/opendesign-startup-observability/evidence/20260830T074140Z-01-python.txt
```
红检与总跑:
```
runlog: mutation-startup-diag rc=1 commit=4f9db1d dirty=yes at=2026-08-30T08:10:01Z file=tracks/opendesign-startup-observability/evidence/20260830T081001Z-01-mutation-startup-diag.txt
runlog: run-all rc=1 commit=6a6cf47 dirty=no at=2026-08-30T08:11:42Z file=tracks/opendesign-startup-observability/evidence/20260830T081142Z-01-run-all.txt
```

**run-all 那份是红的,原因说清楚**:6 段里 5 段 PASS,唯一红的是 e2e 总跑
(4 PASS / 32 FAIL / 2 SKIP)。真因 `Cannot find module 'playwright-core'` ——
这台机器上 e2e 的 playwright 依赖没了(helpers.mjs 从一个**写死的 npx 缓存路径**加载,
那个缓存被清了)。与本单无关,已单独用 `E2E_PW_MODULES` 指到别处真跑过。
**不擅自装依赖**;这是一笔该单独开单的账。

## 空壳红检:哪些断言是"守卫型"

用一个什么都不干的空实现跑判据,**4 条仍然绿**(s5b/s8b/s9/s12)——
它们禁止某事发生,空实现当然满足 ⇒ **只能靠变异证明有用**。
变异 M7/M12/M13/M15 逐条覆盖,**全部咬住**。
我事先预判 3 条、实际 4 条:量比猜准。

## Review(主 agent 自审 —— **在读任何腿的输出之前落盘**)

### 我自己抓到的、并且已修的

1. **🔴 前端首帧判定是错的,而且正是"每次开机都误报"那个形态。**
   第一版 `reportFirstFrame()` 在 `render()` 之后同步等两帧就下结论,而 React 18 的
   `createRoot().render()` 是**异步**的 ⇒ 健康启动可能被判成"根节点尺寸异常"、
   且永不报 `frame_submitted` ⇒ 外壳的首帧看门每次都写诊断。
   已改成在帧预算内轮询(240 帧 ≈ 4s)。
   **诚实标注:这条修复在本机 e2e 里咬不动**(把预算退回 1 帧仍全绿 ——
   这台 Linux 上 React 提交比第一帧还快)。它只在慢机器上才现形 ⇒
   **属于防御性修复,不是被判据逼出来的**,别在文档里写成"已验证必要"。

2. **🔴 诊断快照差点偷走看门狗的证据。** 原本要调 `sup.poll_dead()`,
   读实现才发现它内部走 `take_dead()`、是**破坏性**的 ⇒ 后台崩溃时业主会看到
   "XX 退出了"但**原因是空的**(08-17 判据 c21 治的正是这形状)。改成只读。

3. **想当然引用了不存在的 `open_folder`。** 本项目为"打开文件夹"有过三种写法、
   已统一到 `ds_openfolder` ⇒ 改为复用它,不造第四种。

### 我自己造出来的假绿(记下来,比结论值钱)

4. **追加判据时写在了 `unittest.main()` 后面** ⇒ 新类没被收集,屏幕照印 `OK`。
   唯一线索是"14 条"这个数字没涨。
5. **红检时把 `npm run build` 输出重定向到 /dev/null** ⇒ 构建失败被吞掉,
   e2e 跑的是**旧包**,于是我得出"控制变异没咬住"的**错误结论**并已写给业主一次。
   换成能编过的变异后,e2e 当场红成 0 事件 —— **它是咬得动的**。
   ⇒ 教训:**量具的输出不许静音**;顺带发现 **单跑 e2e 不检查 dist 新鲜度**
   (总跑里有那道闸,单跑没有)⇒ 这是一笔该开单的账。
6. **判据自己少 import / 引用了不存在的 `shell.VERSION` / 变异锚点串味**
   (`except Exception: return False` 在 ds_shell.py 第一处出现在 103 行,
   我的 M18 打到了完全不相干的函数上)。三处都在红检里现形并修掉。

### 已知的取舍与仍敞着的

7. **`manifest()` 会 `import ds_web`** 只为拿版本号(唯一来源)。代价是外壳进程多一次
   import ⇒ **观测本身给启动加了一点点时间**。选它是因为抄一份版本号会过期,
   本项目栽过。量到再说,不预先优化。
8. **导出的诊断 zip 落在 app 目录里,反复导出会堆积。** 本单不做清理。
9. **`FIRST_FRAME_TIMEOUT = 90s` 没有依据。** 已知唯一硬数据是云端冷启虚机 20~40 秒,
   业主机器上从没量过。**正因为不弹框,这个数字不承重** —— 拿到他第一份诊断包再谈收紧。
10. **前端上报链在真 Windows + 真 WebView2 下没验过。** 本机 e2e 用的是 chromium +
    自造的假桥。真桥(pywebview 注入)只有 Windows CI / 真机答得了。

## Panel

- [ ] 待跑(impact=high ⇒ 两条不同家族的健康腿)
