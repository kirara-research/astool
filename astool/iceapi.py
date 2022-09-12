# @(#)IceAPI for allstars
# @(#)2016-2019, The Holy Constituency of the Summer Triangle.
# @(#)All rights reserved.

import base64
import json
import time
import logging
import hmac
import hashlib
import os
import pprint
import binascii
from collections import namedtuple
from typing import Callable, Dict, Optional
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

import requests
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

APIThunkLog = logging.getLogger("ICEAPIThunk")
APIBinderLog = logging.getLogger("ICEBinder")

api_return_t = namedtuple("api_return_t", ("headers", "return_code", "app_data", "server_time"))

DEFAULT_ASSET_STATE = (
    "AW9YpftGljWY/fnzPXciMnWWoSOIQXcdctowkQPUfpAjasaYRfvSidpw1D2"
    + "lmb6Ns2/LLhnLAAXMWlpKtyOIQpFTu3CmZHkVSg=="
)

FastResumeData = TypedDict("FastResumeData", {
    "session_key": str,
    "request_id": int, 
    "master_version": str, 
    "device_token": str,
}, total=True)

def drill_down(some_dict, key_path, default=None):
    level = some_dict
    for k in key_path:
        try:
            level = level[k]
        except (KeyError, IndexError):
            return default
    return level


class ICEMaintenance(Exception):
    pass


class ICEAPIThunk(object):
    special_behaviours: Dict[str, Callable] = {}

    def __init__(self, session: requests.Session, url: str):
        self.session = session
        self.url = url
        pass

    def __repr__(self):
        return "<ICEAPIThunk for url '{0}'>".format(self.url)

    # This is the magic that creates pyobject -> url bindings.
    def __getattr__(self, attr):
        return ICEAPIThunk(self.session, "/".join((self.url, attr)))

    def __call__(self, *args, **kwargs):
        APIThunkLog.debug("callout %s", self.url)

        if self.url in ICEAPIThunk.special_behaviours:
            ret = ICEAPIThunk.special_behaviours[self.url](self.session, self.url, *args, **kwargs)
        else:
            ret = self.session.default_hit_api(self.url, *args, **kwargs)

        APIThunkLog.debug("result: %s -> %d", self.url, ret.return_code)
        return ret

    @staticmethod
    def this_function_specifically_handles_the_url(for_url):
        def _(f):
            ICEAPIThunk.special_behaviours[for_url] = f
            return f

        return _


class ICEBinder(object):
    """
    ICEBinder for allstars
    """

    def __init__(
        self,
        server_info: dict,
        platform: str,  # iOS | Android
        user_id: int = None,
        auth_key: str = None,
        auth_count: int = 0,
    ):
        assert (not any((user_id, auth_key))) or all((user_id, auth_key))

        self.user_id = user_id
        self.auth_count = auth_count

        self.api_host = server_info["root"]
        self.user_agent = server_info["user_agent"]
        self.platform_code = "i" if platform == "iOS" else "a"
        self.rsa_public_key = load_pem_public_key(server_info["public_key"], default_backend())
        assert isinstance(self.rsa_public_key, rsa.RSAPublicKey)

        smkey = server_info["session_mixkey"]
        if isinstance(smkey, list):
            self.mixkeys = tuple(binascii.unhexlify(x) for x in smkey)
        elif isinstance(smkey, str):
            # pre-150 configs
            self.mixkeys = (binascii.unhexlify(smkey),)
        else:
            self.mixkeys = ()

        self.user_language = server_info.get("language")

        self._bootstrap_key = server_info["bootstrap_key"].encode("ascii")
        if not auth_key:
            self.session_key = self._bootstrap_key
            self.authorization_key = None
        else:
            self.session_key = base64.b64decode(auth_key)
            self.authorization_key = auth_key
            assert len(self.session_key) == 32

        self.request_id = 1
        self.master_version: str = None # type: ignore
        self.has_session = False
        self.has_time = False
        self.device_token: str = None # type: ignore

        self.is_fast_resume_in_progress = False
        self.http_session = requests.Session()

        self.api = ICEAPIThunk(self, "")

    def set_login(self, user_id: int = None, auth_key: str = None, auth_count: int = 0):
        assert (not any((user_id, auth_key))) or all((user_id, auth_key))

        self.user_id = user_id
        self.auth_count = auth_count
        if not auth_key:
            self.session_key = self._bootstrap_key
        else:
            self.session_key = base64.b64decode(auth_key)
            assert len(self.session_key) == 32

        self.request_id = 1
        self.master_version = None # type: ignore
        self.has_session = False
        self.has_time = False
        self.device_token = None # type: ignore

        self.is_fast_resume_in_progress = False
        self.http_session.close()
        self.http_session = requests.Session()

    def resume_session(self, resume_info: Optional[FastResumeData], skip_validity_check=False, revalidate_immediately=False):
        if not resume_info:
            return False

        self.session_key = base64.b64decode(resume_info["session_key"])
        self.request_id = resume_info["request_id"]
        self.master_version = resume_info["master_version"]
        self.device_token = resume_info["device_token"]
        self.has_session = True
        self.has_time = True

        self.is_fast_resume_in_progress = False
        self.http_session.close()
        self.http_session = requests.Session()

        if skip_validity_check and revalidate_immediately:
            raise ValueError(
                "You can't request both skip_validity_check and revalidate_immediately at once."
            )

        if skip_validity_check:
            APIBinderLog.debug("Fast resume: picked up session without check")
            return True

        if revalidate_immediately:
            return self.fast_resume_validate(resume_info)

        self.is_fast_resume_in_progress = True
        return True

    def fast_resume_validate(self, resume_info: FastResumeData):
        try:
            response = self.api.bootstrap.fetchBootstrap(
                {
                    "bootstrap_fetch_types": [2],  # banner fetch type
                    "device_token": self.device_token,
                }
            )
        except Exception as e:
            APIBinderLog.warning("Fast resume: failing because {0}".format(e))
            return False

        if response.return_code != 0:
            APIBinderLog.warning("Fast resume: failing because session check returned non-zero")
            return False

        if self.master_version != resume_info["master_version"]:
            APIThunkLog.warning("Fast resume: Master version changed: %s -> %s.",
                resume_info["master_version"], self.master_version)
            APIThunkLog.warning("Fast resume: This is no longer an error.")
            # APIBinderLog.warning("Fast resume: failing because master version changed")
            # return False

        APIBinderLog.debug("Fast resume: picked up session successfully!")
        return True

    def save_session(self) -> Optional[FastResumeData]:
        if not self.has_session:
            return None

        data = {
            "session_key": base64.b64encode(self.session_key).decode("ascii"),
            "request_id": self.request_id,
            "master_version": self.master_version,
            "device_token": self.device_token,
        }
        APIBinderLog.debug("Save session: saved, this ICEBinder is no longer valid past this point")
        self.has_session = False
        self.is_fast_resume_in_progress = False
        self.http_session.close()
        self.http_session = requests.Session()
        return data

    @property
    def session(self):
        return self

    def bless(self, path, payload):
        code = hmac.new(self.session_key, path.encode("utf8"), hashlib.sha1)
        code.update(b" ")
        code.update(payload.encode("utf8"))
        return f'[{payload},"{code.hexdigest()}"]'

    def query(self):
        q = [f"p={self.platform_code}"]

        if self.master_version:
            q.append(f"mv={self.master_version}")

        q.append(f"id={self.request_id}")

        if self.user_id:
            q.append(f"u={self.user_id}")

        if self.has_time:
            q.append(f"t={round(time.time() * 1000)}")

        if self.user_language:
            q.append(f"l={self.user_language}")

        self.request_id += 1
        return "&".join(q)

    def generate_randomkey(self):
        return b"\x00" * 0x20

    def extract_response(self, rsp):
        rsp.raise_for_status()
        try:
            payload = rsp.json()
        except json.JSONDecodeError:
            return api_return_t(rsp.headers, -1, None, 0)

        if os.environ.get("ICEAPI_DEBUG_RESPONSES"):
            pprint.pprint(payload)

        self.has_time = True
        self.master_version = payload[1]
        APIBinderLog.debug(f"IceAPI: Set master version to {self.master_version}!")

        return api_return_t(rsp.headers, payload[2], payload[3], payload[0] / 1000)

    def default_hit_api(
        self, url, payload=None, skip_session_key_check=False, skip_fast_resume=False
    ):
        if not skip_session_key_check and not self.has_session:
            raise ValueError("You need to establish a session before you do that.")

        headers = {}
        headers["User-Agent"] = self.user_agent

        q = self.query()

        destURL = self.api_host.rstrip("/") + f"{url}?{q}"
        destJSON = json.dumps(payload, separators=(",", ":"))

        headers["Content-Type"] = "application/json"
        data = self.bless(f"{url}?{q}", destJSON)

        if os.environ.get("ICEAPI_DEBUG_REQUESTS"):
            pprint.pprint(data)

        if self.is_fast_resume_in_progress and not skip_fast_resume:
            master = self.master_version
            rsp = self.http_session.post(destURL, headers=headers, data=data)

            if rsp.status_code == 403:
                APIThunkLog.warning("The session has gone invalid.")
                rsp = self.relogin_and_retry(url, payload)

            ret = self.extract_response(rsp)

            if self.master_version != master:
                APIThunkLog.warning("Fast resume: Master version changed: %s -> %s.",
                    master, self.master_version)
                APIThunkLog.warning("Fast resume: This is no longer an error.")
                # APIThunkLog.warning("Reestablishing session because master changed.")
                # self.relogin()

            self.is_fast_resume_in_progress = False
            return ret
        else:
            rsp = self.http_session.post(destURL, headers=headers, data=data)
            return self.extract_response(rsp)

    def apply_xorpad(self, a, b):
        return bytes(bytearray(aa ^ bb for aa, bb in zip(a, b)))

    def relogin(self):
        APIBinderLog.debug("Retrying login...")
        ret = self.api.login.login()
        if ret.return_code != 0:
            APIBinderLog.warning("Login failed, trying to reset auth count...")
            self.set_login(
                self.user_id, self.authorization_key, ret.app_data.get("authorization_count") + 1
            )
            self.api.login.login()

    def relogin_and_retry(self, url, payload):
        self.relogin()

        headers = {}
        headers["User-Agent"] = self.user_agent
        q = self.query()

        destURL = self.api_host.rstrip("/") + f"{url}?{q}"
        destJSON = json.dumps(payload, separators=(",", ":"))

        headers["Content-Type"] = "application/json"
        data = self.bless(f"{url}?{q}", destJSON)

        if os.environ.get("ICEAPI_DEBUG_REQUESTS"):
            pprint.pprint(data)

        return self.http_session.post(destURL, headers=headers, data=data)

    #####

    @ICEAPIThunk.this_function_specifically_handles_the_url("/login/startup")
    def login_startup(self, url, payload=None):
        rand = self.generate_randomkey()
        mask = self.rsa_public_key.encrypt(
            rand, OAEP(mgf=MGF1(SHA1()), algorithm=SHA1(), label=None)
        )
        mask = base64.b64encode(mask).decode("ascii")

        params = {"mask": mask, "asset_state": DEFAULT_ASSET_STATE}
        if payload:
            params.update(payload)

        result = self.default_hit_api(url, params, skip_session_key_check=True)
        if "authorization_key" in result.app_data:
            server_mixed = base64.b64decode(result.app_data.get("authorization_key"))
            result.app_data["authorization_key"] = base64.b64encode(
                self.apply_xorpad(rand, server_mixed)
            ).decode("utf8")
            self.authorization_key = result.app_data["authorization_key"]
        return result

    @ICEAPIThunk.this_function_specifically_handles_the_url("/login/login")
    def login_login(self, url, payload=None):
        if self.has_session:
            self.set_login(self.user_id, self.authorization_key, self.auth_count)

        rand = self.generate_randomkey()
        mask = self.rsa_public_key.encrypt(
            rand, OAEP(mgf=MGF1(SHA1()), algorithm=SHA1(), label=None)
        )
        mask = base64.b64encode(mask).decode("ascii")

        result = self.default_hit_api(
            url,
            {
                "user_id": self.user_id,
                "auth_count": self.auth_count,
                "mask": mask,
                "asset_state": DEFAULT_ASSET_STATE
            },
            skip_session_key_check=True,
            skip_fast_resume=True,
        )

        if result.app_data.get("session_key"):
            server_mixed = base64.b64decode(result.app_data.get("session_key"))
            self.session_key = self.apply_xorpad(rand, server_mixed)

            for k in self.mixkeys:
                self.session_key = self.apply_xorpad(self.session_key, k)

            APIBinderLog.debug("A session has been established with key %s.", self.session_key)
            self.has_session = True

        # print(result.app_data)
        token = drill_down(result.app_data, ("user_model", "user_status", "device_token"))
        if token is not None:
            APIBinderLog.debug(f"Device token: {token}")
            self.device_token = token

        self.auth_count += 1
        return result

    @ICEAPIThunk.this_function_specifically_handles_the_url(
        "/dataLink/fetchGameServiceDataBeforeLogin"
    )
    def dataLink_fetchGameServiceDataBeforeLogin(self, url, payload=None):
        rand = self.generate_randomkey()
        mask = self.rsa_public_key.encrypt(
            rand, OAEP(mgf=MGF1(SHA1()), algorithm=SHA1(), label=None)
        )
        mask = base64.b64encode(mask).decode("ascii")

        params = {"mask": mask}
        if payload:
            params.update(payload)

        result = self.default_hit_api(
            url, params, skip_session_key_check=True, skip_fast_resume=True
        )
        return result
