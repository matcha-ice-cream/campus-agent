[app]

# App 名称（手机桌面显示的名字）
# 注意：含中文可能导致 Gradle 打包失败，先用英文名
title = Campus Agent

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
# 用最新 Kivy（2.4.x，支持 Python 3.14，无 config.pxi 老问题）
# requirements 不指定 python 版本：p4a 用默认（3.14）
requirements = python3,kivy,requests

# 权限：网络 + 读存储（上传文件需要）
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# Android 9+ 明文 HTTP 需要允许（App 要连 http://192.168.x.x:8000）
android.allow_backup = True
android.allow_insecure_connections = True

# 图标（可选，用 AI 头像）
# icon.filename = %(source.dir)s/ai助手头像.png
# android.appicon = %(source.dir)s/ai助手头像.png

# 打包成 debug APK（最快）
android.archs = arm64-v8a

[buildozer]

# 日志级别
log_level = 2

# 下载目录（SDK 等大文件）
warn_on_root = 1
