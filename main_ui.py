# ui/main_ui.py
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from utils.db_utils import (
    init_db, get_menu, get_item_by_name, load_menu_from_csv,
    create_order, add_order_items, export_bill_json, export_bill_csv
)
from utils.calculator import line_total, calc_totals

def run_app():
    init_db()  # ensure tables

    root = tk.Tk()
    root.title("Restaurant Billing Software")
    root.geometry("900x620")

    # ---- STATE ----
    menu_cache = {m["name"]: m for m in get_menu()}
    cart = []  # each: {item_id,item_name,qty,unit_price,price,gst,line_total}

    # ---- TOP BAR: Mode + Payment + Load Menu ----
    top = ttk.Frame(root, padding=10); top.pack(fill="x")

    mode_var = tk.StringVar(value="DINE_IN")
    ttk.Label(top, text="Mode:").pack(side="left")
    ttk.Radiobutton(top, text="Dine-In", value="DINE_IN", variable=mode_var).pack(side="left", padx=4)
    ttk.Radiobutton(top, text="Takeaway", value="TAKEAWAY", variable=mode_var).pack(side="left", padx=4)

    ttk.Label(top, text="   Payment:").pack(side="left", padx=(20,0))
    pay_var = tk.StringVar(value="Cash")
    ttk.Combobox(top, textvariable=pay_var, values=["Cash","Card","UPI"], width=10, state="readonly").pack(side="left")

    def on_load_menu():
        path = filedialog.askopenfilename(title="Pick menu.csv", filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            load_menu_from_csv(path)
            # refresh menu cache + combobox
            nonlocal menu_cache
            menu_cache = {m["name"]: m for m in get_menu()}
            item_combo["values"] = list(menu_cache.keys())
            messagebox.showinfo("Menu", "Menu loaded successfully.")
        except Exception as e:
            messagebox.showerror("Menu load failed", str(e))

    ttk.Button(top, text="Load Menu CSV", command=on_load_menu).pack(side="right")

    # ---- ITEM PICKER ----
    picker = ttk.LabelFrame(root, text="Add Items", padding=10); picker.pack(fill="x", padx=10, pady=5)

    ttk.Label(picker, text="Item").grid(row=0, column=0, sticky="w")
    item_var = tk.StringVar()
    item_combo = ttk.Combobox(picker, textvariable=item_var, width=30, state="readonly",
                              values=list(menu_cache.keys()))
    item_combo.grid(row=1, column=0, padx=5, pady=4, sticky="w")

    ttk.Label(picker, text="Qty").grid(row=0, column=1, sticky="w")
    qty_var = tk.IntVar(value=1)
    qty_spin = ttk.Spinbox(picker, from_=1, to=50, textvariable=qty_var, width=6)
    qty_spin.grid(row=1, column=1, padx=5, pady=4, sticky="w")

    def add_to_cart():
        name = item_var.get()
        if not name:
            messagebox.showwarning("Pick item", "Please select an item.")
            return
        meta = menu_cache.get(name) or get_item_by_name(name)
        if not meta:
            messagebox.showerror("Not found", "Item not found in menu.")
            return
        qty = qty_var.get()
        lt = line_total(meta["price"], qty)
        entry = {
            "item_id": meta["id"], "item_name": meta["name"],
            "qty": qty, "unit_price": meta["price"],
            "price": meta["price"], "gst": meta["gst"], "line_total": lt
        }
        cart.append(entry)
        tree.insert("", "end", values=(entry["item_name"], entry["qty"], f"{entry['unit_price']:.2f}",
                                       f"{entry['gst']}%", f"{entry['line_total']:.2f}"))
        update_totals()

    ttk.Button(picker, text="Add", command=add_to_cart).grid(row=1, column=2, padx=10)

    # ---- CART TABLE ----
    table = ttk.LabelFrame(root, text="Cart", padding=10); table.pack(fill="both", expand=True, padx=10, pady=5)
    cols = ("Item","Qty","Unit Price","GST","Line Total")
    tree = ttk.Treeview(table, columns=cols, show="headings", height=10)
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=140 if c=="Item" else 90, anchor="center")
    tree.pack(fill="both", expand=True, side="left")
    ttk.Scrollbar(table, orient="vertical", command=tree.yview).pack(side="right", fill="y")
    tree.configure(yscrollcommand=lambda *args: None)

    def remove_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Remove", "Select a row to remove.")
            return
        idx = tree.index(sel[0])
        tree.delete(sel[0])
        del cart[idx]
        update_totals()

    btns = ttk.Frame(root); btns.pack(fill="x", padx=10)
    ttk.Button(btns, text="Remove Selected", command=remove_selected).pack(side="left")

    # ---- TOTALS ----
    totals = ttk.LabelFrame(root, text="Totals", padding=10); totals.pack(fill="x", padx=10, pady=5)

    subtotal_var = tk.StringVar(value="0.00")
    gst_var = tk.StringVar(value="0.00")
    discount_var = tk.StringVar(value="0.00")
    total_var = tk.StringVar(value="0.00")

    ttk.Label(totals, text="Subtotal:").grid(row=0, column=0, sticky="e"); 
    ttk.Label(totals, textvariable=subtotal_var).grid(row=0, column=1, sticky="w")

    ttk.Label(totals, text="GST:").grid(row=0, column=2, sticky="e"); 
    ttk.Label(totals, textvariable=gst_var).grid(row=0, column=3, sticky="w")

    ttk.Label(totals, text="Discount:").grid(row=1, column=0, sticky="e"); 
    disc_entry = ttk.Entry(totals, textvariable=discount_var, width=10); disc_entry.grid(row=1, column=1, sticky="w")

    ttk.Label(totals, text="TOTAL:").grid(row=1, column=2, sticky="e"); 
    ttk.Label(totals, textvariable=total_var, font=("Segoe UI", 11, "bold")).grid(row=1, column=3, sticky="w")

    def update_totals(*_):
        # convert cart to minimal dicts calc expects
        mini = [{"price": x["price"], "qty": x["qty"], "gst": x["gst"]} for x in cart]
        try:
            d = float(discount_var.get() or 0)
        except ValueError:
            d = 0.0
            discount_var.set("0.00")
        t = calc_totals(mini, d)
        subtotal_var.set(f"{t['subtotal']:.2f}")
        gst_var.set(f"{t['gst_amount']:.2f}")
        total_var.set(f"{t['total']:.2f}")

    disc_entry.bind("<KeyRelease>", update_totals)

    # ---- SAVE BILL ----
    actions = ttk.Frame(root, padding=10); actions.pack(fill="x")
    def save_bill():
        if not cart:
            messagebox.showwarning("Empty", "No items in cart.")
            return
        t = calc_totals([{"price": x["price"], "qty": x["qty"], "gst": x["gst"]} for x in cart],
                        float(discount_var.get() or 0))
        order_id = create_order(
            mode_var.get(), pay_var.get(),
            t["subtotal"], t["gst_amount"], t["discount"], t["total"]
        )
        add_order_items(order_id, cart)
        jpath = export_bill_json(order_id)
        c1, c2 = export_bill_csv(order_id)
        messagebox.showinfo("Saved",
            f"Order #{order_id} saved.\n\nJSON: {jpath}\nCSV: {c1}\nItems: {c2}")
        # reset cart
        for i in tree.get_children(): tree.delete(i)
        cart.clear(); discount_var.set("0.00"); update_totals()

    ttk.Button(actions, text="Save Bill", command=save_bill).pack(side="left")
    ttk.Button(actions, text="Clear", command=lambda: [tree.delete(i) for i in tree.get_children()] or cart.clear() or update_totals()).pack(side="left", padx=8)

    # ---- Ensure a starter menu if empty ----
    if not menu_cache:
        os.makedirs("data", exist_ok=True)
        default_csv = os.path.join("data","menu.csv")
        if not os.path.exists(default_csv):
            with open(default_csv, "w", encoding="utf-8") as f:
                f.write("name,category,price,gst\n"
                        "Masala Dosa,Food,80,5\n"
                        "Paneer Tikka,Food,150,5\n"
                        "Coke,Beverage,40,12\n"
                        "Tea,Beverage,20,5\n"
                        "Ice Cream,Dessert,60,18\n")
        load_menu_from_csv(default_csv)
        menu_cache = {m["name"]: m for m in get_menu()}
        item_combo["values"] = list(menu_cache.keys())

    update_totals()
    root.mainloop()
