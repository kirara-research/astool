import json
import os
import logging
import copy
import time
import random

import iceapi

class MockICE(object):
    def request_maker(self, rkey):
        with open(os.path.join("ex_bootstrap_script", "responses",
            f"{rkey}.response.json"), "r") as rtf:
            server_obj = json.load(rtf)["data"]
        
        ret = iceapi.api_return_t({}, server_obj[2], server_obj[3])
    
        def requester(data):
            print("mock in:", json.dumps(data)[:100], "...")
            return ret

        return requester

def get_url_fragments(fqurl):
    return fqurl.replace("https://", "").split("/", 1)[-1].split("?")[0].split("/")

def ice_endpoint(ice, frags, rkey):
    print(frags)
    if isinstance(ice, MockICE):
        return ice.request_maker(rkey)

    a = ice.api
    for i in frags[1:]:
        a = getattr(a, i)
    return a

def SaveCurrentBeatmapInfo(context, appdata):
    context["live"] = {
        "id": appdata["live"]["live_id"],
        "start": int(time.time() + 6.443),
    }
    logging.info("Saved live id as %s.", context["live"]["id"])

def RestoreBeatmapInfo(context, request):
    request["data"][0]["live_id"] = context["live"]["id"]
    request["data"][0]["live_score"]["start_info"]["created_at"] = context["live"]["start"]
    request["data"][0]["live_score"]["finish_info"]["created_at"] = int(time.time())
    
    logging.info("Restored live id as %s.", request["data"][0]["live_id"])
    return request

green_bold = "\x1b[1;32m"
reset = "\x1b[0m"

def run_playlist(ice, playlist_path):
    with open(playlist_path, "r") as plj:
        timing_list = json.load(plj)

    context = {}
    request_templates = {}
    for desc in timing_list:
        request_id = desc["src"]
        with open(os.path.join(os.path.dirname(playlist_path), 
            f"{request_id}.request.json"), "r") as rtf:
            request_templates[request_id] = json.load(rtf)
        logging.info("Preparing template: %s", request_id)

    # execute
    G = globals()
    for desc in timing_list:
        logging.info("%s<==> STEP: %s%s", green_bold, desc["src"], reset)

        time.sleep(desc["delay"] + (random.random() * (desc["delay"] / 8)))
        if "before_request" in desc:
            func = G.get(desc["before_request"])
            template = func(context, copy.deepcopy(request_templates[desc["src"]]))
        else:
            template = request_templates[desc["src"]]

        ice_post_data = template["data"][0]
        ice_url = ice_endpoint(ice, get_url_fragments(template["url"]), desc["src"])
        resp = ice_url(ice_post_data)
    
        if "after_response" in desc:
            func = G.get(desc["after_response"])
            func(context, resp.app_data)

def main():
    logging.basicConfig(level=logging.INFO)
    run_playlist(MockICE(), "ex_bootstrap_script/0000_playlist.json")

if __name__ == "__main__":
    main()