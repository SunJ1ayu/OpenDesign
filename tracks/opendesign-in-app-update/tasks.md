# Tasks: opendesign-in-app-update

- base-ref: e8d1aee06e28e0911a87ed2d4464f267b4a03481

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 第一刀 D:只查不装(不碰业主机器上任何文件)

- [x] 录夹具:把本仓真实的 `GET /releases` 响应存进仓(判据不许有外网出口 —— 08-10 事故)
      连同那条 `GET /releases/latest → 404` 的实测收据一起留证
- [x] **判据先行(红收据在 evidence/,单独 commit)**:t1 认预发布 / t2 版本按数比 / t3 不比本地新不提示 /
      t7 网络异常安静不甩栈 —— 单独 commit
- [x] 实现:`/api/update/check`(ds_web)+ 把 Sidebar 里那个**没有 onClick 的死按钮**做成真的
      (顺带发现:界面上「检查更新」这个按钮此前就在,点了没反应)
- [x] 红检 17 咬 0 漏(逻辑)+ 5 咬 0 漏(端点);**含**「把挑版本改成 `/releases/latest` 语义」那条

## 第二刀 A:按下去就装好  ⇒ **已拆成后续单 `opendesign-in-app-update-install`,本单不做**

- [ ] **判据先行(此刻应全红)**:t4 校验不过则安装目录零改动 / t5 起不来要回滚且
      安装器管的那些文件逐字节还原 / t6 收摊没收干净不许进安装步 —— 单独 commit
- [ ] 🔴 判据:更新前后 **数据根 `%LOCALAPPDATA%\OpenDesign\` 逐字节不变**
      (design 里"最像绿其实错"的那条:更新成功了但档案没了)
- [ ] 实现:下载 → sha256 校验 → 备份 `$INSTDIR` → 收摊(确认端口/进程真没了)→
      静默装 → 拉起 → **/api/health 回显新版本号才算成功** → 成功删备份 / 失败换回备份
- [ ] 红检

## Windows CI 端到端  ⇒ **随第二刀走,本单不做**

- [ ] 新一支 workflow(照 `windows-package-probe.yml` 的形状:收据 + 住在另一个文件里的第二道闸)
- [ ] `e1` 装 0.98.2 → 走完整更新 → 断言 `/api/health` = 0.98.3 + 截图里窗口在
- [ ] `e2` 把下回来的 exe 改坏一个字节 → 断言拒装,**且 0.98.2 还打得开**

## 收口

- [x] 全仓总跑(`tests/run-all.sh --with-gateway`),收据进 `evidence/`
      —— 两份并排留证:`20260908T005638Z`(红在一条 e2e,是发现夹具洞的唯一入口)+
      `20260908T011208Z-…-v2`(6 段全绿,e2e **0 SKIP**)
- [x] 开后续单 `opendesign-in-app-update-install`(第二刀 + 继承的账 A~D 逐条搬过去)
- [x] panel-review:`impact-risk=high` ⇒ 预算 2 —— 第四轮一次 run、同一 subject digest 下
      **三个家族**(xiaomi / deepseek / moonshot)全部完整交卷全 PASS,超额满足
- [x] 主裁结论写进 verify.md + `decision.json.outcome.verdict` = PASS
- [x] 真机清单 `真机清单-0.98.4.md`(断线前只在散文里写着"⇒ 真机清单一条",没有文件)
- [ ] bump 版本 + 打包 + 成品闸 + 发预发布 —— **bump 已做(0.98.4)**,打包/发布见下
- [ ] **业主真机:走一趟 `真机清单-0.98.4.md`**
      (🔴 注意:「有新版」那整条路这一趟**走不到** —— 装上 0.98.4 时线上最新就是它。
       S6 那条外链验证已写死进后续单的收口清单)
