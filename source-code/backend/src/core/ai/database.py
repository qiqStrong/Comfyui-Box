"""
AI 助手数据库管理模块

负责数据库的初始化、连接管理和基础操作。
"""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from backend.src.utils.paths import get_data_dir, get_scope_category_file


def get_db_path() -> Path:
    """
    返回当前 AI 对话数据库路径。

    默认沿用 ``DB_PATH``（导入期不再解析 scope，避免读配置/补全注册表的副作用）；
    应用启动与 scope 切换时由 ``refresh_scope()`` 依据绑定关系刷新。
    """
    return DB_PATH


# 兼容旧代码的常量，也是当前实际使用的数据库路径（scope 切换时由 refresh_scope 更新）
DB_PATH = get_data_dir() / "ai_assistant.db"


def refresh_scope() -> Path:
    """按当前 scope 绑定重新计算数据库路径（供启动与切换后调用）。"""
    global DB_PATH
    try:
        DB_PATH = Path(get_scope_category_file("ai"))
    except Exception:
        pass
    return DB_PATH



def init_database() -> None:
    """
    初始化 AI 助手数据库
    
    创建必要的表和索引：
    - topics: 话题表
    - messages: 消息表
    - ai_settings: AI 配置表（旧版本，保留用于迁移）
    - api_configs: API 配置表（新版本，支持多配置管理）
    
    数据库初始化后会自动执行配置迁移（如果需要）。
    """
    # 确保 data 目录存在
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建 topics 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 创建 messages 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                model TEXT,
                FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
            )
        ''')
        
        # 创建 messages 表索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_topic_id 
            ON messages(topic_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
            ON messages(timestamp)
        ''')
        
        # 创建 ai_settings 表（旧版本，保留用于迁移）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 创建 api_configs 表（新版本，支持多配置管理）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_configs (
                id TEXT PRIMARY KEY,
                alias TEXT NOT NULL,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT,
                model TEXT NOT NULL,
                models TEXT NOT NULL,
                extra TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'untested',
                last_tested_at TEXT,
                last_test_latency REAL,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 创建 api_configs 表索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_configs_provider 
            ON api_configs(provider)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_configs_is_default 
            ON api_configs(is_default)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_api_configs_updated_at 
            ON api_configs(updated_at)
        ''')
        
        conn.commit()
    finally:
        conn.close()
    
    # 数据库初始化完成后，执行配置迁移
    _run_config_migration()
    
    # 执行数据库 schema 迁移
    _run_schema_migrations()


@contextmanager
def get_db_connection():
    """
    获取数据库连接的上下文管理器
    
    使用示例：
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topics")
            results = cursor.fetchall()
    
    Yields:
        sqlite3.Connection: 数据库连接对象
    """
    conn = sqlite3.connect(get_db_path())
    # 启用外键约束
    conn.execute("PRAGMA foreign_keys = ON")
    # 设置 Row 工厂，使查询结果可以通过列名访问
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """
    执行 SQL 查询的辅助函数
    
    Args:
        query: SQL 查询语句
        params: 查询参数（使用参数化查询防止 SQL 注入）
        fetch_one: 是否返回单条结果
        fetch_all: 是否返回所有结果
        
    Returns:
        如果 fetch_one=True，返回单条结果（dict 或 None）
        如果 fetch_all=True，返回所有结果（list of dict）
        否则返回 lastrowid
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_one:
            row = cursor.fetchone()
            return dict(row) if row else None
        elif fetch_all:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            conn.commit()
            return cursor.lastrowid


def _run_config_migration() -> None:
    """
    执行配置迁移（内部函数）
    
    在数据库初始化后自动调用，将旧版本的单配置模式迁移到新的多配置模式。
    如果不需要迁移或迁移已完成，此函数会静默返回。
    """
    try:
        # 延迟导入，避免循环依赖
        from backend.src.core.ai.config_manager import ConfigManager
        from backend.src.core.ai.config_migrator import ConfigMigrator
        
        # 创建配置管理器和迁移器
        config_manager = ConfigManager()
        migrator = ConfigMigrator(config_manager)
        
        # 检查是否需要迁移
        if migrator.needs_migration():
            import logging
            logger = logging.getLogger(__name__)
            logger.info("检测到旧版本配置，开始自动迁移...")
            
            # 执行迁移
            success = migrator.migrate()
            if success:
                logger.info("配置迁移成功完成")
            else:
                logger.warning("配置迁移失败，请检查日志")
    except Exception as e:
        # 迁移失败不应该阻止系统启动
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"配置迁移过程中发生错误: {e}", exc_info=True)


def _run_schema_migrations() -> None:
    """
    执行数据库 schema 迁移（内部函数）
    
    在数据库初始化后自动调用，执行所有待执行的 schema 迁移。
    迁移失败不应该阻止系统启动。
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # 延迟导入，避免循环依赖
        from backend.src.core.ai.migrations import run_all_migrations
        
        logger.info("开始执行数据库 schema 迁移...")
        success = run_all_migrations(get_db_path())
        
        if success:
            logger.info("数据库 schema 迁移成功完成")
        else:
            logger.warning("数据库 schema 迁移失败，请检查日志")
            
    except Exception as e:
        # 迁移失败不应该阻止系统启动
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"数据库 schema 迁移过程中发生错误: {e}", exc_info=True)
