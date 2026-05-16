# -*- coding: utf-8 -*-
"""
ui/dialog_main.py  —  v1.5

Main dialog for CacaoPlanter QGIS Plugin.

Features:
  - Flexible raster input: DTM Drone, DSM Drone, Ortophoto RGB/MS, SRTM, LiDAR
  - Ortophoto basemap mode (visual only, slope analysis skipped)
  - Raster type dropdown + band selector
  - Global CRS selector using QgsProjectionSelectionWidget
  - Informative tooltips per component

CacaoPlanter — Open Source QGIS Plugin
License: GPL-2.0-or-later
Repository: https://github.com/sylpurnama/CacaoPlanter
"""

import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QGroupBox, QFrame,
    QLineEdit, QFileDialog, QTabWidget, QWidget,
    QTextEdit, QScrollArea, QCheckBox,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont, QIcon, QPixmap

from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsMapLayerProxyModel,
    QgsCoordinateReferenceSystem,
)
from qgis.gui import QgsMapLayerComboBox, QgsProjectionSelectionWidget

from ..core.planting_engine import (
    RASTER_TYPE_OPTIONS,
    BASEMAP_TYPE_KEYS,
    SHADE_TREE_OPTIONS,
    RasterInputInfo,
)


class CacaoDialog(QDialog):
    """
    Main plugin dialog — 3 tabs:
        ⚙  Parameters  : field boundary, raster input, planting pattern,
                          shade trees, CRS
        📁  Output      : project name, directory, export formats
        📊  Summary     : calculation results and population statistics
    """

    PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("CacaoPlanter")
        self.setMinimumWidth(480)
        self.setMinimumHeight(600)

        # Window icon — try both naming conventions
        for icon_name in ("cacao_icon.png", "kakao_icon.png"):
            icon_path = os.path.join(self.PLUGIN_DIR, "icons", icon_name)
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI builder
    # ------------------------------------------------------------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        main_layout.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_parameters(), "  Parameters")
        self.tabs.addTab(self._tab_output(), "  Output")
        self.tabs.addTab(self._tab_summary(), "  Summary")
        main_layout.addWidget(self.tabs)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        self.btn_preview = QPushButton("Quick Estimate")
        self.btn_generate = QPushButton("  Generate Planting Points")
        self.btn_generate.setDefault(True)
        fnt = QFont()
        fnt.setBold(True)
        self.btn_generate.setFont(fnt)

        btn_row.addWidget(self.btn_close)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_preview)
        btn_row.addWidget(self.btn_generate)
        main_layout.addLayout(btn_row)

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)

        # Icon
        for icon_name in ("cacao_icon_64.png", "kakao_icon_64.png"):
            icon_path = os.path.join(self.PLUGIN_DIR, "icons", icon_name)
            if os.path.exists(icon_path):
                lbl_icon = QLabel()
                pix = QPixmap(icon_path).scaled(
                    48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                lbl_icon.setPixmap(pix)
                layout.addWidget(lbl_icon)
                break

        # Text
        txt_layout = QVBoxLayout()
        lbl_title = QLabel("CacaoPlanter")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        lbl_title.setFont(f)

        lbl_sub = QLabel("Cacao & Shade Tree Planting Designer  |  v1.5")
        lbl_sub.setStyleSheet("color: gray; font-size: 10px;")

        txt_layout.addWidget(lbl_title)
        txt_layout.addWidget(lbl_sub)
        layout.addLayout(txt_layout)
        layout.addStretch()
        return frame

    # ------------------------------------------------------------------
    # Tab 1: Parameters
    # ------------------------------------------------------------------

    def _tab_parameters(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── 1. Field Boundary ─────────────────────────────────────────
        grp_field = QGroupBox("1  ·  Field Boundary (Polygon Layer)")
        form = QFormLayout(grp_field)

        self.cb_polygon = QgsMapLayerComboBox()
        self.cb_polygon.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cb_polygon.setToolTip(
            "Select the polygon layer defining the planting area.\n"
            "Accepts Shapefile, GeoPackage, or any digitised polygon layer."
        )
        form.addRow("Polygon layer:", self.cb_polygon)
        layout.addWidget(grp_field)

        # ── 2. Raster Input ───────────────────────────────────────────
        grp_raster = QGroupBox(
            "2  ·  Raster Input  (DEM / Ortophoto / Satellite)")
        grp_raster.setToolTip(
            "Supports all common raster types:\n"
            "• DTM/DSM from drone (Metashape, ODM, Pix4D)\n"
            "• RGB / multispectral ortophoto\n"
            "• SRTM 30m, LiDAR, or any other elevation raster\n"
            "• Formats: GeoTIFF, IMG, VRT, etc."
        )
        form2 = QFormLayout(grp_raster)

        self.cb_raster_type = QComboBox()
        for key, label in RASTER_TYPE_OPTIONS:
            self.cb_raster_type.addItem(label, key)
        self.cb_raster_type.setToolTip(
            "Select the raster type being used.\n"
            "Ortophoto/RGB → used as visual basemap only, "
            "slope NOT analysed.\n"
            "DTM/DSM Drone → slope analysis performed, "
            "high resolution recommended.\n"
            "SRTM → 30m resolution, use only when drone data is unavailable."
        )
        form2.addRow("Raster type:", self.cb_raster_type)

        self.cb_dem = QgsMapLayerComboBox()
        self.cb_dem.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cb_dem.setAllowEmptyLayer(True)
        self.cb_dem.setToolTip(
            "Select a raster layer already loaded in QGIS.\n"
            "Or load it first via Layer > Add Layer > Add Raster Layer."
        )
        form2.addRow("Raster layer:", self.cb_dem)

        self.lbl_band = QLabel("Elevation band:")
        self.spin_band = QSpinBox()
        self.spin_band.setRange(1, 10)
        self.spin_band.setValue(1)
        self.spin_band.setToolTip(
            "Band containing elevation data.\n"
            "For most DEMs: band 1.\n"
            "For multispectral rasters, refer to the raster metadata."
        )
        form2.addRow(self.lbl_band, self.spin_band)

        self.lbl_raster_info = QLabel()
        self.lbl_raster_info.setWordWrap(True)
        self.lbl_raster_info.setStyleSheet(
            "color: #555; font-size: 10px; font-style: italic;"
        )
        form2.addRow("", self.lbl_raster_info)

        self.lbl_slope = QLabel("Maximum slope:")
        self.spin_slope = QDoubleSpinBox()
        self.spin_slope.setRange(5.0, 60.0)
        self.spin_slope.setValue(25.0)
        self.spin_slope.setSuffix(" %")
        self.spin_slope.setToolTip(
            "Points in areas steeper than this value will be "
            "marked as excluded.\n"
            "Recommended for cacao: ≤ 25%  |  Undulating terrain: 15–20%"
        )
        form2.addRow(self.lbl_slope, self.spin_slope)

        layout.addWidget(grp_raster)

        # ── 3. Planting Pattern ───────────────────────────────────────
        grp_pattern = QGroupBox("3  ·  Cacao Planting Pattern")
        form3 = QFormLayout(grp_pattern)

        self.cb_pattern = QComboBox()
        self.cb_pattern.addItem(
            "Triangular (quincunx)  —  denser, +15% population", "segitiga"
        )
        self.cb_pattern.addItem(
            "Square (orthogonal)  —  straight maintenance aisles", "segi_empat"
        )
        self.cb_pattern.setToolTip(
            "Triangular: odd rows are offset by half the column spacing.\n"
            "  → better space efficiency, canopies less likely to overlap.\n"
            "Square: straight grid, easier mechanisation and field operations."
        )
        form3.addRow("Pattern:", self.cb_pattern)

        self.spin_row_spacing = QDoubleSpinBox()
        self.spin_row_spacing.setRange(2.0, 6.0)
        self.spin_row_spacing.setValue(3.0)
        self.spin_row_spacing.setSingleStep(0.5)
        self.spin_row_spacing.setSuffix(" m")
        self.spin_row_spacing.setToolTip(
            "Distance between planting rows. Standard for cacao: 3 m"
        )
        form3.addRow("Row spacing:", self.spin_row_spacing)

        self.spin_col_spacing = QDoubleSpinBox()
        self.spin_col_spacing.setRange(2.0, 6.0)
        self.spin_col_spacing.setValue(3.0)
        self.spin_col_spacing.setSingleStep(0.5)
        self.spin_col_spacing.setSuffix(" m")
        self.spin_col_spacing.setToolTip(
            "Distance within a row (column spacing). Standard for cacao: 3 m"
        )
        form3.addRow("Column spacing:", self.spin_col_spacing)

        layout.addWidget(grp_pattern)

        # ── 4. Shade Trees ────────────────────────────────────────────
        grp_shade = QGroupBox("4  ·  Shade Trees")
        grp_shade.setCheckable(True)
        grp_shade.setChecked(True)
        self.grp_shade = grp_shade
        form4 = QFormLayout(grp_shade)

        self.cb_shade_species = QComboBox()
        self.cb_shade_species.addItems(SHADE_TREE_OPTIONS)
        form4.addRow("Species:", self.cb_shade_species)

        self.spin_shade_ratio = QSpinBox()
        self.spin_shade_ratio.setRange(1, 10)
        self.spin_shade_ratio.setValue(3)
        self.spin_shade_ratio.setPrefix("1 shade : ")
        self.spin_shade_ratio.setSuffix(" cacao")
        self.spin_shade_ratio.setToolTip(
            "Standard ratio: 1 shade tree per 3 cacao trees")
        form4.addRow("Ratio:", self.spin_shade_ratio)

        self.spin_shade_buffer = QDoubleSpinBox()
        self.spin_shade_buffer.setRange(1.0, 8.0)
        self.spin_shade_buffer.setValue(2.0)
        self.spin_shade_buffer.setSuffix(" m")
        self.spin_shade_buffer.setToolTip(
            "Minimum spacing between shade tree points")
        form4.addRow("Minimum buffer:", self.spin_shade_buffer)

        layout.addWidget(grp_shade)

        # ── 5. Output CRS ─────────────────────────────────────────────
        grp_crs = QGroupBox("5  ·  Output Coordinate Reference System")
        form5 = QFormLayout(grp_crs)

        self.crs_selector = QgsProjectionSelectionWidget()
        # Default: WGS 84 / UTM zone 50S — change as needed
        self.crs_selector.setCrs(
            QgsCoordinateReferenceSystem("EPSG:32750")
        )
        self.crs_selector.setToolTip(
            "Select the output CRS for generated point layers.\n"
            "Use a projected CRS (UTM or local) for accurate "
            "distance calculations.\n"
            "Click the globe icon to browse all available CRS options."
        )
        form5.addRow("Output CRS:", self.crs_selector)
        layout.addWidget(grp_crs)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Tab 2: Output
    # ------------------------------------------------------------------

    def _tab_output(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        grp_name = QGroupBox("Project Name")
        form = QFormLayout(grp_name)
        self.txt_project_name = QLineEdit("Cacao_Project")
        self.txt_project_name.setToolTip(
            "Prefix used for all output file names")
        form.addRow("File name prefix:", self.txt_project_name)
        layout.addWidget(grp_name)

        grp_dir = QGroupBox("Output Directory")
        row = QHBoxLayout(grp_dir)
        self.txt_output_dir = QLineEdit(os.path.expanduser("~/cacao_output"))
        btn_browse = QPushButton("Browse…")
        btn_browse.setMaximumWidth(80)
        btn_browse.clicked.connect(self._browse_dir)
        row.addWidget(self.txt_output_dir)
        row.addWidget(btn_browse)
        layout.addWidget(grp_dir)

        grp_fmt = QGroupBox("Export Formats")
        grp_fmt.setToolTip(
            "Select one or more output formats.\n"
            "GeoPackage: recommended for internal GIS archive.\n"
            "KML: for Google Earth and field applications.\n"
            "DXF: for AutoCAD and survey software."
        )
        fmt_layout = QVBoxLayout(grp_fmt)

        self.chk_shp = QCheckBox(
            "Shapefile (.shp)      —  standard GIS format")
        self.chk_gpkg = QCheckBox("GeoPackage (.gpkg)  —  recommended")
        self.chk_kml = QCheckBox(
            "KML (.kml)               —  Google Earth / field use")
        self.chk_dxf = QCheckBox(
            "DXF (.dxf)                —  AutoCAD / survey software")
        self.chk_shp.setChecked(True)
        self.chk_gpkg.setChecked(True)
        for c in [self.chk_shp, self.chk_gpkg, self.chk_kml, self.chk_dxf]:
            fmt_layout.addWidget(c)
        layout.addWidget(grp_fmt)

        layout.addStretch()
        return tab

    # ------------------------------------------------------------------
    # Tab 3: Summary
    # ------------------------------------------------------------------

    def _tab_summary(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setPlaceholderText(
            "Calculation results will appear here after clicking\n"
            "'Quick Estimate' or 'Generate Planting Points'."
        )
        f = QFont("Courier New", 10)
        self.txt_summary.setFont(f)
        layout.addWidget(self.txt_summary)
        return tab

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.cb_raster_type.currentIndexChanged.connect(
            self._on_raster_type_changed)
        self._on_raster_type_changed()

    def _on_raster_type_changed(self):
        """Update UI when raster type changes."""
        rtype = self.cb_raster_type.currentData()
        is_basemap = rtype in BASEMAP_TYPE_KEYS

        self.lbl_slope.setVisible(not is_basemap)
        self.spin_slope.setVisible(not is_basemap)
        self.lbl_band.setVisible(not is_basemap)
        self.spin_band.setVisible(not is_basemap)

        if rtype == "dtm_drone":
            info = (
                "DTM Drone: cm–m resolution, high accuracy. "
                "Slope analysed per pixel."
            )
        elif rtype == "dsm_drone":
            info = (
                "DSM Drone: includes vegetation height. "
                "Slope may be overestimated in tall canopy areas."
            )
        elif rtype in BASEMAP_TYPE_KEYS:
            info = (
                "Ortophoto: used as visual basemap only. "
                "Slope analysis is NOT performed."
            )
        elif rtype == "srtm":
            info = (
                "SRTM 30m: suitable for estimation; limited precision "
                "on gently undulating terrain."
            )
        elif rtype == "lidar_dtm":
            info = (
                "LiDAR DTM: very high accuracy. "
                "Ensure CRS matches the project projection."
            )
        else:
            info = (
                "Other elevation raster. "
                "Ensure the layer is projected and georeferenced."
            )
        self.lbl_raster_info.setText(info)

    # ------------------------------------------------------------------
    # Public getters — called by controller
    # ------------------------------------------------------------------

    def get_polygon_layer(self) -> QgsVectorLayer:
        return self.cb_polygon.currentLayer()

    def get_dem_layer(self) -> QgsRasterLayer:
        return self.cb_dem.currentLayer()

    def get_raster_info(self) -> RasterInputInfo:
        rtype = self.cb_raster_type.currentData() or "dtm_drone"
        band = self.spin_band.value()
        return RasterInputInfo(tipe_key=rtype, band_elevasi=band)

    def get_pola(self) -> str:
        return self.cb_pattern.currentData()

    def get_jarak_baris(self) -> float:
        return self.spin_row_spacing.value()

    def get_jarak_kolom(self) -> float:
        return self.spin_col_spacing.value()

    def get_penaung_aktif(self) -> bool:
        return self.grp_shade.isChecked()

    def get_penaung_jenis(self) -> str:
        return self.cb_shade_species.currentText()

    def get_penaung_rasio(self) -> int:
        return self.spin_shade_ratio.value()

    def get_penaung_buffer(self) -> float:
        return self.spin_shade_buffer.value()

    def get_slope_maks(self) -> float:
        return self.spin_slope.value()

    def get_crs_epsg(self) -> int:
        crs = self.crs_selector.crs()
        if crs.isValid():
            auth = crs.authid()
            if ":" in auth:
                try:
                    return int(auth.split(":")[1])
                except ValueError:
                    pass
        return 32750

    def get_nama_proyek(self) -> str:
        return self.txt_project_name.text().strip() or "Cacao_Project"

    def get_output_dir(self) -> str:
        return self.txt_output_dir.text().strip()

    def get_formats_export(self) -> list:
        fmt = []
        if self.chk_shp.isChecked():
            fmt.append("shapefile")
        if self.chk_gpkg.isChecked():
            fmt.append("geopackage")
        if self.chk_kml.isChecked():
            fmt.append("kml")
        if self.chk_dxf.isChecked():
            fmt.append("dxf")
        return fmt

    # ------------------------------------------------------------------
    # Display results
    # ------------------------------------------------------------------

    def tampilkan_ringkasan(self, result):
        rtype_label = self.cb_raster_type.currentText()
        pattern_label = self.get_pola().replace("_", " ").title()
        sep1 = "=" * 50
        sep2 = "-" * 50
        teks = "\n".join([
            sep1,
            "  CACAOPLANTER  —  RESULTS",
            sep1,
            "",
            f"  Field area         : {result.luas_ha:.2f} ha",
            f"  Planting pattern   : {pattern_label}",
            (
                f"  Spacing (row×col)  : "
                f"{self.get_jarak_baris()} × {self.get_jarak_kolom()} m"
            ),
            f"  Raster input       : {rtype_label[:45]}",
            "",
            sep2,
            f"  Cacao points       : {result.jumlah_kakao:>8,} trees",
            f"  Shade tree points  : {result.jumlah_penaung:>8,} trees",
            f"  Excluded zones     : {result.jumlah_excluded:>8,} points",
            "",
            f"  Cacao density      : {result.kepadatan_kakao_per_ha} trees/ha",
            f"  Shade density      : "
            f"{result.kepadatan_penaung_per_ha} trees/ha",
            sep1,
        ])
        self.txt_summary.setText(teks)
        self.tabs.setCurrentIndex(2)

    def tampilkan_estimasi(
            self, luas_ha: float, est_kakao: int, est_penaung: int):
        sep = "=" * 50
        teks = "\n".join([
            sep,
            "  QUICK ESTIMATE  (no layer generated yet)",
            sep,
            "",
            f"  Field area          : {luas_ha:.2f} ha",
            f"  Estimated cacao     : ±{est_kakao:,} trees",
            f"  Estimated shade     : ±{est_penaung:,} trees",
            "",
            "  Click 'Generate Planting Points' for",
            "  accurate results with per-point slope analysis.",
            sep,
        ])
        self.txt_summary.setText(teks)
        self.tabs.setCurrentIndex(2)

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select output directory", self.txt_output_dir.text()
        )
        if folder:
            self.txt_output_dir.setText(folder)
