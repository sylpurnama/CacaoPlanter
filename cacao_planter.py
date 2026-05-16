# -*- coding: utf-8 -*-
"""
cacao_planter.py  —  v1.5

CacaoPlanter — Open Source QGIS Plugin
Generate cacao and shade tree planting points with configurable
patterns, topography analysis, and multi-format export.

License: GPL-2.0-or-later
Repository: https://github.com/sylpurnama/CacaoPlanter
"""

import os
import math
import traceback
from typing import Optional

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import (
    QgsProject,
    QgsGeometry,
    QgsTask,
    QgsApplication,
    Qgis,
)

from .ui.dialog_main import CacaoDialog
from .core.planting_engine import PlantingEngine, PlantingConfig, LayerBuilder
from .core.exporter import Exporter


# ---------------------------------------------------------------------------
# Background Task
# ---------------------------------------------------------------------------

class GenerateTask(QgsTask):
    """Run PlantingEngine in a background thread so the QGIS UI stays
    responsive.
    """

    def __init__(self, description, cfg, geom_lahan, polygon_crs, dem_layer):
        super().__init__(description, QgsTask.CanCancel)
        self.cfg = cfg
        self.geom_lahan = geom_lahan
        self.polygon_crs = polygon_crs
        self.dem_layer = dem_layer
        self.result = None
        self.error_msg = None

    def run(self):
        try:
            self.result = PlantingEngine(self.cfg).run(
                self.geom_lahan, self.polygon_crs, self.dem_layer, task=self
            )
            return True
        except Exception as e:
            self.error_msg = f"{e}\n\n{traceback.format_exc()}"
            return False


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class CacaoPlanter:

    PLUGIN_NAME = "CacaoPlanter"
    PLUGIN_VERSION = "1.5"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dialog: Optional[CacaoDialog] = None
        self.actions = []
        self.menu = self.PLUGIN_NAME
        self._active_task: Optional[GenerateTask] = None

        self.toolbar = self.iface.addToolBar(self.PLUGIN_NAME)
        self.toolbar.setObjectName("CacaoPlanterToolbar")

        locale = QSettings().value("locale/userLocale", "en")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", f"cacao_{locale}.qm"
        )
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    # ------------------------------------------------------------------
    # QGIS plugin interface
    # ------------------------------------------------------------------

    def initGui(self):
        # Try both naming conventions for the icon file
        icon = QIcon()
        for icon_name in ("cacao_icon.png", "kakao_icon.png"):
            icon_path = os.path.join(self.plugin_dir, "icons", icon_name)
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                break

        action = QAction(icon, self.PLUGIN_NAME, self.iface.mainWindow())
        action.triggered.connect(self.run)
        action.setEnabled(True)
        action.setToolTip(
            f"{self.PLUGIN_NAME} v{self.PLUGIN_VERSION}\n"
            "Generate cacao and shade tree planting points"
        )
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(f"&{self.PLUGIN_NAME}", action)
        self.actions.append(action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(f"&{self.PLUGIN_NAME}", action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        if self.dialog is None:
            self.dialog = CacaoDialog(self.iface)
            self.dialog.btn_generate.clicked.connect(self.on_generate)
            self.dialog.btn_preview.clicked.connect(self.on_preview)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    # ------------------------------------------------------------------
    # Generate handler  (async via QgsTask)
    # ------------------------------------------------------------------

    def on_generate(self):
        cfg = self._read_config()
        if cfg is None:
            return

        polygon_layer = self.dialog.get_polygon_layer()
        if not polygon_layer or not polygon_layer.isValid():
            self._error("No valid polygon layer selected.")
            return

        features = list(polygon_layer.selectedFeatures())
        if not features:
            features = list(polygon_layer.getFeatures())
        if not features:
            self._error("Polygon layer is empty — no features found.")
            return

        polygon_crs = polygon_layer.crs()

        geom_list = [f.geometry() for f in features]
        geom_field = (geom_list[0] if len(geom_list) == 1
                      else QgsGeometry.unaryUnion(geom_list))

        if geom_field is None or geom_field.isEmpty():
            self._error("Polygon geometry is empty or invalid.")
            return

        if geom_field.area() <= 0:
            self._error(
                "Polygon area = 0.\n"
                "Make sure the layer uses a projected CRS "
                "(not geographic degrees)."
            )
            return

        dem_layer = self.dialog.get_dem_layer()

        self.dialog.btn_generate.setEnabled(False)
        self._status("Calculating planting points (background)…")

        task = GenerateTask(
            f"{self.PLUGIN_NAME}: generate",
            cfg, geom_field, polygon_crs, dem_layer,
        )
        task.taskCompleted.connect(lambda: self._on_task_done(task))
        task.taskTerminated.connect(lambda: self._on_task_failed(task))
        self._active_task = task
        QgsApplication.taskManager().addTask(task)

    # ------------------------------------------------------------------
    # Task callbacks
    # ------------------------------------------------------------------

    def _on_task_done(self, task: GenerateTask):
        self.dialog.btn_generate.setEnabled(True)

        if task.error_msg:
            self._error(f"Error during generation:\n{task.error_msg}")
            return

        result = task.result

        if result.jumlah_kakao == 0:
            self._error(
                "No planting points were generated!\n\n"
                f"Debug info:\n{result.debug_info}\n\n"
                "Possible causes:\n"
                f"  • Polygon too small for spacing "
                f"{task.cfg.jarak_baris}×{task.cfg.jarak_kolom} m\n"
                f"  • CRS mismatch ({task.polygon_crs.authid()})\n"
                "  • All points excluded by slope filter"
            )
            return

        self._status("Building layers…")
        builder = LayerBuilder(crs_epsg=result.crs_epsg_hasil)
        lyr_cacao = builder.buat_layer_kakao(result)
        lyr_shade = builder.buat_layer_penaung(result)
        lyr_excluded = builder.buat_layer_excluded(result)

        root = QgsProject.instance().layerTreeRoot()
        old_group = root.findGroup(self.PLUGIN_NAME)
        if old_group:
            root.removeChildNode(old_group)

        group = root.insertGroup(0, self.PLUGIN_NAME)
        QgsProject.instance().addMapLayer(lyr_cacao, False)
        QgsProject.instance().addMapLayer(lyr_shade, False)
        group.addLayer(lyr_shade)
        group.addLayer(lyr_cacao)

        if result.jumlah_excluded > 0:
            QgsProject.instance().addMapLayer(lyr_excluded, False)
            group.addLayer(lyr_excluded)

        formats = self.dialog.get_formats_export()
        if formats:
            Exporter(self.dialog.get_output_dir()).export_semua(
                lyr_cacao, lyr_shade, lyr_excluded,
                self.dialog.get_nama_proyek(), formats
            )

        self._status("Done.")
        self.dialog.tampilkan_ringkasan(result)
        self.iface.mapCanvas().refresh()

        self.iface.messageBar().pushMessage(
            self.PLUGIN_NAME,
            f"Done! {result.jumlah_kakao:,} cacao + "
            f"{result.jumlah_penaung:,} shade trees | "
            f"CRS: EPSG:{result.crs_epsg_hasil}",
            level=Qgis.Success,
            duration=10,
        )

    def _on_task_failed(self, task: GenerateTask):
        self.dialog.btn_generate.setEnabled(True)
        self._error(
            f"Task cancelled or failed.\n"
            f"{task.error_msg or 'No error details available.'}"
        )

    # ------------------------------------------------------------------
    # Quick estimate (synchronous — fast)
    # ------------------------------------------------------------------

    def on_preview(self):
        try:
            cfg = self._read_config()
            if cfg is None:
                return

            polygon_layer = self.dialog.get_polygon_layer()
            if not polygon_layer or not polygon_layer.isValid():
                self._error("Please select a polygon layer first.")
                return

            from qgis.core import QgsDistanceArea
            da = QgsDistanceArea()
            da.setSourceCrs(polygon_layer.crs(),
                            QgsProject.instance().transformContext())
            da.setEllipsoid(QgsProject.instance().ellipsoid())

            area_m2 = sum(
                da.measureArea(f.geometry())
                for f in polygon_layer.getFeatures()
            )
            area_ha = area_m2 / 10_000.0

            dx, dy = cfg.jarak_kolom, cfg.jarak_baris
            area_per_tree = (
                dx * dy * math.sin(math.radians(60))
                if cfg.pola == "segitiga" else dx * dy
            )
            est_cacao = int(area_ha * 10_000 / area_per_tree)
            est_shade = (
                est_cacao // cfg.penaung_rasio if cfg.penaung_aktif else 0
            )

            self.dialog.tampilkan_estimasi(area_ha, est_cacao, est_shade)

        except Exception as e:
            self._error(f"Estimate error:\n{e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_config(self) -> Optional[PlantingConfig]:
        try:
            ri = self.dialog.get_raster_info()
            return PlantingConfig(
                pola=self.dialog.get_pola(),
                jarak_baris=self.dialog.get_jarak_baris(),
                jarak_kolom=self.dialog.get_jarak_kolom(),
                penaung_aktif=self.dialog.get_penaung_aktif(),
                penaung_jenis=self.dialog.get_penaung_jenis(),
                penaung_rasio=self.dialog.get_penaung_rasio(),
                penaung_buffer=self.dialog.get_penaung_buffer(),
                slope_maks=self.dialog.get_slope_maks(),
                raster_dem_info=ri,
                output_crs_epsg=self.dialog.get_crs_epsg(),
            )
        except Exception as e:
            self._error(f"Invalid configuration:\n{e}")
            return None

    def _error(self, msg: str):
        QMessageBox.critical(
            self.iface.mainWindow(),
            f"{self.PLUGIN_NAME} — Error",
            msg,
        )

    def _status(self, text: str):
        self.iface.statusBarIface().showMessage(
            f"{self.PLUGIN_NAME}: {text}"
        )
