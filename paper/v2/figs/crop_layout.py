"""Crop the depth-256 Innovus screenshots to the layout canvas, one identical box for both, and write
fig_layout_v2_d256.png and fig_layout_v3_d256.png next to this script.

Usage: python3 -I paper/v2/figs/crop_layout.py <v2 screenshot> <v3 screenshot>

The screenshots (final 1.0 ns layouts after the two hold passes, folders *_d256_p0.8_nomerge_pnr1.0_nodvtsh2) are
NOT committed: their window title shows the lab-server user name and home path, and the side panel shows the layer
names of the design kit. Only the cropped canvas (no text, no window chrome, no layer panel) is used in the paper.
Both screenshots were taken in the same window size and zoom; the same box is cut from both.
"""
import sys
from pathlib import Path

from PIL import Image

BOX = (98, 183, 763, 834)          # left, upper, right, lower: inside the black canvas, outside every text field
OUT = Path(__file__).resolve().parent

if len(sys.argv) != 3:
    raise SystemExit(__doc__)
for src, name in zip(sys.argv[1:], ('fig_layout_v2_d256.png', 'fig_layout_v3_d256.png')):
    im = Image.open(src)
    if im.size != (1031, 911):
        raise SystemExit(f'{src}: unexpected size {im.size}; check BOX before cropping')
    im.convert('RGB').crop(BOX).save(OUT / name, optimize=True)
    print(f'wrote {name} {BOX[2] - BOX[0]}x{BOX[3] - BOX[1]}')
