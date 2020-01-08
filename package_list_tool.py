#!/usr/bin/env python3
import sqlite3
import sys
import struct
import os
import io
from typing import Set, Iterable, Union
from collections import namedtuple

import plac
import requests

import hwdecrypt

if __name__ == "__main__":
    import astool
else:
    from . import astool

MetapackageDownloadTask = namedtuple("MetapackageDownloadTask", ("name", "splits", "is_meta"))
PackageDownloadTask = namedtuple("PackageDownloadTask", ("name", "size", "offset", "is_meta"))
AnyDownloadTask = Union[MetapackageDownloadTask, PackageDownloadTask]

def get_file(search_paths, pack):
    for p in search_paths:
        candidate = os.path.join(p, f"pkg{pack[0]}", pack)
        if os.path.exists(candidate):
            return candidate
    return None

def get_package_state(roots: Iterable[str]):
    package_prefixes = "0123456789abcdefghijklmnopqrstuvwxyz"
    packages = set()
    for root in roots:
        for letter in package_prefixes:
            packages.update(x for x in os.listdir(os.path.join(root, f"pkg{letter}"))
                if x.startswith(letter))
    return packages

def get_asset_db_groups(db: sqlite3.Connection):
    for pkey, in db.execute("SELECT package_key FROM m_asset_package"):
        yield pkey

def get_match_packages(db: sqlite3.Connection, patterns: Iterable[str]):
    seen = set()
    for pat in patterns:
        for pkey, in db.execute("SELECT package_key FROM m_asset_package WHERE package_key LIKE ?", (pat,)):
            if pkey not in seen:
                yield pkey
            seen.add(pkey)

def get_package_group_info(have: Set[str], db: sqlite3.Connection, pk: str):
    missing = set()
    partial = set()
    for req_name, in db.execute("SELECT pack_name FROM m_asset_package_mapping WHERE package_key = ?", (pk,)):
        if req_name not in have:
            missing.add(req_name)
        else:
            partial.add(req_name)

    return partial, missing

def compute_download_list(wanted_pkgs: Set[str], db: sqlite3.Connection):
    dl = []
    names = set()
    for pack_name in wanted_pkgs:
        if pack_name in names:
            continue

        row = db.execute("SELECT metapack_name, file_size FROM m_asset_package_mapping WHERE pack_name = ?",
            (pack_name,)).fetchone()
        if row and row[0]:
            if row[0] in names:
                continue

            splitlist = []
            contents = db.execute("""SELECT pack_name, file_size, metapack_offset
                FROM m_asset_package_mapping WHERE metapack_name = ?
                ORDER BY metapack_offset""", (row[0],))
            for a, b, c in contents:
                splitlist.append(PackageDownloadTask(a, b, c, False))
            dl.append(MetapackageDownloadTask(row[0], splitlist, True))
            names.add(row[0])
        else:
            dl.append(PackageDownloadTask(pack_name, row[1], 0, False))
            names.add(pack_name)
    return dl

def combine_download_lists(dls: Iterable[Iterable[AnyDownloadTask]]):
    combined_names = set()
    deduplicated_dls = []
    for dl in dls:
        for task in dl:
            if task.name not in combined_names:
                deduplicated_dls.append(task)
            combined_names.add(task.name)

    return deduplicated_dls

def to_unsigned(i: int) -> int:
    return struct.unpack("<I", struct.pack("<i", i))[0]

def external_asset_cache():
    root = os.path.join(os.getenv("ASTOOL_STORAGE", ""), astool.g_SI_TAG, "cache")
    package_prefixes = "0123456789abcdefghijklmnopqrstuvwxyz"
    packages = set()
    for letter in package_prefixes:
        os.makedirs(os.path.join(root, f"pkg{letter}"), exist_ok=True)
    return root

def execute_job_list(jobs, dest):
    url_list = astool.sign_package_urls(job.name for job in jobs)
    assert len(url_list) == len(jobs)

    user_agent = astool.g_SI_DEFAULT["user_agent"]
    for jnum, (job, url) in enumerate(zip(jobs, url_list)):
        canon = job.name
        if job.is_meta:
            print(f"({jnum + 1}/{len(url_list)}) Retrieving {canon} (meta)...")
        else:
            print(f"({jnum + 1}/{len(url_list)}) Retrieving {canon}...")
        rf = requests.get(url, headers={"User-Agent": user_agent})

        if job.is_meta:
            bio = io.BytesIO(rf.content)
            for split in job.splits:
                bio.seek(split.offset)
                print(f"    {split.name}...")
                with open(os.path.join(dest, f"pkg{split.name[0]}", split.name), "wb") as of:
                    of.write(bio.read(split.size))
        else:
            with open(os.path.join(dest, f"pkg{canon[0]}", canon), "wb") as of:
                for chunk in rf.iter_content(chunk_size=0x4000):
                    of.write(chunk)

def get_unreferenced_packages(have: Iterable[str], db: sqlite3.Connection):
    indexed = set(
        package for package, in db.execute(
            "SELECT pack_name FROM m_asset_package_mapping")
    )
    return have - indexed

SEARCH_PATHS = []

def main(master: ("Assume master version (that you already have an asset DB for)", "option", "m"),
         server: ("Server version", "option", "r"),
         validate_only: ("Don't download anything, just validate.", "flag", "n"),
         validate_incomplete_only: ("When validating, print only incomplete packages.", "flag", "i"),
         subcmd: "Command: sync or gc",
        *packages: "Packages to validate or complete"):
    """package_list_tool maintains your local SIFAS asset cache."""
    if not server or server not in astool.SERVER_CONFIG:
        server = "jp"

    astool.g_SI_TAG = server
    astool.g_SI_DEFAULT = astool.resolve_server_config(astool.SERVER_CONFIG[server])

    SEARCH_PATHS.append(external_asset_cache())

    if not master:
        with astool.astool_memo() as memo:
            master = memo["master_version"]

    print("Master:", master)
    path = os.path.join(os.getenv("ASTOOL_STORAGE", ""), astool.g_SI_TAG, "masters",
        master, "asset_i_ja_0.db")
    asset_db = sqlite3.connect(path)

    print("Building package list...", end=" ")
    p = get_package_state(SEARCH_PATHS)
    print(f"{len(p)} packages.")

    if subcmd == "gc":
        return main_gc(p, asset_db, validate_only)
    elif subcmd == "sync":
        return main_pmtool(p, asset_db, validate_only, validate_incomplete_only, packages)
    else:
        print("Unknown command:", subcmd)
        return 1

def main_gc(p, asset_db, validate_only):
    garbage = get_unreferenced_packages(p, asset_db)
    print(garbage)
    freeable = 0

    for pkg in garbage:
        freeable += os.path.getsize(get_file(SEARCH_PATHS, pkg))
        if not validate_only:
            print(f"Removing {pkg}...")
            fqpkg = get_file(SEARCH_PATHS, pkg)
            if fqpkg:
                os.unlink(fqpkg)

    print("{0} bytes ({1:.3f} MB) {2} freed by deleting these unused packages."
        .format(freeable, freeable / (1024 * 1024), "can be" if validate_only else "were"))

def main_pmtool(p, asset_db, validate_only, dash_i, packages):
    if len(packages) == 1 and packages[0] == "everything":
        packages = get_asset_db_groups(asset_db)
    else:
        packages = get_match_packages(asset_db, packages)

    dt = []
    print("Validating packages...")
    for package_group in packages:
        have, donthave = get_package_group_info(p, asset_db, package_group)

        if donthave:
            print(f"Validating '{package_group}'...", end=" ")
            print("\x1b[31m", end="")
            print(f"{len(have)}/{len(have) + len(donthave)} \x1b[0m")
        elif not dash_i:
            print(f"Validating '{package_group}'...", end=" ")
            print("\x1b[32m", end="")
            print(f"{len(have)}/{len(have) + len(donthave)} \x1b[0m")

        if donthave:
            download_list = compute_download_list(donthave, asset_db)
            dt.append(download_list)

    dt = combine_download_lists(dt)
    if dt:
        print("Update statistics:")
        print(f"  {len(dt)} jobs,")
        npkg = sum(1 if isinstance(x, PackageDownloadTask) else len(x.splits)
            for x in dt)
        print(f"  {npkg} new packages,")
        nbytes = sum(x.size if isinstance(x, PackageDownloadTask) else sum(y.size for y in x.splits)
            for x in dt)
        print("  {0} bytes, ({1:.3f} MB).".format(nbytes, nbytes / (1024 * 1024)))
    else:
        print("All packages are up to date. There is nothing to do.")

    if dt and not validate_only:
        execute_job_list(dt, external_asset_cache())

if __name__ == '__main__':
    plac.call(main)
    # main2()
