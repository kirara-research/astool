#!/usr/bin/env python3
import sqlite3
import binascii
import os
import struct

import plac

import hwdecrypt
from astool import ctx, pkg

SEARCH_PATHS = []


def ensure_assets_available(pm: pkg.PackageManager, context: ctx.ASContext, gather_list: set):
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
        pm.execute_job_list(ice, task_list, done=context.release_iceapi)


def to_unsigned(i):
    return struct.unpack("<I", struct.pack("<i", i))[0]


def save_img(pm: pkg.PackageManager, name: str, key: str):
    rows = pm.asset_db.execute(
        "SELECT pack_name, head, size, key1, key2 FROM texture WHERE asset_path = ?", (key,)
    )
    pack, off, size, k1, k2 = rows.fetchone()
    k1 = to_unsigned(k1)
    k2 = to_unsigned(k2)

    try:
        if os.path.exists(name):
            return

        buf = bytearray(size)
        with open(pm.lookup_file(pack), "rb") as src:
            src.seek(off)
            src.readinto(buf)
        keyset = hwdecrypt.Keyset(k1, k2, 0x3039)
        hwdecrypt.decrypt(keyset, buf)

        with open(name, "wb") as dst:
            dst.write(buf)
    except Exception as e:
        print(e)


def main(
    region: ("The astool region to use.", "option", "r"),
    master: ("Assume master version (that you already have an asset DB for)", "option", "m"),
    output: ("Where to put images", "option", "o"),
):
    context = ctx.ASContext(region or "jp", None, None)

    if not master:
        with context.enter_memo() as memo:
            master = memo["master_version"]

    if not output:
        output = "out"
        os.makedirs(output, exist_ok=True)

    print("Master:", master)
    md_path = os.path.join(context.masters, master, "masterdata.db")
    print(md_path)
    data_db = sqlite3.connect(f"file:{md_path}?mode=ro", uri=True)

    pm = pkg.PackageManager(
        os.path.join(context.masters, master, "asset_i_ja.db"), [context.cache]
    )

    to_gather = []
    destinations = []

    for cid, at, ia, ta in data_db.execute(
        """SELECT card_m_id, appearance_type, image_asset_path,
            thumbnail_asset_path
        FROM m_card_appearance"""
    ):
        att = "normal" if at == 1 else "awaken"

        to_gather.append(ia)
        destinations.append(os.path.join(output, f"tex_card_{cid}_{att}.jpg"))
        to_gather.append(ta)
        destinations.append(os.path.join(output, f"tex_card_{cid}_{att}.png"))
        print(f"card: {cid}, {att}")

    # Download anything we need.
    ensure_assets_available(pm, context, to_gather)

    # Save images
    for destination, asset_id in zip(destinations, to_gather):
        save_img(pm, destination, asset_id)


if __name__ == "__main__":
    plac.call(main)
