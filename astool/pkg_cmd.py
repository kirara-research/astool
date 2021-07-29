import os
import logging
from typing import Optional

import plac

from . import pkg

LOGGER = logging.getLogger("astool.pkg.cli")


class PackageManagerMain(object):
    def __init__(self, context):
        self.context = context

    def write_signal(self, signal_pth: Optional[str]):
        if signal_pth is not None:
            with open(signal_pth, "wb") as sigf:
                sigf.write(b"ready\n")
                sigf.flush()

    def sync(self, master, validate_only, signal_pth, quiet, lang, *groups):
        """Download or validate package groups."""
        if not lang:
            lang = self.context.server_config.get("language", "ja")

        if not master:
            with self.context.enter_memo() as memo:
                master = memo["master_version"]

        if not groups:
            LOGGER.warning("No groups specified. Exiting.")
            self.write_signal(signal_pth)
            return

        path = os.path.join(self.context.masters, master, f"asset_i_{lang}_0.db")
        if not os.path.exists(path):
            path = os.path.join(self.context.masters, master, f"asset_i_{lang}.db")

        if not os.path.exists(path):
            LOGGER.critical("Can't find asset DB.")
            self.write_signal(signal_pth)
            return

        manager = pkg.PackageManager(path, (self.context.cache,))

        LOGGER.info("Master: %s", master)
        LOGGER.info("Packages on disk: %d", len(manager.package_state))

        download_tasks = []
        wanted_packages = set()
        resolve_mode = 1

        if len(groups) == 1 and groups[0] == "everything":
            packages = manager.lookup_all_package_groups()
        elif groups[0] == "@":
            resolve_mode = 2
            wanted_packages = manager.prune_package_list(list(groups[1:]))
        else:
            packages = manager.lookup_matching_package_groups(groups)

        if resolve_mode == 1:
            LOGGER.info("Validating packages...")
            for package_group in packages:
                have, donthave = manager.get_package_group(package_group)

                if donthave:
                    print(f"Validating '{package_group}'...", end=" ")
                    print("\x1b[31m", end="")
                    print(f"{len(have)}/{len(have) + len(donthave)} \x1b[0m")
                elif not quiet:
                    print(f"Validating '{package_group}'...", end=" ")
                    print("\x1b[32m", end="")
                    print(f"{len(have)}/{len(have) + len(donthave)} \x1b[0m")

                wanted_packages.update(donthave)
        else:
            LOGGER.info("Proceeding in direct mode.")

        download_tasks = manager.compute_download_list(wanted_packages)
        if download_tasks:
            LOGGER.info("Update statistics:")
            LOGGER.info("  %d jobs,", len(download_tasks))
            npkg = sum(
                1 if isinstance(x, pkg.PackageDownloadTask) else len(x.splits)
                for x in download_tasks
            )
            LOGGER.info("  %d new packages,", npkg)
            nbytes = sum(
                x.size if isinstance(x, pkg.PackageDownloadTask) else sum(y.size for y in x.splits)
                for x in download_tasks
            )
            LOGGER.info("  %d bytes, (%d MB).", nbytes, nbytes / (1024 * 1024))
        else:
            LOGGER.info("All packages are up to date. There is nothing to do.")

        if download_tasks and not validate_only:
            ice = self.context.get_iceapi()

            def on_iceapi_release(ice):
                self.write_signal(signal_pth)
                self.context.release_iceapi(ice)

            manager.execute_job_list(ice, download_tasks, done=on_iceapi_release)
        else:
            self.write_signal(signal_pth)

    def gc(self, master, dry_run, lang):
        """Delete unreferenced packages."""
        if not lang:
            lang = self.context.server_config.get("language", "ja")

        if not master:
            with self.context.enter_memo() as memo:
                master = memo["master_version"]

        path = os.path.join(self.context.masters, master, f"asset_i_{lang}_0.db")
        if not os.path.exists(path):
            path = os.path.join(self.context.masters, master, f"asset_i_{lang}.db")

        if not os.path.exists(path):
            LOGGER.critical("Can't find asset DB.")
            return

        manager = pkg.PackageManager(path, (self.context.cache,))

        LOGGER.info("Master: %s", master)
        LOGGER.info("Packages on disk: %d", len(manager.package_state))
        garbage = manager.get_unreferenced_packages()
        freeable = 0

        for pack in garbage:
            freeable += os.path.getsize(manager.lookup_file(pack))
            if not dry_run:
                LOGGER.info("Removing %s...", pack)
                fqpkg = manager.lookup_file(pack)
                if fqpkg:
                    os.unlink(fqpkg)

        LOGGER.info(
            "%d bytes (%d MB) %s freed by deleting these unused packages.",
            freeable,
            freeable / (1024 * 1024),
            "can be" if dry_run else "were",
        )
