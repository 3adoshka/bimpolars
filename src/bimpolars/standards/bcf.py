"""buildingSMART BFF (ISO 21597) exporter for BimDataFrame failures."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import polars as pl
from bimpolars.frame import BimDataFrame

def export_bcf(
    bdf: BimDataFrame,
    output_path: str | Path,
    project_name: str = "bimpolars QA Audit",
    author: str = "bimpolars-bot",
    filter_col: str = "ids_pass",
    reason_col: str = "ids_failures",
) -> Path:
    from bcf.v2.bcfxml import BcfXml

    bcf_file = BcfXml.create_new(project_name)

    if filter_col in bdf.frame.columns:
        failed = bdf.frame.filter(~pl.col(filter_col).fill_null(True))
    else:
        failed = bdf.frame

    for row in failed.iter_rows(named=True):
        gid = str(row["id"])
        elem_name = row.get("name") or row.get("class") or gid
        reasons = row.get(reason_col) or []
        desc = "\n".join(str(r) for r in reasons) if reasons else "QA check failed"
        topic = bcf_file.add_topic(
            title=f"[{row.get('class', 'IFC')}] {elem_name} ({gid})",
            description=desc,
            author=author,
            topic_type="QA Audit",
            topic_status="Open",
        )
        bbox = row.get("bbox")
        if bbox and all(bbox.get(k) is not None for k in ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax")):
            center = np.array(
                [
                    (bbox["xmin"] + bbox["xmax"]) / 2.0,
                    (bbox["ymin"] + bbox["ymax"]) / 2.0,
                    (bbox["zmin"] + bbox["zmax"]) / 2.0,
                ],
                dtype=np.float64,
            )
            topic.add_viewpoint_from_point_and_guids(center, gid)

    out = Path(output_path)
    bcf_file.save(out)
    return out
