# Tasks: opendesign-update-check-rate-limit

- base-ref: b13a71d7e6fb4e5f95061498d0423cad28e11403

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [ ] 判卷改问法:t12 截获点从 `urlopen` 换到 `OpenerDirector.open`(先于实现,单独提交)
- [ ] 判据先行:`tests/test_ds_update_source.py`(rl1~rl9)、`tests/test_update_manifest.py`(rl10)、`tests/test_update_ui.mjs`(rl11)、`tests/test_update_e2e_harness.py`(rl12)
- [ ] 实现:ds_update 订阅源 + 清单 + 回落 + 人话 + 代理当场读;`installer/make-update-manifest.py`;界面 updateReason;重建 dist
- [ ] fake_github + windows-update-e2e:atom / 清单端点、API 403 模式、备路场景;推 `ci-update/**` 真跑
- [ ] 红检(变异咬住 rl 关键断言)
- [ ] 全仓总跑 --with-gateway
- [ ] panel-review(impact high)→ 仲裁
- [ ] 发版步骤写清(清单随版上传 + 发布核对走产品新路径);bump / 发版连同自动更新那单一起问业主
