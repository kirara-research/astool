import os
import sys
import logging
import json
import time

from astool import iceapi
from astool import ctx

def main(
    region: "API region",
    bundle: ("Bundle version", "option", "b"),
    quiet: ("Disable logging?", "flag", "q"),
    memo: ("Name of the memo file to use. Default is 'astool_store'.", "option", "f"),
    *uids: "user ids"
):
    if not quiet:
        logging.basicConfig(level=logging.INFO)

    context = ctx.ASContext(region, bundle, memo or "astool_store")
    uids = [int(uid) for uid in uids]

    ice = context.get_iceapi()

    for uid in uids:
        print(uid)
        resp = ice.api.userProfile.fetchProfile({"user_id": uid})
        with open(f"{uid}.json", "w") as out:
            json.dump(resp.app_data, out)
        time.sleep(0.3)

    context.release_iceapi(ice)

if __name__ == '__main__':
    import plac
    plac.call(main)