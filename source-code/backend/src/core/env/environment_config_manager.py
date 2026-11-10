"""
Environment configuration manager for Comfyui-Box.

This module provides functionality to manage environment configurations,
including loading, saving, importing, and exporting configurations.
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Union

from .error_codes import ErrorCode, get_error_message
from .types import Environment
from ..config.config_migrator import ConfigMigrator
from ...utils.logger import app_logger as logger


class EnvironmentConfigManager(ConfigMigrator):
    """
    Manager for environment configurations.
    
    单例模式实现，确保全局只有一个实例，保证缓存一致性。
    """
    
    CURRENT_VERSION = "1.0.0"
    CONFIG_FILENAME = "environments.json"
    
    _instance = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, config_dir: Optional[str] = None):
        """
        单例模式：确保全局只有一个实例
        
        Args:
            config_dir: 配置目录（仅首次创建时有效）
            
        Returns:
            EnvironmentConfigManager 实例
        """
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the environment configuration manager.
        
        Args:
            config_dir: Directory to store configuration files.
                       If None, uses default config directory.
        """
        if self._initialized:
            return
        
        self._initialized = True
        
        if config_dir is None:
            from backend.src.utils.paths import get_config_dir
            config_dir = get_config_dir()
        
        super().__init__(Path(config_dir))
        
        self._config_dir = self.config_dir
        self._config_file = self.config_file
        self._backup_dir = self.backup_dir
        
        self._config_cache: Optional[Dict] = None
        self._cache_mtime: Optional[float] = None
        # 父类 load_config 在补全缺失字段/迁移时会回调 self.save_config，
        # 同一线程内需要可重入，避免自锁死。
        self._cache_lock = threading.RLock()
    
    def get_default_config(self) -> Dict:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "version": self.CURRENT_VERSION,
            "environments": [],
            "current_environment_id": None,
            # 多包 / 数据空间注册表（旧配置读取时自动补全）
            "packages": [],
            "data_spaces": [],
            "current_package_id": None,
        }
    
    # 为了向后兼容，保留原有的属性访问器（返回字符串）
    @property
    def config_dir_str(self) -> str:
        """返回配置目录的字符串路径（向后兼容）"""
        return str(self.config_dir)
    
    @property
    def config_file_str(self) -> str:
        """返回配置文件的字符串路径（向后兼容）"""
        return str(self.config_file)
    
    @property
    def backup_dir_str(self) -> str:
        """返回备份目录的字符串路径（向后兼容）"""
        return str(self.backup_dir)
    
    # 保留 config_file_path 属性用于内部使用
    @property
    def config_file_path(self) -> Path:
        """
        返回配置文件的 Path 对象
        
        注意：此属性不会被 pywebview 序列化（通过 __dir__ 方法隐藏）
        """
        return self.config_file
    
    def __dir__(self):
        """
        自定义 dir() 输出，隐藏返回 Path 对象的属性
        
        继承父类的 __dir__ 方法，并额外隐藏 config_file_path 属性
        
        Returns:
            不包含 Path 属性的属性列表
        """
        # 调用父类的 __dir__ 方法
        attrs = super().__dir__()
        
        # 额外移除 EnvironmentConfigManager 特有的 Path 属性
        path_attrs = ['config_file_path', '_config_dir', '_config_file', '_backup_dir']
        return [attr for attr in attrs if attr not in path_attrs]
    
    def load_config(self) -> Dict:
        """
        Load environment configuration from file.
        使用缓存机制减少文件读取次数。
        线程安全：使用锁保护缓存操作。
        
        Returns:
            Dictionary with configuration data
        """
        needs_persist = False
        config: Dict
        with self._cache_lock:
            try:
                if not self.config_file.exists():
                    logger.debug("[EnvironmentConfigManager.load_config] 配置文件不存在，返回默认配置")
                    return self.get_default_config()
                
                current_mtime = os.path.getmtime(self.config_file)
                
                if self._config_cache is not None and self._cache_mtime == current_mtime:
                    return self._config_cache
                
                logger.debug(f"[EnvironmentConfigManager.load_config] 从文件加载配置: {self.config_file}")
                config = super().load_config()

                # 旧配置兼容：补全 packages / data_spaces / 环境绑定字段。
                # 读取本身永不因缺字段报错；回写放到释放锁之后，避免重复加锁。
                try:
                    from ..scope import normalize_registry
                    needs_persist = normalize_registry(config)
                except Exception as exc:
                    logger.warning(f"[EnvironmentConfigManager.load_config] 注册表补全失败（忽略）：{exc}")

                self._config_cache = config
                self._cache_mtime = os.path.getmtime(self.config_file)
                
                logger.debug(f"[EnvironmentConfigManager.load_config] 配置文件加载成功，包含 {len(config.get('environments', []))} 个环境")
            except Exception as e:
                logger.error(f"[EnvironmentConfigManager] 配置文件加载失败：{str(e)}")
                return self.get_default_config()

        if needs_persist:
            try:
                self.save_config(config)
                logger.info("[EnvironmentConfigManager.load_config] 已补全多包/数据空间注册表字段")
            except Exception as exc:
                logger.warning(f"[EnvironmentConfigManager.load_config] 注册表回写失败（忽略）：{exc}")

        return config
    
    def save_config(self, config: Dict) -> bool:
        """
        Save environment configuration to file.
        线程安全：使用锁保护缓存操作。
        
        Args:
            config: Configuration dictionary to save
            
        Returns:
            True if successful, False otherwise
        """
        with self._cache_lock:
            try:
                logger.debug(f"[EnvironmentConfigManager] 开始保存配置，包含 {len(config.get('environments', []))} 个环境")

                try:
                    from ..scope import normalize_registry
                    normalize_registry(config)
                except Exception as exc:
                    logger.warning(f"[EnvironmentConfigManager] 保存前注册表补全失败（忽略）：{exc}")

                success = super().save_config(config)
                
                if success:
                    self._config_cache = config
                    self._cache_mtime = os.path.getmtime(self.config_file)
                    logger.debug(f"[EnvironmentConfigManager] 配置文件保存成功: {self.config_file}")
                
                return success
            except Exception as e:
                logger.error(f"[EnvironmentConfigManager] 配置保存失败: {str(e)}")
                raise
    
    def export_config(self, env_id: str) -> str:
        """
        Export environment configuration to JSON string.
        
        Args:
            env_id: ID of the environment to export
            
        Returns:
            JSON string with configuration data
            
        Raises:
            Exception: If environment not found or export fails
        """
        try:
            config = self.load_config()
            
            # Find the environment
            environment = None
            for env in config["environments"]:
                if env["id"] == env_id:
                    environment = env
                    break
            
            if not environment:
                raise Exception(f"Environment not found: {env_id}")
            
            # Export as JSON string
            return json.dumps(environment, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Failed to export configuration: {str(e)}")
    
    def import_config(self, config_data: str) -> bool:
        """
        Import environment configuration from JSON string.
        
        Args:
            config_data: JSON string with configuration data
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If import fails
        """
        try:
            # Parse JSON
            environment_data = json.loads(config_data)
            
            # Validate structure
            if "id" not in environment_data or "name" not in environment_data:
                raise Exception("Invalid configuration data")
            
            # Load current config
            config = self.load_config()
            
            # Check if environment already exists
            existing_env = None
            for env in config["environments"]:
                if env["id"] == environment_data["id"]:
                    existing_env = env
                    break
            
            if existing_env:
                # Update existing environment
                index = config["environments"].index(existing_env)
                config["environments"][index] = environment_data
            else:
                # Add new environment
                config["environments"].append(environment_data)
            
            # Save config
            self.save_config(config)
            
            return True
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON data: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to import configuration: {str(e)}")
    
    def get_environments(self) -> List[Environment]:
        """
        Get all environments from configuration.
        
        Returns:
            List of Environment objects
        """
        try:
            config = self.load_config()
            logger.debug(f"[EnvironmentConfigManager.get_environments] load_config 返回 {len(config.get('environments', []))} 个环境")
            
            environments = []
            
            for env_data in config.get("environments", []):
                environment = Environment.from_dict(env_data)
                environments.append(environment)
                logger.debug(f"[EnvironmentConfigManager.get_environments] 解析环境：id={environment.id}, name={environment.name}")
            
            return environments
        except Exception as e:
            logger.debug(f"[EnvironmentConfigManager.get_environments] 异常：{e}")
            return []
    
    def get_environment(self, env_id: str) -> Optional[Environment]:
        """
        Get a specific environment by ID.
        
        Args:
            env_id: ID of the environment
            
        Returns:
            Environment object or None if not found
        """
        try:
            config = self.load_config()
            
            for env_data in config.get("environments", []):
                if env_data["id"] == env_id:
                    return Environment.from_dict(env_data)
            
            return None
        except Exception:
            return None
    
    def get_current_environment_id(self) -> Optional[str]:
        """
        Get the current environment ID.
        
        Returns:
            Current environment ID or None
        """
        try:
            config = self.load_config()
            return config.get("current_environment_id")
        except Exception:
            return None
    
    def set_current_environment_id(self, env_id: str) -> bool:
        """
        Set the current environment ID.
        
        Args:
            env_id: ID of the environment to set as current
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.load_config()
            config["current_environment_id"] = env_id
            self.save_config(config)
            return True
        except Exception:
            return False
    

