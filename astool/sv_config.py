#!/usr/bin/env python3
# fmt: off

# @astool_OSS_REDACT_START
# ## How to assemble a server config from scratch:
#
# root:
#     Search for "klabgames.net" in global-metadata. Copy the full
#     URL base out
#
# bootstrap_key:
#     This is right after the root URL. It's always 16 bytes - copy
#     up to the "x'" string.
#
# public_key:
#     Search for "applinks:llas" in global-metadata. The nearest XML
#     key is the one you need. Convert it to PEM using
#     https://superdry.apphb.com/tools/online-rsa-key-converter
#
# session_mixkey: 32 bytes
#     Search for "applinks:llas" in global-metadata and scroll past
#     the RSA key. It's in the middle of a bunch of small ints so
#     should be easily visible.
#
# user_agent:
#     Need to capture it off network, but doesn't matter for API
#     usage. You can copy it from another config
#
# bundle_version:
#     Get it from the App Store info page. It's only used for the
#     plumbing API.
#
# master_keys:
#     These are set by Constant .cctor in libil2cpp.so. First get
#     a memory dump of the decrypted code with GameGuardian:
#
#     - Root the armv7 version of bluestacks with BSTweaker;
#     - Start GameGuardian as root
#     - Unroot bluestacks so the game launches
#     - Use GG to dump memory.
#
#     Then, search for the image and function using the analyzer
#     tool in this repo.
# @astool_OSS_REDACT_END

PUBLIC_KEY_DEFAULT_JP = b""
MIXKEY_DEFAULT_JP = ""

# @astool_OSS_REDACT_START
PUBLIC_KEY_DEFAULT_JP = b"""\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC/ZUSWq8LCuF2JclEp6uuW9+yd
dLQvb2420+F8rxIF8+W53BiF8g9m6nCETdRw7RVnzNABevMndCCTD6oQ6a2w0Qpo
KeT26578UCWtGp74NGg2Q2fHYFMAhTytVk48qO4ViCN3snFs0AURU06niM98MIcE
Unj9vj6kOBlOGv4JWQIDAQAB
-----END PUBLIC KEY-----
"""
MIXKEY_DEFAULT_JP = "65D780D3EED9AF5831FFD5B870C7649FAC254AC21A384B4769814F5EB11AC339"
# @astool_OSS_REDACT_END

SERVER_CONFIG = {}

SERVER_CONFIG["jp"] = [
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1060",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "aNdGirwozqEnoXb0",
        "session_mixkey": [
            "86A06062276ECF7E717BA04EA598617E2FE4F1A274433216A368E1E6DABC6AAC",
            "8C7776ACE1CB03B6247D3CB36FB6433F63B8886209179B932812746DEE35C098",
        ],
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/13 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x5101909d, 0x3f06d7e4, 0x69df2d58],
        "bundle_version": "1.6.0",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1050",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "HEfMsRCTP43dXl66",
        "session_mixkey": [
            "FC11A7F49CDCF784B8B7C7C4A1CFA0AA745A346D406A9FC142B5643E706AD2B2",
            "E4F84C384EEEA5826DCAF1E60787A8F4FE1D5C3B28F6EE09179057D246D49B2E"
        ],
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/13 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x04324df0, 0x06dbd2c0, 0x0104a1cc],
        "bundle_version": "1.5.0",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1041",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "SkOYIxhfI1msD6ku",
        "session_mixkey": MIXKEY_DEFAULT_JP,
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/12 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x0cb3992c, 0x75a632fd, 0x52d42eed],
        "bundle_version": "1.4.1",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1040",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "qIbAhMVtoH4zS9JL",
        "session_mixkey": MIXKEY_DEFAULT_JP,
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/11 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0xE10398E5, 0xE0CBF8BF, 0x0BC28A8E],
        "bundle_version": "1.4.0",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1031",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "VgS4YaPhfxP3qNo9",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/11 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x449ECC82, 0x7E3462AA, 0x273AFADE],
        "bundle_version": "1.3.1",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1030",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "660EgLprLmcMYCBQ",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/9 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0xBFD90149, 0x4260F412, 0x55DB2748],
        "bundle_version": "1.3.0",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1021",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "7xy2slp4ofSixvpZ",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/5 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0xB79E1D01, 0xFAB4DDE8, 0xD8739968],
        "bundle_version": "1.2.1",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1020",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "7xy2slp4ofSixvpZ",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/5 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0xB79E1D01, 0xFAB4DDE8, 0xD8739968],
        "bundle_version": "1.2.0",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1016",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "I6ow2cY1c2wWXJP7",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/3 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x175871A7, 0x7144644B, 0xFC7CF86E],
        "bundle_version": "1.1.2",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1015",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "5H61ESZxJwcsylnk",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/2 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x92A4BAE2, 0x0457DB3E, 0x7B6817CF],
        "bundle_version": "1.1.1",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1010",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "G5OdK4KdQO5UM2nL",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/5 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0x5595F498, 0x15E7EE5, 0x7EF3EAC1],
        "bundle_version": "1.1.0",
    },
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1001",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "P5kjzssUjcDFD0b1",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/1 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [12345, 67890, 31415],
        "bundle_version": "1.0.1",
    },
    # {
    #     "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1002",
    # @astool_OSS_REDACT_START
    #     "bootstrap_key": "i0qzc6XbhFfAxjN2",
    # @astool_OSS_REDACT_END
    #     "public_key": PUBLIC_KEY_DEFAULT_JP,
    #     "user_agent": "allstars/1 CFNetwork/1107.1 Darwin/19.0.0",
    #     "master_keys": [12345, 67890, 31415],
    #     "bundle_version": "1.0.1",
    # }
]

SERVER_CONFIG["j2"] = [
    {
        "root": "https://jp-real-prod-v4tadlicuqeeumke.api.game25.klabgames.net/ep1021",
        # @astool_OSS_REDACT_START
        "bootstrap_key": "7xy2slp4ofSixvpZ",
        # @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_JP,
        "user_agent": "allstars/5 CFNetwork/1107.1 Darwin/19.0.0",
        "master_keys": [0xB79E1D01, 0xFAB4DDE8, 0xD8739968],
        "bundle_version": "1.2.1",
    }
]

# @astool_OSS_REDACT_START
PUBLIC_KEY_DEFAULT_EN = b"""\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC/ZUSWq8LCuF2JclEp6uuW9+yd
dLQvb2420+F8rxIF8+W53BiF8g9m6nCETdRw7RVnzNABevMndCCTD6oQ6a2w0Qpo
KeT26578UCWtGp74NGg2Q2fHYFMAhTytVk48qO4ViCN3snFs0AURU06niM98MIcE
Unj9vj6kOBlOGv4JWQIDAQAB
-----END PUBLIC KEY-----
"""
# @astool_OSS_REDACT_END

SERVER_CONFIG["en"] = [
    {
        "root": "https://gl-real-prod-8f2jln5l4evlw5l1.api.game25.klabgames.net/ep1035",
# @astool_OSS_REDACT_START
        "bootstrap_key": "tqxuRFb0KvZQHTH8",
        "session_mixkey": "294867DF7779DB803CEDAD92E1D53D966F43F425FE2BD9ECFAC6EA1CED6B7246",
# @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_EN,
        "user_agent": "global/7346 CFNetwork/1121.2.2 Darwin/19.2.0",
        "master_keys": [0x7f2276df, 0xb2d758f8, 0x2a469e35],
        "bundle_version": "1.0.2",
        "language": "en",
        "additional_languages": ["ko", "th", "zh"],
    },
    {
        "root": "https://gl-real-prod-8f2jln5l4evlw5l1.api.game25.klabgames.net/ep1034",
# @astool_OSS_REDACT_START
        "bootstrap_key": "e0xrykyuBrLlwZhd",
        "session_mixkey": "294867DF7779DB803CEDAD92E1D53D966F43F425FE2BD9ECFAC6EA1CED6B7246",
# @astool_OSS_REDACT_END
        "public_key": PUBLIC_KEY_DEFAULT_EN,
        "user_agent": "global/7346 CFNetwork/1121.2.2 Darwin/19.2.0",
        "master_keys": [0x6D3C95EA, 0xF1B952FD, 0x1BA88576],
        "bundle_version": "1.0.1",
        "language": "en",
        "additional_languages": ["ko", "th", "zh"],
    }
]
