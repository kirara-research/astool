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

import os
import json
import struct
import binascii
import tempfile
import zlib
import io
import logging
import hashlib

from .sv_config import ServerConfiguration
from .ctx import ASContext
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
    def __init__(self, fobj, fromsi: ServerConfiguration):
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


def download_remote_manifest(
    context: ASContext, master_version: str, force=False, platform_code="i", lang_code=None
):
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

    r = context.session.get(
        f"{root}/masterdata_{platform_code}_{lang_code}",
        headers={"User-Agent": context.server_config["user_agent"]},
    )
    if r.status_code != 200:
        LOGGER.error(
            "Could not get the manifest for version %s, is it out of date?", master_version
        )
        LOGGER.error("The original status code was %d.", r.status_code)
        return None

    with open(dest, "wb") as rm:
        rm.write(r.content)

    with open(os.path.join(local_store, f"auxinfo_{platform_code}"), "w") as auxinfo:
        json.dump({"bundle_version": context.server_config["bundle_version"]}, auxinfo)

    return Manifest(io.BytesIO(r.content), context.server_config)


def file_is_valid(context: ASContext, file: FileReference):
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


def download_one(context: ASContext, file: FileReference):
    local_store = os.path.join(context.masters, file.version)
    remote_root = context.server_config["root"] + f"/static/{file.version}"

    rf = context.session.get(
        f"{remote_root}/{file.name}", headers={"User-Agent": context.server_config["user_agent"]}
    )

    ks = file.getkeys()
    keys = hwdecrypt.Keyset(ks[0], ks[1], ks[2])
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

    os.makedirs(os.path.join(local_store, "enc"), exist_ok=True)

    dest_enc_filename = os.path.join(local_store, "enc", file.name)
    dest_filename = os.path.join(local_store, file.name)

    enc_fd = tempfile.NamedTemporaryFile("wb", dir=local_store, prefix="._astool_temp", delete=False)
    clear_fd = tempfile.NamedTemporaryFile("wb", dir=local_store, prefix="._astool_temp", delete=False)

    with enc_fd, clear_fd:
        for chunk in rf.iter_content(chunk_size=0x4000):
            enc_fd.write(chunk)
            copy = bytearray(chunk)
            hwdecrypt.decrypt(keys, copy)
            clear_fd.write(decompressor.decompress(copy))
        clear_fd.write(decompressor.flush())
    
    # Order is important here because file_is_valid only checks the status of the encrypted file.
    os.chmod(clear_fd.name, 0o644)
    try:
        os.unlink(dest_filename)
    except FileNotFoundError:
        pass
    os.rename(clear_fd.name, dest_filename)

    os.chmod(enc_fd.name, 0o644)
    try:
        os.unlink(dest_enc_filename)
    except FileNotFoundError:
        pass
    os.rename(enc_fd.name, dest_enc_filename)

def update_current_link(context: ASContext, master: str):
    sym_path = os.path.join(context.masters, "current")
    if os.path.exists(sym_path) and not os.path.islink(sym_path):
        raise FileExistsError(f"Cannot replace current link at {sym_path}, it exists and is not a symlink.")

    try:
        os.remove(sym_path)
    except FileNotFoundError:
        pass

    os.symlink(master, sym_path)
