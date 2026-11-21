from __future__ import annotations
from pathlib import Path
from typing import Any
import polars as pl, yaml
from bimpolars.frame import BimDataFrame

def audit_iso19650(bdf: BimDataFrame, bep_yaml: str | Path | dict[str, Any]) -> BimDataFrame:
    rules = yaml.safe_load(Path(bep_yaml).read_text()) if isinstance(bep_yaml, (str, Path)) else bep_yaml
    reg_key = rules.get("name_regex")
    req_psets: dict[str, list[str]] = rules.get("required_psets", {})
    min_span = float(rules.get("min_bbox_span_m", 0.001))
    max_span = float(rules.get("max_bbox_span_m", 500.0))
    prop_dtype = bdf.frame.schema.get("properties")
    pset_names = {f.name for f in prop_dtype.fields} if isinstance(prop_dtype, pl.Struct) else set()
    exprs: list[pl.Expr] = []
    if reg_key and "name" in bdf.frame.columns:
        exprs.append(pl.when(pl.col("name").is_null() | ~pl.col("name").str.contains(reg_key)).then(pl.lit(f"ISO19650 name regex mismatch: {reg_key}")).otherwise(pl.lit(None)))
    if "bbox" in bdf.frame.columns:
        b = pl.col("bbox").struct
        span = pl.max_horizontal(b["xmax"] - b["xmin"], b["ymax"] - b["ymin"], b["zmax"] - b["zmin"])
        exprs.append(pl.when(pl.col("bbox").is_not_null() & ((span < min_span) | (span > max_span))).then(pl.lit("ISO19650 geometry bounds out of tolerance")).otherwise(pl.lit(None)))
    for cls, psets in req_psets.items():
        for ps in psets:
            if ps not in pset_names:
                exprs.append(pl.when(pl.col("class") == cls).then(pl.lit(f"ISO19650 missing Pset {ps} for {cls}")).otherwise(pl.lit(None)))
            else:
                exprs.append(pl.when((pl.col("class") == cls) & pl.col("properties").struct.field(ps).is_null()).then(pl.lit(f"ISO19650 null Pset {ps} on {cls}")).otherwise(pl.lit(None)))
    if exprs:
        r = pl.concat_list(exprs).list.drop_nulls()
        df = bdf.frame.with_columns(r.alias("iso19650_failures"), (r.list.len() == 0).alias("iso19650_pass"))
    else:
        df = bdf.frame.with_columns(pl.lit(True).alias("iso19650_pass"), pl.lit([], dtype=pl.List(pl.String)).alias("iso19650_failures"))
    return BimDataFrame(df, bdf.crs)
