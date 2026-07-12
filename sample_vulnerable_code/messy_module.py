"""
Intentionally low-quality sample code. Gives the Quality Agent something real
to flag (complexity, nesting, mutable defaults, bare except) alongside the
security issues in example.py. Do NOT write code like this.
"""


def process_order(order, items=[], discounts={}):
    # Mutable default arguments — shared across calls.
    total = 0
    if order:
        if "items" in order:
            for item in order["items"]:
                if item.get("qty", 0) > 0:
                    if item.get("price") is not None:
                        if item["price"] > 0:
                            total += item["qty"] * item["price"]
    items.append(order)
    return total, items, discounts


def categorize(value):
    # Branch explosion — cyclomatic complexity well over the threshold.
    if value == 1:
        return "one"
    elif value == 2:
        return "two"
    elif value == 3:
        return "three"
    elif value == 4:
        return "four"
    elif value == 5:
        return "five"
    elif value == 6:
        return "six"
    elif value == 7:
        return "seven"
    elif value == 8:
        return "eight"
    elif value == 9:
        return "nine"
    elif value == 10:
        return "ten"
    elif value == 11:
        return "eleven"
    else:
        return "many"


def parse_all(blobs):
    results = []
    for blob in blobs:
        try:
            results.append(int(blob))
        except:  # bare except swallows everything, even KeyboardInterrupt
            pass
    return results
