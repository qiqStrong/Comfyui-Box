"""
版本控制器
用于管理 ComfyUI 版本
"""

import json
from typing import Dict, List, Optional
from pathlib import Path

from ...utils.logger import app_logger as logger


class VersionController:
    """版本管理控制器"""
    
    def __init__(self, environment_manager=None, comfyui_process=None):
        """
        初始化版本控制器
        
        Args:
            environment_manager: 环境管理器实例
            comfyui_process: ComfyUI 进程实例
        """
        self._window = None
        self._git_manager = None
        self._dependency_manager = None
        self._process_manager = None
        self._environment_manager = environment_manager
        self._comfyui_process = comfyui_process
        self._callback_registered = False
    
    def set_window(self, window):
        """设置窗口引用"""
        self._window = window
    
    def set_environment_manager(self, environment_manager):
        """设置环境管理器"""
        self._environment_manager = environment_manager
    
    def set_comfyui_process(self, comfyui_process):
        """设置 ComfyUI 进程"""
        self._comfyui_process = comfyui_process
        if self._process_manager:
            self._process_manager.set_comfyui_process(comfyui_process)
    
    def _get_current_environment(self) -> Optional[Dict]:
        """
        获取当前环境配置
        
        Returns:
            当前环境配置字典
        """
        if not self._environment_manager:
            return None
        
        try:
            result = self._environment_manager.get_environments()
            if not result.get("success"):
                return None
            
            environments = result.get("environments", [])
            current_env_id = self._environment_manager.config_manager.get_current_environment_id()
            
            for env in environments:
                if env.get("id") == current_env_id:
                    return env
            
            return None
        except Exception as e:
            logger.error(f"[VersionController] 获取当前环境失败: {str(e)}")
            return None
    
    def _init_managers(self):
        """延迟初始化管理器"""
        current_env = self._get_current_environment()
        
        if current_env:
            general = current_env.get("general", {})
            comfyui_path = general.get("comfyuiPath", "")
            python_path = general.get("pythonPath", "")
            
            if self._git_manager is None:
                if comfyui_path:
                    from backend.src.core.git_manager import GitManager
                    self._git_manager = GitManager(comfyui_path)
                    self._register_background_update_callback()
            else:
                if comfyui_path and str(self._git_manager.repo_path) != comfyui_path:
                    from backend.src.core.git_manager import GitManager
                    self._git_manager = GitManager(comfyui_path)
                    self._register_background_update_callback()
                    logger.info(f"[VersionController] Git 管理器已更新到新环境: {comfyui_path}")
            
            if self._dependency_manager is None:
                if comfyui_path and python_path:
                    from backend.src.core.dependency_manager import DependencyManager
                    self._dependency_manager = DependencyManager(comfyui_path, python_path)
            else:
                if comfyui_path and python_path:
                    current_comfyui = getattr(self._dependency_manager, 'comfyui_path', None)
                    if current_comfyui and str(current_comfyui) != comfyui_path:
                        from backend.src.core.dependency_manager import DependencyManager
                        self._dependency_manager = DependencyManager(comfyui_path, python_path)
                        logger.info(f"[VersionController] 依赖管理器已更新到新环境: {comfyui_path}")
        
        if self._process_manager is None:
            from backend.src.core.process_manager import ProcessManager
            self._process_manager = ProcessManager(
                self._comfyui_process,
                self._environment_manager
            )
    
    def _register_background_update_callback(self):
        """注册后台更新回调"""
        if self._callback_registered or not self._git_manager:
            return
        
        def on_version_list_updated(version_type: str, page: int, data: Dict):
            self._notify_version_updated(version_type, page, data)
        
        self._git_manager.set_background_update_callback('version_list_updated', on_version_list_updated)
        self._callback_registered = True
        logger.debug("[VersionController] 已注册后台更新回调")
    
    def _notify_version_updated(self, version_type: str, page: int, data: Dict):
        """
        通知前端版本列表已更新
        
        Args:
            version_type: 版本类型
            page: 页码
            data: 更新后的数据
        """
        if not self._window:
            return
        
        try:
            event_data = {
                "versionType": version_type,
                "page": page,
                "versions": data.get("versions", []),
                "hasMore": data.get("has_more", False)
            }
            
            event_json = json.dumps(event_data, ensure_ascii=False)
            self._window.evaluate_js(
                f"window.dispatchEvent(new CustomEvent('versionListUpdated', {{ detail: {event_json} }}));"
            )
            logger.debug(f"[VersionController] 已通知前端版本列表更新: {version_type}, page={page}")
        except Exception as e:
            logger.warning(f"[VersionController] 通知前端失败: {str(e)}")
    
    def get_versions(self, version_type: str = 'stable', page: int = 1, page_size: int = 20, branch: str = None, force_refresh: bool = False) -> Dict:
        """
        获取版本列表
        
        Args:
            version_type: 版本类型 ('stable' 或 'dev')
            page: 页码
            page_size: 每页数量
            branch: 指定分支名称（可选）
            force_refresh: 是否强制全量刷新
            
        Returns:
            dict: 版本列表响应，包含错误类型和详细信息
        """
        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "errorType": "no_environment",
                    "error": "没有可用的环境，请先添加 ComfyUI 环境",
                    "versions": [],
                    "hasMore": False,
                    "fromCache": False,
                    "cacheAge": 0,
                    "isUpdating": False,
                    "needBackgroundUpdate": False
                }
            
            result = self._git_manager.get_versions(version_type, page, page_size, branch, force_refresh)
            
            if "error_type" in result:
                return {
                    "success": False,
                    "versions": result.get("versions", []),
                    "hasMore": result.get("has_more", False),
                    "errorType": result.get("error_type"),
                    "error": result.get("error"),
                    "repoPath": result.get("repo_path", ""),
                    "branch": result.get("branch", ""),
                    "fromCache": result.get("fromCache", False),
                    "cacheAge": result.get("cacheAge", 0),
                    "isUpdating": result.get("isUpdating", False),
                    "totalCached": result.get("totalCached", 0),
                    "newItemsCount": result.get("newTagsCount", result.get("newCommitsCount", 0)),
                    "needBackgroundUpdate": result.get("needBackgroundUpdate", False)
                }
            
            return {
                "success": True,
                "versions": result.get("versions", []),
                "hasMore": result.get("has_more", False),
                "fromCache": result.get("fromCache", False),
                "cacheAge": result.get("cacheAge", 0),
                "isUpdating": result.get("isUpdating", False),
                "lastFetchTime": result.get("lastFetchTime", ""),
                "totalCached": result.get("totalCached", 0),
                "newItemsCount": result.get("newTagsCount", result.get("newCommitsCount", 0)),
                "needBackgroundUpdate": result.get("needBackgroundUpdate", False)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "errorType": "unknown",
                "versions": [],
                "hasMore": False,
                "fromCache": False,
                "cacheAge": 0,
                "isUpdating": False,
                "needBackgroundUpdate": False
            }
    
    def get_current_version(self) -> Dict:
        """
        获取当前版本信息
        
        Returns:
            dict: 当前版本信息
        """
        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "errorType": "no_environment",
                    "error": "没有可用的环境，请先添加 ComfyUI 环境",
                    "version": None
                }
            
            current = self._git_manager.get_current_version()
            
            return {
                "success": True,
                "version": current
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "version": None
            }
    
    def get_remote_info(self) -> Dict:
        """
        获取远端信息
        
        Returns:
            dict: 远端信息
        """
        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "errorType": "no_environment",
                    "error": "没有可用的环境，请先添加 ComfyUI 环境",
                    "remoteInfo": None
                }
            
            remote_info = self._git_manager.get_remote_info()
            
            return {
                "success": True,
                "remoteInfo": remote_info
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "remoteInfo": None
            }
    
    def switch_version(self, version_id: str, version_type: str, force: bool = False) -> Dict:
        """
        切换版本（带回退机制）
        
        Args:
            version_id: 版本 ID (commit hash)
            version_type: 版本类型 ('stable' 或 'dev')
            force: 是否强制切换（丢弃本地修改）
            
        Returns:
            dict: 切换结果
        """
        original_commit = None

        from backend.src.utils.test_isolation import guard_write

        error = guard_write("切换 ComfyUI 版本")
        if error:
            return {"success": False, "needDependencyUpdate": False, "message": error}

        try:
            logger.info(f"[VersionController] 开始切换版本: {version_id} ({version_type}), force={force}")
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "needDependencyUpdate": False,
                    "message": "没有可用的环境，请先添加 ComfyUI 环境"
                }
            
            logger.info(f"[VersionController] 步骤 0: 保存当前版本")
            original_commit = self._git_manager.get_current_commit()
            if original_commit:
                logger.info(f"[VersionController] 当前版本: {original_commit[:8]}")
            else:
                logger.warning(f"[VersionController] 无法获取当前版本，回退功能将不可用")
            
            logger.info(f"[VersionController] 步骤 1: 执行 Git 切换")
            switch_result = self._git_manager.switch_version(version_id, force=force)
            
            if not switch_result.get("success"):
                logger.error(f"[VersionController] Git 切换失败: {switch_result.get('message')}")
                return switch_result
            
            logger.info(f"[VersionController] Git 切换成功")
            
            if self._environment_manager:
                try:
                    current_env = self._get_current_environment()
                    if current_env:
                        env_id = current_env.get("id")
                        comfyui_path = current_env.get("general", {}).get("comfyuiPath", "")
                        
                        if env_id and comfyui_path:
                            self._environment_manager._update_version_info(env_id, comfyui_path)
                            logger.info(f"[VersionController] 已更新环境 {env_id} 的版本信息")
                except Exception as e:
                    logger.warning(f"[VersionController] 更新版本信息失败: {e}")
            
            logger.info(f"[VersionController] 步骤 3: 检查依赖变更")
            need_update = self._dependency_manager.check_dependency_changes()
            logger.info(f"[VersionController] 依赖检查结果: needDependencyUpdate={need_update}")
            
            return {
                "success": True,
                "needDependencyUpdate": need_update,
                "message": "版本切换成功",
                "originalCommit": original_commit
            }
        except Exception as e:
            logger.error(f"[VersionController] 版本切换异常: {str(e)}", exc_info=True)
            
            if original_commit:
                logger.warning(f"[VersionController] 尝试回退到原始版本: {original_commit[:8]}")
                rollback_result = self._git_manager.rollback_to_commit(original_commit)
                if rollback_result.get("success"):
                    logger.info(f"[VersionController] 回退成功")
                else:
                    logger.error(f"[VersionController] 回退失败: {rollback_result.get('message')}")
            
            return {
                "success": False,
                "needDependencyUpdate": False,
                "message": f"版本切换失败: {str(e)}"
            }
    
    def rollback_version(self, commit_hash: str) -> Dict:
        """
        回退到指定版本
        
        Args:
            commit_hash: 目标 commit hash
            
        Returns:
            dict: 回退结果
        """
        try:
            logger.info(f"[VersionController] 开始回退版本: {commit_hash}")
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "message": "没有可用的环境，请先添加 ComfyUI 环境"
                }
            
            rollback_result = self._git_manager.rollback_to_commit(commit_hash)
            
            if not rollback_result.get("success"):
                logger.error(f"[VersionController] 回退失败: {rollback_result.get('message')}")
                return rollback_result
            
            logger.info(f"[VersionController] 回退成功")
            
            if self._environment_manager:
                try:
                    current_env = self._get_current_environment()
                    if current_env:
                        env_id = current_env.get("id")
                        comfyui_path = current_env.get("general", {}).get("comfyuiPath", "")
                        
                        if env_id and comfyui_path:
                            self._environment_manager._update_version_info(env_id, comfyui_path)
                            logger.info(f"[VersionController] 已更新环境 {env_id} 的版本信息")
                except Exception as e:
                    logger.warning(f"[VersionController] 更新版本信息失败: {e}")
            
            return {
                "success": True,
                "message": "版本回退成功"
            }
        except Exception as e:
            logger.error(f"[VersionController] 版本回退异常: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"版本回退失败: {str(e)}"
            }
    
    def update_dependencies(self) -> Dict:
        """
        更新依赖
        
        Returns:
            dict: 更新结果
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("更新 ComfyUI 依赖")
        if error:
            return {"success": False, "message": error}

        try:
            self._init_managers()
            
            result = self._dependency_manager.update_dependencies()
            
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"依赖更新失败: {str(e)}"
            }
    
    def restart_process(self) -> Dict:
        """
        重启进程
        
        Returns:
            dict: 重启结果
        """
        try:
            self._init_managers()
            
            result = self._process_manager.restart()
            
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"进程重启失败: {str(e)}"
            }
    
    def check_process_status(self) -> Dict:
        """
        检查进程状态
        
        Returns:
            dict: 进程状态
        """
        try:
            self._init_managers()
            
            status = self._process_manager.get_status()
            
            return {
                "success": True,
                "isRunning": status.get("is_running", False),
                "hasTask": status.get("has_task", False)
            }
        except Exception as e:
            return {
                "success": False,
                "isRunning": False,
                "hasTask": False,
                "error": str(e)
            }
    
    def update_remote_url(self, url: str) -> Dict:
        """
        更新远端地址
        
        Args:
            url: 远端仓库地址
            
        Returns:
            dict: 更新结果
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("修改 ComfyUI 远程仓库地址")
        if error:
            return {"success": False, "message": error}

        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "message": "没有可用的环境，请先添加 ComfyUI 环境"
                }
            
            result = self._git_manager.update_remote_url(url)
            
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"更新远端地址失败: {str(e)}"
            }
    
    def fix_git_ownership(self) -> Dict:
        """
        手动修复 Git 所有权问题
        
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        try:
            if not self._git_manager:
                self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "message": "没有可用的环境，请先添加 ComfyUI 环境"
                }
            
            success = self._git_manager._fix_ownership_issue()
            
            if success:
                return {
                    "success": True,
                    "message": "Git 权限问题已修复"
                }
            else:
                repo_path = self._git_manager.repo_path
                return {
                    "success": False,
                    "message": (
                        f"自动修复失败，请手动执行以下命令：\n"
                        f"git config --global --add safe.directory \"{repo_path}\""
                    )
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"修复失败: {str(e)}"
            }
    
    def get_branches(self) -> Dict:
        """
        获取分支列表
        
        Returns:
            dict: {
                "success": bool,
                "current_branch": str,
                "local_branches": List[str],
                "remote_branches": List[str],
                "error": str (可选)
            }
        """
        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "error": "没有可用的环境，请先添加 ComfyUI 环境",
                    "current_branch": None,
                    "local_branches": [],
                    "remote_branches": []
                }
            
            result = self._git_manager.get_branches()
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "获取分支列表失败"),
                    "current_branch": None,
                    "local_branches": [],
                    "remote_branches": []
                }
            
            return {
                "success": True,
                "current_branch": result.get("current_branch"),
                "local_branches": result.get("local_branches", []),
                "remote_branches": result.get("remote_branches", [])
            }
        except Exception as e:
            logger.error(f"[VersionController] 获取分支列表失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "current_branch": None,
                "local_branches": [],
                "remote_branches": []
            }
    
    def switch_branch(self, branch_name: str) -> Dict:
        """
        切换分支
        
        Args:
            branch_name: 分支名称
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        from backend.src.utils.test_isolation import guard_write

        error = guard_write("切换 ComfyUI 分支")
        if error:
            return {"success": False, "message": error}

        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "message": "没有可用的环境，请先添加 ComfyUI 环境"
                }
            
            result = self._git_manager.switch_branch(branch_name)
            
            if result.get("success"):
                self._git_manager.clear_version_cache()
                logger.info(f"[VersionController] 已清除版本列表缓存（切换分支: {branch_name}）")
            
            return result
        except Exception as e:
            logger.error(f"[VersionController] 切换分支失败: {str(e)}")
            return {
                "success": False,
                "message": f"切换分支失败: {str(e)}"
            }
    
    def clear_version_cache(self, version_type: str = None) -> Dict:
        """
        清除版本列表缓存
        
        Args:
            version_type: 版本类型 ('stable' 或 'dev')，如果为 None 则清除所有类型
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        try:
            self._init_managers()
            
            if not self._git_manager:
                return {
                    "success": False,
                    "message": "没有可用的环境，请先添加 ComfyUI 环境"
                }
            
            success = self._git_manager.clear_version_cache(version_type)
            
            if success:
                return {
                    "success": True,
                    "message": "版本列表缓存已清除"
                }
            else:
                return {
                    "success": False,
                    "message": "清除缓存失败"
                }
        except Exception as e:
            logger.error(f"[VersionController] 清除版本缓存失败: {str(e)}")
            return {
                "success": False,
                "message": f"清除缓存失败: {str(e)}"
            }
