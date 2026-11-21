from __future__ import annotations
from pathlib import Path
from typing import Any
import polars as pl, yaml
from bimpolars.frame import BimDataFrame

VALID_CDE_CODES = {"S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"}

def audit_iso19650(bdf: BimDataFrame, bep_yaml: str | Path | dict[str, Any]) -> BimDataFrame:
    rules = yaml.safe_load(Path(bep_yaml).read_text()) if isinstance(bep_yaml, (str, Path)) else bep_yaml
    reg_key = rules.get("name_regex")
    allowed_cde = set(rules.get("allowed_cde_codes", VALID_CDE_CODES))
    req_psets: dict[str, list[str]] = rules.get("required_psets", {})
    req_props: dict[str, dict[str, Any]] = rules.get("required_properties", {})
    min_span, max_span = float(rules.get("min_bbox_span_m", 0.001)), float(rules.get("max_bbox_span_m", 500.0))
    prop_dtype = bdf.frame.schema.get("properties")
    pset_fields = {f.name: f.dtype for f in prop_dtype.fields} if isinstance(prop_dtype, pl.Struct) else {}
    exprs: list[pl.Expr] = []
    if reg_key and "name" in bdf.frame.columns:
        exprs.append(pl.when(pl.col("name").is_null() | ~pl.col("name").str.contains(reg_key)).then(pl.lit(f"ISO19650 name mismatch: {reg_key}")).otherwise(pl.lit(None)))
    if "cde_status" in bdf.frame.columns and rules.get("allowed_cde_codes"):
        exprs.append(pl.when(pl.col("cde_status").is_null() | ~pl.col("cde_status").is_in(list(allowed_cde))).then(pl.lit("ISO19650 invalid CDE suitability code")).otherwise(pl.lit(None)))
    if "bbox" in bdf.frame.columns:
        b = pl.col("bbox").struct
        span = pl.max_horizontal(b["xmax"] - b["xmin"], b["ymax"] - b["ymin"], b["zmax"] - b["zmin"])
        exprs.append(pl.when(pl.col("bbox").is_not_null() & ((span < min_span) | (span > max_span))).then(pl.lit("ISO19650 geometry bounds out of tolerance")).otherwise(pl.lit(None)))
    for cls, psets in req_psets.items():
        for ps in psets:
            cond = (pl.col("class") == cls) if ps not in pset_fields else ((pl.col("class") == cls) & pl.col("properties").struct.field(ps).is_null())
            exprs.append(pl.when(cond).then(pl.lit(f"ISO19650 missing Pset {ps} for {cls}")).otherwise(pl.lit(None)))
    for cls, props in req_props.items():
        for dotted, rule in props.items():
            ps, pr = dotted.split(".", 1)
            sub_ok = isinstance(pset_fields.get(ps), pl.Struct) and pr in {f.name for f in pset_fields[ps].fields}
            if not sub_ok:
                exprs.append(pl.when(pl.col("class") == cls).then(pl.lit(f"ISO19650 missing LOIN {dotted} on {cls}")).otherwise(pl.lit(None)))
            else:
                val = pl.col("properties").struct.field(ps).struct.field(pr)
                fail = val.is_null() | (~val.cast(pl.String).str.contains(str(rule["regex"])) if isinstance(rule, dict) and "regex" in rule else pl.lit(False))
                exprs.append(pl.when((pl.col("class") == cls) & fail).then(pl.lit(f"ISO19650 failed LOIN {dotted} on {cls}")).otherwise(pl.lit(None)))
    r = pl.concat_list(exprs).list.drop_nulls() if exprs else pl.lit([], dtype=pl.List(pl.String))
    df = bdf.frame.with_columns(r.alias("iso19650_failures"), (r.list.len() == 0).alias("iso19650_pass"))
    return BimDataFrame(df, bdf.crs)
