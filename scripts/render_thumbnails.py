#!/usr/bin/python3

"""
Thumbnail generator for KDE/GNOME

Largely based on a script by James Henstridge
(https://askubuntu.com/a/201997)

Unfortunately there seems to be some disagreement between GNOME and KDE
towards how to follow the XDG specs for saving thumbnails. This script
is meant as a workaround to that issue, generating thumbnails that follow
both specifications.

Dependencies: python3 gir1.2-gnomedesktop-3.0 python-pillow

pillow can be installed with `pip install pillow`

You will also need to have the corresponding thumbnailers installed (e.g.
evince-thumbnailer). KDE thumbnailers are not supported. All previews are
generated through GNOME's thumbnail factory and then made compatible with KDE.

Further references:

Thumbnail specifications in KDE/GNOME:

- https://bugs.kde.org/show_bug.cgi?id=393015
- https://api.kde.org/frameworks/kio/html/previewjob_8cpp_source.html
- https://lazka.github.io/pgi-docs/GnomeDesktop-3.0/classes/DesktopThumbnailFactory.html

Setting PNG metadata:

- http://pillow.readthedocs.io/en/5.1.x/PIL.html#PIL.PngImagePlugin.PngInfo
- https://stackoverflow.com/a/10552742/1708932

Copyright: (c) 2012 James Henstridge <https://launchpad.net/~jamesh>
           (c) 2018 Glutanimate <https://glutanimate.com/>
License: MIT license
"""

import os
import sys
from hashlib import md5

from PIL import Image
from PIL import PngImagePlugin

import gi
gi.require_version('GnomeDesktop', '3.0')
from gi.repository import Gio, GnomeDesktop

# FIXME: Hardcoding the Thumbnailer to a generic name
#        regardless of MIME type might not always work
KDE_THUMBNAILER = "KDE Thumbnail Generator"


def update_name_and_meta(thumb_path, filename, mtime, mime_type, size):
    print("Making thumb compatible with KDE...")
    abs_path = os.path.abspath(filename)
    # The spaces in our URI are not escaped. This is not in accordance
    # with the URI RFC2396 which is listed in the freedesktop specs,
    # but it's what KDE currently uses 
    # (cf.: https://bugs.kde.org/show_bug.cgi?id=393015)
    kde_uri = "file://" + abs_path  
    kde_md5 = md5(kde_uri.encode("utf-8")).hexdigest()
    thumb_dir = os.path.dirname(thumb_path)
    kde_thumb_path = os.path.join(thumb_dir, kde_md5 + ".png")

    if os.path.exists(kde_thumb_path):
        print("KDE thumb already exists. Skipping")
        return

    im = Image.open(thumb_path)

    # Set PNG metadata chunk
    meta = PngImagePlugin.PngInfo()
    meta.add_itxt("Software", KDE_THUMBNAILER)
    meta.add_text("Thumb::MTime", str(int(mtime)))
    meta.add_text("Thumb::Mimetype", mime_type)
    meta.add_text("Thumb::Size", str(size))
    meta.add_itxt("Thumb::URI", kde_uri)

    im.save(kde_thumb_path, "png", pnginfo=meta)

    # uncomment this to remove GNOME thumbnails:
    # os.remove(thumb_path)


def make_thumbnail(factory, filename):
    mtime = os.path.getmtime(filename)
    # Use Gio to determine the URI and mime type
    f = Gio.file_new_for_path(filename)
    uri = f.get_uri()
    info = f.query_info(
        'standard::content-type', Gio.FileQueryInfoFlags.NONE, None)
    mime_type = info.get_content_type()
    size = info.get_size()

    if factory.lookup(uri, mtime) is not None:
        print("FRESH       %s" % uri)
        return False

    if not factory.can_thumbnail(uri, mime_type, mtime):
        print("UNSUPPORTED %s" % uri)
        return False

    thumbnail = factory.generate_thumbnail(uri, mime_type)
    if thumbnail is None:
        print("ERROR       %s" % uri)
        return False

    factory.save_thumbnail(thumbnail, uri, mtime)

    thumb_path = factory.lookup(uri, mtime)
    update_name_and_meta(thumb_path, filename, mtime, mime_type, size)

    print("OK          %s" % uri)

    return True


def thumbnail_folder(factory, folder):
    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            make_thumbnail(factory, os.path.join(dirpath, filename))


def main(argv):
    factory = GnomeDesktop.DesktopThumbnailFactory()
    for filename in argv[1:]:
        if os.path.isdir(filename):
            thumbnail_folder(factory, filename)
        else:
            make_thumbnail(factory, filename)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
