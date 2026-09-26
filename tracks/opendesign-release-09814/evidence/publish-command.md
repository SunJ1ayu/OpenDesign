# 0.98.14 正式发布命令(等待最终批准)

先验证 `python3 tracks/opendesign-release-09814/evidence/check-assets.py`;
此文件准备命令,不会自行执行。版本包来源为成功 run 36226326190。

```bash
git push origin main
gh release create v0.98.14 \
  /root/opendesign-release14/artifact/OpenDesign-0.98.14-electron-setup.exe \
  /root/opendesign-release14/artifact/OpenDesign-0.98.14-electron-setup.exe.blockmap \
  /root/opendesign-release14/latest.yml \
  --repo SunJ1ayu/OpenDesign \
  --target b37b8ddd4c3be2f35fccf6c8a853caab3036bd0f \
  --title 'OpenDesign 0.98.14' \
  --notes-file tracks/opendesign-release-09814/evidence/release-notes.md
```

明确 target 为被测提交,不依赖默认分支当时在哪。发布后再核正式源 latest/tag/三样字节与本次 manifest 相同,
核旧版 blockmap 仍在,记录生产源收据后归档。正式 release 非 prerelease,会进入自动更新源。
