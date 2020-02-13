import os

import plac

from . import pkg


class PackageManagerMain(object):
    def __init__(self, context):
        self.context = context

    def sync(self, master, validate_only, quiet, lang, *groups):
        """Download or validate package groups."""
        if not lang:
            lang = "ja"

        if not master:
            with self.context.enter_memo() as memo:
                master = memo["master_version"]

        path = os.path.join(self.context.masters, master, f"asset_i_{lang}_0.db")
        manager = pkg.PackageManager(path, (self.context.cache,))

        print("Master:", master)
        print("Packages on disk:", len(manager.package_state))

        if len(groups) == 1 and groups[0] == "everything":
            packages = manager.lookup_all_package_groups()
        else:
            packages = manager.lookup_matching_package_groups(groups)

        download_tasks = []
        wanted_packages = set()

        print("Validating packages...")
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

        download_tasks = manager.compute_download_list(wanted_packages)
        if download_tasks:
            print("Update statistics:")
            print(f"  {len(download_tasks)} jobs,")
            npkg = sum(
                1 if isinstance(x, pkg.PackageDownloadTask) else len(x.splits)
                for x in download_tasks
            )
            print(f"  {npkg} new packages,")
            nbytes = sum(
                x.size if isinstance(x, pkg.PackageDownloadTask) else sum(y.size for y in x.splits)
                for x in download_tasks
            )
            print("  {0} bytes, ({1:.3f} MB).".format(nbytes, nbytes / (1024 * 1024)))
        else:
            print("All packages are up to date. There is nothing to do.")

        if download_tasks and not validate_only:
            ice = self.context.get_iceapi()
            manager.execute_job_list(
                ice, download_tasks, done=self.context.release_iceapi, quiet=quiet
            )

    def gc(self, master, dry_run, lang):
        """Delete unreferenced packages."""
        if not lang:
            lang = "ja"

        if not master:
            with self.context.enter_memo() as memo:
                master = memo["master_version"]

        path = os.path.join(self.context.masters, master, f"asset_i_{lang}_0.db")
        manager = pkg.PackageManager(path, (self.context.cache,))

        print("Master:", master)
        print("Packages on disk:", len(manager.package_state))
        garbage = manager.get_unreferenced_packages()
        freeable = 0

        for pack in garbage:
            freeable += os.path.getsize(manager.lookup_file(pack))
            if not dry_run:
                print(f"Removing {pack}...")
                fqpkg = manager.lookup_file(pack)
                if fqpkg:
                    os.unlink(fqpkg)

        print(
            "{0} bytes ({1:.3f} MB) {2} freed by deleting these unused packages.".format(
                freeable, freeable / (1024 * 1024), "can be" if dry_run else "were"
            )
        )
