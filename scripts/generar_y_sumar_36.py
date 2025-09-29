import subprocess
import re
import sys
from datetime import date
from calendar import monthrange

# Config
IDENT = '26489799'
# Use the same Python executable running this script to avoid environment differences
PY = sys.executable
GEN_SCRIPT = 'generar_pdf_oficial.py'

# Months from Sep 2022 to Aug 2025 inclusive
start_year = 2022
start_month = 9
months = []
for y in range(2022, 2026):
    for m in range(1, 13):
        if (y == 2022 and m < 9):
            continue
        if (y == 2025 and m > 8):
            continue
        months.append((y, m))

pattern_cap = re.compile(r"Total\s*capital[:\s]*\$?\s*([\d,\.,]+)", re.IGNORECASE)
pattern_int = re.compile(r"Total\s*intereses[:\s]*\$?\s*([\d,\.,]+)", re.IGNORECASE)
# Accept both 'liquidación' (with accent) and 'liquidacion' (without), allow optional emoji/prefix
pattern_tot = re.compile(r"(?:[\w\W]{0,8})?Total\s*liquidac[ió]n[:\s]*\$?\s*([\d,\.,]+)", re.IGNORECASE)

results = []
total_cap = 0.0
total_int = 0.0
total_all = 0.0

for año, mes in months:
    cmd = [PY, GEN_SCRIPT, '--id', IDENT, '--periodo', 'custom', '--año-inicio', str(año), '--mes-inicio', str(mes)]
    print(f"Generando cuenta inicio {año}-{mes:02d} ...")
    # Force UTF-8 for the child process to avoid encoding errors on Windows console
    env = dict(**(subprocess.os.environ))
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    # Combine stdout and stderr because the generator may print to stderr when encoding fails
    out = (proc.stdout or '') + '\n' + (proc.stderr or '')
    # Buscar totales
    cap = 0.0
    inte = 0.0
    tot = 0.0
    m_cap = pattern_cap.search(out)
    m_int = pattern_int.search(out)
    m_tot = pattern_tot.search(out)
    if m_cap:
        cap = float(m_cap.group(1).replace(',', '').replace('.', '', m_cap.group(1).count(','))) if False else float(m_cap.group(1).replace(',', ''))
    if m_int:
        inte = float(m_int.group(1).replace(',', ''))
    if m_tot:
        tot = float(m_tot.group(1).replace(',', ''))

    # If total not found, fallback to capital + intereses when available
    if tot == 0.0 and (cap != 0.0 or inte != 0.0):
        tot = cap + inte

    results.append({'año': año, 'mes': mes, 'capital': cap, 'intereses': inte, 'total': tot, 'stdout': out})
    total_cap += cap
    total_int += inte
    total_all += tot

# Print summary
print('\nResumen por mes generado:')
for r in results:
    print(f"{r['año']}-{r['mes']:02d} | Capital: ${r['capital']:,.2f} | Intereses: ${r['intereses']:,.2f} | Total: ${r['total']:,.2f}")

print('\nAcumulados GENERADOS:')
print(f"Capital total: ${total_cap:,.2f}")
print(f"Intereses total: ${total_int:,.2f}")
print(f"Gran Total: ${total_all:,.2f}")

# Save CSV
import csv
with open('GENERADAS_26489799_36.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['año','mes','capital','intereses','total'])
    writer.writeheader()
    for r in results:
        writer.writerow({'año': r['año'], 'mes': r['mes'], 'capital': r['capital'], 'intereses': r['intereses'], 'total': r['total']})

print('\nCSV creado: GENERADAS_26489799_36.csv')
