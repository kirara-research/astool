#!/usr/bin/env python3
import sqlite3
import sys
import struct
import os
import io
import logging
import asyncio
import time
from typing import Set, Iterable, Union, TypeVar, Tuple, List
from collections import namedtuple
from contextlib import contextmanager

import plac
import requests

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from . import hwdecrypt
except ImportError:
    import hwdecrypt

LOGGER = logging.getLogger("astool.pkg")

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


@contextmanager
def execution_timer(name):
    t = time.monotonic()
    yield
    logging.info("%s: %f s", name, time.monotonic() - t)


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

        query = """SELECT DISTINCT pack_name, file_size, metapack_name, metapack_offset
            FROM m_asset_package_mapping WHERE metapack_name IN ({0})
            ORDER BY metapack_name, metapack_offset"""

        split_list = None
        mp_name = None
        for pack_name, file_size, metapack_name, metapack_offset in fast_select(self.asset_db, query, metas):
            if mp_name != metapack_name:
                if mp_name:
                    split_list.sort(key=lambda x: x.offset)
                    tasks.append(MetapackageDownloadTask(mp_name, split_list, True))
                mp_name = metapack_name
                split_list = []

            seen_list.add(pack_name)
            split_list.append(PackageDownloadTask(pack_name, file_size, metapack_offset, False))

        if split_list:
            split_list.sort(key=lambda x: x.offset)
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

    def execute_job_list(self, ice, jobs, done=None):
        url_list = ice.api.asset.getPackUrl({"pack_names": [job.name for job in jobs]})
        ua = ice.user_agent
        if done:
            done(ice)

        if url_list.return_code != 0:
            raise ValueError("Failed to get the url list!")

        url_list = url_list.app_data["url_list"]
        assert len(url_list) == len(jobs)

        if aiohttp and not os.environ.get("ASTOOL_NEVER_AIO"):
            asyncio.run(self.download_with_aiohttp(zip(jobs, url_list), len(jobs), ua))
        else:
            self.download_with_requests(zip(jobs, url_list), len(jobs), ua)

    def meta_list_is_monotonic(self, split_list: Iterable[PackageDownloadTask]):
        offset = 0
        for j in split_list:
            if j.offset < offset:
                return False
            offset = j.offset + j.size

        return True

    def destination_for_new_file(self, package_name: str):
        return os.path.join(self.search_paths[-1], f"pkg{package_name[0]}", package_name)

    async def aio_download_task(self, session, queue, user_agent):
        while not queue.empty():
            task, url = await queue.get()
            canon = task.name
            logging.info("Begin retrieving %s, %d left...", canon, queue.qsize())
            resp = await session.get(url)
            # logging.info("Checkpoint %s: response received...", canon)

            if task.is_meta:
                assert self.meta_list_is_monotonic(task.splits)
                offset = 0

                for split in task.splits:
                    # logging.info("Checkpoint %s: beginning demux for %s...", canon, split.name)
                    if offset < split.offset:
                        rem = split.offset - offset
                        while rem:
                            chunk = await resp.content.read(min(0x10000, rem))
                            if not chunk:
                                break
                            rem -= len(chunk)
                            offset += len(chunk)

                    assert offset == split.offset, f"{canon}: {split.name} not aligned at start"

                    rem = split.size
                    with open(self.destination_for_new_file(split.name), "wb") as of:
                        while True:
                            chunk = await resp.content.read(min(0x10000, rem))
                            if not chunk:
                                break
                            of.write(chunk)
                            offset += len(chunk)
                            rem -= len(chunk)

                    assert rem == 0, f"{canon}: {split.name} not fully written"
                    self.package_state.add(split.name)
            else:
                # logging.info("Checkpoint %s: beginning demux for %s...", canon, canon)
                with open(self.destination_for_new_file(canon), "wb") as of:
                    while True:
                        chunk = await resp.content.read(0x10000)
                        if not chunk:
                            break
                        of.write(chunk)

                self.package_state.add(canon)

            queue.task_done()
            # logging.info("Done retrieving %s, %d left...", canon, queue.qsize())

    async def download_with_aiohttp(self, jobs, count, user_agent):
        with execution_timer("Prepare queue"):
            queue = asyncio.Queue()
            for job in jobs:
                queue.put_nowait(job)

        with execution_timer("Download tasks"):
            async with aiohttp.ClientSession(headers={"User-Agent": user_agent}) as session:
                tasks = []
                for i in range(10):
                    task = asyncio.create_task(self.aio_download_task(session, queue, user_agent))
                    tasks.append(task)

                tasks.append(asyncio.create_task(queue.join()))
                await asyncio.gather(*tasks)

    def download_with_requests(self, jobs, count, user_agent):
        dl_session = requests.Session()

        for i, (job, url) in enumerate(jobs):
            canon = job.name
            LOGGER.info("(%d/%d) Retrieving %s...", i + 1, count, canon)
            rf = dl_session.get(url, headers={"User-Agent": user_agent})

            if job.is_meta:
                bio = io.BytesIO(rf.content)
                for split in job.splits:
                    bio.seek(split.offset)
                    LOGGER.debug("    %s...", split.name)
                    with open(self.destination_for_new_file(split.name), "wb") as of:
                        of.write(bio.read(split.size))
                    self.package_state.add(split.name)
            else:
                with open(self.destination_for_new_file(canon), "wb") as of:
                    for chunk in rf.iter_content(chunk_size=0x10000):
                        of.write(chunk)
                self.package_state.add(canon)

        dl_session.close()
