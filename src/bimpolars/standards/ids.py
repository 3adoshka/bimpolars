from __future__ import annotations
from pathlib import Path
import ifcopenshell, polars as pl
from ifctester import ids
from bimpolars.frame import BimDataFrame

def validate_ids(bdf: BimDataFrame, ifc_path: str | Path, ids_path: str | Path, id_col: str = "id") -> BimDataFrame:
    model = ifcopenshell.open(str(ifc_path))
    spec_file = ids.open(str(ids_path))
    spec_file.validate(model)
    fail_map: dict[str, list[str]] = {}
    for spec in spec_file.specifications:
        spec_name = getattr(spec, "name", "Unnamed IDS Specification")
        for el in getattr(spec, "failed_entities", []):
            gid = getattr(el, "GlobalId", None)
            if gid:
                fail_map.setdefault(gid, []).append(f"IDS [{spec_name}] failed")
    if fail_map:
        fail_df = pl.DataFrame({id_col: list(fail_map.keys()), "ids_failures": list(fail_map.values())})
        joined = bdf.frame.join(fail_df, on=id_col, how="left").with_columns(
            pl.col("ids_failures").fill_null([]),
            pl.col("ids_failures").is_null().alias("ids_pass"),
        )
    else:
        joined = bdf.frame.with_columns(
            pl.lit([], dtype=pl.List(pl.String)).alias("ids_failures"),
            pl.lit(True).alias("ids_pass"),
        )
    return BimDataFrame(joined, bdf.crs)
