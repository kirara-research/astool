#!/usr/bin/env python3
import sqlite3
import binascii
import os
import struct
import logging
from typing import Optional, Sequence

import plac

import hwdecrypt
from astool import ctx, pkg

SEARCH_PATHS = []


def write_signal(signal_pth: Optional[str]):
    if signal_pth is not None:
        with open(signal_pth, "wb") as sigf:
            sigf.write(b"ready\n")
            sigf.flush()


def ensure_assets_available(
    pm: pkg.PackageManager,
    context: ctx.ASContext,
    gather_list: Sequence[str],
    signal_pth: str = None,
):
    # First, get the list of packages we already have.
    packages = set()

    for k in gather_list:
        # Convert asset names to their containing packages.
        val = pm.asset_db.execute(
            "SELECT pack_name FROM texture WHERE asset_path = ?", (k,)
        ).fetchone()
        if val:
            if val[0] not in pm.package_state:
                packages.add(val[0])
        else:
            print(f"warning: cannot resolve {k} to a package name. this will cause issues later.")

    if packages:
        # Convert the list of packages to a list of downloads.
        # This will select metapackages if needed.
        task_list = pm.compute_download_list(packages)

        # Now execute to the cache path. Metapackages will be unpacked.
        ice = context.get_iceapi()

        def on_release_iceapi(ice):
            write_signal(signal_pth)
            context.release_iceapi(ice)

        pm.execute_job_list(ice, task_list, done=on_release_iceapi)
    else:
        write_signal(signal_pth)


def to_unsigned(i):
    return struct.unpack("<I", struct.pack("<i", i))[0]


def main(
    region: ("The astool region to use.", "option", "r"),
    master: ("Assume master version (that you already have an asset DB for)", "option", "m"),
    signal_cts: ("Path to write 'ready' to when finished using SAPI.", "option", "sfd"),
    lang: ("Language code", "option", "l"),
    quiet: ("Suppress most output", "flag", "q"),
):
    context = ctx.ASContext(region or "jp", None, None)

    if not master:
        with context.enter_memo() as memo:
            master = memo["master_version"]

    if not lang:
        lang = "ja"

    if not quiet:
        logging.basicConfig(format="srb:  %(levelname)s: %(message)s", level=logging.DEBUG)

    logging.info("Master: %s", master)
    md_path = os.path.join(context.masters, master, "masterdata.db")
    logging.info("path: %s", md_path)
    data_db = sqlite3.connect(f"file:{md_path}?mode=ro", uri=True)

    pm = pkg.PackageManager(
        os.path.join(context.masters, master, f"asset_i_{lang}.db"), [context.cache]
    )

    to_gather = []

    for (path,) in data_db.execute("SELECT path FROM m_decoration_texture"):
        to_gather.append(path)
        logging.debug("Asset: %s", path)

    logging.info("Need %d files", len(to_gather))
    # Download anything we need.
    ensure_assets_available(pm, context, to_gather, signal_pth=signal_cts)


if __name__ == "__main__":
    plac.call(main)
