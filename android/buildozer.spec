[app]

# App 名称（手机桌面显示的名字）
# 说明：ZZUN(郑州大学北校区) + Agent；去掉连字符和空格让桌面完整显示
title = ZZUN-Agent

# 包名（唯一标识，格式：域名反写.应用名）
package.name = campusagent
package.domain = com.mocha

# 源码入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# 版本
version = 0.3.0
version.code = 1

# 屏幕方向：竖屏
orientation = portrait

# 键盘弹出时窗口自动调整（配合 App 内 Window.softinput_mode）
android.window_soft_input_mode = adjustResize

# Kivy 相关
requirements = python3,kivy,requests

# 权限：网络（App 只通过 HTTP 通信，不需要存储权限）
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# Android 9+ 明文 HTTP 需要允许（App 要连 http://192.168.x.x:8000）
android.allow_backup = True
android.allow_insecure_connections = True

# 图标（512x512 PNG，去水印后）
icon.filename = %(source.dir)s/zzun_icon.png
android.appicon = %(source.dir)s/zzun_icon.png

# Loading 界面：暂不配置 presplash（部分机型 presplash 导致启动闪退，待排查）
# presplash.filename = %(source.dir)s/zzun_presplash.png

# 打包架构：同时支持 64位(arm64-v8a) + 32位(armeabi-v7a) 手机，避免老机型闪退
android.archs = arm64-v8a,armeabi-v7a

[buildozer]

# 日志级别
log_level = 2

# 下载目录（SDK 等大文件）
warn_on_root = 1
