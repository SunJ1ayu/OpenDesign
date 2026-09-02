# Tasks: opendesign-release-0983

- base-ref: fefefb5

- [ ] T1 bump bin/ds_web.py VERSION 0.98.2 → 0.98.3
- [ ] T2 修 windows-package-probe.yml 四处默认值 0.98.2 → 0.98.3
- [ ] T3 跑 installer/build-installer.sh,四道闸必须全绿
- [ ] T4 从 exe 内容读回版本号 = 0.98.3(不看文件名)
- [ ] T5 发 pre-release win-installer-0.98.3 并上传资产
- [ ] T6 业主真机装一趟 + 回显版本(只有他能做)
