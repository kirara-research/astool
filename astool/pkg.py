#!/usr/bin/env python3
import sqlite3
import sys
import struct
import os
import io
from typing import Set, Iterable, Union, TypeVar, Tuple, List
from collections import namedtuple

import plac
import requests

try:
    from . import hwdecrypt
except ImportError:
    import hwdecrypt

MetapackageDownloadTask = namedtuple("MetapackageDownloadTask", ("name", "splits", "is_meta"))
PackageDownloadTask = namedtuple("PackageDownloadTask", ("name", "size", "offset", "is_meta"))
AnyDownloadTask = Union[MetapackageDownloadTask, PackageDownloadTask]


def fast_select(db, query, dset, groups=500):
    llen = None
    cur = db.cursor()

    while dset:
        page = [dset.pop() for _ in range(min(len(dset), groups))]
        if llen != len(page):
            llen = len(page)
            qs = ",".join("?" for _ in range(llen))
            sqls = query.format(qs)

        cur = db.execute(sqls, page)
        yield from cur


class PackageManager(object):
    def __init__(self, master: str, search_paths: Iterable[str]):
        self.search_paths = list(search_paths)
        self.package_state = self.compute_package_state(self.search_paths)
        self.asset_db = sqlite3.connect(master)

    @staticmethod
    def compute_package_state(roots: Iterable[str]):
        package_prefixes = "0123456789abcdefghijklmnopqrstuvwxyz"
        packages = set()
        for root in roots:
            for letter in package_prefixes:
                os.makedirs(os.path.join(root, f"pkg{letter}"), exist_ok=True)
                packages.update(x for x in os.listdir(os.path.join(root, f"pkg{letter}")) if x.startswith(letter))
        return packages

    def lookup_file(self, pack: str) -> str:
        for p in self.search_paths:
            candidate = os.path.join(p, f"pkg{pack[0]}", pack)
            if os.path.exists(candidate):
                return candidate
        return None

    def lookup_all_package_groups(self) -> Iterable[str]:
        for (pkey,) in self.asset_db.execute("SELECT package_key FROM m_asset_package"):
            yield pkey

    def lookup_matching_package_groups(self, patterns: Iterable[str]) -> Iterable[set]:
        seen = set()
        for pat in patterns:
            for (pkey,) in self.asset_db.execute(
                "SELECT package_key FROM m_asset_package WHERE package_key LIKE ?", (pat,)
            ):
                if pkey not in seen:
                    yield pkey
                seen.add(pkey)

    def get_package_group(self, pk: str) -> Tuple[set, set]:
        missing = set()
        partial = set()
        for (req_name,) in self.asset_db.execute(
            "SELECT pack_name FROM m_asset_package_mapping WHERE package_key = ?", (pk,)
        ):
            if req_name not in self.package_state:
                missing.add(req_name)
            else:
                partial.add(req_name)

        return partial, missing

    def get_unreferenced_packages(self) -> set:
        indexed = set(package for package, in self.asset_db.execute("SELECT pack_name FROM m_asset_package_mapping"))
        return self.package_state - indexed

    def resolve_metapackages(self, metas: Set[str]) -> Tuple[set, list]:
        seen_list = set()
        tasks = []

        query = """SELECT pack_name, file_size, metapack_name, metapack_offset
            FROM m_asset_package_mapping WHERE metapack_name IN ({0})
            ORDER BY metapack_name, metapack_offset"""

        split_list = None
        mp_name = None
        for pack_name, file_size, metapack_name, metapack_offset in fast_select(self.asset_db, query, metas):
            if mp_name != metapack_name:
                if mp_name:
                    tasks.append(MetapackageDownloadTask(mp_name, split_list, True))
                mp_name = metapack_name
                split_list = []

            seen_list.add(pack_name)
            split_list.append(PackageDownloadTask(pack_name, file_size, metapack_offset, False))

        if split_list:
            tasks.append(MetapackageDownloadTask(mp_name, split_list, True))

        return seen_list, tasks

    def compute_download_list(self, wanted_pkgs: Set[str]) -> List[AnyDownloadTask]:
        dl = []
        names = set()

        llen = None
        sqls = ""
        cur = self.asset_db.cursor()
        while wanted_pkgs:
            metapackages = set()
            page = [wanted_pkgs.pop() for _ in range(min(len(wanted_pkgs), 500))]
            if llen != len(page):
                llen = len(page)
                qs = ",".join("?" for _ in range(llen))
                sqls = "SELECT DISTINCT pack_name, metapack_name, file_size FROM m_asset_package_mapping WHERE pack_name IN ({0})".format(
                    qs
                )

            for pack_name, metapack_name, file_size in cur.execute(sqls, page):
                if not metapack_name:
                    dl.append(PackageDownloadTask(pack_name, file_size, 0, False))
                else:
                    metapackages.add(metapack_name)

            seen_packages, dl_tasks = self.resolve_metapackages(metapackages)
            dl.extend(dl_tasks)
            wanted_pkgs -= seen_packages

        return dl

    @staticmethod
    def combine_download_lists(dls: Iterable[Iterable[AnyDownloadTask]]) -> List[AnyDownloadTask]:
        combined_names = set()
        deduplicated_dls = []
        for dl in dls:
            for task in dl:
                if task.name not in combined_names:
                    deduplicated_dls.append(task)
                combined_names.add(task.name)

        return deduplicated_dls

    def execute_job_list(self, ice, jobs, done=None, quiet=False):
        url_list = ice.api.asset.getPackUrl({"pack_names": [job.name for job in jobs]})
        if done:
            done(ice)

        if url_list.return_code != 0:
            raise ValueError("Failed to get the url list!")

        url_list = url_list.app_data["url_list"]
        assert len(url_list) == len(jobs)

        for jnum, (job, url) in enumerate(zip(jobs, url_list)):
            canon = job.name
            if job.is_meta:
                if not quiet:
                    print(f"({jnum + 1}/{len(url_list)}) Retrieving {canon} (meta)...")
            else:
                if not quiet:
                    print(f"({jnum + 1}/{len(url_list)}) Retrieving {canon}...")
            rf = requests.get(url, headers={"User-Agent": ice.user_agent})

            if job.is_meta:
                bio = io.BytesIO(rf.content)
                for split in job.splits:
                    bio.seek(split.offset)
                    if not quiet:
                        print(f"    {split.name}...")
                    with open(os.path.join(self.search_paths[-1], f"pkg{split.name[0]}", split.name), "wb") as of:
                        of.write(bio.read(split.size))
            else:
                with open(os.path.join(self.search_paths[-1], f"pkg{canon[0]}", canon), "wb") as of:
                    for chunk in rf.iter_content(chunk_size=0x4000):
                        of.write(chunk)
