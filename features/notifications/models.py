from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Notification:
    id: str = ""
    title: str = ""
    message: str = ""
    type: str = ""
    is_read: bool = False
    created_at: str = ""
    payload: dict = field(default_factory=dict)
