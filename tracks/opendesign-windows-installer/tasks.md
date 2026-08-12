# Tasks: opendesign-windows-installer

- base-ref: c24a3b5a42be23b7f1adcd7bc9a6846ff4bd50d7

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 派给

**S0 全部主 agent 自己干,不派腿。** 理由不是"腿不行",是这单的工作量几乎全在
**判据本身**(spike.py 就是 oracle),而 oracle 永远不外包。剩下的是打包动作,
比写任务书还短。S1 造安装器时重新评估分层。

## S0 —— 探路包(回答:免装 Python 跑不跑得动)

- [x] 摸底:向导可被脚本替代(探针 6/6 + 我补强的判据 C 两问)
- [x] 摸底:119 依赖全部有 Windows 轮子、0 源码包
- [x] 摸底:离线装配 payload 成立(rc=0,355MB)
- [x] 摸底:embeddable Python 3.12.10 存在且版本对得上
- [ ] 写 `spike.py`(判据本体,六问 + 七个防骗焊点)—— **先单独 commit,再动别的**
- [ ] 红检:把 spike.py 对着**故意坏掉的输入**跑一遍,证明它咬得动
      (至少:假装 sys.executable 在包外 → 必须红;anydoc 断言改错 → 必须红)
- [ ] 组包:embeddable python + `._pth` 放开 + payload + ds 文件 + `跑一下.bat`
- [ ] 本机能验的部分先验掉(zip 结构完整性、`._pth` 内容、文件齐不齐、体积)
- [ ] 出 zip + 写三句话操作说明
- [ ] **业主真机跑一趟**(只有他能做)→ 收 `收据.txt`

## S1 —— 安装器(等 S0 结果,现在不展开)

- [ ] **规划双出**(设计要点见 design.md,S1 命中触发条件,不许省)
- [ ] 定:运行时形态(S0 绿 = embeddable;S0 红 = 退到完整 Python)
- [ ] 定:更新路径(不带 Git 怎么升级;注意助手契约光拷文件不生效)
- [ ] 定:key + WebUI 口令在哪一步录入
- [ ] NSIS 脚本 + 在本机构建 .exe
- [ ] 卸载、开始菜单、桌面图标
- [ ] verify(lane 见 verify.md;**碰装机/权限/key ⇒ 预计 full**)
