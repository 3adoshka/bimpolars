"""buildingSMART IDS (ISO 7817-1) validation adapter for BimDataFrame."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import polars as pl
from bimpolars.frame import BimDataFrame

def validate_ids(bdf: BimDataFrame, ifc_source: str | Path, ids_source: str | Path) -> BimDataFrame:
    import ifcopenshell
    from ifctester import ids
    ifc_file = ifcopenshell.open(str(ifc_source))
    ids_spec = ids.open(str(ids_source))
    ids_spec.validate(ifc_file)
    failure_rows: list[dict[str, Any]] = []
    for spec in ids_spec.specifications:
        if spec.status:
            continue
        spec_label = f"{spec.name}: {spec.description}" if spec.description else str(spec.name)
        for entity in getattr(spec, "failed_entities", []):
            global_id = getattr(entity, "GlobalId", None)
            if global_id:
                failure_rows.append({"id": str(global_id), "reason": spec_label})
    if failure_rows:
        failures_df = pl.DataFrame(failure_rows).group_by("id").agg(pl.col("reason").alias("ids_failures"))
        joined = bdf.frame.join(failures_df, on="id", how="left").with_columns(
            pl.col("ids_failures").fill_null([]),
            pl.col("ids_failures").is_null().alias("ids_pass"),
        )
    else:
        joined = bdf.frame.with_columns(
            pl.lit(True).alias("ids_pass"),
            pl.lit([], dtype=pl.List(pl.String)).alias("ids_failures"),
        )
    return BimDataFrame(joined)
