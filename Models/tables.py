"""Модель стола в зале для мини-системы бронирования (будущая таблица `dining_tables`).

Связь: один стол — много броней; в `bookings` поле `dining_table_id` → `dining_tables.id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from postgres_driver import PostgresDriver

# Имя `tables` в SQL путается с «таблицей БД», поэтому таблица данных — `dining_tables`.
DINING_TABLES_TABLE_NAME = "dining_tables"

DINING_TABLES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dining_tables (
    id SERIAL PRIMARY KEY,
    label VARCHAR(64) NOT NULL UNIQUE,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    zone VARCHAR(128)
);
"""


@dataclass
class DiningTable:
    """Стол в заведении: место, на которое вешается бронь."""

    id: int | None
    label: str
    capacity: int
    zone: str | None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> DiningTable:
        """Собрать модель из строки `RealDictCursor` / результата `RETURNING *`."""
        return cls(
            id=row["id"],
            label=row["label"],
            capacity=int(row["capacity"]),
            zone=row.get("zone"),
        )


def create_dining_table(
    driver: PostgresDriver,
    label: str,
    capacity: int,
    zone: str | None = None,
) -> DiningTable:
    """Создать стол (`INSERT`)."""
    row = driver.create(
        DINING_TABLES_TABLE_NAME,
        {"label": label, "capacity": capacity, "zone": zone},
    )
    return DiningTable.from_row(row)


def get_dining_table_by_id(driver: PostgresDriver, table_id: int) -> DiningTable | None:
    """Прочитать стол по `id` (`SELECT` одной строки)."""
    rows = driver.read(
        DINING_TABLES_TABLE_NAME,
        filters={"id": table_id},
        limit=1,
    )
    return DiningTable.from_row(rows[0]) if rows else None


def list_dining_tables(
    driver: PostgresDriver,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[DiningTable]:
    """Список столов (`SELECT`)."""
    rows = driver.read(DINING_TABLES_TABLE_NAME, limit=limit, offset=offset)
    return [DiningTable.from_row(r) for r in rows]


def update_dining_table(
    driver: PostgresDriver,
    table_id: int,
    data: dict[str, Any],
) -> DiningTable | None:
    """Обновить стол (`UPDATE`), ключи — `label`, `capacity`, `zone`."""
    if not data:
        raise ValueError("Передайте хотя бы одно поле в `data`.")
    rows = driver.update(DINING_TABLES_TABLE_NAME, data, {"id": table_id})
    return DiningTable.from_row(rows[0]) if rows else None


def delete_dining_table(driver: PostgresDriver, table_id: int) -> DiningTable | None:
    """Удалить стол по `id` (`DELETE`). Связанные брони удаляются каскадом в БД."""
    rows = driver.delete(DINING_TABLES_TABLE_NAME, {"id": table_id})
    return DiningTable.from_row(rows[0]) if rows else None
