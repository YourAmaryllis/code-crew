"""Convert OTM YAML threat models to tool-specific output formats.

Supported targets:
  threat-dragon  — OWASP Threat Dragon v2 JSON (version 2.6.2)
  irius-risk     — via StartLeft CLI (startleft parse --type OTM --output-type IRIUSRISK)
  microsoft-tmmt — not yet supported
"""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore[assignment]

TD_VERSION = "2.6.2"

# STRIDE category normalisation: lower-no-spaces → canonical Threat Dragon label
_STRIDE_LABELS: dict[str, tuple[str, str]] = {
    "spoofing":              ("Spoofing",              "STRIDE"),
    "tampering":             ("Tampering",              "STRIDE"),
    "repudiation":           ("Repudiation",            "STRIDE"),
    "informationdisclosure": ("Information disclosure", "STRIDE"),
    "denialofservice":       ("Denial of service",      "STRIDE"),
    "dos":                   ("Denial of service",      "STRIDE"),
    "elevationofprivilege":  ("Elevation of privilege", "STRIDE"),
}


# ── helpers ─────────────────────────────────────────────────────────────────

def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-") or "item"


def _new_id() -> str:
    return str(uuid.uuid4())


def _risk_score(value: Any, default: int = 50) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return 100 if value else 0
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    if isinstance(value, str):
        word = value.strip().upper()
        mapping = {"HIGH": 100, "CRITICAL": 100, "MEDIUM": 50, "LOW": 10, "NONE": 0}
        if word in mapping:
            return mapping[word]
    return default


def _severity(risk: dict[str, Any]) -> str:
    score = _risk_score(risk.get("impact"), default=50)
    if score >= 80:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _stride_type(categories: list[str]) -> tuple[str, str]:
    for cat in categories:
        key = re.sub(r"[^a-zA-Z]", "", cat).lower()
        if key in _STRIDE_LABELS:
            return _STRIDE_LABELS[key]
    # Non-STRIDE category (PLOT4ai, LINDDUN, DIE …) — use the raw name
    if categories:
        return categories[0].strip(), "Generic"
    return "Threat", "Generic"


def _ports() -> dict[str, Any]:
    sides = ("top", "right", "bottom", "left")
    groups = {
        s: {
            "position": s,
            "attrs": {
                "circle": {
                    "r": 4, "magnet": True,
                    "stroke": "#5F95FF", "strokeWidth": 1,
                    "fill": "#fff", "style": {"visibility": "hidden"},
                }
            },
        }
        for s in sides
    }
    return {"groups": groups, "items": [{"group": s, "id": _new_id()} for s in sides]}


# ── cell builders ────────────────────────────────────────────────────────────

def _boundary_box(name: str, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    return {
        "position": {"x": x, "y": y},
        "size": {"width": width, "height": height},
        "attrs": {"label": {"text": name}},
        "visible": True,
        "shape": "trust-boundary-box",
        "id": _new_id(),
        "zIndex": -1,
        "data": {
            "type": "tm.BoundaryBox",
            "description": "",
            "isTrustBoundary": True,
            "hasOpenThreats": False,
        },
    }


def _component_cell(
    comp: dict[str, Any], x: int, y: int, threats: list[dict[str, Any]]
) -> dict[str, Any]:
    name = comp.get("name") or comp.get("id", "component")
    has_open = any(t.get("status") == "Open" for t in threats)
    ctype = (comp.get("type") or "service").lower()

    if ctype in ("actor", "external-entity", "external-service"):
        shape = "actor"
        size = {"width": 130, "height": 60}
        data_type = "tm.Actor"
        extra: dict[str, Any] = {"providesAuthentication": False}
    elif ctype in ("datastore", "database", "store", "queue"):
        shape = "store"
        size = {"width": 160, "height": 64}
        data_type = "tm.Store"
        extra = {"isALog": False, "storesCredentials": False, "isEncrypted": False}
    else:
        shape = "process"
        size = {"width": 150, "height": 80}
        data_type = "tm.Process"
        extra = {
            "handlesCardPayment": False,
            "handlesGoodsOrServices": False,
            "isWebApplication": ctype in ("service", "api", "lambda", "ecs-task"),
            "privilegeLevel": "",
        }

    return {
        "position": {"x": x, "y": y},
        "size": size,
        "attrs": {
            "text": {"text": name[:40]},
            "body": {"stroke": "#333333", "strokeWidth": 1.5, "strokeDasharray": ""},
        },
        "visible": True,
        "shape": shape,
        "ports": _ports(),
        "id": _new_id(),
        "zIndex": 2,
        "data": {
            "type": data_type,
            "name": name,
            "description": comp.get("description") or "",
            "outOfScope": False,
            "reasonOutOfScope": "",
            "hasOpenThreats": has_open,
            "threats": threats,
            **extra,
        },
    }


def _flow_cell(
    name: str,
    protocol: str,
    source_cell: dict[str, Any],
    target_cell: dict[str, Any],
    threats: list[dict[str, Any]],
) -> dict[str, Any] | None:
    src_ports = source_cell.get("ports", {}).get("items") or []
    tgt_ports = target_cell.get("ports", {}).get("items") or []
    if not src_ports or not tgt_ports:
        return None
    src_port, tgt_port = _directional_ports(source_cell, target_cell)
    encrypted = protocol.upper().startswith("HTTPS") or "TLS" in protocol.upper() or "MTLS" in protocol.upper()
    return {
        "shape": "flow",
        "zIndex": 10,
        "id": _new_id(),
        "connector": "smooth",
        "attrs": {
            "line": {
                "targetMarker": {"name": "block"},
                "sourceMarker": {"name": ""},
                "strokeDasharray": "",
            }
        },
        "source": {"cell": source_cell["id"], "port": src_ports[src_port]["id"]},
        "target": {"cell": target_cell["id"], "port": tgt_ports[tgt_port]["id"]},
        "labels": [{"attrs": {"label": {"text": name[:48]}}}],
        "data": {
            "type": "tm.Flow",
            "name": name,
            "description": protocol,
            "outOfScope": False,
            "reasonOutOfScope": "",
            "hasOpenThreats": any(t.get("status") == "Open" for t in threats),
            "isBidirectional": False,
            "isEncrypted": encrypted,
            "isPublicNetwork": False,
            "protocol": protocol,
            "threats": threats,
        },
    }


# ── threat builder ───────────────────────────────────────────────────────────

def _td_threat(
    threat: dict[str, Any],
    mitigations_by_id: dict[str, dict[str, Any]],
    links: list[dict[str, str]],
) -> dict[str, Any]:
    categories = threat.get("categories") or []
    threat_type, model_type = _stride_type(categories)
    mitigation_texts: list[str] = []
    implemented = False
    for link in links:
        m = mitigations_by_id.get(link.get("mitigation", ""))
        if m:
            text = m.get("description") or m.get("name") or ""
            if text:
                mitigation_texts.append(text)
            if link.get("state") == "implemented":
                implemented = True
    return {
        "id": _new_id(),
        "title": threat.get("name") or threat.get("id") or "Threat",
        "description": threat.get("description") or "",
        "type": threat_type,
        "modelType": model_type,
        "severity": _severity(threat.get("risk") or {}),
        "status": "Mitigated" if implemented else "Open",
        "mitigation": "\n\n".join(mitigation_texts),
    }


# ── layout ───────────────────────────────────────────────────────────────────

def _cell_center(cell: dict[str, Any]) -> tuple[float, float]:
    pos = cell.get("position", {})
    size = cell.get("size", {})
    return (
        pos.get("x", 0) + size.get("width", 0) / 2,
        pos.get("y", 0) + size.get("height", 0) / 2,
    )


def _directional_ports(src_cell: dict[str, Any], tgt_cell: dict[str, Any]) -> tuple[int, int]:
    """Choose source/target port indices based on relative node positions.

    Port order in _ports(): 0=top, 1=right, 2=bottom, 3=left.
    Picks the pair that keeps the connector on the natural side of each node.
    """
    sx, sy = _cell_center(src_cell)
    tx, ty = _cell_center(tgt_cell)
    dx, dy = tx - sx, ty - sy
    if abs(dx) >= abs(dy):
        return (1, 3) if dx >= 0 else (3, 1)  # horizontal: right→left or left→right
    else:
        return (2, 0) if dy >= 0 else (0, 2)  # vertical: bottom→top or top→bottom


def _graphviz_positions(
    components: list[dict[str, Any]],
    trust_zones: list[dict[str, Any]],
    dataflows: list[dict[str, Any]],
    comp_lookup: dict[str, str],
    canvas_w: int = 1400,
    canvas_h: int = 900,
) -> dict[str, tuple[int, int]]:
    """Compute node positions via graphviz dot layout.

    Returns {comp_id: (x, y)} using the graphviz binary found on PATH.
    Returns {} if graphviz or pygraphviz is unavailable.
    """
    import shutil
    if not shutil.which("dot"):
        return {}
    try:
        import pygraphviz as pgv
    except ImportError:
        return {}

    G = pgv.AGraph(directed=True, strict=False)
    G.graph_attr.update(
        rankdir="LR",
        splines="ortho",
        nodesep="0.6",
        ranksep="1.2",
        compound="true",
    )
    # Use fixed-size nodes; graphviz dimensions are in inches at 72 dpi
    G.node_attr.update(shape="box", width="2.2", height="1.0", fixedsize="true", fontsize="10")

    # Group components by trust zone for cluster subgraphs
    zone_comps: dict[str, list[str]] = {}
    for comp in components:
        parent = comp.get("parent") or {}
        zone_id = parent.get("trustZone") or (trust_zones[0]["id"] if trust_zones else "private")
        zone_comps.setdefault(zone_id, []).append(comp["id"])

    for zone in trust_zones:
        zone_id = zone["id"]
        members = zone_comps.get(zone_id, [])
        if not members:
            continue
        sub = G.add_subgraph(
            members,
            name=f"cluster_{zone_id}",
            label=zone.get("name", zone_id),
            style="rounded",
        )
        for comp_id in members:
            comp = next((c for c in components if c["id"] == comp_id), None)
            label = (comp.get("name", comp_id) if comp else comp_id)[:24]
            sub.add_node(comp_id, label=label)

    # Add any nodes not yet in the graph
    for comp in components:
        if not G.has_node(comp["id"]):
            G.add_node(comp["id"], label=comp.get("name", comp["id"])[:24])

    # Add dataflow edges
    for flow in dataflows:
        src = _resolve(flow.get("source"), comp_lookup)
        dst = _resolve(flow.get("destination") or flow.get("target"), comp_lookup)
        if src and dst and src != dst:
            G.add_edge(src, dst)

    G.layout(prog="dot")

    # Extract positions; graphviz uses pts with origin at bottom-left
    raw: list[tuple[str, float, float]] = []
    for node in G.nodes():
        pos_str = node.attr.get("pos", "")
        if not pos_str:
            continue
        try:
            gx, gy = map(float, pos_str.split(","))
            raw.append((str(node), gx, gy))
        except ValueError:
            continue

    if not raw:
        return {}

    xs = [r[1] for r in raw]
    ys = [r[2] for r in raw]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    rx = max_x - min_x or 1.0
    ry = max_y - min_y or 1.0
    pad = 120

    result: dict[str, tuple[int, int]] = {}
    for node_id, gx, gy in raw:
        px = pad + int((gx - min_x) / rx * (canvas_w - 2 * pad))
        # Flip y: graphviz y increases upward, screen y increases downward
        py = pad + int((1.0 - (gy - min_y) / ry) * (canvas_h - 2 * pad))
        result[node_id] = (px, py)

    return result


def _layout(
    components: list[dict[str, Any]],
    trust_zones: list[dict[str, Any]],
    threat_instances: dict[str, list[dict[str, Any]]],
    dataflows: list[dict[str, Any]] | None = None,
    comp_lookup: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    zone_order = [z["id"] for z in trust_zones]
    zone_name = {z["id"]: z.get("name", z["id"]) for z in trust_zones}
    grouped: dict[str, list[dict[str, Any]]] = {z: [] for z in zone_order}
    default_zone = zone_order[0] if zone_order else "private"

    for comp in components:
        parent = comp.get("parent") or {}
        zone_id = parent.get("trustZone") or default_zone
        grouped.setdefault(zone_id, []).append(comp)

    # Try graphviz layout; fall back to grid if unavailable
    gv_pos = _graphviz_positions(
        components, trust_zones,
        dataflows or [], comp_lookup or {},
    ) if dataflows is not None else {}

    cells: list[dict[str, Any]] = []
    cell_by_id: dict[str, dict[str, Any]] = {}

    if gv_pos:
        # ── graphviz path: place nodes at computed positions, draw zone boxes ──
        zone_pad = 40
        for zone_id in zone_order:
            comps = grouped.get(zone_id) or []
            if not comps:
                continue
            positions = [gv_pos.get(c["id"], (200, 200)) for c in comps]
            min_x = min(p[0] for p in positions) - zone_pad
            min_y = min(p[1] for p in positions) - zone_pad
            max_x = max(p[0] for p in positions) + zone_pad + 160  # comp width
            max_y = max(p[1] for p in positions) + zone_pad + 80   # comp height
            cells.append(_boundary_box(
                zone_name.get(zone_id, zone_id),
                min_x, min_y,
                max_x - min_x, max_y - min_y,
            ))
            for comp in comps:
                x, y = gv_pos.get(comp["id"], (200, 200))
                cell = _component_cell(comp, x, y, threat_instances.get(comp["id"], []))
                cells.append(cell)
                cell_by_id[comp["id"]] = cell
    else:
        # ── grid fallback ─────────────────────────────────────────────────────
        x_offset = 40
        cols, col_w, row_h, pad, gap = 3, 200, 120, 40, 80

        for zone_id in zone_order:
            comps = grouped.get(zone_id) or []
            if not comps:
                continue
            rows = (len(comps) + cols - 1) // cols
            box_w = pad * 2 + cols * col_w
            box_h = pad * 2 + rows * row_h
            cells.append(_boundary_box(zone_name.get(zone_id, zone_id), x_offset, 40, box_w, box_h))
            for i, comp in enumerate(comps):
                x = x_offset + pad + (i % cols) * col_w
                y = 40 + pad + (i // cols) * row_h
                cell = _component_cell(comp, x, y, threat_instances.get(comp["id"], []))
                cells.append(cell)
                cell_by_id[comp["id"]] = cell
            x_offset += box_w + gap

    return cells, cell_by_id


# ── ref resolution ───────────────────────────────────────────────────────────

def _build_lookup(*items_lists: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for items in items_lists:
        for item in items:
            item_id = item.get("id") or ""
            name = item.get("name") or ""
            lookup[item_id] = item_id
            if name:
                lookup[name] = item_id
                lookup[_slug(name)] = item_id
    return lookup


def _resolve(value: Any, lookup: dict[str, str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("component") or value.get("id") or value.get("name")
    text = str(value).strip()
    return lookup.get(text) or lookup.get(_slug(text))


# ── normalisation helpers ────────────────────────────────────────────────────

def _norm_trustzone(zone: dict[str, Any]) -> dict[str, Any]:
    z = deepcopy(zone)
    name = str(z.get("name") or z.get("id") or "trust-zone")
    z.setdefault("id", _slug(name))
    z.setdefault("name", name)
    # normalise rating / trustRating
    if "rating" in z and "risk" not in z:
        z["risk"] = {"trustRating": _risk_score(z.pop("rating"), default=50)}
    elif isinstance(z.get("risk"), dict):
        r = z["risk"]
        if "rating" in r:
            r["trustRating"] = _risk_score(r.pop("rating"), default=50)
    return z


def _norm_component(comp: dict[str, Any], tz_ids: set[str]) -> dict[str, Any]:
    c = deepcopy(comp)
    name = str(c.get("name") or c.get("id") or "component")
    c.setdefault("id", _slug(name))
    c.setdefault("name", name)
    c.setdefault("type", "service")
    parent = c.get("parent")
    if isinstance(parent, str):
        c["parent"] = {"trustZone": parent}
    elif not isinstance(parent, dict) or "trustZone" not in parent:
        c["parent"] = {"trustZone": next(iter(tz_ids), "private")}
    return c


# ── main converter ───────────────────────────────────────────────────────────

def otm_to_threat_dragon(otm_path: Path, output_path: Path) -> None:
    """Read an OTM YAML file and write a Threat Dragon v2 JSON file."""
    if _yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")

    raw = _yaml.safe_load(otm_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{otm_path} did not parse to a YAML mapping")

    project = raw.get("project") or {}
    proj_name = project.get("name") or otm_path.stem

    trust_zones = [_norm_trustzone(z) for z in (raw.get("trustZones") or raw.get("trustzones") or [])]
    if not trust_zones:
        trust_zones = [{"id": "private", "name": "Private", "risk": {"trustRating": 75}}]
    tz_ids = {z["id"] for z in trust_zones}

    raw_comps = raw.get("components") or []
    components = [_norm_component(c, tz_ids) for c in raw_comps]

    threats_raw = raw.get("threats") or []
    mitigations_raw = raw.get("mitigations") or []
    dataflows_raw = raw.get("dataflows") or []

    comp_lookup = _build_lookup(components)
    threat_lookup = _build_lookup(threats_raw)
    mit_lookup = {m.get("id", ""): m for m in mitigations_raw}

    # Build mitigation links per threat
    mit_links_by_threat: dict[str, list[dict[str, str]]] = {}
    for m in mitigations_raw:
        linked = m.get("mitigatedThreats") or m.get("targetedThreats") or []
        for ref in linked:
            tid = _resolve(ref, threat_lookup) or _slug(str(ref))
            mit_links_by_threat.setdefault(tid, []).append(
                {"mitigation": m.get("id", ""), "state": str(m.get("state") or "required")}
            )

    # Build per-component threat instances
    comp_threat_instances: dict[str, list[dict[str, Any]]] = {}
    for threat in threats_raw:
        tid = threat.get("id", "")
        links = mit_links_by_threat.get(tid, [])
        td = _td_threat(threat, mit_lookup, links)
        for target in threat.get("targetedComponents") or []:
            cid = _resolve(target, comp_lookup)
            if cid:
                comp_threat_instances.setdefault(cid, []).append(deepcopy(td))

    # Layout diagram cells
    cells, cell_by_id = _layout(
        components, trust_zones, comp_threat_instances,
        dataflows=dataflows_raw, comp_lookup=comp_lookup,
    )

    # Add synthetic components referenced in dataflows but missing from components
    for flow in dataflows_raw:
        for ref_key in ("source", "destination", "target"):
            ref = flow.get(ref_key)
            if ref is None:
                continue
            cid = _resolve(ref, comp_lookup)
            if cid and cid not in cell_by_id:
                synth = {
                    "id": cid,
                    "name": str(ref) if isinstance(ref, str) else cid,
                    "type": "external-entity",
                    "description": "External entity",
                    "parent": {"trustZone": "internet" if "internet" in tz_ids else next(iter(tz_ids), "private")},
                }
                cell = _component_cell(synth, 40, 40, [])
                cells.append(cell)
                cell_by_id[cid] = cell

    # Add flow cells
    for flow in dataflows_raw:
        src_id = _resolve(flow.get("source"), comp_lookup)
        dst_id = _resolve(flow.get("destination") or flow.get("target"), comp_lookup)
        if not src_id or not dst_id:
            continue
        src_cell = cell_by_id.get(src_id)
        dst_cell = cell_by_id.get(dst_id)
        if not src_cell or not dst_cell:
            continue
        attrs = flow.get("attributes") or {}
        protocol = attrs.get("protocol") or str(flow.get("protocol") or flow.get("name") or "")
        flow_cell = _flow_cell(
            flow.get("name") or flow.get("id", "flow"),
            protocol,
            src_cell,
            dst_cell,
            [],
        )
        if flow_cell:
            cells.append(flow_cell)

    # Diagram type from representations
    reps = raw.get("representations") or []
    diag_rep = next((r for r in reps if r.get("type") == "diagram"), None)
    diag_type = ((diag_rep or {}).get("attributes") or {}).get("diagramType") or "STRIDE"

    td_model = {
        "version": TD_VERSION,
        "otmVersion": str(raw.get("otmVersion") or "0.2.0"),
        "summary": {
            "title": proj_name,
            "owner": project.get("owner") or "",
            "ownerContact": project.get("ownerContact") or "",
            "description": project.get("description") or "",
            "id": project.get("id") or _slug(proj_name),
        },
        "detail": {
            "contributors": [],
            "diagrams": [
                {
                    "id": 0,
                    "title": (diag_rep or {}).get("name") or "Architecture Diagram",
                    "diagramType": diag_type,
                    "placeholder": f"New {diag_type} diagram description",
                    "thumbnail": f"./public/content/images/thumbnail.{diag_type.lower()}.jpg",
                    "version": TD_VERSION,
                    "cells": cells,
                }
            ],
            "diagramTop": 1,
            "reviewer": "",
            "threatTop": len(threats_raw),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(td_model, indent=2) + "\n", encoding="utf-8")
