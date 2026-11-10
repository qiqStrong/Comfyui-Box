"""
默认配置管理器

负责管理全局默认 API 配置的读取、写入和清除操作。
默认配置保存在用户数据根的 config/default_config.json（用户级运行时状态），
与随包的只读模板 resource/config/default_config.json 不是同一份文件。
"""

import json
import logging
from pathlib import Path
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)


class DefaultConfigManager:
    """
    默认配置管理器
    
    管理全局默认 API 配置 ID，支持：
    - 读取默认配置 ID
    - 设置默认配置 ID
    - 清除默认配置 ID
    - 自动创建配置文件
    - 处理文件损坏等异常情况
    
    配置文件格式：
    {
        "default_api_config_id": "uuid-string" | null
    }
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化默认配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 <用户数据根>/config/default_config.json
        """
        if config_path is None:
            # 使用绝对路径
            from backend.src.utils.paths import get_config_dir
            config_path = get_config_dir() / "default_config.json"
        
        self.config_path = config_path
        self._lock = Lock()  # 线程锁，确保并发安全
        
        # 确保配置文件存在
        self._ensure_config_file()
    
    def _ensure_config_file(self) -> None:
        """
        确保配置文件存在
        
        如果文件不存在，创建默认配置文件。
        """
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件不存在，创建默认配置
            if not self.config_path.exists():
                default_config = {
                    "default_api_config_id": None
                }
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"创建默认配置文件: {self.config_path}")
        
        except Exception as e:
            logger.error(f"创建配置文件失败: {e}", exc_info=True)
    
    def _read_config(self) -> dict:
        """
        读取配置文件
        
        Returns:
            dict: 配置数据字典
            
        Raises:
            Exception: 读取或解析失败时抛出异常
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}", exc_info=True)
            # 文件损坏，返回默认配置
            return {"default_api_config_id": None}
        
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}", exc_info=True)
            raise
    
    def _write_config(self, config: dict) -> bool:
        """
        写入配置文件
        
        Args:
            config: 配置数据字典
            
        Returns:
            bool: 写入是否成功
        """
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入配置文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置文件写入成功: {self.config_path}")
            return True
        
        except Exception as e:
            logger.error(f"写入配置文件失败: {e}", exc_info=True)
            return False
    
    def get_default_config_id(self) -> Optional[str]:
        """
        获取默认配置 ID
        
        Returns:
            Optional[str]: 默认配置 ID，如果未设置则返回 None
        """
        with self._lock:
            try:
                config = self._read_config()
                config_id = config.get("default_api_config_id")
                
                if config_id:
                    logger.debug(f"获取默认配置 ID: {config_id}")
                else:
                    logger.debug("未设置默认配置")
                
                return config_id
            
            except Exception as e:
                logger.error(f"获取默认配置 ID 失败: {e}", exc_info=True)
                return None
    
    def set_default_config_id(self, config_id: str) -> bool:
        """
        设置默认配置 ID
        
        Args:
            config_id: API 配置 ID
            
        Returns:
            bool: 设置是否成功
            
        Raises:
            ValueError: config_id 为空时抛出异常
        """
        if not config_id or not config_id.strip():
            raise ValueError("配置 ID 不能为空")
        
        with self._lock:
            try:
                # 读取现有配置
                config = self._read_config()
                
                # 更新默认配置 ID
                config["default_api_config_id"] = config_id
                
                # 写入配置文件
                success = self._write_config(config)
                
                if success:
                    logger.info(f"设置默认配置成功: {config_id}")
                else:
                    logger.error(f"设置默认配置失败: {config_id}")
                
                return success
            
            except Exception as e:
                logger.error(f"设置默认配置 ID 失败: {e}", exc_info=True)
                return False
    
    def clear_default_config_id(self) -> bool:
        """
        清除默认配置 ID
        
        将默认配置 ID 设置为 None。
        
        Returns:
            bool: 清除是否成功
        """
        with self._lock:
            try:
                # 读取现有配置
                config = self._read_config()
                
                # 清除默认配置 ID
                config["default_api_config_id"] = None
                
                # 写入配置文件
                success = self._write_config(config)
                
                if success:
                    logger.info("清除默认配置成功")
                else:
                    logger.error("清除默认配置失败")
                
                return success
            
            except Exception as e:
                logger.error(f"清除默认配置 ID 失败: {e}", exc_info=True)
                return False
    
    def validate_and_clear_if_invalid(self, config_exists_checker) -> Optional[str]:
        """
        验证默认配置是否有效，如果无效则自动清除
        
        Args:
            config_exists_checker: 配置存在性检查函数，接收 config_id 参数，返回 bool
            
        Returns:
            Optional[str]: 有效的默认配置 ID，如果无效或不存在则返回 None
        """
        config_id = self.get_default_config_id()
        
        if config_id is None:
            return None
        
        # 检查配置是否存在
        if not config_exists_checker(config_id):
            logger.warning(f"默认配置 {config_id} 不存在，自动清除")
            self.clear_default_config_id()
            return None
        
        return config_id
