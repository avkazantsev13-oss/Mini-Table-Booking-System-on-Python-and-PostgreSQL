"""Создание таблиц users, dining_tables, bookings и заполнение демо-данными (.env)."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from psycopg2.extras import RealDictCursor

from Models.booking import (
    BOOKINGS_FK_INDEXES_SQL,
    BOOKINGS_FK_MIGRATE_ON_DELETE_CASCADE_SQL,
    BOOKINGS_TABLE_NAME,
    BOOKINGS_TABLE_SQL,
)
from Models.tables import DINING_TABLES_TABLE_NAME, DINING_TABLES_TABLE_SQL
from Models.user import USER_TABLE_NAME, USERS_TABLE_SQL
from postgres_driver import PostgresDriver


def _slot_fits(
    table_id: int,
    cap: int,
    start: datetime,
    end: datetime,
    party: int,
    existing: list[tuple[int, int, datetime, datetime]],
) -> bool:
    if party > cap:
        return False
    for tid, _, s, e in existing:
        if tid != table_id:
            continue
        if start < e and end > s:
            return False
    return True


def main() -> None:
    random.seed(42)

    driver = PostgresDriver()
    conn = driver._connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(USERS_TABLE_SQL)
                cur.execute(DINING_TABLES_TABLE_SQL)
                cur.execute(BOOKINGS_TABLE_SQL)
                cur.execute(BOOKINGS_FK_MIGRATE_ON_DELETE_CASCADE_SQL)
                cur.execute(BOOKINGS_FK_INDEXES_SQL)
                cur.execute(
                    "TRUNCATE TABLE bookings, dining_tables, users "
                    "RESTART IDENTITY CASCADE;"
                )
    finally:
        conn.close()

    users_data = [
        {
            "full_name": "Елена Воробьёва",
            "phone": "+7 (903) 112-22-33",
        },
        {
            "full_name": "Андрей Никитин",
            "phone": "+7 (926) 445-66-77",
        },
        {
            "full_name": "Мария Казакова",
            "phone": "+7 (915) 888-99-00",
        },
        {
            "full_name": "Олег Фёдоров",
            "phone": None,
        },
        {
            "full_name": "Светлана Орлова",
            "phone": "+7 (916) 777-44-22",
        },
    ]

    tables_data = [
        {"label": "1", "capacity": 2, "zone": "основной зал"},
        {"label": "2", "capacity": 4, "zone": "основной зал"},
        {"label": "3", "capacity": 4, "zone": "основной зал"},
        {"label": "VIP-1", "capacity": 6, "zone": "VIP-зал"},
        {"label": "VIP-2", "capacity": 8, "zone": "VIP-зал"},
        {"label": "Т-1", "capacity": 4, "zone": "терраса"},
        {"label": "Т-2", "capacity": 2, "zone": "терраса"},
    ]

    user_rows: list[dict] = []
    for u in users_data:
        user_rows.append(driver.create(USER_TABLE_NAME, u))

    table_rows: list[dict] = []
    for t in tables_data:
        table_rows.append(driver.create(DINING_TABLES_TABLE_NAME, t))

    user_ids = [int(r["id"]) for r in user_rows]
    table_info = [(int(r["id"]), int(r["capacity"])) for r in table_rows]

    base_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    base_day += timedelta(days=1)

    lunch_hours = [12, 13]
    dinner_hours = [18, 19, 20]
    durations_min = [90, 105, 120]

    booked: list[tuple[int, int, datetime, datetime]] = []
    inserted = 0
    attempts = 0
    max_attempts = 500

    while inserted < 10 and attempts < max_attempts:
        attempts += 1
        day_offset = random.randint(0, 6)
        slot_date = base_day + timedelta(days=day_offset)
        hour = random.choice(
            lunch_hours if random.random() < 0.45 else dinner_hours,
        )
        minute = random.choice([0, 15, 30])
        start = slot_date.replace(hour=hour, minute=minute)
        dur = random.choice(durations_min)
        end = start + timedelta(minutes=dur)

        tid, cap = random.choice(table_info)
        party = random.randint(1, min(cap, 6))

        if _slot_fits(tid, cap, start, end, party, booked):
            driver.create(
                BOOKINGS_TABLE_NAME,
                {
                    "user_id": random.choice(user_ids),
                    "dining_table_id": tid,
                    "starts_at": start,
                    "ends_at": end,
                    "party_size": party,
                },
            )
            booked.append((tid, cap, start, end))
            inserted += 1

    if inserted < 10:
        raise RuntimeError(
            f"Не удалось подобрать 10 непересекающихся броней за {max_attempts} попыток "
            f"(получилось {inserted}).",
        )

    print("Таблицы созданы, данные загружены.")
    print(f"  Пользователей: {len(user_rows)}")
    print(f"  Столов: {len(table_rows)}")
    print("  Броней: 10")

    conn = driver._connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS c FROM {USER_TABLE_NAME};",
                )
                print(f"  Проверка users: {cur.fetchone()['c']} строк")
                cur.execute(
                    f"SELECT COUNT(*) AS c FROM {DINING_TABLES_TABLE_NAME};",
                )
                print(f"  Проверка dining_tables: {cur.fetchone()['c']} строк")
                cur.execute(
                    f"SELECT COUNT(*) AS c FROM {BOOKINGS_TABLE_NAME};",
                )
                print(f"  Проверка bookings: {cur.fetchone()['c']} строк")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
