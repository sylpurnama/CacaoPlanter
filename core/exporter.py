# -*- coding: utf-8 -*-
"""
core/exporter.py

Export planting point layers to multiple formats:
    - Shapefile  (.shp)
    - GeoPackage (.gpkg)
    - KML        (.kml)  — field use / Google Earth
    - DXF        (.dxf)  — AutoCAD / survey software

CacaoPlanter — Open Source QGIS Plugin
License: GPL-2.0-or-later
"""

import os
from datetime import datetime
from typing import Optional

from qgis.core import (
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsProject,
)


class Exporter:
    """
    Export planting result layers to various file formats.

    Example::
        exporter = Exporter(output_dir="/home/user/cacao_output")
        exporter.export_shapefile(cacao_layer, "BlockA_Cacao")
        exporter.export_kml(cacao_layer,       "BlockA_Cacao")
    """

    FORMAT_MAP = {
        "shapefile":  ("ESRI Shapefile", ".shp"),
        "geopackage": ("GPKG",           ".gpkg"),
        "kml":        ("KML",            ".kml"),
        "dxf":        ("DXF",            ".dxf"),
    }

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_shapefile(self, layer: QgsVectorLayer,
                          file_name: str, crs_epsg: int = 4326) -> str:
        return self._export(layer, file_name, "shapefile", crs_epsg)

    def export_geopackage(self, layer: QgsVectorLayer,
                           file_name: str, crs_epsg: int = 4326) -> str:
        return self._export(layer, file_name, "geopackage", crs_epsg)

    def export_kml(self, layer: QgsVectorLayer, file_name: str) -> str:
        return self._export(layer, file_name, "kml", crs_epsg=4326)

    def export_dxf(self, layer: QgsVectorLayer,
                    file_name: str, crs_epsg: int = 4326) -> str:
        return self._export(layer, file_name, "dxf", crs_epsg)

    def export_semua(self,
                      layer_kakao:    QgsVectorLayer,
                      layer_penaung:  Optional[QgsVectorLayer],
                      layer_excluded: Optional[QgsVectorLayer],
                      nama_proyek:    str,
                      formats:        list) -> dict:
        """Export all layers in the selected formats."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        hasil     = {}

        pairs = [
            (layer_kakao,    f"{nama_proyek}_Cacao_{timestamp}"),
            (layer_penaung,  f"{nama_proyek}_Shade_{timestamp}"),
            (layer_excluded, f"{nama_proyek}_Excluded_{timestamp}"),
        ]

        for layer, file_name in pairs:
            if layer is None:
                continue
            paths = []
            for fmt in formats:
                try:
                    paths.append(self._export(layer, file_name, fmt))
                except Exception as e:
                    paths.append(f"[ERROR] {fmt}: {e}")
            hasil[file_name] = paths

        return hasil

    def _export(self, layer: QgsVectorLayer,
                 file_name: str, format_key: str,
                 crs_epsg: int = 4326) -> str:
        if format_key not in self.FORMAT_MAP:
            raise ValueError(
                f"Unknown format '{format_key}'. "
                f"Options: {list(self.FORMAT_MAP.keys())}"
            )

        driver, ext  = self.FORMAT_MAP[format_key]
        output_path  = os.path.join(self.output_dir, file_name + ext)

        options               = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName    = driver
        options.fileEncoding  = "UTF-8"

        if format_key == "kml":
            options.datasourceOptions = ["NameField=type"]
        elif format_key == "dxf":
            options.datasourceOptions = ["HEADER_STRING=CacaoPlanter"]

        error, error_msg = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, output_path,
            QgsCoordinateTransformContext(), options,
        )

        if error != QgsVectorFileWriter.NoError:
            raise RuntimeError(
                f"Export to {format_key} failed: {error_msg}\nPath: {output_path}"
            )

        return output_path
