import os
import logging
import json
from itertools import zip_longest
from contextlib import contextmanager

from . import iceapi
from .sv_config import SERVER_CONFIG

LOGGER = logging.getLogger("astool.scfg")

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
        raise ValueError(
            f"There is no astool server configuration that matches the exact version {exact}."
        )

    the_max = None
    for v in candidates:
        if not the_max or vercmp(v["bundle_version"], the_max["bundle_version"]) > 0:
            the_max = v

    return the_max


class ASContext(object):
    def __init__(self, region: str, bundle: str, memo: str):
        if region not in SERVER_CONFIG:
            raise ValueError(f"Not a defined region: {region}")

        self.region = region
        self.bundle = bundle
        self.memo_name = memo or "astool_store"
        self.server_config = resolve_server_config(SERVER_CONFIG.get(self.region), self.bundle)

        self.root = os.path.join(os.getenv("ASTOOL_STORAGE", ""), self.region)
        self.cache = os.path.join(self.root, "cache")
        self.masters = os.path.join(self.root, "masters")
        self.memo_full_path = os.path.join(self.root, f"{self.memo_name}.json")

        os.makedirs(self.cache, exist_ok=True)
        os.makedirs(self.masters, exist_ok=True)

        if not self.bundle:
            self.bundle = self.server_config["bundle_version"]

    @contextmanager
    def enter_memo(self):
        try:
            with open(self.memo_full_path, "r") as js:
                memo = json.load(js)
        except FileNotFoundError:
            memo = {}

        yield memo

        with open(self.memo_full_path, "w") as js:
            json.dump(memo, js)

    def get_iceapi(self, reauth=False, validate=False):
        with self.enter_memo() as memo:
            uid = memo.get("user_id")
            pwd = memo.get("password")
            auc = memo.get("auth_count")
            fast_resume = memo.get("resume_data")

        if not all((uid, pwd, auc is not None)):
            raise ValueError("You need an account to do that.")

        ice = iceapi.ICEBinder(self.server_config, "iOS", uid, pwd, auc)
        if reauth or not ice.resume_session(fast_resume, revalidate_immediately=validate):
            ret = ice.api.login.login()
            if ret.return_code != 0:
                LOGGER.warning("Login failed, trying to reset auth count...")
                ice.set_login(uid, pwd, ret.app_data.get("authorization_count") + 1)
                ice.api.login.login()

        return ice

    def get_empty_iceapi(self):
        return iceapi.ICEBinder(self.server_config, "iOS", None, None, 0)

    def release_iceapi(self, ice, save_session=True):
        with self.enter_memo() as memo:
            memo["master_version"] = ice.master_version
            memo["auth_count"] = ice.auth_count
            if save_session:
                memo["resume_data"] = ice.save_session()
            else:
                memo["resume_data"] = None
