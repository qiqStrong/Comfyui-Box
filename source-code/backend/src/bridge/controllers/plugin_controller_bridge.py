"""
插件管理控制器桥接层

连接前端和后端插件管理功能
"""

from pathlib import Path
from typing import Dict, Optional, List
from backend.src.core.plugin.plugin_controller import PluginController
from backend.src.core.settings_manager import SettingsManager
from backend.src.utils.logger import app_logger as logger


class PluginControllerBridge:
    """插件管理控制器桥接"""
    
    def __init__(self, environment_manager):
        """
        初始化插件控制器桥接（增强版：使用环境 Python）
        
        增强功能：
        1. 尝试获取当前环境的 Python 路径
        2. 如果成功，使用环境 Python 初始化
        3. 如果失败，降级到默认 Python（保持向后兼容）
        
        Args:
            environment_manager: 环境管理器实例
        """
        self.environment_manager = environment_manager
        
        # 初始化设置管理器
        self.settings_manager = SettingsManager()
        
        # 尝试获取当前环境的 Python 路径
        env = self._get_current_environment()
        python_path = None
        if env and env.get("pythonPath"):
            python_path = Path(env.get("pythonPath"))
            logger.info(f"[PluginControllerBridge] 初始化使用环境 Python: {python_path}")
        else:
            logger.warning("[PluginControllerBridge] 初始化时未找到环境 Python，使用默认")
        
        # 导入 Git 配置
        from backend.src.utils.git_config import get_git_executable
        from backend.src.utils.paths import get_cache_dir
        
        # 初始化插件控制器（使用 cache 目录存储缓存）
        cache_dir = get_cache_dir("plugins")
        self.controller = PluginController(
            cache_dir=cache_dir,
            git_path=get_git_executable(),  # 动态获取 Git 路径
            python_path=python_path,  # 使用环境 Python（如果可用）
            max_workers=10
        )
        
        self._window = None
    
    def set_window(self, window):
        """设置窗口引用"""
        self._window = window
    
    def _get_current_environment(self) -> Optional[Dict]:
        """获取当前环境配置"""
        try:
            # 先尝试获取当前环境
            env_obj = self.environment_manager.get_current_environment()
            if env_obj:
                # Environment对象转换为字典
                return {
                    "id": env_obj.id,
                    "comfyuiPath": str(env_obj.path),  # Environment.path 就是 ComfyUI 路径
                    "pythonPath": str(env_obj.config.general.python_path) if env_obj.config.general.python_path else None
                }
            
            # 如果没有当前环境，尝试获取第一个可用环境
            envs_result = self.environment_manager.get_environments()
            if envs_result.get("success") and envs_result.get("environments"):
                environments = envs_result.get("environments")
                if environments and len(environments) > 0:
                    # 返回第一个环境
                    first_env = environments[0]
                    # 从general字段获取路径
                    general = first_env.get("general", {})
                    return {
                        "id": first_env.get("id"),
                        "comfyuiPath": general.get("comfyuiPath"),
                        "pythonPath": general.get("pythonPath")
                    }
            
            return None
        except Exception as e:
            logger.error(f"[PluginControllerBridge] 获取当前环境失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _collect_custom_nodes_paths(self, comfyui_path: str, environment_obj) -> List[Path]:
        """
        收集所有 custom_nodes 路径（主路径 + 外置路径）
        
        从环境的 model_path_configs 中提取外置 custom_nodes 目录路径。
        主路径始终排第一。
        
        Args:
            comfyui_path: ComfyUI 安装路径
            environment_obj: Environment 对象（用于读取 model_path_configs）
            
        Returns:
            Path 列表，第一个为主路径，后续为外置路径
        """
        paths = [Path(comfyui_path) / "custom_nodes"]
        
        if environment_obj and hasattr(environment_obj, 'model_path_configs'):
            for config in environment_obj.model_path_configs:
                cn_rel = config.paths.get("custom_nodes") or config.paths.get("customNodes")
                if cn_rel:
                    ext_path = Path(config.base_path) / cn_rel
                    if ext_path.exists() and ext_path not in paths:
                        paths.append(ext_path)
        
        return paths
    
    def _ensure_environment_set(self) -> bool:
        """
        确保环境已设置（增强版：支持多路径 + 动态更新 Python 路径）
        
        增强功能：
        1. 获取当前环境配置
        2. 收集所有 custom_nodes 路径（主路径 + 外置路径）
        3. 动态更新 DependencyManager 的 Python 路径
        4. 只在路径变化时更新和记录日志
        5. 确保后台任务使用正确的 Python 环境
        
        Returns:
            bool: 环境设置是否成功
        """
        env = self._get_current_environment()
        if not env:
            logger.warning("[PluginControllerBridge] 未找到可用环境")
            return False
        
        env_id = env.get("id")
        # 尝试多个可能的路径字段名
        comfyui_path = env.get("comfyuiPath") or env.get("comfyui_path")
        python_path = env.get("pythonPath")
        
        if not env_id or not comfyui_path:
            logger.warning(f"[PluginControllerBridge] 环境配置无效: env_id={env_id}, comfyui_path={comfyui_path}")
            return False
        
        # 动态更新 DependencyManager 的 Python 路径
        if python_path:
            new_python_path = Path(python_path)
            current_python_path = self.controller.dependency_manager._python_path
            
            # 只在路径变化时更新和记录日志
            if str(current_python_path) != str(new_python_path):
                self.controller.dependency_manager._python_path = new_python_path
                logger.info(f"[PluginControllerBridge] 已更新 Python 路径: {new_python_path}")
        else:
            logger.warning(f"[PluginControllerBridge] 环境 {env_id} 未配置 Python 路径")
        
        # 获取完整的 Environment 对象以读取 model_path_configs
        environment_obj = self.environment_manager.get_current_environment()
        
        # 收集所有 custom_nodes 路径（主路径 + 外置路径）
        custom_nodes_paths = self._collect_custom_nodes_paths(comfyui_path, environment_obj)
        
        # 设置环境（传递路径列表）
        self.controller.set_environment(env_id, custom_nodes_paths, Path(python_path) if python_path else None)
        
        return True
    
    # API 方法
    
    def get_plugins(self, use_cache: bool = True) -> Dict:
        """获取插件列表"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境或环境配置无效'
            }
        
        result = self.controller.get_plugins(use_cache)
        
        # 返回结果（移除调试日志）
        return result
    
    def search_plugins(self, keyword: str) -> Dict:
        """搜索插件"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.search_plugins(keyword)
    
    def refresh_plugins(self) -> Dict:
        """刷新插件列表"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.refresh_plugins()
    
    def refresh_plugin_git_info(self, plugin_name: str) -> Dict:
        """
        刷新单个插件的 Git 信息
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            刷新结果，包含更新后的插件信息
        """
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.refresh_plugin_git_info(plugin_name)
    
    def get_refresh_progress(self) -> Dict:
        """获取刷新进度"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.get_refresh_progress()
    
    def cancel_background_update(self) -> Dict:
        """取消后台更新任务"""
        return self.controller.cancel_background_update()
    
    def get_plugin_dependencies(self, plugin_name: str) -> Dict:
        """获取插件依赖"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.get_plugin_dependencies(plugin_name)
    
    def install_dependency(
        self,
        plugin_name: str,
        package: str,
        version: str = "",
        pip_options: Optional[List[str]] = None
    ) -> Dict:
        """
        安装依赖（增强版：使用当前环境的 Python 和 pip 选项）
        
        增强功能：
        1. 从当前环境获取 Python 路径
        2. 传递给 PluginController 确保使用正确的 Python
        3. 支持 pip 额外选项（如 --extra-index-url）
        4. 避免依赖被安装到系统 Python 环境
        
        Args:
            plugin_name: 插件名称
            package: 包名
            version: 版本要求
            pip_options: pip 额外选项列表（可选，如 ["--extra-index-url", "https://..."]）
        
        Returns:
            安装结果
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("安装插件依赖")
        if error:
            return {'success': False, 'error': error, 'log_file': None}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境',
                'log_file': None
            }
        
        # 获取当前环境的 Python 路径
        env = self._get_current_environment()
        if not env:
            return {
                'success': False,
                'error': '无法获取当前环境配置',
                'log_file': None
            }
        
        python_path = env.get("pythonPath")
        if not python_path:
            return {
                'success': False,
                'error': '当前环境未配置 Python 路径',
                'log_file': None
            }
        
        logger.info(f"[PluginControllerBridge] 安装依赖配置: plugin={plugin_name}, package={package}, python_path={python_path}, pip_options={pip_options}")
        
        # 传递 Python 路径和 pip 选项给 PluginController
        return self.controller.install_dependency(
            plugin_name=plugin_name,
            package=package,
            version=version,
            python_path=Path(python_path),
            pip_options=pip_options
        )
    
    def update_plugin(self, plugin_name: str, force: bool = False) -> Dict:
        """
        更新插件
        
        Args:
            plugin_name: 插件名称
            force: 是否强制覆盖本地修改
            
        Returns:
            dict: 更新结果
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("更新插件")
        if error:
            return {'success': False, 'error': error}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        def progress_callback(progress_data: Dict):
            if self._window:
                try:
                    import json
                    event_data = {**progress_data, 'plugin_name': plugin_name}
                    js_code = f"window.dispatchEvent(new CustomEvent('plugin-update-progress', {{detail: {json.dumps(event_data, ensure_ascii=False)}}}));"
                    self._window.evaluate_js(js_code)
                except Exception as e:
                    logger.warning(f"[Bridge] 发送更新进度事件失败: {e}")
        
        return self.controller.update_plugin(plugin_name, force=force, progress_callback=progress_callback)
    
    def update_all_plugins(self, python_path: Optional[str] = None, max_workers: Optional[int] = None) -> Dict:
        """
        一键更新所有插件（增强版）
        
        增强功能：
        1. 从当前环境获取 Python 路径（如果未提供）
        2. 从系统设置获取 Git 并发数配置（如果未提供）
        3. 传递这些参数给 PluginController
        4. 返回包含依赖安装统计的结果
        
        Args:
            python_path: Python 可执行文件路径（可选，未提供时从环境获取）
            max_workers: Git 并发数（可选，未提供时从设置获取）
        
        Returns:
            dict: 更新结果，包含摘要统计
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("批量更新插件")
        if error:
            return {'success': False, 'error': error}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        # 如果未提供 python_path，从当前环境获取
        if python_path is None:
            env = self._get_current_environment()
            if not env:
                return {
                    'success': False,
                    'error': '无法获取当前环境配置'
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    'success': False,
                    'error': '当前环境未配置 Python 路径'
                }
        
        # 如果未提供 max_workers，从系统设置获取
        if max_workers is None:
            settings_result = self.settings_manager.get_settings()
            max_workers = 10  # 默认值
            
            if settings_result.get("success"):
                settings = settings_result.get("settings", {})
                # 从 general 配置中获取 git_concurrent_workers
                general = settings.get("general", {})
                max_workers = general.get("git_concurrent_workers", 10)
        
        logger.info(f"[PluginControllerBridge] 批量更新配置: python_path={python_path}, max_workers={max_workers}")
        
        # 调用 PluginController 的增强版 update_all_plugins
        return self.controller.update_all_plugins(
            python_path=Path(python_path),
            max_workers=max_workers
        )
    
    def get_update_info(self, plugin_name: str) -> Dict:
        """获取更新信息"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.get_update_info(plugin_name)
    
    def switch_branch(
        self, 
        plugin_name: str, 
        branch: str,
        commit_hash: str = None,
        commit_date: str = None
    ) -> Dict:
        """
        切换分支
        
        Args:
            plugin_name: 插件名称
            branch: 分支名
            commit_hash: 分支的 commit hash（可选，前端已获取）
            commit_date: 分支的 commit date（可选，前端已获取）
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("切换插件分支")
        if error:
            return {'success': False, 'error': error}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.switch_branch(plugin_name, branch, commit_hash, commit_date)
    
    def switch_plugin_version(
        self,
        plugin_name: str,
        commit_hash: str,
        commit_date: str = None,
        behind_commits: int = None,
        force: bool = False
    ) -> Dict:
        """
        切换插件版本
        
        Args:
            plugin_name: 插件名称
            commit_hash: 目标 commit hash
            commit_date: 提交日期（可选，前端已获取）
            behind_commits: 落后提交数（可选，前端已计算）
            force: 是否强制覆盖本地修改
            
        Returns:
            dict: 切换结果
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("切换插件版本")
        if error:
            return {'success': False, 'error': error}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        def progress_callback(progress_data: Dict):
            if self._window:
                try:
                    import json
                    event_data = {**progress_data, 'plugin_name': plugin_name}
                    js_code = f"window.dispatchEvent(new CustomEvent('plugin-switch-progress', {{detail: {json.dumps(event_data, ensure_ascii=False)}}}));"
                    self._window.evaluate_js(js_code)
                except Exception as e:
                    logger.warning(f"[Bridge] 发送切换版本进度事件失败: {e}")
        
        return self.controller.switch_plugin_version(
            plugin_name,
            commit_hash,
            commit_date=commit_date,
            behind_commits=behind_commits,
            force=force,
            progress_callback=progress_callback
        )
    
    def get_branches(self, plugin_name: str) -> Dict:
        """获取分支列表"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.get_branches(plugin_name)
    
    def uninstall_plugin(self, plugin_name: str) -> Dict:
        """卸载插件"""
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("卸载插件")
        if error:
            return {'success': False, 'error': error}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.uninstall_plugin(plugin_name)
    
    def open_plugin_folder(self, plugin_name: str) -> Dict:
        """打开插件文件夹"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.open_plugin_folder(plugin_name)
    
    def detect_conflicts(self) -> Dict:
        """检测插件依赖冲突"""
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.detect_conflicts()
    
    def toggle_plugin_enabled(self, plugin_name: str, enabled: bool) -> Dict:
        """切换插件启用/禁用状态"""
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("启用/禁用插件")
        if error:
            return {'success': False, 'error': error}

        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.toggle_plugin_enabled(plugin_name, enabled)
    
    def check_git_permissions(self) -> Dict:
        """
        检查 Git 权限（前端 API）
        
        Returns:
            检查结果字典
            {
                'success': bool,
                'total': int,
                'problem_count': int,
                'problem_repos': List[Dict],
                'git_version': str,
                'is_supported': bool,
                'error': str  # 错误信息（失败时）
            }
        """
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.check_git_permissions()
    
    def fix_git_permissions(self) -> Dict:
        """
        修复 Git 权限（前端 API）
        
        Returns:
            修复结果字典
            {
                'success': bool,
                'total': int,
                'fixed': int,
                'failed': int,
                'failed_repos': List[Dict],
                'duration': float,
                'error': str  # 错误信息（失败时）
            }
        """
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.fix_git_permissions()
    
    def set_plugin_remote_url(self, plugin_name: str, remote_url: str) -> Dict:
        """
        设置插件的远端地址
        
        Args:
            plugin_name: 插件名称
            remote_url: 远端仓库地址
            
        Returns:
            dict: 操作结果
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("修改插件远端地址")
        if error:
            return {'success': False, 'error': error}
        if not self._ensure_environment_set():
            return {
                'success': False,
                'error': '未设置环境'
            }
        
        return self.controller.set_plugin_remote_url(plugin_name, remote_url)
