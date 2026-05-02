"""Простой GUI (tkinter) для пользователей, столов и бронирований."""

from __future__ import annotations

import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from Models import booking as booking_model
from Models import tables as tables_model
from Models import user as user_model
from postgres_driver import PostgresDriver

DATETIME_HINT = "ГГГГ-ММ-ДД ЧЧ:ММ"
DATETIME_RE = re.compile(
    r"^\s*(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})\s*$",
)


def parse_datetime(text: str) -> datetime:
    text = text.strip()
    m = DATETIME_RE.match(text)
    if not m:
        raise ValueError(f"Ожидается формат {DATETIME_HINT}")
    y, mo, d, h, mi = map(int, m.groups())
    return datetime(y, mo, d, h, mi, 0)


def format_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


class BookingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Бронирование столов")
        self.geometry("920x620")
        self.minsize(800, 500)

        try:
            self.driver = PostgresDriver()
        except Exception as err:
            messagebox.showerror(
                "Ошибка подключения",
                f"Не удалось создать подключение к БД:\n{err}",
            )
            self.driver = None

        self._build_notebook()
        if self.driver:
            self.refresh_users()
            self.refresh_tables()
            self.refresh_bookings()
            self._fill_booking_combos()

    def _safe_call(self, fn, *args, **kwargs):
        if not self.driver:
            messagebox.showwarning("Нет БД", "Подключение к базе недоступно.")
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as err:
            messagebox.showerror("Ошибка", str(err))
            return None

    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tab_users = ttk.Frame(nb, padding=6)
        self.tab_tables = ttk.Frame(nb, padding=6)
        self.tab_bookings = ttk.Frame(nb, padding=6)
        nb.add(self.tab_users, text="Пользователи")
        nb.add(self.tab_tables, text="Столы")
        nb.add(self.tab_bookings, text="Бронирования")

        self._build_users_tab()
        self._build_tables_tab()
        self._build_bookings_tab()

    # --- Пользователи ---
    def _build_users_tab(self) -> None:
        cols = ("id", "full_name", "phone", "created_at")
        self.users_tree = ttk.Treeview(
            self.tab_users,
            columns=cols,
            show="headings",
            height=14,
        )
        for c, t in zip(cols, ("ID", "ФИО", "Телефон", "Создан")):
            self.users_tree.heading(c, text=t)
            self.users_tree.column(c, width=160 if c != "id" else 50)

        sy = ttk.Scrollbar(self.tab_users, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=sy.set)
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        self.users_tree.bind("<<TreeviewSelect>>", self._on_user_select)

        form = ttk.LabelFrame(self.tab_users, text="Добавить / изменить", padding=8)
        form.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(form, text="ФИО:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.user_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.user_name_var, width=40).grid(
            row=0, column=1, columnspan=3, sticky=tk.W, pady=2,
        )

        ttk.Label(form, text="Телефон:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.user_phone_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.user_phone_var, width=40).grid(
            row=1, column=1, columnspan=3, sticky=tk.W, pady=2,
        )

        bf = ttk.Frame(form)
        bf.grid(row=2, column=0, columnspan=4, pady=8)
        ttk.Button(bf, text="Обновить список", command=self.refresh_users).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Добавить", command=self.add_user).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Сохранить изменения", command=self.update_user).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Удалить", command=self.delete_user).pack(side=tk.LEFT, padx=4)

        self.selected_user_id: int | None = None

    def _on_user_select(self, _event=None) -> None:
        sel = self.users_tree.selection()
        if not sel:
            self.selected_user_id = None
            return
        vals = self.users_tree.item(sel[0], "values")
        self.selected_user_id = int(vals[0])
        self.user_name_var.set(vals[1])
        self.user_phone_var.set(vals[2] if vals[2] else "")

    def refresh_users(self) -> None:
        if not self.driver:
            return
        for i in self.users_tree.get_children():
            self.users_tree.delete(i)
        users = self._safe_call(user_model.list_users, self.driver)
        if users is None:
            return
        for u in users:
            self.users_tree.insert(
                "",
                tk.END,
                values=(
                    u.id,
                    u.full_name,
                    u.phone or "",
                    format_dt(u.created_at),
                ),
            )

    def add_user(self) -> None:
        name = self.user_name_var.get().strip()
        if not name:
            messagebox.showwarning("Проверка", "Укажите ФИО.")
            return
        phone_raw = self.user_phone_var.get().strip()
        phone = phone_raw if phone_raw else None
        u = self._safe_call(user_model.create_user, self.driver, name, phone)
        if u:
            self.refresh_users()
            messagebox.showinfo("Готово", f"Пользователь добавлен, id={u.id}.")

    def update_user(self) -> None:
        if self.selected_user_id is None:
            messagebox.showwarning("Выбор", "Выберите строку в таблице.")
            return
        name = self.user_name_var.get().strip()
        if not name:
            messagebox.showwarning("Проверка", "Укажите ФИО.")
            return
        phone_raw = self.user_phone_var.get().strip()
        data = {"full_name": name, "phone": phone_raw if phone_raw else None}
        out = self._safe_call(
            user_model.update_user,
            self.driver,
            self.selected_user_id,
            data,
        )
        if out:
            self.refresh_users()
            messagebox.showinfo("Готово", "Данные сохранены.")

    def delete_user(self) -> None:
        if self.selected_user_id is None:
            messagebox.showwarning("Выбор", "Выберите строку в таблице.")
            return
        if not messagebox.askyesno("Удаление", "Удалить пользователя и связанные брони?"):
            return
        self._safe_call(user_model.delete_user, self.driver, self.selected_user_id)
        self.selected_user_id = None
        self.user_name_var.set("")
        self.user_phone_var.set("")
        self.refresh_users()
        self.refresh_bookings()
        self._fill_booking_combos()

    # --- Столы ---
    def _build_tables_tab(self) -> None:
        cols = ("id", "label", "capacity", "zone")
        self.tables_tree = ttk.Treeview(
            self.tab_tables,
            columns=cols,
            show="headings",
            height=14,
        )
        for c, t in zip(cols, ("ID", "Метка", "Мест", "Зона")):
            self.tables_tree.heading(c, text=t)
            self.tables_tree.column(c, width=140 if c != "id" else 50)

        sy = ttk.Scrollbar(self.tab_tables, orient=tk.VERTICAL, command=self.tables_tree.yview)
        self.tables_tree.configure(yscrollcommand=sy.set)
        self.tables_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        self.tables_tree.bind("<<TreeviewSelect>>", self._on_table_select)

        form = ttk.LabelFrame(self.tab_tables, text="Добавить / изменить", padding=8)
        form.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(form, text="Метка:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.table_label_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.table_label_var, width=24).grid(
            row=0, column=1, sticky=tk.W, pady=2,
        )

        ttk.Label(form, text="Мест:").grid(row=0, column=2, sticky=tk.W, padx=8)
        self.table_cap_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.table_cap_var, width=8).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(form, text="Зона:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.table_zone_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.table_zone_var, width=40).grid(
            row=1, column=1, columnspan=3, sticky=tk.W, pady=2,
        )

        bf = ttk.Frame(form)
        bf.grid(row=2, column=0, columnspan=4, pady=8)
        ttk.Button(bf, text="Обновить список", command=self.refresh_tables).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Добавить", command=self.add_table).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Сохранить изменения", command=self.update_table).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Удалить", command=self.delete_table).pack(side=tk.LEFT, padx=4)

        self.selected_table_id: int | None = None

    def _on_table_select(self, _event=None) -> None:
        sel = self.tables_tree.selection()
        if not sel:
            self.selected_table_id = None
            return
        vals = self.tables_tree.item(sel[0], "values")
        self.selected_table_id = int(vals[0])
        self.table_label_var.set(vals[1])
        self.table_cap_var.set(str(vals[2]))
        self.table_zone_var.set(vals[3] or "")

    def refresh_tables(self) -> None:
        if not self.driver:
            return
        for i in self.tables_tree.get_children():
            self.tables_tree.delete(i)
        rows = self._safe_call(tables_model.list_dining_tables, self.driver)
        if rows is None:
            return
        for t in rows:
            self.tables_tree.insert(
                "",
                tk.END,
                values=(t.id, t.label, t.capacity, t.zone or ""),
            )
        self._fill_booking_combos()

    def add_table(self) -> None:
        label = self.table_label_var.get().strip()
        if not label:
            messagebox.showwarning("Проверка", "Укажите метку стола.")
            return
        try:
            cap = int(self.table_cap_var.get().strip())
        except ValueError:
            messagebox.showwarning("Проверка", "Мест — целое число.")
            return
        zone_raw = self.table_zone_var.get().strip()
        zone = zone_raw if zone_raw else None
        t = self._safe_call(
            tables_model.create_dining_table,
            self.driver,
            label,
            cap,
            zone,
        )
        if t:
            self.refresh_tables()
            messagebox.showinfo("Готово", f"Стол добавлен, id={t.id}.")

    def update_table(self) -> None:
        if self.selected_table_id is None:
            messagebox.showwarning("Выбор", "Выберите строку в таблице.")
            return
        label = self.table_label_var.get().strip()
        if not label:
            messagebox.showwarning("Проверка", "Укажите метку.")
            return
        try:
            cap = int(self.table_cap_var.get().strip())
        except ValueError:
            messagebox.showwarning("Проверка", "Мест — целое число.")
            return
        zone_raw = self.table_zone_var.get().strip()
        data = {
            "label": label,
            "capacity": cap,
            "zone": zone_raw if zone_raw else None,
        }
        out = self._safe_call(
            tables_model.update_dining_table,
            self.driver,
            self.selected_table_id,
            data,
        )
        if out:
            self.refresh_tables()
            messagebox.showinfo("Готово", "Данные сохранены.")

    def delete_table(self) -> None:
        if self.selected_table_id is None:
            messagebox.showwarning("Выбор", "Выберите строку в таблице.")
            return
        if not messagebox.askyesno("Удаление", "Удалить стол и связанные брони?"):
            return
        self._safe_call(
            tables_model.delete_dining_table,
            self.driver,
            self.selected_table_id,
        )
        self.selected_table_id = None
        self.table_label_var.set("")
        self.table_cap_var.set("")
        self.table_zone_var.set("")
        self.refresh_tables()
        self.refresh_bookings()
        self._fill_booking_combos()

    # --- Бронирования ---
    def _build_bookings_tab(self) -> None:
        cols = ("id", "user_id", "table_id", "starts_at", "ends_at", "party_size")
        twrap = ttk.Frame(self.tab_bookings)
        twrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.book_tree = ttk.Treeview(
            twrap,
            columns=cols,
            show="headings",
            height=11,
        )
        heads = ("ID", "Пользователь", "Стол", "Начало", "Конец", "Гостей")
        for c, h in zip(cols, heads):
            self.book_tree.heading(c, text=h)
            self.book_tree.column(c, width=110 if c != "id" else 45)

        sy = ttk.Scrollbar(twrap, orient=tk.VERTICAL, command=self.book_tree.yview)
        self.book_tree.configure(yscrollcommand=sy.set)
        self.book_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        self.book_tree.bind("<<TreeviewSelect>>", self._on_booking_select)

        newf = ttk.LabelFrame(self.tab_bookings, text="Новая бронь", padding=8)
        newf.pack(fill=tk.X, pady=6)

        ttk.Label(newf, text="Гость:").grid(row=0, column=0, sticky=tk.W, padx=4)
        self.book_user_combo = ttk.Combobox(newf, width=42, state="readonly")
        self.book_user_combo.grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=4, pady=2)

        ttk.Label(newf, text="Стол:").grid(row=1, column=0, sticky=tk.W, padx=4)
        self.book_table_combo = ttk.Combobox(newf, width=42, state="readonly")
        self.book_table_combo.grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=4, pady=2)

        ttk.Label(newf, text=f"Начало ({DATETIME_HINT}):").grid(
            row=2, column=0, sticky=tk.W, padx=4,
        )
        self.book_start_var = tk.StringVar()
        ttk.Entry(newf, textvariable=self.book_start_var, width=22).grid(
            row=2, column=1, sticky=tk.W, pady=2,
        )

        ttk.Label(newf, text=f"Конец ({DATETIME_HINT}):").grid(
            row=2, column=2, sticky=tk.W, padx=8,
        )
        self.book_end_var = tk.StringVar()
        ttk.Entry(newf, textvariable=self.book_end_var, width=22).grid(
            row=2, column=3, sticky=tk.W, pady=2,
        )

        ttk.Label(newf, text="Гостей:").grid(row=3, column=0, sticky=tk.W, padx=4)
        self.book_party_var = tk.StringVar(value="2")
        ttk.Entry(newf, textvariable=self.book_party_var, width=8).grid(
            row=3, column=1, sticky=tk.W, pady=2,
        )

        bf = ttk.Frame(newf)
        bf.grid(row=4, column=0, columnspan=4, pady=8)
        ttk.Button(bf, text="Обновить список", command=self.refresh_bookings).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Добавить бронь", command=self.add_booking).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Сохранить изменения", command=self.update_booking).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(bf, text="Удалить бронь", command=self.delete_booking).pack(
            side=tk.LEFT, padx=4,
        )

        av = ttk.LabelFrame(self.tab_bookings, text="Проверка доступности стола", padding=8)
        av.pack(fill=tk.X, pady=4)

        ttk.Label(av, text="Стол:").grid(row=0, column=0, sticky=tk.W, padx=4)
        self.av_table_combo = ttk.Combobox(av, width=42, state="readonly")
        self.av_table_combo.grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)

        ttk.Label(av, text=f"Начало ({DATETIME_HINT}):").grid(
            row=1, column=0, sticky=tk.W, padx=4,
        )
        self.av_start_var = tk.StringVar()
        ttk.Entry(av, textvariable=self.av_start_var, width=22).grid(
            row=1, column=1, sticky=tk.W, pady=2,
        )

        ttk.Label(av, text=f"Конец ({DATETIME_HINT}):").grid(
            row=1, column=2, sticky=tk.W, padx=8,
        )
        self.av_end_var = tk.StringVar()
        ttk.Entry(av, textvariable=self.av_end_var, width=22).grid(
            row=1, column=3, sticky=tk.W, pady=2,
        )

        ttk.Button(
            av,
            text="Проверить доступность",
            command=self.check_availability,
        ).grid(row=2, column=0, columnspan=4, pady=10)

        self.selected_booking_id: int | None = None

    def _parse_combo_user(self) -> int | None:
        s = self.book_user_combo.get()
        if not s or "—" not in s:
            return None
        part = s.split("—", 1)[0].strip()
        try:
            return int(part)
        except ValueError:
            return None

    def _parse_combo_table(self) -> int | None:
        s = self.book_table_combo.get()
        if not s or "—" not in s:
            return None
        part = s.split("—", 1)[0].strip()
        try:
            return int(part)
        except ValueError:
            return None

    def _parse_combo_av_table(self) -> int | None:
        s = self.av_table_combo.get()
        if not s or "—" not in s:
            return None
        part = s.split("—", 1)[0].strip()
        try:
            return int(part)
        except ValueError:
            return None

    def _fill_booking_combos(self) -> None:
        if not self.driver:
            return
        users = user_model.list_users(self.driver)
        tables = tables_model.list_dining_tables(self.driver)
        uv = [f"{u.id} — {u.full_name}" for u in users]
        tv = [f"{t.id} — {t.label} ({t.zone or 'без зоны'})" for t in tables]
        self.book_user_combo["values"] = uv
        self.book_table_combo["values"] = tv
        self.av_table_combo["values"] = tv
        if uv and not self.book_user_combo.get():
            self.book_user_combo.current(0)
        if tv and not self.book_table_combo.get():
            self.book_table_combo.current(0)
        if tv and not self.av_table_combo.get():
            self.av_table_combo.current(0)

    def _on_booking_select(self, _event=None) -> None:
        sel = self.book_tree.selection()
        if not sel:
            self.selected_booking_id = None
            return
        vals = self.book_tree.item(sel[0], "values")
        self.selected_booking_id = int(vals[0])
        uid, tid = int(vals[1]), int(vals[2])
        # set combos by id
        for i, u in enumerate(self.book_user_combo["values"]):
            if u.startswith(f"{uid} —"):
                self.book_user_combo.current(i)
                break
        for i, t in enumerate(self.book_table_combo["values"]):
            if t.startswith(f"{tid} —"):
                self.book_table_combo.current(i)
                break
        self.book_start_var.set(vals[3])
        self.book_end_var.set(vals[4])
        self.book_party_var.set(str(vals[5]))

    def refresh_bookings(self) -> None:
        if not self.driver:
            return
        for i in self.book_tree.get_children():
            self.book_tree.delete(i)
        books = self._safe_call(booking_model.list_bookings, self.driver)
        if books is None:
            return
        for b in books:
            self.book_tree.insert(
                "",
                tk.END,
                values=(
                    b.id,
                    b.user_id,
                    b.dining_table_id,
                    format_dt(b.starts_at),
                    format_dt(b.ends_at),
                    b.party_size,
                ),
            )

    def add_booking(self) -> None:
        uid = self._parse_combo_user()
        tid = self._parse_combo_table()
        if uid is None or tid is None:
            messagebox.showwarning("Проверка", "Выберите гостя и стол в списках.")
            return
        try:
            start = parse_datetime(self.book_start_var.get())
            end = parse_datetime(self.book_end_var.get())
            party = int(self.book_party_var.get().strip())
        except ValueError as err:
            messagebox.showwarning("Проверка", str(err))
            return
        b = self._safe_call(
            booking_model.create_booking,
            self.driver,
            uid,
            tid,
            start,
            end,
            party,
        )
        if b:
            self.refresh_bookings()
            messagebox.showinfo("Готово", f"Бронь создана, id={b.id}.")

    def update_booking(self) -> None:
        if self.selected_booking_id is None:
            messagebox.showwarning("Выбор", "Выберите бронь в таблице.")
            return
        uid = self._parse_combo_user()
        tid = self._parse_combo_table()
        if uid is None or tid is None:
            messagebox.showwarning("Проверка", "Выберите гостя и стол.")
            return
        try:
            start = parse_datetime(self.book_start_var.get())
            end = parse_datetime(self.book_end_var.get())
            party = int(self.book_party_var.get().strip())
        except ValueError as err:
            messagebox.showwarning("Проверка", str(err))
            return
        data = {
            "user_id": uid,
            "dining_table_id": tid,
            "starts_at": start,
            "ends_at": end,
            "party_size": party,
        }
        out = self._safe_call(
            booking_model.update_booking,
            self.driver,
            self.selected_booking_id,
            data,
        )
        if out:
            self.refresh_bookings()
            messagebox.showinfo("Готово", "Бронь обновлена.")

    def delete_booking(self) -> None:
        if self.selected_booking_id is None:
            messagebox.showwarning("Выбор", "Выберите бронь в таблице.")
            return
        if not messagebox.askyesno("Удаление", "Удалить выбранную бронь?"):
            return
        self._safe_call(
            booking_model.delete_booking,
            self.driver,
            self.selected_booking_id,
        )
        self.selected_booking_id = None
        self.refresh_bookings()

    def check_availability(self) -> None:
        tid = self._parse_combo_av_table()
        if tid is None:
            messagebox.showwarning("Проверка", "Выберите стол.")
            return
        try:
            start = parse_datetime(self.av_start_var.get())
            end = parse_datetime(self.av_end_var.get())
        except ValueError as err:
            messagebox.showwarning("Проверка", str(err))
            return
        ok = self._safe_call(
            booking_model.check_table_availability,
            self.driver,
            tid,
            start,
            end,
        )
        if ok is None:
            return
        if ok:
            messagebox.showinfo(
                "Доступность",
                "Стол свободен в указанном интервале.",
            )
        else:
            messagebox.showwarning(
                "Доступность",
                "Стол занят: интервал пересекается с существующей бронью.",
            )


def main() -> None:
    app = BookingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
