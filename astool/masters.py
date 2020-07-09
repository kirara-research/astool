#!/usr/bin/env python3
# Produces the following structure:
# $ASTOOL_STORAGE
#  |
#  + masters
#    |
#    + <version>
#      |
#      + dbs.....
# Change the root by exporting ASTOOL_STORAGE.

import sys
import os
import struct
import binascii
import subprocess
import zlib
import io
import logging
import hashlib
from itertools import zip_longest

import requests

try:
    from . import hwdecrypt
except ImportError:
    import hwdecrypt

# Thanks to esterTion and CPPO for help

LOGGER = logging.getLogger("astool.masters")


def eatbytes(stream, n):
    return stream.read(n)


def prefixstring(stream):
    ln = ubyte(stream)
    return stream.read(ln).decode("ascii")


def ubyte(stream):
    return struct.unpack("<B", stream.read(1))[0]


def uint(stream):
    return struct.unpack("<I", stream.read(4))[0]


class FileReference(object):
    def __init__(self, version, name, sha, si):
        self.version = version
        self.name = name
        self.sha = sha
        self.encrypted_sha = None
        self.size = None
        self.keys = si["master_keys"]

    def getkeys(self):
        keys = [int(self.sha[:8], 16), int(self.sha[8:16], 16), int(self.sha[16:24], 16)]
        return [a ^ b for a, b in zip(self.keys, keys)]

    def __repr__(self):
        return "<FileReference {0} {1} {2} {3} {4}>".format(
            self.name, self.sha, self.encrypted_sha, self.size, self.getkeys()
        )


class Manifest(object):
    def __init__(self, fobj, fromsi):
        sha1hash = eatbytes(fobj, 20)
        self.version = prefixstring(fobj)
        self.lang = prefixstring(fobj)

        self.files = []
        nfentries = ubyte(fobj)
        for i in range(nfentries):
            na = prefixstring(fobj)
            ha = prefixstring(fobj)
            self.files.append(FileReference(self.version, na, ha, fromsi))

        for i in range(nfentries):
            sha1 = binascii.hexlify(eatbytes(fobj, 20)).decode("ascii")
            size = uint(fobj)
            self.files[i].encrypted_sha = sha1
            self.files[i].size = size

    def __repr__(self):
        return "<Manifest {0} {1}>:\n".format(self.version, self.lang) + "\n".join(
            "    " + repr(x) for x in self.files
        )


def download_remote_manifest(context, master_version, force=False, platform_code="i", lang_code=None):
    root = context.server_config["root"] + f"/static/{master_version}"
    local_store = os.path.join(context.masters, master_version)
    os.makedirs(local_store, exist_ok=True)

    if lang_code is None:
        lang_code = context.server_config.get("language", "ja")

    dest = os.path.join(local_store, f"masterdata_{platform_code}_{lang_code}")
    if os.path.exists(dest) and not force:
        with open(dest, "rb") as f:
            try:
                return Manifest(f, context.server_config)
            except Exception as e:
                LOGGER.warning("Can't read the disk manifest, trying to download a fresh one.")

    r = requests.get(
        f"{root}/masterdata_{platform_code}_{lang_code}",
        headers={"User-Agent": context.server_config["user_agent"]},
    )
    if r.status_code != 200:
        LOGGER.error("Could not get the manifest for version %s, is it out of date?", master_version)
        LOGGER.error("The original status code was %d.", r.status_code)
        return None

    with open(dest, "wb") as rm:
        rm.write(r.content)

    return Manifest(io.BytesIO(r.content), context.server_config)


def file_is_valid(context, file: FileReference):
    local_store = os.path.join(context.masters, file.version)

    p = os.path.join(local_store, "enc", file.name)
    if not os.path.exists(p):
        return False

    h = hashlib.sha1()
    with open(p, "rb") as stream:
        while 1:
            chunk = stream.read(0x4000)
            if not chunk:
                break
            h.update(chunk)

    if file.encrypted_sha == h.hexdigest():
        return True
    return False


def download_one(context, file: FileReference):
    local_store = os.path.join(context.masters, file.version)
    remote_root = context.server_config["root"] + f"/static/{file.version}"

    rf = requests.get(
        f"{remote_root}/{file.name}", headers={"User-Agent": context.server_config["user_agent"]}
    )

    ks = file.getkeys()
    keys = hwdecrypt.Keyset(ks[0], ks[1], ks[2])
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

    os.makedirs(os.path.join(local_store, "enc"), exist_ok=True)

    with open(os.path.join(local_store, "enc", file.name), "wb") as enc_fd, open(
        os.path.join(local_store, file.name), "wb"
    ) as use_fd:
        for chunk in rf.iter_content(chunk_size=0x4000):
            enc_fd.write(chunk)
            copy = bytearray(chunk)
            hwdecrypt.decrypt(keys, copy)
            use_fd.write(decompressor.decompress(copy))
        use_fd.write(decompressor.flush())
