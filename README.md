# CacaoPlanter

**CacaoPlanter** — Generate cacao and shade tree planting points with configurable patterns, topography analysis, and multi-format export — without leaving QGIS.

![version](https://img.shields.io/badge/version-1.5.1-blue)
[![QGIS](https://img.shields.io/badge/QGIS-3.16%2B-green?logo=qgis&logoColor=white)](https://qgis.org)
![license](https://img.shields.io/badge/license-GPL--2.0--or--later-brightgreen)
[![Python](https://img.shields.io/badge/python-3.7%2B-blue?logo=python&logoColor=white)](https://www.python.org)
![QGIS review](https://img.shields.io/badge/QGIS%20review-under%20review-orange)

---

## Features

- **Planting point generation** — triangular (quincunx) and square (orthogonal) grid patterns
- **Shade tree planning** — configurable species, ratio, and minimum buffer
- **Slope analysis** — filter unsuitable terrain using any elevation raster (DTM/DSM Drone, SRTM 30m, LiDAR DTM) or skip entirely
- **Global CRS support** — works with any projected coordinate system worldwide via interactive CRS selector
- **Planting block grid** — fishnet polygon layer aligned to row/column spacing
- **Population statistics** — trees/ha for cacao and shade trees
- **Multi-format export** — Shapefile, GeoPackage, KML (Google Earth / field apps), DXF (AutoCAD / survey)
- **Non-blocking processing** — background QgsTask keeps QGIS responsive during generation

---

## Requirements

| Component | Minimum version |
|-----------|----------------|
| QGIS      | 3.16            |
| Python    | 3.7             |
| NumPy     | bundled with QGIS |

---

## Installation

### From QGIS Plugin Repository *(recommended)*
1. QGIS → **Plugins** → **Manage and Install Plugins**
2. Search for **CacaoPlanter**
3. Click **Install Plugin**

### From ZIP
1. Download the latest release ZIP from [Releases](https://github.com/sylpurnama/CacaoPlanter/releases)
2. QGIS → **Plugins** → **Manage and Install Plugins** → **Install from ZIP**
3. Select the downloaded ZIP and click **Install Plugin**

---

## Quick Start

1. Load a **polygon layer** defining your planting area
2. *(Optional)* Load an **elevation raster** (DTM/DSM from drone, SRTM, LiDAR)
3. Open CacaoPlanter from the toolbar or **Plugins → CacaoPlanter**
4. Configure spacing, pattern, shade tree ratio, and output CRS
5. Click **Generate Planting Points**

---

## Supported Raster Types

| Type | Slope Analysis | Notes |
|------|---------------|-------|
| DTM Drone (Metashape / ODM / Pix4D) | ✅ | Recommended — cm to m resolution |
| DSM Drone | ✅ | Includes vegetation height; slope may be overestimated |
| SRTM 30m | ✅ | Public DEM; limited precision on gentle slopes |
| LiDAR DTM | ✅ | Very high accuracy |
| RGB / Multispectral Orthophoto | ❌ | Used as visual basemap only |
| No raster | ❌ | Fast-path mode — no slope filtering |

---

## Output Layers

| Layer | Description |
|-------|-------------|
| Cacao Planting Points | All valid planting locations |
| Shade Tree Points | Selected shade tree positions |
| Excluded Zones (Slope) | Points removed by slope filter |
| Planting Block Grid | Fishnet polygons aligned to spacing |

---

## License

This plugin is released under the [GNU General Public License v2.0 or later](LICENSE).

---

## Contributing

Bug reports and pull requests are welcome at:
https://github.com/sylpurnama/CacaoPlanter/issues
