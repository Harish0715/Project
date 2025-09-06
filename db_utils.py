# utils/db_utils.py
import os, sqlite3, csv, json
from datetime import datetime

DB_PATH = os.path.join("db", "restaurant.db")

def _conn():
    os.makedirs("db", exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                price REAL NOT NULL,
                gst REAL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT CHECK(mode IN ('DINE_IN','TAKEAWAY')) NOT NULL,
                payment_method TEXT NOT NULL,
                subtotal REAL NOT NULL,
                gst_amount REAL NOT NULL,
                discount REAL NOT NULL,
                total REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                qty INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(item_id) REFERENCES menu(id)
            )
        """)
        con.commit()

def load_menu_from_csv(csv_path: str):
    # expects columns: name,category,price,gst
    with _conn() as con, open(csv_path, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [(r["name"], r.get("category",""), float(r["price"]), float(r.get("gst",0) or 0))
                for r in reader]
        cur = con.cursor()
        # replace entire menu for simplicity
        cur.execute("DELETE FROM menu")
        cur.executemany("INSERT OR REPLACE INTO menu(name,category,price,gst) VALUES(?,?,?,?)", rows)
        con.commit()

def get_menu():
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT id, name, category, price, gst FROM menu ORDER BY name")
        cols = ["id","name","category","price","gst"]
        return [dict(zip(cols,row)) for row in cur.fetchall()]

def get_item_by_name(name: str):
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT id, name, price, gst FROM menu WHERE name=?", (name,))
        row = cur.fetchone()
        if not row: return None
        return {"id": row[0], "name": row[1], "price": row[2], "gst": row[3]}

def create_order(mode, payment_method, subtotal, gst_amount, discount, total):
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""INSERT INTO orders(mode,payment_method,subtotal,gst_amount,discount,total,created_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (mode, payment_method, subtotal, gst_amount, discount, total,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
        return cur.lastrowid

def add_order_items(order_id: int, items: list):
    # items: [{item_id, item_name, qty, unit_price, line_total}]
    with _conn() as con:
        cur = con.cursor()
        cur.executemany("""INSERT INTO order_items(order_id,item_id,item_name,qty,unit_price,line_total)
                           VALUES(?,?,?,?,?,?)""",
                        [(order_id, it["item_id"], it["item_name"], it["qty"], it["unit_price"], it["line_total"])
                         for it in items])
        con.commit()

def get_order_detail(order_id: int):
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        ocols = [d[0] for d in cur.description]
        order = dict(zip(ocols, cur.fetchone()))
        cur.execute("SELECT item_name, qty, unit_price, line_total FROM order_items WHERE order_id=?", (order_id,))
        icols = [d[0] for d in cur.description]
        items = [dict(zip(icols, r)) for r in cur.fetchall()]
        return {"order": order, "items": items}

def export_bill_json(order_id: int, out_dir="data"):
    os.makedirs(out_dir, exist_ok=True)
    data = get_order_detail(order_id)
    path = os.path.join(out_dir, f"bill_{order_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path

def export_bill_csv(order_id: int, out_dir="data"):
    os.makedirs(out_dir, exist_ok=True)
    data = get_order_detail(order_id)
    # order header
    order = data["order"]
    items = data["items"]
    order_path = os.path.join(out_dir, f"bill_{order_id}_order.csv")
    items_path = os.path.join(out_dir, f"bill_{order_id}_items.csv")
    # write order one-line CSV
    with open(order_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(order.keys()))
        writer.writeheader(); writer.writerow(order)
    # write items CSV
    with open(items_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["item_name","qty","unit_price","line_total"])
        writer.writeheader(); writer.writerows(items)
    return order_path, items_path
