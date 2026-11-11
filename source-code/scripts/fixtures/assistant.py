"""AI 助手假数据：话题与消息记录。

不写入 api_configs —— 假密钥会导致发送请求时报错，
未配置状态本身也是需要验证的一种界面状态。
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from .context import FIXTURE_TAG, Manifest

TITLE = "AI 对话"

VARIANTS = {
    "basic": "4 个话题 / 13 条消息",
    "edge": "basic + 空话题 / 50 条长对话 / 4000 字超长单条",
    "empty": "无对话记录，验证空状态",
}

# (话题名, [(角色, 内容), ...])
_TOPICS: List[tuple] = [
    (
        f"{FIXTURE_TAG} 工作流调试",
        [
            ("user", "我这个 SDXL 工作流出图全黑，帮我看看可能是什么原因？"),
            ("assistant", "先确认三点：1) Checkpoint 是否加载成功；2) VAE 是否匹配；"
                          "3) KSampler 的 denoise 是否被设成了 0。全黑最常见的是 VAE 不匹配。"),
            ("user", "换成配套 VAE 之后正常了，谢谢。"),
            ("assistant", "不客气。建议把配套 VAE 记在提示词配方的备注里，下次直接复用。"),
        ],
    ),
    (
        f"{FIXTURE_TAG} 显存优化",
        [
            ("user", "12G 显存跑 1024x1024 会 OOM，有什么办法？"),
            ("assistant", "可以试：--medvram 或 --lowvram 启动参数、开启 fp8 精度、"
                          "把 batch size 降到 1，或先用 768 生成再放大。"),
            ("user", "开了 fp8 之后速度慢了一点，但确实不 OOM 了。"),
        ],
    ),
    (
        f"{FIXTURE_TAG} 提示词写法",
        [
            ("user", "写人像提示词有什么结构建议？"),
            ("assistant", "常用结构：主体 → 动作/姿态 → 光线 → 镜头 → 画质修饰。"
                          "反向提示词里放通用的低质量词即可，不要堆太多。"),
        ],
    ),
    (
        f"{FIXTURE_TAG} 插件冲突",
        [
            ("user", "装了两个节点包之后启动报 ImportError。"),
            ("assistant", "大概率是依赖版本冲突。可以先禁用其中一个，"
                          "用二分法定位，再检查两个包 requirements 里是否有互斥的版本约束。"),
            ("user", "定位到了，是 numpy 版本冲突。"),
            ("assistant", "那就是了。统一到较高版本通常能同时满足，注意 Python 版本也要匹配。"),
        ],
    ),
]


def _db_path() -> Path:
    from backend.src.core.ai.database import get_db_path

    return Path(get_db_path())


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS topics (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            topic_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            model TEXT,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_topic_id ON messages(topic_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        """
    )


def _clear_fixture_rows(connection: sqlite3.Connection) -> None:
    """只删自己写过的行，保留用户真实对话。"""
    pattern = f"{FIXTURE_TAG}%"
    connection.execute(
        "DELETE FROM messages WHERE topic_id IN (SELECT id FROM topics WHERE name LIKE ?)",
        (pattern,),
    )
    connection.execute("DELETE FROM topics WHERE name LIKE ?", (pattern,))


def _insert_topic(connection: sqlite3.Connection, index: int, name: str,
                  turns: List[tuple]) -> int:
    topic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"comfyui-box-fixture-topic-{index}"))
    base = datetime(2026, 10, 20, 10, 0, 0) + timedelta(days=index)
    created = base.isoformat(timespec="seconds")
    updated = (base + timedelta(minutes=3 * len(turns))).isoformat(timespec="seconds")

    connection.execute(
        "INSERT OR REPLACE INTO topics (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (topic_id, name, created, updated),
    )

    for order, (role, content) in enumerate(turns):
        message_id = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                    f"comfyui-box-fixture-message-{index}-{order}"))
        timestamp = (base + timedelta(minutes=3 * order)).isoformat(timespec="seconds")
        connection.execute(
            "INSERT OR REPLACE INTO messages "
            "(id, topic_id, role, content, timestamp, model) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, topic_id, role, content, timestamp, "fixture-model"),
        )
    return len(turns)


def _edge_topics() -> List[tuple]:
    """边界话题：空话题、长对话、超长单条。"""
    long_dialogue = []
    for turn in range(25):
        long_dialogue.append(("user", f"第 {turn + 1} 轮：这个参数该怎么调？"))
        long_dialogue.append(("assistant", f"第 {turn + 1} 轮回答：建议按场景逐步调整。"))

    huge = "这是一条用于验证消息气泡换行与滚动性能的超长消息。" * 180

    return [
        (f"{FIXTURE_TAG} 空话题", []),
        (f"{FIXTURE_TAG} 长对话", long_dialogue),
        (f"{FIXTURE_TAG} 超长消息", [("user", huge), ("assistant", "收到，已阅读完整内容。")]),
    ]


def seed(manifest: Manifest, variant: str = "basic") -> Dict:
    """写入话题与消息。"""
    if variant not in VARIANTS:
        raise ValueError(f"未知 AI 对话变体: {variant}")

    topics: List[tuple] = []
    if variant != "empty":
        topics = list(_TOPICS)
        if variant == "edge":
            topics += _edge_topics()

    db_file = _db_path()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    manifest.backup(db_file)
    manifest.record(db_file)

    connection = sqlite3.connect(db_file)
    try:
        _ensure_schema(connection)
        _clear_fixture_rows(connection)
        message_total = 0
        for index, (name, turns) in enumerate(topics, start=1):
            message_total += _insert_topic(connection, index, name, turns)
        connection.commit()
    finally:
        connection.close()

    manifest.set_domain_files("assistant", [db_file])
    return {
        "variant": variant,
        "topics": len(topics),
        "messages": message_total,
        "db": str(db_file),
    }
