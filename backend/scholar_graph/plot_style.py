"""Shared plot colors and available local font; no font redistribution or download."""
import os
from pathlib import Path
COLORS=['#14544b','#3c6e8f','#b38335','#7c609a','#527f73','#bb6458']
def plot_font():
    from matplotlib.font_manager import FontProperties
    for name in [os.getenv('SCHOLAR_GRAPH_FONT',''),'C:/Windows/Fonts/msyh.ttc','/app/fonts/cjk.ttc',
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
        if name and Path(name).is_file():return FontProperties(fname=name),True
    return FontProperties(family='DejaVu Sans'),False
