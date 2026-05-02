"""Модель пользователя для мини-системы бронирования (будущая таблица `users`).

Связь: один пользователь — много броней; дочерняя таблица `bookings` хранит `user_id` → `users.id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from postgres_driver import PostgresDriver

USER_TABLE_NAME = "users"

USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(32),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


@dataclass
class User:
    """Гость/пользователь: кто делает бронирование (без учётной записи и статусов)."""

    id: int | None
    full_name: str
    phone: str | None
    created_at: datetime | None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> User:
        """Собрать модель из строки `RealDictCursor` / результата `RETURNING *`."""
        return cls(
            id=row["id"],
            full_name=row["full_name"],
            phone=row.get("phone"),
            created_at=row.get("created_at"),
        )


def create_user(
    driver: PostgresDriver,
    full_name: str,
    phone: str | None = None,
) -> User:
    """Создать пользователя (`INSERT`)."""
    row = driver.create(
        USER_TABLE_NAME,
        {"full_name": full_name, "phone": phone},
    )
    return User.from_row(row)


def get_user_by_id(driver: PostgresDriver, user_id: int) -> User | None:
    """Прочитать пользователя по `id` (`SELECT` одной строки)."""
    rows = driver.read(USER_TABLE_NAME, filters={"id": user_id}, limit=1)
    return User.from_row(rows[0]) if rows else None


def list_users(
    driver: PostgresDriver,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[User]:
    """Список пользователей (`SELECT`)."""
    rows = driver.read(USER_TABLE_NAME, limit=limit, offset=offset)
    return [User.from_row(r) for r in rows]


def update_user(
    driver: PostgresDriver,
    user_id: int,
    data: dict[str, Any],
) -> User | None:
    """Обновить поля пользователя (`UPDATE`), ключи — только колонки таблицы."""
    if not data:
        raise ValueError("Передайте хотя бы одно поле в `data`.")
    rows = driver.update(USER_TABLE_NAME, data, {"id": user_id})
    return User.from_row(rows[0]) if rows else None


def delete_user(driver: PostgresDriver, user_id: int) -> User | None:
    """Удалить пользователя по `id` (`DELETE`). Связанные брони удаляются каскадом в БД."""
    rows = driver.delete(USER_TABLE_NAME, {"id": user_id})
    return User.from_row(rows[0]) if rows else None
