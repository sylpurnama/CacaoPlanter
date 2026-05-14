# -*- coding: utf-8 -*-
"""
CacaoPlanter — QGIS Plugin
Generate cacao and shade tree planting points with configurable
patterns, topography analysis, and multi-format export.

License: GPL-2.0-or-later
Repository: https://github.com/sylpurnama/CacaoPlanter
"""


def classFactory(iface):
    """QGIS entry point — called when plugin is loaded.

    :param iface: QgsInterface instance provided by QGIS.
    :returns:     CacaoPlanter plugin instance.
    """
    from .cacao_planter import CacaoPlanter
    return CacaoPlanter(iface)
