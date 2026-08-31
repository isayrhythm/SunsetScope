from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    base_url: str
    store_path: Path
    source_timeout: float
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    admin_email: str
    rate_limit_ip: int
    rate_limit_email: int
    rate_limit_window: int

    @classmethod
    def from_env(cls) -> "Settings":
        store_path = Path(os.getenv("SUNSETSCOPE_STORE_PATH", "data/store.json"))
        if not store_path.is_absolute():
            store_path = ROOT / store_path
        smtp_user = os.getenv("SUNSETSCOPE_SMTP_USER", "").strip()
        return cls(
            base_url=os.getenv("SUNSETSCOPE_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            store_path=store_path,
            source_timeout=float(os.getenv("SUNSETSCOPE_SOURCE_TIMEOUT", "15")),
            smtp_host=os.getenv("SUNSETSCOPE_SMTP_HOST", "smtp.qq.com"),
            smtp_port=int(os.getenv("SUNSETSCOPE_SMTP_PORT", "465")),
            smtp_user=smtp_user,
            smtp_password=os.getenv("SUNSETSCOPE_SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SUNSETSCOPE_SMTP_FROM", smtp_user).strip(),
            admin_email=os.getenv("SUNSETSCOPE_ADMIN_EMAIL", smtp_user).strip(),
            rate_limit_ip=int(os.getenv("SUNSETSCOPE_RATE_LIMIT_IP", "20")),
            rate_limit_email=int(os.getenv("SUNSETSCOPE_RATE_LIMIT_EMAIL", "5")),
            rate_limit_window=int(os.getenv("SUNSETSCOPE_RATE_LIMIT_WINDOW", "3600")),
        )

    def require_mail(self) -> None:
        if not self.smtp_user or not self.smtp_password or not self.smtp_from:
            raise RuntimeError("邮件服务尚未配置，请设置 SMTP 环境变量")
