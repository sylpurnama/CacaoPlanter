# -*- coding: utf-8 -*-
"""
core/planting_engine.py  —  v1.5

CacaoPlanter — Open Source QGIS Plugin
License: GPL-2.0-or-later
Repository: https://github.com/sylpurnama/CacaoPlanter

Performance notes (v1.3+):
  - Grid generation   : numpy meshgrid — ~50-100x faster than Python while-loop
  - Polygon clip      : prepareGeometry() once, batch 50k points
  - Slope filter      : provider.block() reads entire DEM once, Sobel kernel
                        on numpy array, O(1) lookup per point; fallback to
                        identify() only for DEM > 50 MP
  - Layer building    : addFeatures() bulk insert — 1 commit instead of N
  - Shade tree layout : numpy array slice [::ratio] — O(1)
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from qgis.core import (
    QgsPoint,
    QgsPointXY,
    QgsGeometry,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsRaster,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsMarkerSymbol,
    QgsDistanceArea,
    QgsProject,
    QgsUnitTypes,
    QgsTask,
)
from qgis.PyQt.QtCore import QVariant

log = logging.getLogger("CacaoPlanter")

# ---------------------------------------------------------------------------
# Constants  (names kept backward-compatible with v1.4 dialog getters)
# ---------------------------------------------------------------------------

RASTER_TYPE_OPTIONS = [
    ("dtm_drone", "DTM Drone — ground surface (Metashape / ODM / Pix4D)"),
    ("dsm_drone", "DSM Drone — top-of-canopy / building surface"),
    ("ortofoto_rgb", "RGB Ortophoto — visual basemap (slope skipped)"),
    ("ortofoto_ms", "Multispectral Ortophoto — basemap (slope skipped)"),
    ("srtm", "SRTM 30m — public DEM"),
    ("lidar_dtm", "LiDAR DTM — high-precision ground surface"),
    ("dem_other", "Other DEM / elevation raster"),
]

# Legacy alias so old code using RASTER_TIPE_OPTIONS still works
RASTER_TIPE_OPTIONS = RASTER_TYPE_OPTIONS

BASEMAP_TYPE_KEYS = {"ortofoto_rgb", "ortofoto_ms"}
# Legacy alias
BASEMAP_TIPE_KEYS = BASEMAP_TYPE_KEYS

SHADE_TREE_OPTIONS = [
    "Gliricidia (Gliricidia sepium)",
    "Leucaena (Leucaena leucocephala)",
    "Coconut (Cocos nucifera)",
    "Coral tree (Erythrina subumbrans)",
    "Falcata (Falcataria moluccana)",
    "Banana (Musa spp.)",
    "Custom (enter manually)…",
]

# Legacy alias
JENIS_PENAUNG_OPTIONS = SHADE_TREE_OPTIONS


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RasterInputInfo:
    tipe_key: str = "dtm_drone"
    band_elevasi: int = 1
    adalah_basemap: bool = False

    def __post_init__(self):
        self.adalah_basemap = self.tipe_key in BASEMAP_TYPE_KEYS


@dataclass
class PlantingConfig:
    pola: str = "segitiga"
    jarak_baris: float = 3.0
    jarak_kolom: float = 3.0

    penaung_aktif: bool = True
    penaung_jenis: str = SHADE_TREE_OPTIONS[0]
    penaung_rasio: int = 3
    penaung_buffer: float = 2.0

    slope_maks: float = 25.0
    raster_dem_info: Optional[RasterInputInfo] = None
    output_crs_epsg: int = 32750


@dataclass
class PlantingResult:
    titik_kakao: List[QgsPointXY] = field(default_factory=list)
    titik_penaung: List[QgsPointXY] = field(default_factory=list)
    titik_excluded: List[QgsPointXY] = field(default_factory=list)

    luas_ha: float = 0.0
    jumlah_kakao: int = 0
    jumlah_penaung: int = 0
    jumlah_excluded: int = 0
    kepadatan_kakao_per_ha: float = 0.0
    kepadatan_penaung_per_ha: float = 0.0

    crs_epsg_hasil: int = 32750
    slope_dianalisis: bool = False
    raster_sumber: str = "-"
    pesan: str = ""
    debug_info: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PlantingEngine:
    """
    Main planting point generation engine.

    Public API (backward-compatible with v1.2+):
        result = PlantingEngine(config).run(
            polygon_geom, polygon_crs, dem_layer, task=None
        )
    """

    _MAX_PIXEL_BLOCK = 50_000_000
    _BATCH_CONTAINS = 50_000

    def __init__(self, config: PlantingConfig):
        self.cfg = config

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self,
            polygon_geom: QgsGeometry,
            polygon_crs: QgsCoordinateReferenceSystem,
            dem_layer: Optional[QgsRasterLayer] = None,
            task: Optional[QgsTask] = None) -> PlantingResult:

        result = PlantingResult()

        dx_native, dy_native = self._meter_to_native(
            self.cfg.jarak_kolom, self.cfg.jarak_baris,
            polygon_geom, polygon_crs
        )
        log.debug(
            f"CRS: {polygon_crs.authid()} "
            f"dx={dx_native:.6f}  dy={dy_native:.6f}"
        )

        da = QgsDistanceArea()
        da.setSourceCrs(polygon_crs, QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())
        result.luas_ha = da.measureArea(polygon_geom) / 10_000.0

        # 1. Grid (numpy)
        candidate_arr = self._generate_grid(polygon_geom, dx_native, dy_native)
        log.debug(f"Grid candidates: {len(candidate_arr)}")

        if task and task.isCanceled():
            return result

        # 2. Clip to polygon
        inside_arr = self._clip_to_polygon(polygon_geom, candidate_arr, task)
        log.debug(f"Inside polygon: {len(inside_arr)}")

        result.debug_info = (
            f"CRS: {polygon_crs.authid()} | "
            f"dx={dx_native:.5f} dy={dy_native:.5f} | "
            f"candidates={len(candidate_arr)} inside={len(inside_arr)}"
        )

        if task and task.isCanceled():
            return result

        # 3. Slope filter
        ri = self.cfg.raster_dem_info
        has_dem = dem_layer is not None and dem_layer.isValid()
        use_dem = has_dem and ri is not None and not ri.adalah_basemap

        if use_dem:
            ok_arr, excl_arr = self._filter_slope(
                inside_arr, dem_layer, ri, polygon_crs, task
            )
            result.titik_excluded = [QgsPointXY(x, y) for x, y in excl_arr]
            result.jumlah_excluded = len(excl_arr)
            result.slope_dianalisis = True
            result.raster_sumber = dict(RASTER_TYPE_OPTIONS).get(
                ri.tipe_key, ri.tipe_key)
        else:
            ok_arr = inside_arr
            if ri and ri.adalah_basemap:
                result.raster_sumber = (
                    "Ortophoto/basemap (slope analysis skipped)"
                )

        if task and task.isCanceled():
            return result

        # 4. Store cacao points
        result.titik_kakao = [QgsPointXY(x, y) for x, y in ok_arr]
        result.jumlah_kakao = len(result.titik_kakao)

        # 5. Shade trees
        if self.cfg.penaung_aktif and len(ok_arr) > 0:
            result.titik_penaung = self._place_shade(ok_arr)
            result.jumlah_penaung = len(result.titik_penaung)

        # 6. Density
        if result.luas_ha > 0:
            result.kepadatan_kakao_per_ha = round(
                result.jumlah_kakao / result.luas_ha, 1)
            result.kepadatan_penaung_per_ha = round(
                result.jumlah_penaung / result.luas_ha, 1)

        # 7. Output CRS
        auth = polygon_crs.authid()
        result.crs_epsg_hasil = (
            int(auth.split(":")[1]
                ) if ":" in auth else self.cfg.output_crs_epsg
        )

        result.pesan = self._build_message(result)
        return result

    # ------------------------------------------------------------------
    # Step 1: numpy grid
    # ------------------------------------------------------------------

    def _generate_grid(self, geom: QgsGeometry,
                       dx: float, dy: float) -> np.ndarray:
        bbox = geom.boundingBox()
        x0, x1 = bbox.xMinimum(), bbox.xMaximum()
        y0, y1 = bbox.yMinimum(), bbox.yMaximum()

        if self.cfg.pola == "segitiga":
            dy_eff = dy * math.sin(math.radians(60))
            ys = np.arange(y0, y1 + dy_eff * 0.01, dy_eff)
            parts = []
            for j, y in enumerate(ys):
                offset = (dx / 2.0) if (j % 2 == 1) else 0.0
                xs = np.arange(x0 + offset, x1 + dx * 0.01, dx)
                parts.append(np.column_stack([xs, np.full(len(xs), y)]))
            return np.vstack(parts) if parts else np.empty((0, 2))
        else:
            xs = np.arange(x0, x1 + dx * 0.01, dx)
            ys = np.arange(y0, y1 + dy * 0.01, dy)
            XX, YY = np.meshgrid(xs, ys)
            return np.column_stack([XX.ravel(), YY.ravel()])

    # ------------------------------------------------------------------
    # Step 2: clip to polygon
    # ------------------------------------------------------------------

    def _clip_to_polygon(self, geom: QgsGeometry,
                         pts: np.ndarray,
                         task: Optional[QgsTask]) -> np.ndarray:
        # QgsGeometry.createGeometryEngine() provides prepared geometry
        # compatible with all QGIS 3.x versions.
        # prepareGeometry() on QgsGeometry directly does not exist.
        engine = QgsGeometry.createGeometryEngine(geom.constGet())
        engine.prepareGeometry()

        inside = []
        n, B = len(pts), self._BATCH_CONTAINS

        for start in range(0, n, B):
            if task and task.isCanceled():
                break
            for x, y in pts[start: start + B]:
                if engine.contains(QgsPoint(x, y)):
                    inside.append((x, y))
            if task:
                task.setProgress(int(60 * min(start + B, n) / n))

        return np.array(inside) if inside else np.empty((0, 2))

    # ------------------------------------------------------------------
    # Step 3: slope filter
    # ------------------------------------------------------------------

    def _filter_slope(self, pts, dem_layer, ri, polygon_crs, task):
        provider = dem_layer.dataProvider()
        extent = dem_layer.extent()
        dem_crs = dem_layer.crs()
        w, h = dem_layer.width(), dem_layer.height()

        crs_valid = dem_crs.isValid() and polygon_crs.isValid()
        need_xform = crs_valid and dem_crs.authid() != polygon_crs.authid()
        xform = (
            QgsCoordinateTransform(polygon_crs, dem_crs,
                                   QgsCoordinateTransformContext())
            if need_xform else None
        )

        if w * h <= self._MAX_PIXEL_BLOCK:
            slope_arr, geo = self._read_slope_array(provider, extent, w, h)
            return self._classify_array(pts, slope_arr, geo, xform, task)
        else:
            log.warning(
                f"DEM too large ({w * h:,} px), "
                "using per-point identify() fallback"
            )
            return self._classify_identify(
                pts, provider, extent, ri.band_elevasi, xform, task
            )

    def _read_slope_array(self, provider, extent, w, h):
        block = provider.block(1, extent, w, h)
        dem = np.frombuffer(bytes(block.data()), dtype=np.float32) \
            .reshape(h, w).astype(np.float64)

        if provider.sourceHasNoDataValue(1):
            dem[dem == provider.sourceNoDataValue(1)] = np.nan

        cell_x = extent.width() / w
        cell_y = extent.height() / h
        pad = np.pad(dem, 1, mode="edge")
        dzdx = (pad[1:-1, 2:] - pad[1:-1, :-2]) / (2.0 * cell_x)
        dzdy = (pad[2:, 1:-1] - pad[:-2, 1:-1]) / (2.0 * cell_y)
        slope = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))
        slope[np.isnan(dem)] = np.nan

        geo = {
            "xmin": extent.xMinimum(), "ymax": extent.yMaximum(),
            "cell_x": cell_x, "cell_y": cell_y, "w": w, "h": h,
        }
        return slope, geo

    def _classify_array(self, pts, slope_arr, geo, xform, task):
        ok, exc = [], []
        n, B = len(pts), 10_000

        for start in range(0, n, B):
            if task and task.isCanceled():
                break
            for x, y in pts[start: start + B]:
                if xform:
                    pt = xform.transform(QgsPointXY(x, y))
                    px, py = pt.x(), pt.y()
                else:
                    px, py = x, y
                col = int((px - geo["xmin"]) / geo["cell_x"])
                row = int((geo["ymax"] - py) / geo["cell_y"])
                if not (0 <= col < geo["w"] and 0 <= row < geo["h"]):
                    exc.append((x, y))
                    continue
                s = slope_arr[row, col]
                if np.isnan(s) or s > self.cfg.slope_maks:
                    exc.append((x, y))
                else:
                    ok.append((x, y))
            if task:
                task.setProgress(60 + int(39 * min(start + B, n) / n))

        return (np.array(ok) if ok else np.empty((0, 2)),
                np.array(exc) if exc else np.empty((0, 2)))

    def _classify_identify(self, pts, provider, extent, band, xform, task):
        ok, exc = [], []
        n, B = len(pts), 5_000

        for start in range(0, n, B):
            if task and task.isCanceled():
                break
            for x, y in pts[start: start + B]:
                if xform:
                    pt = xform.transform(QgsPointXY(x, y))
                    px, py = pt.x(), pt.y()
                else:
                    px, py = x, y
                if not extent.contains(QgsPointXY(px, py)):
                    exc.append((x, y))
                    continue
                res = provider.identify(QgsPointXY(px, py),
                                        QgsRaster.IdentifyFormatValue)
                v = res.results().get(band) if res.isValid() else None
                (exc if v is None else ok).append((x, y))
            if task:
                task.setProgress(60 + int(39 * min(start + B, n) / n))

        return (np.array(ok) if ok else np.empty((0, 2)),
                np.array(exc) if exc else np.empty((0, 2)))

    # ------------------------------------------------------------------
    # Step 4: shade tree placement
    # ------------------------------------------------------------------

    def _place_shade(self, pts_arr: np.ndarray) -> List[QgsPointXY]:
        rasio = max(1, self.cfg.penaung_rasio)
        return [QgsPointXY(x, y) for x, y in pts_arr[::rasio]]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _meter_to_native(self, dx_m, dy_m, geom, crs):
        units = crs.mapUnits()
        if units == QgsUnitTypes.DistanceMeters:
            return dx_m, dy_m
        elif units == QgsUnitTypes.DistanceDegrees:
            center = geom.centroid().asPoint()
            lat_rad = math.radians(center.y())
            dx_deg = dx_m / (111_320.0 * math.cos(lat_rad))
            dy_deg = dy_m / 110_574.0
            return dx_deg, dy_deg
        else:
            f = QgsUnitTypes.fromUnitToUnitFactor(
                QgsUnitTypes.DistanceMeters, units
            )
            return dx_m * f, dy_m * f

    def _build_message(self, r: PlantingResult) -> str:
        cfg = self.cfg
        lines = [
            f"Field area         : {r.luas_ha:.4f} ha",
            f"Pattern            : {cfg.pola.replace('_', ' ').title()}",
            f"Spacing (row×col)  : {cfg.jarak_baris} × {cfg.jarak_kolom} m",
            f"Output CRS         : EPSG:{r.crs_epsg_hasil}",
            "",
            f"Cacao points       : "
            f"{r.jumlah_kakao:,}  ({r.kepadatan_kakao_per_ha}/ha)",
            f"Shade tree points  : "
            f"{r.jumlah_penaung:,}  ({r.kepadatan_penaung_per_ha}/ha)",
        ]
        if r.slope_dianalisis:
            lines += [
                f"Excluded points    : "
                f"{r.jumlah_excluded:,}  (slope > {cfg.slope_maks}%)",
                f"Elevation source   : {r.raster_sumber}",
            ]
        elif r.raster_sumber != "-":
            lines.append(f"Raster input       : {r.raster_sumber}")
        else:
            lines.append("Slope analysis     : not active")
        lines += ["", f"[DEBUG] {r.debug_info}"]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer builder  (bulk insert — 1 commit)
# ---------------------------------------------------------------------------

class LayerBuilder:
    COLORS = {"kakao": "#2D6A4F", "penaung": "#52B788", "excluded": "#E63946"}
    SIZES = {"kakao": 3.0, "penaung": 5.0, "excluded": 2.5}

    def __init__(self, crs_epsg: int = 32750):
        self.crs_epsg = crs_epsg

    def buat_layer_kakao(
            self, result: PlantingResult,
            nama: str = "Cacao Planting Points") -> QgsVectorLayer:
        return self._build(result.titik_kakao, nama, "kakao",
                           "Theobroma cacao", "OK", result.crs_epsg_hasil)

    def buat_layer_penaung(self, result: PlantingResult,
                           nama: str = "Shade Tree Points") -> QgsVectorLayer:
        return self._build(result.titik_penaung, nama, "penaung",
                           result.raster_sumber or "Shade tree", "Shade",
                           result.crs_epsg_hasil)

    def buat_layer_excluded(
            self, result: PlantingResult,
            nama: str = "Excluded Zones (Slope)") -> QgsVectorLayer:
        return self._build(result.titik_excluded, nama, "excluded",
                           "-", "Slope exceeded", result.crs_epsg_hasil)

    def _build(self, points, nama, ptype, species, status, crs_epsg):
        layer = QgsVectorLayer(f"Point?crs=EPSG:{crs_epsg}", nama, "memory")
        dp = layer.dataProvider()
        flds = QgsFields()
        for nm, tp in [
            ("id", QVariant.Int),
            ("type", QVariant.String),
            ("species", QVariant.String),
            ("coord_x", QVariant.Double),
            ("coord_y", QVariant.Double),
            ("status", QVariant.String),
        ]:
            flds.append(QgsField(nm, tp))
        dp.addAttributes(flds)
        layer.updateFields()

        feats = []
        for i, pt in enumerate(points, 1):
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(pt))
            f.setAttributes([
                i, ptype.capitalize(), species,
                round(pt.x(), 6), round(pt.y(), 6), status
            ])
            feats.append(f)
        dp.addFeatures(feats)
        layer.updateExtents()
        self._apply_style(layer, ptype)
        return layer

    def _apply_style(self, layer, ptype):
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": self.COLORS.get(ptype, "#888888"),
            "size": str(self.SIZES.get(ptype, 3.0)),
            "outline_style": "no",
        })
        layer.renderer().setSymbol(sym)
        layer.triggerRepaint()
