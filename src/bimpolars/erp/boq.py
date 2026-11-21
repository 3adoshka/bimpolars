from __future__ import annotations
from pathlib import Path
import polars as pl
from bimpolars.frame import BimDataFrame

DEFAULT_UNICLASS_MAP: dict[str, tuple[str, str]] = {
    "IfcWall": ("EF_25_10", "Walls"),
    "IfcWallStandardCase": ("EF_25_10", "Walls"),
    "IfcSlab": ("EF_20_10", "Floors and slabs"),
    "IfcColumn": ("EF_15_10", "Columns"),
    "IfcBeam": ("EF_15_20", "Beams"),
    "IfcDoor": ("EF_25_30", "Doors"),
    "IfcWindow": ("EF_25_40", "Windows"),
    "IfcStair": ("EF_20_30", "Stairs and ramps"),
}

def build_boq(bdf: BimDataFrame, uniclass_map: dict[str, tuple[str, str]] | None = None) -> pl.DataFrame:
    mapping = uniclass_map or DEFAULT_UNICLASS_MAP
    lookup = pl.DataFrame({
        "class": list(mapping.keys()),
        "uniclass_code": [v[0] for v in mapping.values()],
        "uniclass_group": [v[1] for v in mapping.values()],
    })
    df = bdf.frame.join(lookup, on="class", how="left").with_columns(
        pl.col("uniclass_code").fill_null("EF_90_90"),
        pl.col("uniclass_group").fill_null("Unmapped / General"),
    )
    if "bbox" in df.columns:
        b = pl.col("bbox").struct
        vol_expr = ((b["xmax"] - b["xmin"]).abs() * (b["ymax"] - b["ymin"]).abs() * (b["zmax"] - b["zmin"]).abs()).fill_null(0.0)
    else:
        vol_expr = pl.lit(0.0)
    return (
        df.with_columns(vol_expr.alias("_approx_bbox_vol_m3"))
        .group_by(["uniclass_code", "uniclass_group", "class"])
        .agg(
            pl.len().alias("element_count"),
            pl.col("_approx_bbox_vol_m3").sum().alias("net_bbox_volume_m3"),
        )
        .sort("uniclass_code")
    )
