[app]

# App 名称（手机桌面显示的名字）
title = 郑大北区Agent助手

# 包名（唯一标识，格式：域名反写.应用名）
package.name = campusagent
package.domain = com.mocha

# 源码入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# 版本
version = 0.3.0
version.code = 1

# Kivy 相关
requirements = python3,kivy,requests,python-docx,pyjnius,android

# 权限：网络 + 读存储（上传文件需要）
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_DOCUMENTS

# Android 9+ 明文 HTTP 需要允许（App 要连 http://192.168.x.x:8000）
android.allow_backup = True
android.allow_insecure_connections = True

# 图标（可选，用 AI 头像）
# icon.filename = %(source.dir)s/ai助手头像.png
# android.appicon = %(source.dir)s/ai助手头像.png

# 打包成 debug APK（最快）
android.archs = arm64-v8a

# 复用已下载的 python-for-android（避免每次从 GitHub 克隆）
p4a.source_dir = ~/.buildozer/android/platform/python-for-android

[buildozer]

# 日志级别
log_level = 2

# 下载目录（SDK 等大文件）
warn_on_root = 1

# ===== 国内镜像加速（避免从 Google 下载卡死） =====
# Android SDK 组件下载镜像（腾讯云）
android_sdk_repository = https://mirrors.cloud.tencent.com/AndroidSDK/
# 源码仓库镜像（阿里云，镜像 android.googlesource.com）
android_ndk_repository = https://mirrors.aliyun.com/android.googlesource.com/android-ndk/
# Maven 仓库镜像
android_maven_repository = https://maven.aliyun.com/repository/public
# Gradle 下载镜像
gradle_repository = https://mirrors.cloud.tencent.com/gradle/
