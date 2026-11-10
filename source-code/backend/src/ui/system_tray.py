"""
系统托盘管理模块

提供 Windows 系统托盘功能，支持：
- 最小化窗口到托盘（隐藏窗口）
- 从托盘恢复窗口
- 启动/停止 ComfyUI
- 退出应用

注意：pystray 不支持双击事件, default=True 的菜单项在单击图标时激活
"""

import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from backend.src.utils.logger import app_logger as logger
from backend.src.utils.paths import get_resource_logo_dir


class SystemTrayManager:
    """系统托盘管理器"""
    
    _instance: Optional['SystemTrayManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._tray = None
        self._icon = None
        self._window = None
        self._api = None
        self._running = False
        self._thread = None

        self._on_restore: Optional[Callable] = None
        self._on_exit: Optional[Callable] = None
        self._on_start_comfyui: Optional[Callable] = None
        self._on_stop_comfyui: Optional[Callable] = None
    
    def set_window(self, window):
        """设置主窗口引用"""
        self._window = window
    
    def set_api(self, api):
        """设置 API 引用"""
        self._api = api
    
    def set_callbacks(
        self,
        on_restore: Callable,
        on_exit: Callable,
        on_start_comfyui: Optional[Callable] = None,
        on_stop_comfyui: Optional[Callable] = None,
    ):
        """设置回调函数"""
        self._on_restore = on_restore
        self._on_exit = on_exit
        self._on_start_comfyui = on_start_comfyui
        self._on_stop_comfyui = on_stop_comfyui
    
    def _load_icon(self):
        """加载托盘图标"""
        try:
            from PIL import Image

            icon_path = get_resource_logo_dir() / 'icon.png'

            if icon_path.exists():
                self._icon = Image.open(icon_path)
                logger.debug(f"[SystemTray] 图标加载成功: {icon_path}")
            else:
                self._icon = Image.new('RGBA', (64, 64), color=(59, 130, 246, 255))
                logger.warning(f"[SystemTray] 图标文件不存在，使用默认图标")

            if self._icon.size != (64, 64):
                self._icon = self._icon.resize((64, 64), Image.Resampling.LANCZOS)

            return self._icon
        except Exception as e:
            logger.error(f"[SystemTray] 加载图标失败: {e}")
            return None
    
    def _create_menu(self):
        """创建托盘菜单"""
        import pystray
        from pystray import MenuItem as item

        def restore_window(icon, item):
            logger.info("[SystemTray] 单击图标，恢复窗口")
            if self._on_restore:
                self._on_restore()

        def start_comfyui(icon, item):
            logger.info("[SystemTray] 点击启动 ComfyUI")
            if self._on_start_comfyui:
                self._on_start_comfyui()

        def stop_comfyui(icon, item):
            logger.info("[SystemTray] 点击停止 ComfyUI")
            if self._on_stop_comfyui:
                self._on_stop_comfyui()

        def exit_app(icon, item):
            logger.info("[SystemTray] 点击退出应用")
            if self._on_exit:
                self._on_exit()

        menu_items = [
            item('恢复窗口', restore_window, default=True),
            item('启动 ComfyUI', start_comfyui),
            item('停止 ComfyUI', stop_comfyui),
            item('退出应用', exit_app),
        ]

        return pystray.Menu(*menu_items)

    def _setup(self, icon):
        """pystray setup 回调,在图标准备好后执行"""
        icon.visible = True
        logger.info("[SystemTray] 托盘图标已显示")

    def create(self):
        """创建系统托盘"""
        if sys.platform != 'win32':
            logger.warning("[SystemTray] 仅支持 Windows 平台")
            return False

        if self._running and self._tray is not None:
            logger.debug("[SystemTray] 托盘已存在且正在运行")
            return True

        try:
            import pystray

            icon = self._load_icon()
            if icon is None:
                return False

            menu = self._create_menu()

            self._tray = pystray.Icon(
                name='Comfyui-Box',
                icon=icon,
                title='Comfyui-Box',
                menu=menu
            )

            self._running = True
            logger.info("[SystemTray] 托盘创建成功")
            return True

        except ImportError:
            logger.error("[SystemTray] pystray 未安装，请运行 pip install pystray")
            return False
        except Exception as e:
            logger.error(f"[SystemTray] 创建托盘失败: {e}")
            return False

    def show(self):
        """显示托盘图标"""
        if self._tray is None:
            if not self.create():
                return False

        if self._thread is not None and self._thread.is_alive():
            logger.debug("[SystemTray] 托盘线程已在运行")
            return True

        try:
            self._thread = threading.Thread(target=self._tray.run, args=(self._setup,), daemon=True)
            self._thread.start()
            logger.info("[SystemTray] 托盘图标已显示")
            return True
        except Exception as e:
            logger.error(f"[SystemTray] 显示托盘失败: {e}")
            return False

    def hide(self):
        """隐藏托盘图标"""
        if self._tray is None:
            return

        try:
            self._tray.visible = False
            logger.debug("[SystemTray] 托盘图标已隐藏")
        except Exception as e:
            logger.error(f"[SystemTray] 隐藏托盘失败: {e}")

    def destroy(self):
        """销毁托盘"""
        if self._tray is None:
            return

        try:
            self._tray.stop()
            self._tray = None
            self._thread = None
            self._running = False
            self._initialized = False
            logger.info("[SystemTray] 托盘已销毁")
        except Exception as e:
            logger.error(f"[SystemTray] 销毁托盘失败: {e}")

    def update_comfyui_status(self, is_running: bool):
        """更新 ComfyUI 运行状态（可用于更新菜单项状态）"""
        logger.debug(f"[SystemTray] ComfyUI 状态更新: {is_running}")

    @property
    def is_running(self) -> bool:
        """托盘是否正在运行"""
        return self._running and self._tray is not None


system_tray_manager = SystemTrayManager()