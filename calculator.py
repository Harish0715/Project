# utils/calculator.py
def line_total(unit_price: float, qty: int) -> float:
    return round(unit_price * qty, 2)

def calc_totals(cart_items: list, discount: float = 0.0):
    """
    cart_items: [{price, qty, gst}]
    Returns: dict(subtotal, gst_amount, discount, total)
    """
    subtotal = sum(ci["price"] * ci["qty"] for ci in cart_items)
    gst_amount = sum((ci["price"] * ci["qty"]) * (ci.get("gst", 0)/100.0) for ci in cart_items)
    subtotal = round(subtotal, 2)
    gst_amount = round(gst_amount, 2)
    discount = round(float(discount or 0), 2)
    total = round(subtotal + gst_amount - discount, 2)
    return {"subtotal": subtotal, "gst_amount": gst_amount, "discount": discount, "total": total}
