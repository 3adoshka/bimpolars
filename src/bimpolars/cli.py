from __future__ import annotations
import argparse, sys
from pathlib import Path
import bimpolars as bp
from bimpolars.erp import build_boq, push_boq
from bimpolars.standards import audit_iso19650, export_bcf, validate_bsdd_uris, validate_ids

def _cmd_audit(args: argparse.Namespace) -> int:
    bdf = bp.read_ifc(args.ifc)
    if args.bep:
        bdf = audit_iso19650(bdf, args.bep)
    if args.ids:
        bdf = validate_ids(bdf, args.ifc, args.ids)
    if args.bsdd:
        bdf = validate_bsdd_uris(bdf, offline=args.offline)
    if args.bcf:
        export_bcf(bdf, args.bcf)
    passed = int(bdf.frame["iso19650_pass"].sum()) if "iso19650_pass" in bdf.frame.columns else len(bdf.frame)
    print(f"Audited {len(bdf.frame)} elements | ISO19650 passed: {passed}")
    return 0

def _cmd_boq(args: argparse.Namespace) -> int:
    bdf = bp.read_ifc(args.ifc)
    boq = build_boq(bdf)
    out = push_boq(boq, args.out)
    print(f"Exported BOQ ({len(boq)} rows) -> {out}")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bimpolars", description="openBIM & ERP CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    p_aud = sub.add_parser("audit", help="Run ISO 19650 / IDS / bSDD checks and export BCF")
    p_aud.add_argument("ifc", help="Path to IFC file")
    p_aud.add_argument("--bep", help="Path to ISO 19650 YAML BEP rules")
    p_aud.add_argument("--ids", help="Path to buildingSMART IDS XML")
    p_aud.add_argument("--bsdd", action="store_true", help="Validate bSDD URIs")
    p_aud.add_argument("--offline", action="store_true", help="Use bSDD cache only")
    p_aud.add_argument("--bcf", help="Output .bcfzip path")
    p_aud.set_defaults(func=_cmd_audit)
    p_boq = sub.add_parser("boq", help="Generate Uniclass 2015 Bill of Quantities")
    p_boq.add_argument("ifc", help="Path to IFC file")
    p_boq.add_argument("--out", default="boq.parquet", help="Output .parquet or .json path")
    p_boq.set_defaults(func=_cmd_boq)
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
