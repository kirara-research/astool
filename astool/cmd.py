import plac
import os
import sys
import logging

import zlib
import hwdecrypt
from . import iceapi
from . import bootstrap_promote
from . import pkg_cmd
from . import ctx
from . import masters
from .sv_config import SERVER_CONFIG
import json

LOGGER = logging.getLogger("astool.cli")


class ASToolMainCommand(object):
    commands = (
        "bootstrap",
        # "sign_package_urls",
        "accept_tos",
        "resolve",
        "promote",
        "invalidate",
        "pkg_sync",
        "pkg_gc",
        "dl_master",
        "current_master",
        "master_gc",
        "decrypt_master",
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

    def current_master(self):
        """Print the current master version."""

        with self.context.enter_memo(rdonly=True) as memo:
            print(memo.get("latest_complete_master", ""))

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

        LOGGER.info("astool: Bootstrapped with id=%s, pw=%s", memo["user_id"], memo["password"])
        ice.set_login(memo["user_id"], memo["password"], 1)
        ice.api.login.login()
        ret = ice.api.terms.agreement({"terms_version": 1})
        if ret.return_code == 0:
            LOGGER.info("astool: Agreed to the terms of service...")
        else:
            LOGGER.error("TOS agreement failed: %d %s", ret.return_code, ret.app_data)

        with self.context.enter_memo() as memo:
            memo["auth_count"] = 1

    def accept_tos(self):
        """Accept the TOS."""

        ice = self.context.get_iceapi()

        ret = ice.api.terms.agreement({"terms_version": 1})
        if ret.return_code == 0:
            LOGGER.info("astool: Agreed to the terms of service...")

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
            LOGGER.warning("Login failed, trying to reset auth count...")
            ice.set_login(uid, pwd, ret.app_data.get("authorization_count") + 1)
            ret = ice.api.login.login()

        if ret.app_data["user_model"]["user_status"]["tutorial_end_at"] == 0:
            LOGGER.warning("astool: I'm going to complete the tutorial for this account.")
            if input("This process cannot be undone. Are you sure? (type 'yes') > ") == "yes":
                bootstrap_promote.run_playlist(ice, "ex_bootstrap_script/0000_playlist.json")
        else:
            LOGGER.warning(
                "This account has already finished the tutorial. "
                + "If you want to do this again, run bootstrap to create a new account."
            )

        with self.context.enter_memo() as memo:
            memo["master_version"] = ice.master_version
            memo["auth_count"] = ice.auth_count
            memo["resume_data"] = None

    def pkg(self, *args):
        first = sys.argv.index("pkg") + 1
        plac.call(
            pkg_cmd.PackageManagerMain(self.context),
            arglist=sys.argv[first:],
        )

    def live_master_check(self):
        if not os.environ.get("LIVE_MASTER_CHECK_ALLOWED"):
            return None

        ice = self.context.get_iceapi(validate=True)
        m = ice.master_version
        self.context.release_iceapi(ice)
        return m

    def dl_master(
        self,
        master: ("Master version", "option", "m"),
        force: ("Always re-download files", "flag", "f"),
    ):
        if not master:
            master = self.live_master_check()

            if not master:
                with self.context.enter_memo() as memo:
                    master = memo["master_version"]

        LOGGER.info(
            "Master: %s, Application: %s", master, self.context.server_config["bundle_version"]
        )

        langs = [self.context.server_config.get("language", "ja")]
        langs.extend(self.context.server_config.get("additional_languages", ()))
        have_files = set()

        for lang_code in langs:
            manifest = masters.download_remote_manifest(self.context, master, lang_code=lang_code)
            for file in manifest.files:
                if file.name in have_files:
                    continue
                if not masters.file_is_valid(self.context, file) or force:
                    LOGGER.info("Retrieving and decrypting %s...", file.name)
                    masters.download_one(self.context, file)
                    have_files.add(file.name)
                else:
                    LOGGER.info("File %s is still valid!", file.name)
        
        try:
            masters.update_current_link(self.context, master)
        except OSError as e:
            LOGGER.error("Can't update current master symlink: %s", str(e))
        
        with self.context.enter_memo() as memo:
            memo["latest_complete_master"] = master

    def decrypt_master(self, filename):
        wd = os.path.dirname(filename)
        auxinfo = os.path.join(wd, "auxinfo_i")
        masterinfo = os.path.join(wd, "masterdata_i_ja")
        with open(auxinfo, "r") as f:
            server_config = ctx.resolve_server_config(
                SERVER_CONFIG["jp"], exact=json.load(f).get("bundle_version")
            )

        with open(masterinfo, "rb") as f:
            manifest = masters.Manifest(f, server_config)

        for file in manifest.files:
            if file.name == os.path.basename(filename):
                break
        else:
            print("File not in manifest")

        ks = file.getkeys()
        keys = hwdecrypt.Keyset(ks[0], ks[1], ks[2])
        decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

        with open(filename, "rb") as ef, open(f"{file}.dec", "wb") as of:
            while True:
                chunk = ef.read(65536)
                if not chunk:
                    break

                copy = bytearray(chunk)
                hwdecrypt.decrypt(keys, copy)
                of.write(decompressor.decompress(copy))
            of.write(decompressor.flush())

    def pkg_sync(
        self,
        master: ("Assume master version (that you already have an asset DB for)", "option", "m"),
        validate_only: ("Don't download anything, just validate.", "flag", "n"),
        signal_cts: ("Path to write 'ready' to when finished using SAPI.", "option", "sfd"),
        lang: ("Asset language (default: ja)", "option", "g"),
        *groups: "Packages to validate or complete",
    ):
        cmd = pkg_cmd.PackageManagerMain(self.context)
        cmd.sync(master, validate_only, signal_cts, self.quiet, lang, *groups)

    def pkg_gc(
        self,
        master: ("Assume master version (that you already have an asset DB for)", "option", "m"),
        dry_run: ("Don't download anything, just validate.", "flag", "n"),
        lang: ("Asset language (default: ja)", "option", "g"),
    ):
        cmd = pkg_cmd.PackageManagerMain(self.context)
        cmd.gc(master, dry_run, lang)

    def master_gc(
        self,
        dry_run: ("Dry run. Don't delete any files.", "flag", "n"),
    ):
        with self.context.enter_memo(rdonly=True) as memo:
            protect_master = [memo.get("master_version"), memo.get("latest_complete_master")]

        version_list = []
        lang = self.context.server_config.get("language", "ja")
        for mv_dir in os.listdir(self.context.masters):
            fullp = os.path.join(self.context.masters, mv_dir)
            if os.path.islink(fullp) or not os.path.isdir(fullp):
                continue

            if mv_dir in protect_master:
                LOGGER.info("%s is in use, not adding to cleanup list", mv_dir)
                continue

            if not os.path.exists(
                os.path.join(self.context.masters, mv_dir, "auxinfo_i")
            ) and not os.path.exists(os.path.join(self.context.masters, mv_dir, "auxinfo_a")):
                LOGGER.info("%s has no auxinfo, not adding to cleanup list", mv_dir)
                continue

            for try_name in [f"masterdata_i_{lang}", f"masterdata_a_{lang}"]:
                try:
                    mt = os.path.getmtime(os.path.join(self.context.masters, mv_dir, try_name))
                    version_list.append((mt, mv_dir))
                    break
                except FileNotFoundError:
                    continue

        cleaned_bytes = 0
        for _, version in version_list[:-5]:
            dir = os.path.join(self.context.masters, version)
            for file in os.listdir(dir):
                # .gz for compatibility with old archive style
                if not (file.endswith(".db.gz") or file.endswith(".db")):
                    continue

                full_path = os.path.join(dir, file)
                cleaned_bytes += os.path.getsize(full_path)
                if not dry_run:
                    os.unlink(full_path)

        LOGGER.info("master_gc: cleaned up %s bytes, %s MB", cleaned_bytes, cleaned_bytes / 1048576)
