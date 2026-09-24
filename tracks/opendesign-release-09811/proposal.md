# Proposal: OpenDesign 0.98.11 发布(正式 release `v0.98.11`)

- Date: 2026-09-24
- 业主原话:「搞完发新版本，然后我这边应该能接收到更新自己更新对吧」;问 0.98.10 是不是软件自己提示更新的 →
  「是软件自己提示的， 你做完直接传上去吧」⇒ 授权推送 main + 创建正式 release;业主机器 0.98.10,走应用内自动更新(0.98.9→0.98.10 已真机走通)。
- 发的内容(都已归档 PASS):
  - `opendesign-quiet-start-icons`(`53560cc`):启动横幅整条删掉;侧栏换 ZCode 同款 lucide 图标。
  - `opendesign-kimi-glm-vendors`(`fa6cb94`):加 Kimi 按量 / GLM 套餐 / GLM 按量三家,每家 key 卡片带「获取 API Key」链接。

## 本单做什么

1. 版本号 0.98.10 → 0.98.11(`bin/ds_web.py VERSION`、`desktop/package.json`、lock 根版本;只加第三位)。
2. 本地总跑;云 Windows `electron-e2e` 整跑 FAIL 0(兑现 quiet-start 移交的两条云 e2e:E2.connecting 反向、E2.noreload 改判),从同一次运行取出货三样。
3. 两家族评审;推送 main;照 `installer/RELEASE.md` 发布正式 release;发布后生产源 smoke(latest 指向 0.98.11、字节 = artifact、旧 blockmap `download/v0.98.10/` 在)。
4. **发布 + smoke 当天归档**(0.98.10 单的教训:留单等真机,仓库级绑定会漂移);业主真机回显事后补进已归档 verify.md。

## 验收边界与轮次预算

- 承诺:发出去的安装包来自云上测过的同一次运行、与被测版只差更新源;正式版三样资产;生产源 latest 指向 0.98.11 且字节一致;
  已装 0.98.10 的机器能从生产源看到 0.98.11。
- 发版说明(中文)写:新厂商三家 + key 链接;启动横幅删除与新图标;Kimi/GLM 模型名按官方文档、未经真 key 验证(建议先用真 key 试一句);
  正在用非主厂商时给它换 key 会回到那家默认模型(老行为,另排)。
- 不承诺:业主真机结果(事后补记)。
- 实质评审上限:2 轮(impact=high:公开发布 = production_side_effect)。题面只问发布会不会弄坏东西;「锤子砸墙」类照报不算阻断。
