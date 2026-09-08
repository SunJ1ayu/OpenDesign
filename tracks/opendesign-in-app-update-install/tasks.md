# Tasks: opendesign-in-app-update-install

- base-ref: 9af63761ebbb88a289354609c38aa0d342ded952

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 0. 开工前先拍板(见 proposal「先要拍的板」)

- [ ] 版本化布局 + 指针:做 / 不做
- [ ] 回滚口径:失败之后"还原"到什么程度
- [ ] `pick_latest` 要不要放宽(继承的账 D —— 第二刀真下载了,取舍变了)

## 1. 判据先行(**此刻应全红**,单独 commit)

- [ ] t4 校验不过则安装目录**零改动**
- [ ] t5 起不来要回滚,且安装器管的那些文件**逐字节还原**
- [ ] t6 收摊没收干净(端口/进程还在)**不许进安装步**
- [ ] 🔴 更新前后 **数据根 `%LOCALAPPDATA%\OpenDesign\` 逐字节不变**
      (design 里"最像绿其实错"的那条:更新成功了但档案没了)

## 2. 实现

- [ ] 下载 → sha256 校验(用 GitHub 给的 `digest`)→ 备份 `$INSTDIR` →
      收摊(确认端口/进程真没了)→ 静默装 → 拉起 →
      **`/api/health` 回显新版本号才算成功** → 成功删备份 / 失败换回备份
- [ ] 红检

## 3. Windows CI 端到端

- [ ] 新一支 workflow(照 `windows-package-probe.yml` 的形状:收据 + 住在
      另一个文件里的第二道闸)
- [ ] `e1` 装旧版 → 走完整更新 → 断言 `/api/health` = 新版本号 + 截图里窗口在
- [ ] `e2` 把下回来的 exe 改坏一个字节 → 断言拒装,**且旧版还打得开**

## 4. 继承的账(逐条,别丢)

- [ ] **B**:`project-thread.e2e.mjs` 自己用 `/api/projects/create` 造夹具
      (现在靠机器上碰巧有那两个项目文件 ⇒ 换台机器新克隆必红,
      而且报错里一个字都不提夹具。机制写在 `tests/e2e/README.md` 第 3b 步)
- [ ] **C1**:`notesSummary` 跳 setext 标题时把下面那行下划线一起吃掉(1~2 字符的 `==`/`--`)
- [ ] **C2**:多行 setext 标题不能只跳最后一行
- [ ] **C3**:列表项紧贴 `---` 时,第一条要点不该被当成标题吃掉
- [ ] **C4**:给 `installer/build-installer.sh` 的 `EXE=` 那行加机械断言,
      和 `bin/ds_update.py:35` 的 `ASSET_RE` 绑起来(现在只有注释级契约)

## 5. 收口

- [ ] 全仓总跑(`tests/run-all.sh --with-gateway`),收据进 `evidence/`
- [ ] panel-review:`impact-risk=high` ⇒ 预算 2,两个不同模型家族
- [ ] bump 版本 + 打包 + 成品闸 + 发预发布
- [ ] 🔴 **业主真机第一条:点那行「下载 …」链接,看浏览器开不开(继承的账 A / S6)**
      —— 他手上的 0.98.4 会在这一版发出去之后**第一次真的说"有新版"**,
      那是这条路唯一走得到的时刻。同时看蓝点 `●` 够不够显眼、会不会太吵。
- [ ] **业主真机:故意跑一次完整更新**(只有他能做 —— CI 上没有杀软、没有他家那条网)
