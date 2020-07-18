#!/usr/bin/env python3
import sqlite3
import binascii
import os
import struct
import zlib

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


def save_img(pm: pkg.PackageManager, table: str, name: str, key: str):
    rows = pm.asset_db.execute(
        f"SELECT pack_name, head, size, key1, key2 FROM {table} WHERE asset_path = ?", (key,)
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
        print("warn: missing:", name)


def select_deps(asset_db, dep_asset):
    for row in asset_db.execute(
        "SELECT dependency FROM member_model_dependency WHERE asset_path=?", (dep_asset,)
    ):
        yield row[0]


def select_model_bases(data_db):
    for row in data_db.execute(
        "SELECT id, member_m_id, thumbnail_image_asset_path, model_asset_path FROM m_suit"
    ):
        print(f"- {row[1]}_{row[0]}")
        yield f"{row[1]}_{row[0]}", row[2], row[3]


def select_idlers(data_db):
    for row in data_db.execute("SELECT member_m_id, idle_animation_clip_path FROM m_navi_model"):
        print(f"- LibIdle {row[0]}")
        yield row[0], row[1]


def select_anims(pm_asset_db):
    for row in pm_asset_db.execute("SELECT asset_path FROM navi_motion"):
        print(f"- LibAny {row[0]}")
        yield hex(zlib.crc32(row[0].encode("utf8")))[2:], row[0]


def main(
    region: ("The astool region to use.", "option", "r"),
    master: ("Assume master version (that you already have an asset DB for)", "option", "m"),
    output: "Output file name",
):
    context = ctx.ASContext(region or "jp", None, None)

    if not master:
        with context.enter_memo() as memo:
            master = memo["master_version"]

    print("Master:", master)
    md_path = os.path.join(context.masters, master, "masterdata.db")
    data_db = sqlite3.connect(f"file:{md_path}?mode=ro", uri=True)

    pm = pkg.PackageManager(
        os.path.join(context.masters, master, "asset_i_ja.db"), [context.cache]
    )

    for model_base, thumb_asset, unity_asset in select_model_bases(data_db):
        out_base = os.path.join(output, model_base)
        os.makedirs(out_base, exist_ok=True)
        save_img(pm, "texture", os.path.join(out_base, "thumbnail.png"), thumb_asset)
        save_img(pm, "member_model", os.path.join(out_base, "root.unity3d"), unity_asset)

        for i, dependency in enumerate(select_deps(pm.asset_db, unity_asset)):
            if dependency.startswith("§"):
                continue

            save_img(pm, "member_model", os.path.join(out_base, f"file_{i}.unity3d"), dependency)

    os.makedirs(os.path.join(output, "IdleAnimations.library"), exist_ok=True)
    for char_id, unity_asset in select_idlers(data_db):
        save_img(
            pm,
            "navi_motion",
            os.path.join(output, "IdleAnimations.library", f"{char_id}.unity3d"),
            unity_asset,
        )

    os.makedirs(os.path.join(output, "AllAnimations.library"), exist_ok=True)
    for name, unity_asset in select_anims(pm.asset_db):
        save_img(
            pm,
            "navi_motion",
            os.path.join(output, "AllAnimations.library", f"{name}.unity3d"),
            unity_asset,
        )


if __name__ == "__main__":
    plac.call(main)
