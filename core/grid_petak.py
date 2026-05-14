# -*- coding: utf-8 -*-
"""
core/grid_petak.py

Generate a planting block grid layer (fishnet polygons).
Each cell represents one planting block aligned to row/column spacing.

Output layer attributes:
    block_id  : sequential block number
    row       : row number
    col       : column number
    area_m2   : cell area in m²
    status    : "inside" | "edge" (relative to field polygon)

CacaoPlanter — Open Source QGIS Plugin
License: GPL-2.0-or-later
"""

import math
from typing import Optional

from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsVectorLayer,
    QgsFillSymbol,
)
from qgis.PyQt.QtCore import QVariant


class GridBlockBuilder:
    """
    Generate a polygon grid layer aligned to planting row/column spacing.

    Each cell = one planting block of size dx × dy (or dx × dy_eff for
    triangular pattern where dy_eff = dy × sin 60°).

    Usage::
        builder = GridBlockBuilder(crs_epsg=32750)
        layer   = builder.build_grid(field_geom, dx, dy, pattern="square")
    """

    def __init__(self, crs_epsg: int = 32750):
        self.crs_epsg = crs_epsg

    def build_grid(self,
                   field_geom:   QgsGeometry,
                   dx_native:    float,
                   dy_native:    float,
                   pattern:      str = "square",
                   layer_name:   str = "Planting Block Grid") -> QgsVectorLayer:
        """
        Args:
            field_geom  : polygon boundary (in native CRS units)
            dx_native   : cell width in native CRS units
            dy_native   : cell height in native CRS units
            pattern     : "square" | "triangular"
            layer_name  : output layer name
        Returns:
            QgsVectorLayer of polygon grid cells
        """
        layer = self._init_layer(layer_name)
        dp    = layer.dataProvider()

        bbox  = field_geom.boundingBox()
        x0, x1 = bbox.xMinimum(), bbox.xMaximum()
        y0, y1 = bbox.yMinimum(), bbox.yMaximum()

        dy_eff = (dy_native * math.sin(math.radians(60))
                  if pattern in ("triangular", "segitiga") else dy_native)

        feats    = []
        block_id = 1
        row      = 1
        y        = y0

        while y < y1:
            col     = 1
            x_start = (x0 + dx_native / 2.0
                       if pattern in ("triangular", "segitiga") and row % 2 == 0
                       else x0)
            x = x_start

            while x < x1 + dx_native:
                ring = [
                    QgsPointXY(x,            y),
                    QgsPointXY(x + dx_native, y),
                    QgsPointXY(x + dx_native, y + dy_eff),
                    QgsPointXY(x,             y + dy_eff),
                    QgsPointXY(x,             y),
                ]
                cell_geom = QgsGeometry.fromPolygonXY([ring])

                if field_geom.intersects(cell_geom):
                    clipped = cell_geom.intersection(field_geom)
                    if clipped and not clipped.isEmpty():
                        status = "inside" if field_geom.contains(cell_geom) else "edge"
                        feat   = QgsFeature(layer.fields())
                        feat.setGeometry(cell_geom)
                        feat.setAttributes([
                            block_id, row, col,
                            round(cell_geom.area(), 2), status,
                        ])
                        feats.append(feat)
                        block_id += 1

                x   += dx_native
                col += 1

            y   += dy_eff
            row += 1

        dp.addFeatures(feats)
        layer.updateExtents()
        self._apply_style(layer)
        return layer

    # backward-compatible alias
    def buat_grid(self, lahan_geom, dx_native, dy_native,
                  pola="segi_empat", nama_layer="Planting Block Grid"):
        pattern = "triangular" if pola == "segitiga" else "square"
        return self.build_grid(lahan_geom, dx_native, dy_native,
                                pattern, nama_layer)

    def _init_layer(self, name: str) -> QgsVectorLayer:
        layer = QgsVectorLayer(
            f"Polygon?crs=EPSG:{self.crs_epsg}", name, "memory"
        )
        dp   = layer.dataProvider()
        flds = QgsFields()
        for nm, tp in [
            ("block_id", QVariant.Int),
            ("row",      QVariant.Int),
            ("col",      QVariant.Int),
            ("area_m2",  QVariant.Double),
            ("status",   QVariant.String),
        ]:
            flds.append(QgsField(nm, tp))
        dp.addAttributes(flds)
        layer.updateFields()
        return layer

    def _apply_style(self, layer: QgsVectorLayer):
        sym = QgsFillSymbol.createSimple({
            "color":         "255,220,0,0",
            "outline_color": "#DAA520",
            "outline_width": "0.35",
            "outline_style": "dash",
        })
        layer.renderer().setSymbol(sym)
        layer.triggerRepaint()


# backward-compatible alias for old import names
GridPetakBuilder = GridBlockBuilder
