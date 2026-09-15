# Tasks: opendesign-atomic-archive-write

- base-ref: 2063c9a7c077e9d238cb25cd09937c40fe4aee8f

- [ ] 判据先行:`tests/test_ds_atomic_write.py`(aw1~aw13),在现有代码上跑出红,单独 commit
- [ ] 实现:`ds_common.archive_lock / atomic_write_text / replace_with_retry`,`locked_rw` 改走它们
- [ ] `ds_refs.add_style`、`ds_tools.rename_project` 改走同一套;`ds_tools` 改引用 ds_common 的 replace_with_retry
- [ ] 红检脚本(变异咬住 aw1/aw3/aw4/aw7/aw9/aw10/aw13)
- [ ] Windows 探针:windows runner 上跑 `tests.test_ds_atomic_write`(aw12 真问)
- [ ] 全仓总跑
- [ ] panel-review(impact high ⇒ 预算 2)→ 仲裁
- [ ] bump 版本号 / 发版:**问业主**(0.98.4 刚发)
