"""Ad-hoc verification: bulk discount applies at exactly min_amount."""
import sys, os

sys.path.insert(0, 'pristine')
from main import apply_bulk_discount, compute_subtotal, LineItem, parse_lines

errors = []

# 1. Subtotal EXACTLY at $500 should get the 10% discount (this is the fix)
d500 = apply_bulk_discount(500.0)
if d500 != round(500.0 * 0.9, 2):
    errors.append(f'FAIL: subtotal=500 -> {d500}, expected 450.0')

# 2. Subtotal ABOVE $500 still gets discount (regression check)
d600 = apply_bulk_discount(600.0)
if d600 != round(600.0 * 0.9, 2):
    errors.append(f'FAIL: subtotal=600 -> {d600}, expected 540.0')

# 3. Subtotal BELOW $500 gets no discount
nd = apply_bulk_discount(499.99)
if nd != round(499.99, 2):
    errors.append(f'FAIL: subtotal=499.99 -> {nd}')

# 4. Zero subtotal gets no discount
z = apply_bulk_discount(0.0)
if z != 0.0:
    errors.append(f'FAIL: subtotal=0 -> {z}')

# 5. Round-trip via parse_lines + compute_subtotal at boundary
rows = ['SKU1,Widget A,4,125.0', 'SKU2,Widget B,3,100.0']
items = parse_lines(rows)
sub = compute_subtotal(items)
final = apply_bulk_discount(sub)
if final != round(800.0 * 0.9, 2):
    errors.append(f'FAIL: subtotal={sub} -> {final}, expected 720.0')

# 6. Files match exactly (pristine and work dir should be identical)
with open('pristine/main.py') as f1, open('work__d69dd927/main.py') as f2:
    if f1.read() != f2.read():
        errors.append('FAIL: work file does not match pristine')

if errors:
    print('FAILED:')
    for e in errors:
        print(e)
else:
    print('ALL CHECKS PASSED')
