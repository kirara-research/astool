import plac
import os
import logging
from itertools import zip_longest
from contextlib import contextmanager

from . import iceapi
from . import bootstrap_promote
from . import pkg_cmd
from . import ctx
from . import masters
from .sv_config import SERVER_CONFIG
import json


class ASToolMainCommand(object):
    commands = (
        "bootstrap",
        # "sign_package_urls",
        "accept_tos",
        "resolve",
        "promote",
        "invalidate",
        "pkg",
        "dl_master",
    )

    def __init__(
        self,
        region: "API region",
        bundle: ("Bundle version", "option", "b"),
        quiet: ("Disable logging?", "flag", "q"),
        memo: ("Name of the memo file to use. Default is 'astool_store'.", "option", "f"),
    ):
        if not quiet:
            logging.basicConfig(level=logging.INFO)

        self.quiet = quiet
        self.context = ctx.ASContext(region, bundle, memo or "astool_store")

    def __enter__(self):
        pass

    def __exit__(self, etype, exc, tb):
        pass

    def resolve(self):
        """Print the bundle version."""

        print(self.context.server_config["bundle_version"])

    def invalidate(self):
        """Remove fast resume data from the memo."""

        with self.context.enter_memo() as memo:
            memo["resume_data"] = None

    def bootstrap(self):
        """Create an account and accept the TOS."""

        ice = self.context.get_empty_iceapi()
        ret = ice.api.login.startup(
            {
                "resemara_detection_identifier": "",
                # FIXME: The offset is from UTC, but ignores DST. Which we can't calculate
                #   without pulling in pytz.
                "time_difference": 0,
            }
        )

        with self.context.enter_memo() as memo:
            memo["user_id"] = ret.app_data.get("user_id")
            memo["password"] = ret.app_data.get("authorization_key")
            memo["auth_count"] = 0

        print("astool: Bootstrapped with id={0}, pw={1}".format(memo["user_id"], memo["password"]))
        ice.set_login(memo["user_id"], memo["password"], 1)
        ice.api.login.login()
        ret = ice.api.terms.agreement({"terms_version": 1})
        if ret.return_code == 0:
            print("astool: Agreed to the terms of service...")
        else:
            print(ret.return_code, ret.app_data)

        with self.context.enter_memo() as memo:
            memo["auth_count"] = 1

    def accept_tos(self):
        """Accept the TOS."""

        ice = self.context.get_iceapi()

        ret = ice.api.terms.agreement({"terms_version": 1})
        if ret.return_code == 0:
            print("astool: Agreed to the terms of service...")

        self.context.release_iceapi(ice)

    def promote(self):
        with self.context.enter_memo() as memo:
            uid = memo.get("user_id")
            pwd = memo.get("password")
            auc = memo.get("auth_count")

        if not all((uid, pwd, auc)):
            raise ValueError("You need an account to do that.")

        ice = iceapi.ICEBinder(self.context.server_config, "iOS", uid, pwd, auc)
        ret = ice.api.login.login()
        if ret.return_code != 0:
            print("Login failed, trying to reset auth count...")
            ice.set_login(uid, pwd, ret.app_data.get("authorization_count") + 1)
            ret = ice.api.login.login()

        if ret.app_data["user_model"]["user_status"]["tutorial_end_at"] == 0:
            print("astool: I'm going to complete the tutorial for this account.")
            if input("This process cannot be undone. Are you sure? (type 'yes') > ") == "yes":
                bootstrap_promote.run_playlist(ice, "ex_bootstrap_script/0000_playlist.json")
        else:
            print(
                "This account has already finished the tutorial. "
                "If you want to do this again, run bootstrap to create a new account."
            )

        with self.context.enter_memo() as memo:
            memo["master_version"] = ice.master_version
            memo["auth_count"] = ice.auth_count
            memo["resume_data"] = None

    def pkg(self, *args):
        plac.call(
            pkg_cmd.PackageManagerMain(self.context), arglist=args,
        )

    def live_master_check(self):
        if not os.environ.get("LIVE_MASTER_CHECK_ALLOWED"):
            return None

        ice = self.context.get_iceapi(validate=True)
        m = ice.master_version
        self.context.release_iceapi(ice)
        return m

    def dl_master(
        self, master: ("Master version", "option", "m"), force: ("Always re-download files", "flag", "f"),
    ):
        if not master:
            master = self.live_master_check()

            if not master:
                with self.context.enter_memo() as memo:
                    master = memo["master_version"]

        print(f"Master: {master}, Application: {self.context.server_config['bundle_version']}")

        manifest = masters.download_remote_manifest(self.context, master)
        for file in manifest.files:
            if not masters.file_is_valid(self.context, file) or force:
                print(f"Retrieving and decrypting {file.name}...")
                masters.download_one(self.context, file)
            else:
                print(f"File {file.name} is still valid!")
