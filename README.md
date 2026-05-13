# Kakao Planting Designer for QGIS

> Precision Spatial Planning for Cocoa Plantation Design Using GIS, DEM, and Drone Data

![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-green)
![Python](https://img.shields.io/badge/Python-3.x-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Version](https://img.shields.io/badge/Version-1.3.0-orange)

## Overview

Kakao Planting Designer is a QGIS plugin developed to support precision planning of cocoa plantations using geospatial technologies. The plugin automatically generates optimal planting points for cocoa trees and shade trees based on user-defined spacing, planting patterns, and terrain constraints derived from Digital Elevation Models (DEM).

The plugin is designed for researchers, plantation managers, agricultural consultants, and students working in precision agriculture, agroforestry, and geospatial analysis.

## Key Features

- Generate cocoa planting points within user-defined polygon boundaries.
- Support square and triangular planting patterns.
- Automatic shade tree placement based on configurable ratios.
- Slope-based exclusion using DEM, DTM, LiDAR, and SRTM.
- Compatibility with drone orthophotos and multispectral imagery.
- High-performance NumPy processing for large datasets.
- Bulk creation of memory layers in QGIS.
- Progress reporting and task cancellation support.
- Export-ready output layers for further GIS analysis.

## Supported Raster Inputs

| Raster Type | Purpose |
|----------|----------|
| DTM Drone | Terrain slope analysis |
| DSM Drone | Surface model analysis |
| LiDAR DTM | High-precision terrain modeling |
| SRTM 30m | Public DEM source |
| Orthophoto RGB | Visual basemap only |
| Orthophoto Multispectral | Visual basemap only |
| Other DEM | Custom elevation raster |

## Installation

### Manual Installation

1. Download the latest release ZIP from GitHub.
2. Open QGIS.
3. Navigate to `Plugins → Manage and Install Plugins → Install from ZIP`.
4. Select the downloaded ZIP file.
5. Activate the plugin.

## Workflow

1. Prepare a polygon representing the plantation boundary.
2. (Optional) Load a DEM or terrain raster.
3. Open Kakao Planting Designer.
4. Configure planting spacing and pattern.
5. Set slope threshold and shade tree options.
6. Run the analysis.
7. Review generated cocoa, shade, and excluded layers.

## Output Layers

- **Titik Tanam Kakao** — Recommended cocoa planting points.
- **Titik Tanam Penaung** — Shade tree locations.
- **Zona Excluded (Slope)** — Areas excluded due to steep terrain.

## Planting Patterns

### Square Pattern
Uniform rectangular spacing.

### Triangular Pattern
Optimized staggered layout with higher planting density.

## Performance Optimizations

Version 1.3 introduces major performance improvements:

- NumPy-based grid generation.
- Batch polygon clipping.
- Raster block reading for DEM processing.
- Vectorized slope calculations.
- Bulk feature insertion.
- Efficient shade tree selection.

These enhancements enable processing of thousands to millions of candidate points efficiently.

## Applications

- Precision cocoa plantation planning
- Agroforestry design
- Terrain suitability analysis
- Academic research
- Teaching GIS and remote sensing
- Plantation management decision support

## System Requirements

- QGIS 3.28 or newer
- Python 3.x (included with QGIS)
- NumPy

## Repository Structure

```text
kakao_planting_designer/
├── __init__.py
├── metadata.txt
├── kakao_planting_designer.py
├── dialog_main.py
├── dialog_main.ui
├── resources.py
├── icon.png
├── core/
│   └── planting_engine.py
└── exporter/
    └── exporter.py
