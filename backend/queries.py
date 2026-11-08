"""
backend/queries.py
=====================================================================
CONSULTAS DE HISTÓRICOS (requisito del parcial).

Interfaz de línea de comandos para recuperar los datos almacenados
en SQLite. Ejecutar desde la raíz del proyecto:

    python -m backend.queries resumen
    python -m backend.queries lecturas -n 20
    python -m backend.queries eventos -n 30
    python -m backend.queries eventos --tipo MOTION_DETECTED
    python -m backend.queries comandos -n 10
    python -m backend.queries entre --desde 2026-11-08T00:00:00 \
                                    --hasta 2026-11-08T23:59:59
=====================================================================
"""

import argparse
import sys

from backend.database import Database


def _print_table(rows, columns=None):
    """Imprime filas de sqlite3.Row como una tabla alineada."""
    if not rows:
        print("  (sin resultados)")
        return
    columns = columns or list(rows[0].keys())
    widths = {c: max(len(str(c)), *(len(str(r[c]) if r[c] is not None else "")
                                    for r in rows)) for c in columns}
    header = " | ".join(str(c).ljust(widths[c]) for c in columns)
    print(header)
    print("-+-".join("-" * widths[c] for c in columns))
    for row in rows:
        print(" | ".join(
            ("" if row[c] is None else str(row[c])).ljust(widths[c])
            for c in columns))


def cmd_resumen(db: Database, _args):
    """Estadísticas generales del sistema."""
    data = db.resumen()
    print("=== RESUMEN DEL SISTEMA DE SEGURIDAD ===")
    for key, value in data.items():
        print("  {:<20}: {}".format(key, value))


def cmd_lecturas(db: Database, args):
    """Últimas lecturas de sensores."""
    rows = db.ultimas_lecturas(args.limit)
    _print_table(rows, columns=[
        "id", "recibido_at", "motion", "lux", "light_state",
        "armed", "alarm", "detail"])


def cmd_eventos(db: Database, args):
    """Últimos eventos de seguridad."""
    rows = db.eventos(limit=args.limit, tipo=args.tipo)
    _print_table(rows, columns=[
        "id", "recibido_at", "tipo", "estado", "fuente", "detalle"])


def cmd_comandos(db: Database, args):
    """Últimos comandos ejecutados."""
    rows = db.comandos(args.limit)
    _print_table(rows, columns=[
        "id", "recibido_at", "origen", "comando", "estado", "detalle"])


def cmd_entre(db: Database, args):
    """Lecturas dentro de un rango de fechas."""
    rows = db.entre_fechas(args.desde, args.hasta, args.limit)
    _print_table(rows, columns=[
        "id", "recibido_at", "motion", "lux", "armed", "alarm", "detail"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.queries",
        description="Consultas a la base de datos del Sistema de Seguridad",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("resumen", help="estadísticas generales")
    p.set_defaults(func=cmd_resumen)

    p = sub.add_parser("lecturas", help="últimas lecturas de sensores")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(func=cmd_lecturas)

    p = sub.add_parser("eventos", help="últimos eventos de seguridad")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.add_argument("--tipo", help="filtra por tipo, ej. MOTION_DETECTED")
    p.set_defaults(func=cmd_eventos)

    p = sub.add_parser("comandos", help="últimos comandos ejecutados")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(func=cmd_comandos)

    p = sub.add_parser("entre", help="lecturas entre dos fechas ISO")
    p.add_argument("--desde", required=True, help="2026-11-08T00:00:00")
    p.add_argument("--hasta", required=True, help="2026-11-08T23:59:59")
    p.add_argument("-n", "--limit", type=int, default=200)
    p.set_defaults(func=cmd_entre)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    db = Database()
    try:
        args.func(db, args)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
