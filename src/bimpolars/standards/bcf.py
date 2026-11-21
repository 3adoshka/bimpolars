from __future__ import annotations
import uuid
from pathlib import Path
import polars as pl
from bcf.v2.bcfxml import BcfXml
from bcf.v2.model import Component, Components, ComponentSelection, ComponentVisibility, Direction, PerspectiveCamera, Point, ViewSetupHints, VisualizationInfo
from bcf.v2.visinfo import VisualizationInfoHandler
from bimpolars.frame import BimDataFrame

def export_bcf(bdf: BimDataFrame, out_path: str | Path, project_name: str = "bimpolars Audit", filter_col: str = "iso19650_pass", reason_cols: tuple[str, ...] = ("iso19650_failures", "ids_failures"), author: str = "bimpolars@openbim.local") -> Path:
    df = bdf.frame.filter(~pl.col(filter_col)) if filter_col in bdf.frame.columns else bdf.frame
    bcf = BcfXml.create_new(project_name)
    avail_reasons = [c for c in reason_cols if c in df.columns]
    for row in df.iter_rows(named=True):
        gid = str(row.get("id") or "")
        reasons = [r for col in avail_reasons for r in (row.get(col) or [])]
        desc = "; ".join(reasons) or "Failed openBIM audit gate"
        th = bcf.add_topic(title=f"[{row.get("class", "Element")}] {row.get("name") or gid}", description=desc, author=author, topic_type="Clash" if "geometry" in desc.lower() else "Error")
        bbox = row.get("bbox")
        if isinstance(bbox, dict) and all(bbox.get(k) is not None for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")):
            cx, cy, cz = (bbox["xmin"] + bbox["xmax"]) / 2.0, (bbox["ymin"] + bbox["ymax"]) / 2.0, (bbox["zmin"] + bbox["zmax"]) / 2.0
            span = max(abs(bbox["xmax"] - bbox["xmin"]), abs(bbox["ymax"] - bbox["ymin"]), abs(bbox["zmax"] - bbox["zmin"]), 1.0)
            dist = span * 2.0
            cam = PerspectiveCamera(
                camera_view_point=Point(x=cx - dist, y=cy - dist, z=cz + dist),
                camera_direction=Direction(x=0.57735, y=0.57735, z=-0.57735),
                camera_up_vector=Direction(x=0.40825, y=0.40825, z=0.81650),
                field_of_view=60.0,
            )
            comps = Components(selection=ComponentSelection(component=[Component(ifc_guid=gid)]), visibility=ComponentVisibility(default_visibility=True), view_setup_hints=ViewSetupHints(spaces_visible=False, space_boundaries_visible=False, openings_visible=False)) if gid else None
            vis = VisualizationInfo(guid=str(uuid.uuid4()), components=comps, perspective_camera=cam)
            th.add_visinfo_handler(VisualizationInfoHandler(visualization_info=vis, xml_handler=bcf._xml_handler))
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    bcf.save(str(dest))
    return dest
