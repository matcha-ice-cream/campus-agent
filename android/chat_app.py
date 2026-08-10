# -*- coding: utf-8 -*-
"""
校园信息查询 Agent — Android App（Kivy）
=========================================
聊天界面：用户输入问题 → 调用后端 /api/query → 显示回答 + 来源

连接后端：把 SERVER_URL 改成你电脑的局域网 IP
"""

import json
import threading
import urllib.request

from kivy.app import App
from kivy.metrics import dp  # 密度适配：Android 高分屏自动放大，根治“字太小”
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.core.text import LabelBase

# 字体：Windows 用微软雅黑；Android 不注册自定义字体（系统自带中文字体，
# 注册路径可能因系统版本不同而缺失，曾在 Android 10+ 导致启动崩溃）
from kivy.core.text import LabelBase
from kivy.utils import platform as _platform
if _platform == "win":
    LabelBase.register(name="chinese", fn_regular="C:/Windows/Fonts/msyh.ttc")
# Android: 不注册 chinese，Kivy 用系统默认字体（中文正常显示）

# 设置全局默认字体，让 FileChooser 等内置控件的中英文都正常显示
from kivy.core.text import LabelBase as _LB
if _platform == "win":
    try:
        _LB.register(name="Roboto", fn_regular="C:/Windows/Fonts/msyh.ttc")
    except Exception:
        pass

# ============ 配置 ============
# 后端服务器地址（阿里云 ECS 公网 IP）
SERVER_URL = "http://120.26.244.59:8000/api/query"
# 头像路径（与 chat_app.py 同目录；打包时统一为英文文件名避免编码问题）
USER_AVATAR = "user_avatar.png"
AI_AVATAR = "ai_avatar.png"
# ==============================


def clean_markdown(text):
    """清理回答中的 Markdown 符号（Kivy Label 不渲染这些）"""
    import re
    # 去掉加粗 **xxx** → xxx
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 去掉行首的 - 或 * 列表符号
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    # 去掉剩余的孤立 **
    text = text.replace("**", "")
    # 合并 LLM 硬插的单换行（保留段落间的双换行）
    # 先把双换行换成占位符，单换行换成空格，再恢复双换行
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)          # 压缩多余空行
    text = re.sub(r"\n\n", "\x00", text)            # 双换行 → 占位
    text = re.sub(r"\n", "", text)                  # 单换行 → 去掉（合并句子）
    text = text.replace("\x00", "\n\n")             # 恢复段落
    return text


class ChatMessage(BoxLayout):
    """单条聊天消息：带头像，用户消息右对齐，回答左对齐"""
    def __init__(self, text, is_user, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.padding = (10, 6)
        self.spacing = 8

        # 头像（固定在顶部：容器占满高度，内部弹性空白把图片推到顶部）
        avatar_box = BoxLayout(orientation="vertical", size_hint=(None, 1), width=44)
        avatar = Image(
            source=USER_AVATAR if is_user else AI_AVATAR,
            size_hint=(None, None),
            size=(44, 44),
            keep_ratio=True,
        )
        avatar_box.add_widget(avatar)
        avatar_box.add_widget(BoxLayout())  # 弹性空白，把头像推到顶部

        # 气泡内容（AI 回答 92% 宽减少折行；用户消息 65% 右对齐贴头像）
        bubble_ratio = 0.65 if is_user else 0.92
        bubble = BoxLayout(orientation="vertical", size_hint=(bubble_ratio, None), padding=(12, 8))
        label = Label(
            text=text,
            size_hint_y=None,
            halign="right" if is_user else "left",  # 用户消息文本右对齐贴头像
            valign="top",
            text_size=(None, None),
            color=(1, 1, 1, 1),
            font_name="chinese",
        )
        bubble.add_widget(label)

        # 用户消息：头像在右，气泡靠右
        if is_user:
            self.add_widget(BoxLayout(size_hint_x=0.08))  # 弹性空白，气泡靠右
            self.add_widget(bubble)
            self.add_widget(avatar_box)
        else:
            # AI 回答：头像在左，气泡靠左
            self.add_widget(avatar_box)
            self.add_widget(bubble)
            self.add_widget(BoxLayout(size_hint_x=0.08))  # 弹性空白

        # 换行：text_size 宽度 = label 实际宽度（BoxLayout 已自动扣除 padding），
        # 文字恰好填满整行才换行；max(w,1) 防止布局初期宽度为 0/负值导致提前换行
        def _update_text_size(inst, w):
            inst.text_size = (max(w, 1), None)
        label.bind(width=_update_text_size)

        # 高度链：label 纹理高度 → bubble 高度 → 消息高度（不小于头像高度）
        def _update_height(inst, tex_size):
            label.height = tex_size[1]
            h = max(tex_size[1] + 16, 44)
            bubble.height = h
            self.height = h + 12
        label.bind(texture_size=_update_height)


class ChatApp(App):
    """主应用"""
    def build(self):
        # 软键盘弹出时自动上移内容（Android）：below_target 把输入框推到键盘上方
        from kivy.core.window import Window
        Window.softinput_mode = "below_target"

        root = BoxLayout(orientation="vertical")

        # ===== ScreenManager：两个页面 =====
        self.sm = ScreenManager()

        # --- 首页（聊天） ---
        home = Screen(name="home")
        home_layout = BoxLayout(orientation="vertical")

        # 标题
        title = Label(
            text="郑州大学北校区Agent助手",
            size_hint_y=None,
            height=dp(56),
            font_size=dp(22),
            bold=True,
            font_name="chinese",
        )
        home_layout.add_widget(title)

        # 标题下分隔线（与背景色不同的细线，区分标题和对话区）
        divider = BoxLayout(size_hint_y=None, height=dp(2))
        divider_line = BoxLayout(size_hint=(1, 1))
        from kivy.graphics import Color, Rectangle
        with divider_line.canvas:
            Color(0.35, 0.5, 0.9, 1)  # 蓝色细线
            self._divider_rect = Rectangle()
        divider_line.bind(
            size=lambda inst, s: setattr(self._divider_rect, "size", s),
            pos=lambda inst, p: setattr(self._divider_rect, "pos", p),
        )
        divider.add_widget(divider_line)
        home_layout.add_widget(divider)

        # 免责提示（细灰字）
        disclaimer = Label(
            text="回答由AI生成，仅供参考",
            size_hint_y=None,
            height=dp(28),
            font_size=dp(13),
            color=(0.6, 0.6, 0.6, 1),
            font_name="chinese",
        )
        home_layout.add_widget(disclaimer)

        # 消息区域（可滚动）
        self.chat_scroll = ScrollView()
        self.message_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
        self.message_box.bind(minimum_height=self.message_box.setter("height"))
        self.chat_scroll.add_widget(self.message_box)
        home_layout.add_widget(self.chat_scroll)

        # 输入框 + 发送按钮（加大，适配手指触控）
        bottom = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(110))
        self.input = TextInput(
            hint_text="输入你的问题，比如：现在这个时间南门开着吗？",
            multiline=True,  # 允许提示文字换行显示完整
            font_name="chinese",
            font_size=dp(20),
        )
        # 提示文字宽度限制为输入框宽度，超长自动换行
        self.input.bind(
            width=lambda inst, w: setattr(
                inst, "hint_text_size", (w - dp(10), None)
            )
        )
        self.input.hint_text_size = (dp(200), None)
        send_btn = Button(text="发送", size_hint_x=None, width=dp(110), font_name="chinese", font_size=dp(24))
        send_btn.bind(on_press=self.on_send)
        bottom.add_widget(self.input)
        bottom.add_widget(send_btn)
        home_layout.add_widget(bottom)

        home.add_widget(home_layout)
        self.sm.add_widget(home)

        # --- 更多页 ---
        more = Screen(name="more")
        more_layout = BoxLayout(orientation="vertical", padding=dp(25), spacing=dp(24))
        more_title = Label(
            text="更多功能",
            size_hint_y=None,
            height=dp(80),
            font_size=dp(32),
            bold=True,
            font_name="chinese",
        )
        more_layout.add_widget(more_title)
        more_layout.add_widget(BoxLayout(size_hint_y=0.10))  # 顶部留白

        upload_btn = Button(
            text="上传课表（docx）",
            size_hint=(1, None),
            height=dp(110),
            font_name="chinese",
            font_size=dp(30),
        )
        upload_btn.bind(on_press=self.on_upload)
        more_layout.add_widget(upload_btn)

        # 上传课表说明文字（放大到约4倍视觉尺寸）
        upload_hint = Label(
            text="上传课表功能是为了方便同学们查询校园Agent助手有关自己课程的问题，不上传则无法回答课程、老师等有关问题。\n\n有更多疑问请联系管理员，QQ：1304821679",
            size_hint=(1, None),
            height=dp(200),
            font_size=dp(24),
            halign="left",
            valign="top",
            font_name="chinese",
            text_size=(None, None),
            color=(0.75, 0.75, 0.75, 1),
        )
        upload_hint.bind(width=lambda inst, w: setattr(upload_hint, "text_size", (w - dp(10), None)))
        more_layout.add_widget(upload_hint)

        # 查看教程按钮
        tutorial_btn = Button(
            text="查看课表获取教程",
            size_hint=(1, None),
            height=dp(110),
            font_name="chinese",
            font_size=dp(30),
            background_color=(0.2, 0.5, 0.9, 1),
        )
        tutorial_btn.bind(on_press=self.on_tutorial)
        more_layout.add_widget(tutorial_btn)

        more_layout.add_widget(BoxLayout())  # 底部弹性
        more.add_widget(more_layout)
        self.sm.add_widget(more)

        root.add_widget(self.sm)

        # ===== 底部 tab 栏 =====
        tabs = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(70))
        self.btn_home = Button(
            text="首页",
            font_name="chinese",
            font_size=dp(20),
            background_color=(0.2, 0.5, 0.9, 1),
        )
        self.btn_more = Button(
            text="更多",
            font_name="chinese",
            font_size=dp(20),
            background_color=(0.3, 0.3, 0.3, 1),
        )
        self.btn_home.bind(on_press=lambda *a: self.switch_tab("home"))
        self.btn_more.bind(on_press=lambda *a: self.switch_tab("more"))
        tabs.add_widget(self.btn_home)
        tabs.add_widget(self.btn_more)
        root.add_widget(tabs)

        # 欢迎消息
        Clock.schedule_once(lambda dt: self._add_msg("你好！我是校园Agent助手，可以问我校历、课表、校医院、食堂等信息。", False), 0.1)

        return root

    def switch_tab(self, name):
        """切换 tab"""
        self.sm.current = name
        self.btn_home.background_color = (0.2, 0.5, 0.9, 1) if name == "home" else (0.3, 0.3, 0.3, 1)
        self.btn_more.background_color = (0.2, 0.5, 0.9, 1) if name == "more" else (0.3, 0.3, 0.3, 1)

    def on_tutorial(self, instance):
        """查看课表获取教程：跳转系统浏览器（原版方式），Windows 打开本地文件"""
        try:
            from kivy.utils import platform
            if platform == "android":
                import webbrowser
                webbrowser.open("http://120.26.244.59:8000/static/tutorial.mp4")
            else:
                # Windows：打开本地视频
                import os
                video = r"D:\mocha_workbench\agent_lab\campus_agent\课表获取视频教程.mp4"
                if os.path.exists(video):
                    os.startfile(video)
                else:
                    self._add_msg("本地教程视频不存在", False)
        except Exception as e:
            self._add_msg(f"打开教程失败：{e}", False)

    def on_upload(self, instance):
        """点击上传课表：Android 调系统文件选择器，Windows 用 FileChooser 兜底"""
        try:
            from kivy.utils import platform
            if platform == "android":
                self._android_pick_file()
            else:
                self._windows_file_chooser()
        except Exception as e:
            self._add_msg(f"打开文件选择器失败：{e}", False)

    def _android_pick_file(self):
        """Android：用 pyjnius 调系统 SAF 文件选择器"""
        from kivy.clock import Clock
        try:
            from jnius import autoclass, cast
            from android.activity import bind as activity_bind

            Intent = autoclass("android.content.Intent")
            Activity = autoclass("android.app.Activity")
            Uri = autoclass("android.net.Uri")

            self._pending_upload = False

            def on_activity_result(request_code, result_code, data):
                if request_code == 1001 and result_code == Activity.RESULT_OK and data:
                    uri = data.getData()
                    # 读取文件内容
                    import android  # noqa
                    from android.content import Context
                    resolver = cast("android.content.Context", Activity).getContentResolver()
                    stream = resolver.openInputStream(uri)
                    content = stream.read()
                    stream.close()
                    self._add_msg("正在上传课表…", True)
                    Clock.schedule_once(lambda dt, b=content: self._upload_schedule_bytes(b, "课表.docx"), 0)
                else:
                    self._add_msg("未选择文件", False)

            activity_bind(on_activity_result=on_activity_result)

            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            current = autoclass("org.kivy.android.PythonActivity").mActivity
            current.startActivityForResult(intent, 1001)
        except Exception as e:
            self._add_msg(f"Android 文件选择不可用：{e}", False)

    def _windows_file_chooser(self):
        """Windows：Kivy FileChooser"""
        from kivy.uix.filechooser import FileChooserListView
        from kivy.uix.popup import Popup

        chooser = FileChooserListView(
            filters=["*.docx"],
            path="C:/Users/13048/Desktop",
            font_name="chinese",
        )
        popup = Popup(title="选择课表 docx 文件", content=chooser, size_hint=(0.9, 0.9))

        def on_select(*args):
            if chooser.selection:
                filepath = chooser.selection[0]
                popup.dismiss()
                self._add_msg(f"正在上传课表：{filepath.split('/')[-1]}", True)
                threading.Thread(target=self._upload_schedule, args=(filepath,), daemon=True).start()

        chooser.bind(on_submit=on_select)
        popup.open()

    def _upload_schedule(self, filepath):
        """上传课表 docx 到后端（Windows：从路径读文件）"""
        try:
            with open(filepath, "rb") as f:
                file_bytes = f.read()
            filename = filepath.split("/")[-1].split("\\")[-1]
            self._upload_schedule_bytes(file_bytes, filename)
        except Exception as e:
            Clock.schedule_once(lambda dt, t=f"读取文件失败：{e}": self._add_msg(t, False), 0)

    def _upload_schedule_bytes(self, file_bytes, filename="课表.docx"):
        """上传课表字节流到后端（Android/Windows 共用）"""
        import uuid
        boundary = uuid.uuid4().hex

        # 构造 multipart/form-data
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        upload_url = SERVER_URL.replace("/api/query", "/api/upload-schedule")
        try:
            req = urllib.request.Request(
                upload_url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                msg = result.get("message", "上传完成")
                if result.get("success"):
                    text = "✅ " + msg
                else:
                    text = "❌ " + msg
        except Exception as e:
            text = f"上传失败：{e}"
        Clock.schedule_once(lambda dt, t=text: self._add_msg(t, False), 0)

    def on_send(self, instance):
        """点击发送按钮"""
        question = self.input.text.strip()
        if not question:
            return
        self._add_msg(question, True)
        self.input.text = ""

        # 后台线程请求，不阻塞 UI
        threading.Thread(target=self._query, args=(question,), daemon=True).start()

    def _query(self, question):
        """请求后端"""
        try:
            data = json.dumps({"question": question}).encode("utf-8")
            req = urllib.request.Request(
                SERVER_URL,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                answer = result.get("answer", "（无回答）")
                # 清理 Markdown 符号（Kivy 不渲染 **、- 等）
                answer = clean_markdown(answer)
                text = answer
        except Exception as e:
            text = f"请求失败：{e}"
        Clock.schedule_once(lambda dt, t=text: self._add_msg(t, False), 0)

    def _add_msg(self, text, is_user):
        """在聊天区添加一条消息"""
        msg = ChatMessage(text, is_user)
        self.message_box.add_widget(msg)
        # 滚动到底部
        Clock.schedule_once(lambda dt: self.chat_scroll.scroll_to(msg), 0.1)


if __name__ == "__main__":
    import sys
    import os
    import traceback

    # 崩溃日志文件路径（App 私有目录）
    def _crash_log_path():
        try:
            from kivy.utils import platform
            if platform == "android":
                # Android: 写到 App 私有外部目录（无需权限）
                from android.storage import app_storage_dir
                return os.path.join(app_storage_dir(), "crash_log.txt")
            else:
                return os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")
        except Exception:
            return None

    # 全局异常钩子：落盘 + 打印 + 尝试显示
    def global_excepthook(exc_type, exc_value, exc_tb):
        try:
            detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            print(detail)
            # 落盘
            path = _crash_log_path()
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(detail)
            # 尝试在聊天区显示
            msg = "程序异常：%s" % exc_value
            try:
                app = ChatApp.get_running_app()
                if app:
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt, m=msg: app._add_msg(m, False), 0)
            except Exception:
                pass
        except Exception:
            pass
    sys.excepthook = global_excepthook

    ChatApp().run()
