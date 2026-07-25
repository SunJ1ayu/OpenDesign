# Tasks: opendesign-image-upload

- base-ref: c1ed7d1

> oracle 先行:先红检、先 commit,再动实现。oracle 对任何执行腿 off-limits。

## Oracle(先行)

- [x] `tests/test_ds_web_upload.py` — 名字闸表驱动 + 端点闸序 + **主判据走 /api/intake**
      + 撞名不覆盖 + 零写盘 + 无临时文件残留
- [x] `tests/e2e/image_upload.e2e.mjs` — 真 chromium DataTransfer 拖拽 → 卡片可见 →
      扫描整理 → 确认执行 → 文件到位

## 实现

- [x] `_safe_upload_name` 纯函数(复用 PROJECT_NAME_RE + 四条额外闸 + 截长)
- [x] `POST /api/upload` 针孔(12 道闸,tmp + os.replace + O_EXCL 撞名重试 + finally 清理)
- [ ] `X-Content-Type-Options: nosniff` + `Handler.timeout`
- [x] 前端:**图墙整页**拖拽区(收件箱卡片空箱时不渲染,不适合当投放区) + "已存为 xxx" 回显 + 引导指向「扫描整理」按钮
- [x] 版本号 0.48.0

## 收货

- [x] 全部 oracle 绿(30 例)+ 回归全套(pytest 635→640、node 200、e2e 17/17)
- [x] **亲自截图看**:拖拽高亮、上传后卡片、"已存为"提示
- [ ] verify.md(**full 四审** —— 第一个网页写盘口,不打折)
- [ ] UNTESTED 清单:Windows 文件名语义(ADS/保留名/尾点/大小写/长路径)+ 真机验收要点
