# CacaoPlanter

> **QGIS Plugin** — Generate cacao and shade tree planting points with configurable patterns, topographic slope analysis, and multi-format export.

[![QGIS](https://img.shields.io/badge/QGIS-3.16%2B-green?logo=qgis)](https://qgis.org)
[![License](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.5.0-orange)](https://github.com/sylpurnama/CacaoPlanter/releases)
[![QGIS Plugins](https://img.shields.io/badge/QGIS%20Plugin%20Repository-CacaoPlanter-brightgreen)](https://plugins.qgis.org/plugins/cacao_planter/)

---

## Overview

**CacaoPlanter** is an open-source QGIS plugin that helps agronomy and GIS teams plan cacao (*Theobroma cacao*) planting layouts directly on georeferenced maps. It generates individual planting point locations based on configurable row/column spacing, supports triangular and square grid patterns, integrates slope analysis from elevation rasters, and exports results to multiple GIS and CAD formats.

![CacaoPlanter Dialog](icons/cacao_icon_64.png)

---

## Features

| Feature | Description |
|---------|-------------|
| **Planting point generation** | Triangular (quincunx) and square (orthogonal) grid patterns |
| **Shade tree planning** | Configurable species, ratio (e.g. 1:3), and minimum buffer distance |
| **Slope analysis** | Filter unsuitable terrain from DTM/DSM Drone, SRTM, LiDAR, or skip if no DEM |
| **Global CRS support** | Interactive CRS selector — works with any projected coordinate system worldwide |
| **Planting block grid** | Fishnet polygon layer aligned to row/column spacing |
| **Population statistics** | Density report in trees/ha for cacao and shade trees |
| **Multi-format export** | Shapefile, GeoPackage, KML (Google Earth), DXF (AutoCAD/survey) |
| **Non-blocking processing** | Background QgsTask — QGIS UI stays responsive during generation |

---

## Supported Raster Input Types

| Raster Type | Slope Analysis | Notes |
|-------------|:--------------:|-------|
| DTM Drone (Metashape / ODM / Pix4D) | ✅ | Recommended — cm to m resolution |
| DSM Drone | ✅ | Includes vegetation height; slope may be overestimated under tall canopy |
| SRTM 30m | ✅ | Public DEM; limited precision on gently undulating terrain |
| LiDAR DTM | ✅ | Very high accuracy ground surface |
| RGB / Multispectral Ortophoto | ❌ | Visual basemap only — slope analysis skipped |
| *(none)* | ❌ | Fast-path mode — no raster I/O |

---

## Output Layers

| Layer | Description |
|-------|-------------|
| **Cacao Planting Points** | All valid planting locations within the field boundary |
| **Shade Tree Points** | Selected shade tree positions (1 per N cacao trees) |
| **Excluded Zones (Slope)** | Points removed because slope exceeded the maximum threshold |
| **Planting Block Grid** | Fishnet polygon layer aligned to row/column spacing |

---

## Requirements

| Component | Minimum |
|-----------|---------|
| QGIS | 3.16 |
| Python | 3.7 |
| NumPy | Bundled with QGIS |

---

## Installation

### From QGIS Plugin Repository *(recommended)*
1. QGIS → **Plugins** → **Manage and Install Plugins**
2. Search: `CacaoPlanter`
3. Click **Install Plugin**

### From ZIP
1. Download the latest ZIP from [Releases](https://github.com/sylpurnama/CacaoPlanter/releases)
2. QGIS → **Plugins** → **Manage and Install Plugins** → **Install from ZIP**
3. Select the downloaded ZIP → **Install Plugin**

### Manual
1. Extract the ZIP so that `cacao_planter/` folder (containing `metadata.txt` and `__init__.py`) is placed inside:
   - **Windows:** `C:\Users\<user>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux/macOS:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
2. Restart QGIS and enable the plugin via **Plugins → Manage and Install Plugins**

---

## Quick Start

1. Load a **polygon layer** that defines your planting field boundary
2. *(Optional)* Load an **elevation raster** (DTM/DSM drone, SRTM, LiDAR)
3. Open CacaoPlanter from the **toolbar** or **Plugins → CacaoPlanter**
4. **Parameters tab:**
   - Select your polygon layer
   - Select raster type and layer (or leave empty to skip slope analysis)
   - Choose planting pattern (triangular or square)
   - Set row and column spacing (default: 3 × 3 m)
   - Configure shade tree ratio and species
   - Select output CRS using the interactive CRS selector
5. **Output tab:** Set project name, output directory, and export formats
6. Click **Generate Planting Points**
7. Results appear in the **Summary tab** and as new layers in the QGIS layer panel

---

## Parameters Reference

### Planting Pattern

| Pattern | Description | Population effect |
|---------|-------------|:-----------------:|
| Triangular (quincunx) | Odd rows offset by ½ column spacing | +~15% vs square |
| Square (orthogonal) | Straight grid, aligned rows and columns | Baseline |

### Slope Filter

The slope threshold (default: 25%) is applied per pixel using a Sobel 3×3 finite-difference kernel computed from the elevation raster. Points falling in areas steeper than the threshold are written to the **Excluded Zones** layer rather than discarded, allowing manual review.

### Output CRS

Select any projected CRS from the global QGIS CRS database. Use a **projected CRS** (UTM or local grid) for accurate metric spacing. Geographic CRS (degrees) is supported but spacing will be approximated.

---

## Changelog

```
1.5.0 - Full English UI, global CRS selector, removed institutional branding,
        icon fallback fix, backward-compatible aliases
1.4.0 - Performance: numpy grid, prepared geometry engine, block-read DEM slope,
        QgsTask background thread, bulk layer insert
1.3.0 - Planting block grid layer, flexible raster input, square grid alignment fix
1.2.0 - CRS-aware grid, QgsDistanceArea area calc, debug info, group deduplication
1.1.0 - Fix NameError Optional, flexible raster input, plugin icon, auto CRS transform
1.0.0 - Initial release
```

---

## Contributing

Bug reports and feature requests are welcome via [Issues](https://github.com/sylpurnama/CacaoPlanter/issues).

Pull requests are also welcome. Please open an issue first to discuss the proposed change.

---

## License

Released under the [GNU General Public License v2.0 or later](LICENSE).

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
