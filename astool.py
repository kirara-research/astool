#!/usr/bin/env python3
import logging
import contextlib
import sys
import json
import io
import os
import zlib
from datetime import datetime
from itertools import zip_longest

import requests

try:
    from . import iceapi
    from .sv_config import SERVER_CONFIG
except ImportError:
    import iceapi
    from sv_config import SERVER_CONFIG

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

g_SI_DEFAULT = None
g_SI_TAG = None

def calc_time_offset():
    utc = datetime.utcnow().timestamp()
    local = datetime.now().timestamp()
    return local - utc

@contextlib.contextmanager
def astool_memo(si_tag=None):
    if si_tag is None:
        si_tag = g_SI_TAG

    store = os.path.join(os.getenv("ASTOOL_STORAGE", ""), si_tag, "astool_store.json")
    try:
        with open(store, "r") as js:
            memo = json.load(js)
    except FileNotFoundError:
        memo = {}

    yield memo

    with open(store, "w") as js:
        json.dump(memo, js)

def sign_package_urls(url_list):
    with astool_memo() as memo:
        uid = memo.get("user_id")
        pwd = memo.get("password")
        auc = memo.get("auth_count")
        fast_resume = memo.get("resume_data")

    if not all((uid, pwd, auc)):
        raise ValueError("You need an account to do that.")

    ice = iceapi.ICEBinder(g_SI_DEFAULT, "iOS", uid, pwd, auc)
    if not ice.resume_session(fast_resume):
        ret = ice.api.login.login()
        if ret.return_code != 0:
            print("Login failed, trying to reset auth count...")
            ice.set_login(uid, pwd, ret.app_data.get("authorization_count") + 1)
            ice.api.login.login()

    ret = ice.api.asset.getPackUrl({
        "pack_names": [str(x) for x in url_list]
    })

    with astool_memo() as memo:
        memo["master_version"] = ice.master_version
        memo["auth_count"] = ice.auth_count
        memo["resume_data"] = ice.save_session()

    return ret.app_data.get("url_list")

def command_accept_tos(argv):
    with astool_memo() as memo:
        uid = memo.get("user_id")
        pwd = memo.get("password")
        auc = memo.get("auth_count")
        fast_resume = memo.get("resume_data")

    if not all((uid, pwd, auc)):
        raise ValueError("You need an account to do that.")

    ice = iceapi.ICEBinder(g_SI_DEFAULT, "iOS", uid, pwd, auc)
    if not ice.resume_session(fast_resume):
        ret = ice.api.login.login()
        if ret.return_code != 0:
            print("Login failed, trying to reset auth count...")
            ice.set_login(uid, pwd, ret.app_data.get("authorization_count") + 1)
            ice.api.login.login()

    ret = ice.api.terms.agreement({"terms_version": 1})
    if ret.return_code == 0:
        print("astool: Agreed to the terms of service...")

    with astool_memo() as memo:
        memo["master_version"] = ice.master_version
        memo["auth_count"] = ice.auth_count
        memo["resume_data"] = ice.save_session()

def command_bootstrap(argv):
    ice = iceapi.ICEBinder(g_SI_DEFAULT, "iOS", None, None, 0)
    ret = ice.api.login.startup({
        "resemara_detection_identifier": "",
        # FIXME: The offset is from UTC, but ignores DST. Which we can't calculate
        #   without pulling in pytz.
        "time_difference": 0,
    })

    print(ret.app_data)
    with astool_memo() as memo:
        memo["user_id"] = ret.app_data.get("user_id")
        memo["password"] = ret.app_data.get("authorization_key")
        memo["auth_count"] = 0

    ice.set_login(memo["user_id"], memo["password"], 1)
    ice.api.login.login()
    ret = ice.api.terms.agreement({"terms_version": 1})
    if ret.return_code == 0:
        print("astool: Agreed to the terms of service...")
    else:
        print(ret.return_code, ret.app_data)
    print("astool: Bootstrapped with id={0}, pw={1}".format(
        memo["user_id"], memo["password"]))

    with astool_memo() as memo:
        memo["auth_count"] = 1

def command_sign_package_urls(argv):
    print(sign_package_urls(argv))

def command_resolve_svc(argv):
    print(g_SI_DEFAULT["bundle_version"])

COMMANDS = {
    "bootstrap": command_bootstrap,
    "sign_package_urls": command_sign_package_urls,
    "accept_tos": command_accept_tos,
    "resolve": command_resolve_svc,
}
def main():
    global g_SI_TAG, g_SI_DEFAULT
    logging.basicConfig(level=logging.INFO)

    args = sys.argv[1:]
    si_tag = args.pop(0)
    g_SI_TAG = si_tag
    g_SI_DEFAULT = resolve_server_config(SERVER_CONFIG[g_SI_TAG])

    cmd = args.pop(0)
    if cmd not in COMMANDS:
        print("astool: Unrecognized command")
        rc = 1
    else:
        rc = COMMANDS[cmd](args)
    sys.exit(rc or 0)

if __name__ == '__main__':
    main()
