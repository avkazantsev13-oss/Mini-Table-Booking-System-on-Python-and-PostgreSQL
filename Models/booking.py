"""Модель бронирования стола для мини-системы (будущая таблица `bookings`).

Связи в БД (логика «многие к одному» со стороны `bookings`):
  users (1) ──< (*) bookings: каждая бронь ссылается на одного пользователя (`user_id`).
  dining_tables (1) ──< (*) bookings: каждая бронь — на один стол (`dining_table_id`).

Удаление пользователя или стола каскадирует в `bookings`: связанные брони удаляются
(`ON DELETE CASCADE` на обоих внешних ключах).
При смене `id` у родителя дочерние строки получают новый ключ (ON UPDATE CASCADE).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from Models.tables import DINING_TABLES_TABLE_NAME
from Models.user import USER_TABLE_NAME
from postgres_driver import PostgresDriver

BOOKINGS_TABLE_NAME = "bookings"

BOOKINGS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    dining_table_id INTEGER NOT NULL,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    party_size INTEGER NOT NULL CHECK (party_size > 0),
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id)
        REFERENCES {USER_TABLE_NAME}(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_bookings_dining_table FOREIGN KEY (dining_table_id)
        REFERENCES {DINING_TABLES_TABLE_NAME}(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT chk_booking_interval CHECK (ends_at > starts_at)
);
"""

# Индексы по внешним ключам — ускоряют JOIN и проверку ссылочной целостности.
BOOKINGS_FK_INDEXES_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{BOOKINGS_TABLE_NAME}_user_id
    ON {BOOKINGS_TABLE_NAME} (user_id);
CREATE INDEX IF NOT EXISTS idx_{BOOKINGS_TABLE_NAME}_dining_table_id
    ON {BOOKINGS_TABLE_NAME} (dining_table_id);
"""

# Перевод уже созданной таблицы `bookings` на ON DELETE CASCADE (старые схемы с RESTRICT).
# Убираем и именованные ограничения, и типичные имена PostgreSQL: tablename_columnname_fkey.
BOOKINGS_FK_MIGRATE_ON_DELETE_CASCADE_SQL = f"""
ALTER TABLE {BOOKINGS_TABLE_NAME} DROP CONSTRAINT IF EXISTS fk_bookings_user;
ALTER TABLE {BOOKINGS_TABLE_NAME} DROP CONSTRAINT IF EXISTS fk_bookings_dining_table;
ALTER TABLE {BOOKINGS_TABLE_NAME} DROP CONSTRAINT IF EXISTS bookings_user_id_fkey;
ALTER TABLE {BOOKINGS_TABLE_NAME} DROP CONSTRAINT IF EXISTS bookings_dining_table_id_fkey;
ALTER TABLE {BOOKINGS_TABLE_NAME}
    ADD CONSTRAINT fk_bookings_user FOREIGN KEY (user_id)
        REFERENCES {USER_TABLE_NAME}(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE;
ALTER TABLE {BOOKINGS_TABLE_NAME}
    ADD CONSTRAINT fk_bookings_dining_table FOREIGN KEY (dining_table_id)
        REFERENCES {DINING_TABLES_TABLE_NAME}(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE;
"""


@dataclass
class Booking:
    """Бронь: кто (пользователь), какой стол, интервал времени и число гостей."""

    id: int | None
    user_id: int
    dining_table_id: int
    starts_at: datetime
    ends_at: datetime
    party_size: int

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Booking:
        """Собрать модель из строки `RealDictCursor` / результата `RETURNING *`."""
        return cls(
            id=row["id"],
            user_id=int(row["user_id"]),
            dining_table_id=int(row["dining_table_id"]),
            starts_at=row["starts_at"],
            ends_at=row["ends_at"],
            party_size=int(row["party_size"]),
        )


def check_table_availability(
    driver: PostgresDriver,
    dining_table_id: int,
    starts_at: datetime,
    ends_at: datetime,
    *,
    exclude_booking_id: int | None = None,
) -> bool:
    """
    Проверить, свободен ли стол в интервале [starts_at, ends_at).

    Пересечение с уже существующей бронью того же стола запрещено
    (конец одной брони может совпадать с началом следующей — без пересечения).

    Возвращает True, если слот свободен; False, если есть конфликт.
    Для правки существующей брони передайте exclude_booking_id, чтобы не считать её за конфликт.
    """
    if ends_at <= starts_at:
        raise ValueError("Интервал брони неверен: ends_at должен быть позже starts_at.")

    sql = f"""
        SELECT 1 AS hit
        FROM {BOOKINGS_TABLE_NAME}
        WHERE dining_table_id = %s
          AND starts_at < %s
          AND ends_at > %s
        """
    params: list[Any] = [dining_table_id, ends_at, starts_at]
    if exclude_booking_id is not None:
        sql += " AND id <> %s"
        params.append(exclude_booking_id)
    sql += " LIMIT 1"

    conn = driver._connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conflict = cur.fetchone() is not None
    finally:
        conn.close()

    return not conflict


def create_booking(
    driver: PostgresDriver,
    user_id: int,
    dining_table_id: int,
    starts_at: datetime,
    ends_at: datetime,
    party_size: int,
) -> Booking:
    """Создать бронь (`INSERT`). Не допускает пересечения по столу с другими бронями."""
    if not check_table_availability(
        driver, dining_table_id, starts_at, ends_at,
    ):
        raise ValueError(
            "Стол занят: интервал пересекается с другой бронью.",
        )
    row = driver.create(
        BOOKINGS_TABLE_NAME,
        {
            "user_id": user_id,
            "dining_table_id": dining_table_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "party_size": party_size,
        },
    )
    return Booking.from_row(row)


def get_booking_by_id(driver: PostgresDriver, booking_id: int) -> Booking | None:
    """Прочитать бронь по `id` (`SELECT` одной строки)."""
    rows = driver.read(
        BOOKINGS_TABLE_NAME,
        filters={"id": booking_id},
        limit=1,
    )
    return Booking.from_row(rows[0]) if rows else None


def list_bookings(
    driver: PostgresDriver,
    *,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Booking]:
    """Список броней (`SELECT`), опционально по фильтрам (`user_id`, `dining_table_id`, …)."""
    rows = driver.read(
        BOOKINGS_TABLE_NAME,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    # Сортировка в Python; при limit/offset упорядочены только строки текущей «страницы».
    rows_sorted = sorted(rows, key=lambda r: r["starts_at"])
    return [Booking.from_row(r) for r in rows_sorted]


def update_booking(
    driver: PostgresDriver,
    booking_id: int,
    data: dict[str, Any],
) -> Booking | None:
    """Обновить бронь (`UPDATE`), ключи — колонки таблицы кроме `id`.

    При смене стола или времени проверяется отсутствие пересечений с другими бронями.
    """
    if not data:
        raise ValueError("Передайте хотя бы одно поле в `data`.")
    current = get_booking_by_id(driver, booking_id)
    if not current:
        return None

    new_table = int(data.get("dining_table_id", current.dining_table_id))
    new_start = data.get("starts_at", current.starts_at)
    new_end = data.get("ends_at", current.ends_at)
    if not isinstance(new_start, datetime) or not isinstance(new_end, datetime):
        raise TypeError("starts_at и ends_at должны быть datetime.")

    if any(
        k in data
        for k in ("dining_table_id", "starts_at", "ends_at")
    ):
        if not check_table_availability(
            driver,
            new_table,
            new_start,
            new_end,
            exclude_booking_id=booking_id,
        ):
            raise ValueError(
                "Стол занят: интервал пересекается с другой бронью.",
            )

    rows = driver.update(BOOKINGS_TABLE_NAME, data, {"id": booking_id})
    return Booking.from_row(rows[0]) if rows else None


def delete_booking(driver: PostgresDriver, booking_id: int) -> Booking | None:
    """Удалить бронь по `id` (`DELETE`)."""
    rows = driver.delete(BOOKINGS_TABLE_NAME, {"id": booking_id})
    return Booking.from_row(rows[0]) if rows else None
