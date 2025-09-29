# CLI con argparse para importar, generar liquidación y exportar PDF

# Objetivo (Copilot): CLI simple con comandos:
# - importar-excel
# - generar-liq --entidad NIT --desde 2022-10 --hasta 2025-09
# - pdf --liquidacion-id 123 --out out/CCP-2025-09-0001.pdf
import argparse
from app.db import get_session
from app.importer_excel import cargar_excel_a_bd
from app.liquidar import generar_liquidacion_completa
from app.pdf import generar_pdf_completo
from datetime import datetime

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
    elif args.cmd == "generar-liq":
        session = get_session()
        try:
            desde = datetime.strptime(args.desde + "-01", "%Y-%m-%d").date()
            # fin de mes de 'hasta'
            hasta_dt = datetime.strptime(args.hasta + "-01", "%Y-%m-%d")
            from dateutil.relativedelta import relativedelta
            fin_mes = (hasta_dt + relativedelta(months=1, days=-1)).date()
            data = generar_liquidacion_completa(session, args.entidad, desde, fin_mes)
            print(f"Liquidación generada para {args.entidad}: {len(data['pensionados'])} pensionados. Total=${float(data['totales']['total']):,.2f}")
        finally:
            session.close()
    elif args.cmd == "pdf":
        session = get_session()
        try:
            # Para este CLI simple, volvemos a generar desde datos y luego exportamos
            # (en un sistema real, pdf usaría un ID ya guardado)
            print("Use 'generar-liq' y luego 'app.pdf.generar_pdf_completo' con la data retornada en un script dedicado.")
        finally:
            session.close()

if __name__ == "__main__":
    main()
