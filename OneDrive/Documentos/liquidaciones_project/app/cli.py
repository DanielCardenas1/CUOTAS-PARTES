# CLI con argparse para importar, generar liquidación y exportar PDF

# Objetivo (Copilot): CLI simple con comandos:
# - importar-excel
# - generar-liq --entidad NIT --desde 2022-10 --hasta 2025-09
# - pdf --liquidacion-id 123 --out out/CCP-2025-09-0001.pdf
import argparse
from app.db import get_session
from app.importer_excel import cargar_excel_a_bd

def main():
    parser = argparse.ArgumentParser("Liquidaciones CLI")
    sub = parser.add_subparsers(dest="cmd")

    # importar-excel
    sub.add_parser("importar-excel")

    # generar-liq
    p_gen = sub.add_parser("generar-liq")
    p_gen.add_argument("--entidad", required=True)     # NIT o id
    p_gen.add_argument("--desde", required=True)       # YYYY-MM
    p_gen.add_argument("--hasta", required=True)       # YYYY-MM

    # pdf
    p_pdf = sub.add_parser("pdf")
    p_pdf.add_argument("--liquidacion-id", required=True, type=int)
    p_pdf.add_argument("--out", required=True)

    args = parser.parse_args()

    if args.cmd == "importar-excel":
        session = get_session()
        cargar_excel_a_bd(session)
        print("Importación de Excel completada.")
        session.close()
    # Aquí puedes enrutar los otros comandos (generar-liq, pdf)

if __name__ == "__main__":
    main()
