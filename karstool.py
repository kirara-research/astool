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
import plac

from libpenguin import karsffi

try:
    import astool
except ImportError:
    import sv_config as astool

try:
    import iceapi
except ImportError:
    iceapi = None
    print("IceAPI is not available. astool integration is disabled.")

# Thanks to esterTion and CPPO for help

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
    def __init__(self, name, sha, si):
        self.name = name
        self.sha = sha
        self.encrypted_sha = None
        self.size = None
        self.keys = si["master_keys"]

    def getkeys(self):
        keys = [int(self.sha[:8], 16), int(self.sha[8:16], 16), int(self.sha[16:24], 16)]
        return [a ^ b for a, b in zip(self.keys, keys)]

    def __repr__(self):
        return "<FileReference {0} {1} {2} {3} {4}>".format(self.name, self.sha, self.encrypted_sha, self.size, self.getkeys())

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
            self.files.append(FileReference(na, ha, fromsi))

        for i in range(nfentries):
            sha1 = binascii.hexlify(eatbytes(fobj, 20)).decode("ascii")
            size = uint(fobj)
            self.files[i].encrypted_sha = sha1
            self.files[i].size = size

    def __repr__(self):
        return ("<Manifest {0} {1}>:\n".format(self.version, self.lang) +
            "\n".join("    " + repr(x) for x in self.files))

def vercmp(a, b):
    aa = a.split(".")
    bb = b.split(".")

    for av, bv in zip_longest(aa, bb, fillvalue="0"):
        if av == bv:
            continue
        if av > bv:
            return 1
        else:
            return -1
    return 0

def resolve_server_config(candidates, exact=None):
    if exact is not None:
        for v in candidates:
            if v["bundle_version"] == exact:
                return v
        raise ValueError(f"There is no astool server configuration that matches the exact version {exact}.")

    the_max = None
    for v in candidates:
        if not the_max or vercmp(v["bundle_version"], the_max["bundle_version"]) > 0:
            the_max = v

    return the_max

def live_master_check(tag, server_configuration):
    with astool.astool_memo(tag) as memo:
        uid = memo.get("user_id")
        pwd = memo.get("password")
        auc = memo.get("auth_count")
        fast_resume = memo.get("resume_data")

    if not all((uid, pwd)):
        raise ValueError("You need an account to do that.")

    ice = iceapi.ICEBinder(server_configuration, "iOS", uid, pwd, auc)
    if not ice.resume_session(fast_resume):
        ret = ice.api.login.login()
        if ret.return_code != 0:
            print("Login failed, trying to reset auth count...")
            ice.set_login(uid, pwd, ret.app_data.get("authorization_count") + 1)
            ice.api.login.login()

    with astool.astool_memo(tag) as memo:
        memo["master_version"] = ice.master_version
        memo["auth_count"] = ice.auth_count
        memo["resume_data"] = ice.save_session()

    return ice.master_version

def file_is_valid(local_root, file):
    p = os.path.join(local_root, f"enc_{file.name}")
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

def download_one(user_agent, remote_root, local_root, file):
    rf = requests.get(f"{remote_root}/{file.name}",
        headers={"User-Agent": user_agent})

    ks = file.getkeys()
    keys = karsffi.PenguinKeyset(ks[0], ks[1], ks[2])
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

    with open(os.path.join(local_root, f"enc_{file.name}"), 'wb') as enc_fd, \
        open(os.path.join(local_root, f"{file.name}"), 'wb') as use_fd:
        for chunk in rf.iter_content(chunk_size=0x4000):
            enc_fd.write(chunk)
            karsffi.decrypt(keys, chunk)
            #use_fd.write(chunk)
            use_fd.write(decompressor.decompress(chunk))
        use_fd.write(decompressor.flush())

def main(force: ("Download files even if they are valid", "flag", "f"),
         master: ("Master version to download against", "option", "m"),
         bundle: ("Bundle version to download against", "option", "b"),
         server: ("Server to download against", "option", "r")):
    logging.basicConfig(level=logging.INFO)
    karsffi.init()

    if not server or server not in astool.SERVER_CONFIG:
        server = "jp"

    if iceapi is None and not master:
        print("You need to provide the master version (./karstool -m <version>).")
        return

    try:
        server_configuration = resolve_server_config(astool.SERVER_CONFIG[server], bundle)
    except ValueError as e:
        print(f"Failed to resolve server configuration: {str(e)}")
        return

    if not master:
        if os.getenv("LIVE_MASTER_CHECK_ALLOWED"):
            mv = live_master_check(server, server_configuration)
        else:
            with astool.astool_memo(server) as memo:
                mv = memo["master_version"]
    else:
        mv = master

    print(f"Master: {mv}, Application: {server_configuration['bundle_version']}")
    root = server_configuration["root"] + f"/static/{mv}"
    local_store = os.path.join(os.getenv("ASTOOL_STORAGE", ""), server,
        "masters", mv)
    os.makedirs(local_store, exist_ok=True)

    r = requests.get(f"{root}/masterdata_i_ja",
        headers={"User-Agent": server_configuration["user_agent"]})
    if r.status_code != 200:
        print(f"Could not get the manifest for version {mv}, is it out of date?")
        print(f"The original status code was {r.status_code}.")
        return

    with open(os.path.join(local_store, "masterdata_i_ja"), "wb") as rm:
        rm.write(r.content)

    manifest = Manifest(io.BytesIO(r.content), server_configuration)
    for file in manifest.files:
        if not file_is_valid(local_store, file) or force:
            print(f"Retrieving and decrypting {file.name}...")
            download_one(server_configuration["user_agent"], root, local_store, file)
        else:
            print(f"File {file.name} is still valid!")

if __name__ == '__main__':
    plac.call(main)
