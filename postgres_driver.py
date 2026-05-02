import os
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2 import OperationalError, sql
from psycopg2.extras import RealDictCursor


class PostgresDriver:
    """Reusable PostgreSQL driver with basic CRUD operations."""

    def __init__(self, env_path: str | None = None, auto_load_env: bool = True) -> None:
        if auto_load_env:
            default_env_path = os.path.join(os.path.dirname(__file__), ".env")
            load_dotenv(env_path or default_env_path)
        self._params = self._get_connection_params()

    @staticmethod
    def _get_connection_params() -> dict[str, Any]:
        """Build PostgreSQL connection settings from environment variables."""
        return {
            "host": os.getenv("PGHOST", "localhost"),
            "port": int(os.getenv("PGPORT", "5432")),
            "dbname": os.getenv("PGDATABASE", "postgres"),
            "user": os.getenv("PGUSER", "postgres"),
            "password": os.getenv("PGPASSWORD", ""),
        }

    def _connect(self):
        """Create and return a new PostgreSQL connection."""
        try:
            return psycopg2.connect(**self._params)
        except OperationalError as err:
            raise ConnectionError(f"PostgreSQL connection failed: {err}") from err

    @staticmethod
    def _handle_db_error(operation: str, err: psycopg2.Error) -> None:
        """Raise a readable DB error with operation context."""
        raise RuntimeError(f"Database error during {operation}: {err}") from err

    @staticmethod
    def _where_clause(filters: dict[str, Any]) -> tuple[sql.SQL, list[Any]]:
        """Build SQL WHERE clause from dictionary filters."""
        if not filters:
            return sql.SQL(""), []

        conditions = []
        values: list[Any] = []
        for key, value in filters.items():
            conditions.append(
                sql.SQL("{} = %s").format(sql.Identifier(key))
            )
            values.append(value)

        where_sql = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
        return where_sql, values

    def create(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new row and return the inserted record."""
        if not data:
            raise ValueError("`data` must not be empty for create operation.")

        columns = list(data.keys())
        values = list(data.values())

        query = sql.SQL(
            "INSERT INTO {table} ({fields}) VALUES ({placeholders}) RETURNING *;"
        ).format(
            table=sql.Identifier(table),
            fields=sql.SQL(", ").join(sql.Identifier(col) for col in columns),
            placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )

        conn = self._connect()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, values)
                    row = cursor.fetchone()
            return dict(row) if row else {}
        except psycopg2.Error as err:
            self._handle_db_error("create", err)
        finally:
            conn.close()

    def read(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        columns: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read rows from table using optional filters, columns, limit, and offset."""
        selected_fields = (
            sql.SQL(", ").join(sql.Identifier(col) for col in columns)
            if columns
            else sql.SQL("*")
        )
        where_sql, where_values = self._where_clause(filters or {})

        query = sql.SQL("SELECT {fields} FROM {table}{where_sql}").format(
            fields=selected_fields,
            table=sql.Identifier(table),
            where_sql=where_sql,
        )

        params: list[Any] = list(where_values)
        if limit is not None:
            query += sql.SQL(" LIMIT %s")
            params.append(limit)
        if offset is not None:
            query += sql.SQL(" OFFSET %s")
            params.append(offset)
        query += sql.SQL(";")

        conn = self._connect()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except psycopg2.Error as err:
            self._handle_db_error("read", err)
        finally:
            conn.close()

    def update(
        self,
        table: str,
        data: dict[str, Any],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Update rows by filters and return updated records."""
        if not data:
            raise ValueError("`data` must not be empty for update operation.")
        if not filters:
            raise ValueError("`filters` must not be empty for update operation.")

        set_parts = []
        set_values: list[Any] = []
        for key, value in data.items():
            set_parts.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
            set_values.append(value)

        where_sql, where_values = self._where_clause(filters)

        query = sql.SQL("UPDATE {table} SET {set_sql}{where_sql} RETURNING *;").format(
            table=sql.Identifier(table),
            set_sql=sql.SQL(", ").join(set_parts),
            where_sql=where_sql,
        )

        params = set_values + where_values
        conn = self._connect()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except psycopg2.Error as err:
            self._handle_db_error("update", err)
        finally:
            conn.close()

    def delete(self, table: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Delete rows by filters and return deleted records."""
        if not filters:
            raise ValueError("`filters` must not be empty for delete operation.")

        where_sql, where_values = self._where_clause(filters)
        query = sql.SQL("DELETE FROM {table}{where_sql} RETURNING *;").format(
            table=sql.Identifier(table),
            where_sql=where_sql,
        )

        conn = self._connect()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, where_values)
                    rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except psycopg2.Error as err:
            self._handle_db_error("delete", err)
        finally:
            conn.close()
