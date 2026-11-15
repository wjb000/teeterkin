#!/usr/bin/env python3
"""Download maker CAD used in the assembly into cad/vendor/ (not redistributed in this repo):
Seeed Studio XIAO ESP32S3. Run: python cad/fetch_vendor.py"""
import io, os, urllib.request, zipfile
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor'); os.makedirs(OUT, exist_ok=True)
SRC = {'xiao_esp32s3.step': 'https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-3d_model.zip'}
for name, url in SRC.items():
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read()))
    n = next(n for n in z.namelist() if n.lower().endswith(('.step', '.stp')) and not n.startswith('__MACOSX'))
    open(os.path.join(OUT, name), 'wb').write(z.read(n)); print('->', name)
