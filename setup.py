"""Build:  python3 setup.py py2app     (test fast with: python3 setup.py py2app -A)

Put your pngquant binary next to this file (named `pngquant`) before building.
"""
from setuptools import setup

APP = ["pngquant_preview_app.py"]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["webview"],
    "resources": ["pngquant"],  # copied to Contents/Resources/pngquant
    "plist": {
        "CFBundleName": "Didit",
        "CFBundleDisplayName": "Didit",
        "CFBundleIdentifier": "local.didit.app",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [{
            "CFBundleTypeName": "Image",
            "CFBundleTypeRole": "Viewer",
            "LSItemContentTypes": ["public.png", "public.jpeg", "public.image"],
        }],
    },
}

setup(app=APP, options={"py2app": OPTIONS}, setup_requires=["py2app"])
