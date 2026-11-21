from __future__ import annotations
import polars as pl
from bimpolars.frame import BimDataFrame

DEFAULT_UNICLASS_MAP: dict[str, tuple[str, str]] = {
    "IfcWall": ("EF_25_10", "Walls"),
    "IfcWallStandardCase": ("EF_25_10", "Walls"),
    "IfcCurtainWall": ("Ss_25_10_20", "Curtain walling systems"),
    "IfcSlab": ("EF_20_10", "Floors and slabs"),
    "IfcRoof": ("EF_20_20", "Roofs"),
    "IfcColumn": ("EF_15_10", "Columns"),
    "IfcBeam": ("EF_15_20", "Beams"),
    "IfcFooting": ("EF_10_10", "Foundations"),
    "IfcPile": ("EF_10_20", "Piles"),
    "IfcDoor": ("Pr_30_59_24", "Doorsets"),
    "IfcWindow": ("Pr_30_59_98", "Windows"),
    "IfcStair": ("EF_20_30", "Stairs and ramps"),
    "IfcRailing": ("Pr_35_90_68", "Railings and balustrades"),
    "IfcCovering": ("Ss_30_42", "Ceiling and wall finishes"),
    "IfcPipeSegment": ("Ss_55_70", "Piped supply systems"),
    "IfcDuctSegment": ("Ss_65_40", "Ventilation ducting systems"),
}

def _extract_qto_expr(df: pl.DataFrame, field_names: tuple[str, ...]) -> pl.Expr:
    prop_dtype = df.schema.get("properties")
    if not isinstance(prop_dtype, pl.Struct):
        return pl.lit(None, dtype=pl.Float64)
    candidates: list[pl.Expr] = []
    for pset_field in prop_dtype.fields:
        if isinstance(pset_field.dtype, pl.Struct):
            sub_names = {f.name for f in pset_field.dtype.fields}
            for target in field_names:
                if target in sub_names:
                    candidates.append(pl.col("properties").struct.field(pset_field.name).struct.field(target).cast(pl.Float64, strict=False))
    return pl.coalesce(candidates) if candidates else pl.lit(None, dtype=pl.Float64)

def build_boq(bdf: BimDataFrame, uniclass_map: dict[str, tuple[str, str]] | None = None) -> pl.DataFrame:
    mapping = uniclass_map or DEFAULT_UNICLASS_MAP
    lookup = pl.DataFrame({"class": list(mapping.keys()), "uniclass_code": [v[0] for v in mapping.values()], "uniclass_group": [v[1] for v in mapping.values()]})
    df = bdf.frame.join(lookup, on="class", how="left").with_columns(pl.col("uniclass_code").fill_null("EF_90_90"), pl.col("uniclass_group").fill_null("Unmapped / General"))
    qto_vol = _extract_qto_expr(df, ("NetVolume", "GrossVolume", "Volume"))
    qto_area = _extract_qto_expr(df, ("NetArea", "GrossArea", "NetSideArea", "Area")).fill_null(0.0)
    qto_len = _extract_qto_expr(df, ("Length", "Height", "Width")).fill_null(0.0)
    if "bbox" in df.columns:
        b = pl.col("bbox").struct
        bbox_vol = ((b["xmax"] - b["xmin"]).abs() * (b["ymax"] - b["ymin"]).abs() * (b["zmax"] - b["zmin"]).abs()).fill_null(0.0)
    else:
        bbox_vol = pl.lit(0.0)
    return (
        df.with_columns(
            pl.coalesce([qto_vol, bbox_vol]).alias("_vol_m3"),
            qto_area.alias("_area_m2"),
            qto_len.alias("_len_m"),
            pl.when(qto_vol.is_not_null()).then(pl.lit("Qto")).otherwise(pl.lit("bbox_fallback")).alias("quantity_source"),
        )
        .group_by(["uniclass_code", "uniclass_group", "class", "quantity_source"])
        .agg(
            pl.len().alias("element_count"),
            pl.col("_vol_m3").sum().round(4).alias("net_volume_m3"),
            pl.col("_area_m2").sum().round(4).alias("net_area_m2"),
            pl.col("_len_m").sum().round(4).alias("net_length_m"),
        )
        .sort(["uniclass_code", "quantity_source"])
    )
