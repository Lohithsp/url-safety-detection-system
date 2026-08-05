"""SQL persistence and admin analytics for URL scan history."""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
)


def database_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "url_safety")
    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{name}"


metadata = MetaData()

scan_history = Table(
    "scan_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=True),
    Column("url", String(2048), nullable=False),
    Column("prediction", String(20), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("risk_level", String(20), nullable=False),
    Column("explanation", Text, nullable=False),
    Column("scan_time", DateTime, nullable=False, default=datetime.utcnow),
)


def get_engine():
    return create_engine(database_url(), pool_pre_ping=True)


def create_tables() -> None:
    metadata.create_all(get_engine())


def store_scan_result(
    user_id: int | None,
    url: str,
    prediction: str,
    confidence: float,
    risk_level: str,
    explanation: str,
) -> int:
    create_tables()
    with get_engine().begin() as conn:
        result = conn.execute(
            scan_history.insert().values(
                user_id=user_id,
                url=url,
                prediction=prediction,
                confidence=confidence,
                risk_level=risk_level,
                explanation=explanation,
                scan_time=datetime.utcnow(),
            )
        )
        return int(result.inserted_primary_key[0])


def admin_dashboard_stats() -> dict:
    create_tables()
    with get_engine().connect() as conn:
        total = conn.execute(select(func.count()).select_from(scan_history)).scalar_one()
        malicious = conn.execute(
            select(func.count()).select_from(scan_history).where(scan_history.c.prediction == "Malicious")
        ).scalar_one()
        safe = conn.execute(
            select(func.count()).select_from(scan_history).where(scan_history.c.prediction == "Safe")
        ).scalar_one()
        risk_rows = conn.execute(
            select(scan_history.c.risk_level, func.count()).group_by(scan_history.c.risk_level)
        ).all()
        recent = conn.execute(
            select(scan_history).order_by(scan_history.c.scan_time.desc()).limit(50)
        ).mappings().all()
    return {
        "total_scans": int(total),
        "malicious_detections": int(malicious),
        "safe_detections": int(safe),
        "risk_distribution": {row[0]: int(row[1]) for row in risk_rows},
        "recent_scan_history": [dict(row) for row in recent],
    }


if __name__ == "__main__":
    create_tables()
    print("scan_history table is ready.")
