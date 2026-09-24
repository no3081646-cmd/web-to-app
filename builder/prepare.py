#!/usr/bin/env python3
"""Generate a ready-to-compile Android project from the template.

Reads configuration from environment variables and writes the project into
$OUT_DIR (default: build-project).
"""
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template")
OUT = os.environ.get("OUT_DIR", "build-project")

APP_NAME = os.environ.get("APP_NAME", "My App").strip() or "My App"
PACKAGE_NAME = os.environ.get("PACKAGE_NAME", "com.example.app").strip()
VERSION_NAME = os.environ.get("VERSION_NAME", "1.0.0").strip() or "1.0.0"
VERSION_CODE = os.environ.get("VERSION_CODE", "1").strip() or "1"
SOURCE_TYPE = os.environ.get("SOURCE_TYPE", "url").strip()
SOURCE_URL = os.environ.get("SOURCE_URL", "").strip()
PERMISSIONS = os.environ.get("PERMISSIONS", "").strip()

if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$", PACKAGE_NAME):
    sys.exit("Nama paket tidak valid: %s" % PACKAGE_NAME)
if not re.match(r"^\d+$", VERSION_CODE):
    sys.exit("Version code harus angka")
if SOURCE_TYPE not in ("url", "html", "zip"):
    sys.exit("Jenis sumber tidak dikenal")
if not SOURCE_URL:
    sys.exit("Sumber kosong")


def xml_escape(value):
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "\\'"))


if os.path.exists(OUT):
    shutil.rmtree(OUT)
shutil.copytree(TEMPLATE, OUT)

assets_www = os.path.join(OUT, "app", "src", "main", "assets", "www")

if SOURCE_TYPE == "url":
    start_url = SOURCE_URL
    offline = "false"
else:
    os.makedirs(assets_www, exist_ok=True)
    tmp = "/tmp/source.bin"
    urllib.request.urlretrieve(SOURCE_URL, tmp)
    if SOURCE_TYPE == "html":
        shutil.copy(tmp, os.path.join(assets_www, "index.html"))
    else:
        with zipfile.ZipFile(tmp) as zf:
            for member in zf.namelist():
                target = os.path.normpath(os.path.join(assets_www, member))
                if not target.startswith(os.path.abspath(assets_www)) and \
                        not target.startswith(assets_www):
                    continue
            zf.extractall(assets_www)
        # Find index.html, flatten if it sits inside a single wrapper folder.
        if not os.path.exists(os.path.join(assets_www, "index.html")):
            found = None
            for root, _dirs, files in os.walk(assets_www):
                if "index.html" in files:
                    if found is None or len(root) < len(found):
                        found = root
            if found is None:
                sys.exit("index.html tidak ditemukan di dalam ZIP")
            if found != assets_www:
                for name in os.listdir(found):
                    shutil.move(os.path.join(found, name), os.path.join(assets_www, name))
    start_url = "file:///android_asset/www/index.html"
    offline = "true"

perm_lines = []
seen = set()
for raw in PERMISSIONS.split(","):
    name = raw.strip()
    if not name or name == "android.permission.INTERNET":
        continue
    if not re.match(r"^[A-Za-z0-9_.]+$", name):
        continue
    if not name.startswith("android.permission.") and "." not in name:
        name = "android.permission." + name
    if name in seen:
        continue
    seen.add(name)
    perm_lines.append('    <uses-permission android:name="%s" />' % name)

replacements = {
    "@@PACKAGE_NAME@@": PACKAGE_NAME,
    "@@VERSION_CODE@@": VERSION_CODE,
    "@@VERSION_NAME@@": VERSION_NAME,
    "@@APP_NAME@@": xml_escape(APP_NAME),
    "@@START_URL@@": start_url.replace("\\", "\\\\").replace('"', '\\"'),
    "@@OFFLINE_MODE@@": offline,
}

for path in [os.path.join(OUT, "app", "build.gradle"),
             os.path.join(OUT, "app", "src", "main", "AndroidManifest.xml")]:
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    for key, value in replacements.items():
        content = content.replace(key, value)
    content = content.replace("<!-- @@PERMISSIONS@@ -->", "\n".join(perm_lines))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

print("Proyek siap:", OUT)
print("Paket:", PACKAGE_NAME, "versi", VERSION_NAME, "(" + VERSION_CODE + ")")
print("URL awal:", start_url)
print("Izin tambahan:", len(perm_lines))
