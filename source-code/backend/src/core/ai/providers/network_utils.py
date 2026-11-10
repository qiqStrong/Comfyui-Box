"""
网络工具函数

提供统一的网络连接配置，支持系统代理设置。
"""

import aiohttp
from typing import Optional
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


def get_proxy_from_settings(force_enable: Optional[bool] = None) -> Optional[str]:
    """
    从系统设置中读取代理配置
    
    Args:
        force_enable: 强制启用/禁用代理
            - True: 强制启用代理（读取系统设置中的代理地址）
            - False: 强制禁用代理（直接返回 None）
            - None: 使用系统设置的 enabled 字段决定
    
    Returns:
        str: 代理地址（格式：http://host:port），如果未启用则返回 None
        
    Note:
        读取用户数据根 config/settings.json 中的 proxy 配置
    """
    try:
        # 如果强制禁用代理，直接返回 None
        if force_enable is False:
            logger.debug("[代理配置] 强制禁用代理")
            return None
        
        from backend.src.utils.paths import get_config_dir
        settings_path = get_config_dir() / "settings.json"
        if not settings_path.exists():
            logger.debug("[代理配置] 配置文件不存在")
            return None
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        proxy_config = settings.get('proxy', {})
        
        # 检查是否启用代理
        # - force_enable=True: 强制启用（忽略系统设置的 enabled 字段）
        # - force_enable=None: 使用系统设置的 enabled 字段
        if force_enable is True:
            enabled = True
            logger.debug("[代理配置] 强制启用代理")
        else:
            enabled = proxy_config.get('enabled', False)
            logger.debug(f"[代理配置] 使用系统设置: enabled={enabled}")
        
        if not enabled:
            logger.debug("[代理配置] 代理未启用")
            return None
        
        host = proxy_config.get('host', '').strip()
        port = proxy_config.get('port', '').strip()
        
        # 验证配置
        if not host or not port:
            logger.warning(f"[代理配置] 代理配置不完整: host={host}, port={port}")
            return None
        
        # 构建代理 URL
        proxy_url = f"http://{host}:{port}"
        logger.info(f"[代理配置] 使用代理: {proxy_url}")
        return proxy_url
    
    except Exception as e:
        # 读取失败时返回 None，不影响正常功能
        logger.warning(f"[代理配置] 读取代理配置失败: {e}")
        return None


def create_proxy_connector(use_proxy: bool = True) -> aiohttp.TCPConnector:
    """
    创建支持系统代理的 TCP 连接器
    
    Args:
        use_proxy: 是否使用代理（默认 True）。本地服务（如 Ollama）应设置为 False
    
    Returns:
        aiohttp.TCPConnector: 配置好的连接器
        
    Note:
        - 从系统设置（用户数据根 config/settings.json）读取代理配置
        - 每次请求后关闭连接，避免连接池问题
        - 本地服务（如 Ollama）不应使用代理
        
    Example:
        # 使用代理（默认）
        connector = create_proxy_connector()
        
        # 不使用代理（本地服务）
        connector = create_proxy_connector(use_proxy=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url) as response:
                ...
    """
    return aiohttp.TCPConnector(
        ssl=None,  # 使用默认 SSL 验证
        force_close=True,  # 每次请求后关闭连接
        enable_cleanup_closed=True  # 自动清理关闭的连接
    )


def create_client_session(
    timeout: aiohttp.ClientTimeout, 
    use_proxy: bool = True
) -> aiohttp.ClientSession:
    """
    创建支持系统代理的 HTTP 客户端会话
    
    Args:
        timeout: 超时配置
        use_proxy: 是否使用代理（默认 True）。本地服务（如 Ollama）应设置为 False
        
    Returns:
        aiohttp.ClientSession: 配置好的会话对象
        
    Note:
        - 从系统设置读取代理配置
        - 使用 create_proxy_connector() 创建连接器
        - 调用方需要使用 async with 管理会话生命周期
        - 本地服务（如 Ollama）不应使用代理
        
    Example:
        # 使用代理（默认）
        timeout = aiohttp.ClientTimeout(total=30)
        async with create_client_session(timeout) as session:
            async with session.get(url, headers=headers) as response:
                ...
        
        # 不使用代理（本地服务）
        async with create_client_session(timeout, use_proxy=False) as session:
            ...
    """
    connector = create_proxy_connector(use_proxy)
    
    # 获取代理配置
    proxy_url = None
    if use_proxy:
        proxy_url = get_proxy_from_settings()
        logger.debug(f"[网络工具] 创建会话，use_proxy={use_proxy}, proxy_url={proxy_url}")
    else:
        logger.debug(f"[网络工具] 创建会话，use_proxy={use_proxy}，不使用代理")
    
    # 创建会话时传递代理配置
    session_kwargs = {
        'timeout': timeout,
        'connector': connector,
        'trust_env': False  # 不使用环境变量，使用系统设置
    }
    
    # 如果有代理配置，添加到会话参数中
    # 注意：aiohttp 的代理需要在每个请求中指定，而不是在 Session 级别
    # 所以这里我们只记录代理 URL，实际使用时需要在请求中传递
    
    return aiohttp.ClientSession(**session_kwargs)


def get_websocket_proxy() -> Optional[str]:
    """
    获取 WebSocket 代理配置
    
    Returns:
        str: 代理地址（格式：http://host:port），如果未启用则返回 None
        
    Note:
        - 从系统设置读取代理配置
        - WebSocket 使用 HTTP 代理协议
        
    Example:
        proxy = get_websocket_proxy()
        if proxy:
            # 使用代理连接 WebSocket
            async with websockets.connect(url, proxy=proxy) as ws:
                ...
    """
    return get_proxy_from_settings()
