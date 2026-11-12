# 任我行 378 · 现代 Android 重新打包

把 `F:\download\任我行.apk`（`com.qyqd`，versionCode 378）重新打包，使其能在 Android 14 / 15 / 16 上**安装**。

## 为什么原来装不上

| 项 | 原包 | 结果 |
| --- | --- | --- |
| `targetSdkVersion` | 22 | Android 14 起拒绝 < 23；**Android 15 / 16 起拒绝 < 24** |
| 签名方案 | 仅 v1（JAR），无 APK Signing Block | 新系统会告警 |
| 原生库 | 只有 `armeabi-v7a` | 纯 64 位机型无法安装 |

## 这次改了什么

**只改了一个编译后的整数**：`AndroidManifest.xml` 里 `uses-sdk` 的 `android:targetSdkVersion` 由 `22` 改为 `24`。

- 没有反编译、没有改代码、没有重排资源表 —— 资源 ID 零漂移。
- 校验方式：解包后逐条目比对，**831 个文件与原包逐字节一致**，只有 `AndroidManifest.xml` 和签名文件不同。
- 重新签名：v1 + v2 + v3，`zipalign -p 4` 已对齐。

> 为什么不能“真正重新编译”：这个包被 **360 加固**（`assets/libjiagu.so` + `com.stub.StubApp`），`classes.dex` 只有 11 个壳类，真实代码是加密后塞在 dex 数据段里的。没有源码、没有原始工程，能做的只有改打包元数据。

## 安装注意

1. **先卸载旧版本**再装。签名换了（`CN=Renwoxing Rebuild`），不能覆盖安装。
2. 安装时若提示“未知来源”，在系统里允许即可。
3. **纯 64 位机型仍然装不上**：包里只有 `armeabi-v7a` 的百度地图 SDK 和加固壳，没有 arm64 版本。小米/OPPO/vivo/荣耀的大多数机型仍兼容 32 位；Pixel 7 及更新机型不行。
4. 加固壳在 Android 10+ 上能否正常解密运行**未在真机验证**（本机没有设备/模拟器）。如果打开闪退，属于壳与新系统的兼容问题，不是这次改动导致的。

## 构建

```bash
# 需要 JDK 17 和 Android build-tools（含 zipalign / lib/apksigner.jar）
python3 tools/build.py \
  --input original/renwoxing-378-original.apk \
  --output dist/renwoxing-378-modern.apk \
  --build-tools /path/to/build-tools/34.0.0 \
  --keystore signing/rebuild-key.p12 \
  --ks-pass renwoxing2026 --key-alias renwoxing --key-pass renwoxing2026
```

GitHub Actions：打 `v*` 标签或手动触发 `Build APK` 工作流，会自动构建并发布 Release。

## 签名密钥

`signing/rebuild-key.p12` 是本次生成的自签名密钥（口令 `renwoxing2026`），故意提交到仓库里：这样以后每次构建签名一致，新版本可以覆盖安装旧版本。它只用于这个重新打包的应用，不要拿去签别的东西。
