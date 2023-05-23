from dataclasses import dataclass
import base64
import os
import shutil
import logging
import sqlite3
import struct
from typing import Dict, List, Any, Optional

from astool import pkg, ctx
import hwdecrypt
import plac

LOGGER = logging.getLogger("astool.unpack_fs")

def to_unsigned(i):
    return struct.unpack("<I", struct.pack("<i", i))[0]

### MARK: FS unpack rules and actions

@dataclass
class Job:
    table_name: str
    asset_name: str
    size: int
    extra: Any

class Action:
    def get_instances(self, sql: sqlite3.Connection, for_rule: "UnpackRule", name_mapping: Dict[str, str]): ...
    def perform_jobs(self, job_list: "List[Job]", manager: pkg.PackageManager, stage_dir: str): ...

class DecryptFileSegment(Action):
    """Decrypts files using HWD.
        Configuration:
        - ext: file extension, without leading period.
        - encode_filenames: whether to base32-encode the asset_path (some tables like adv_script have plain names)
    """
    def __init__(self, ext: str, encode_filenames=True):
        self.ext = ext
        self.encode_filenames = encode_filenames

    def get_instances(self, sql: sqlite3.Connection, for_rule: "UnpackRule", name_mapping: Dict[str, str]):
        cur = sql.cursor()
        for asset_path, pack_name, head, size, key1, key2 in cur.execute(f"SELECT asset_path, pack_name, head, size, key1, key2 FROM {for_rule.table_name}").fetchall():
            mapped = name_mapping.get(asset_path)
            if mapped is None:
                if self.encode_filenames:
                    asset_name = base64.b32encode(asset_path.encode("utf8")).decode("ascii").strip("=")
                else:
                    asset_name = asset_path
            else:
                asset_name = os.path.join("mapped", mapped)

            yield Job(
                for_rule.table_name, 
                asset_name,
                size,
                (pack_name, head, size, key1, key2)
            )
    
    def perform_jobs(self, job_list: List[Job], manager: pkg.PackageManager, stage_dir: str):
        for job in job_list:
            pack_name, head, size, key1, key2 = job.extra
            buf = bytearray(size)
            keyset = hwdecrypt.Keyset(to_unsigned(key1), to_unsigned(key2), 0x3039)

            real_pkg = manager.lookup_file(pack_name)
            if not real_pkg:
                LOGGER.warning("Missing package %s for job %s, skipping.", pack_name, job.asset_name)
                continue

            with open(real_pkg, "rb") as src:
                src.seek(head)
                src.readinto(buf)
            
            hwdecrypt.decrypt(keyset, buf)
            with open(os.path.join(stage_dir, job.asset_name + f".{self.ext}"), "wb") as dst:
                dst.write(buf)

class DecryptTexture(DecryptFileSegment):
    """Specific for texture table. Does the same thing as DecryptFileSegment, but identifies file type
        based on file signatures and adds the appropriate extension.
        Configuration: None.
    """
    def __init__(self):
        super().__init__("?", True)

    def perform_jobs(self, job_list: List[Job], manager: pkg.PackageManager, stage_dir: str):
        for job in job_list:
            pack_name, head, size, key1, key2 = job.extra
            buf = bytearray(size)
            keyset = hwdecrypt.Keyset(to_unsigned(key1), to_unsigned(key2), 0x3039)

            real_pkg = manager.lookup_file(pack_name)
            if not real_pkg:
                #LOGGER.warning("Missing package %s for job %s, skipping.", pack_name, job.asset_name)
                continue

            with open(real_pkg, "rb") as src:
                src.seek(head)
                src.readinto(buf)
            
            hwdecrypt.decrypt(keyset, buf)
            if buf[:2] == b"\xFF\xD8":
                ext = "jpg"
            elif buf[:4] == b"\x89\x50\x4E\x47":
                ext = "png"
            else:
                LOGGER.warning("Cannot identify file: %s.", job.asset_name)
                ext = "unknown_texture"

            with open(os.path.join(stage_dir, job.asset_name + f".{ext}"), "wb") as dst:
                dst.write(buf)

class CopyAudioBankFilePair(Action):
    """Specific for m_asset_sound table. Copies ACB/AWB bank pairs.
        Configuration: None.
    """
    def get_instances(self, sql: sqlite3.Connection, for_rule: "UnpackRule", name_mapping: Dict[str, str]):
        cur = sql.cursor()
        for sheet_name, acb_name, awb_name, acbsz, awbsz in cur.execute(
            f"""SELECT DISTINCT sheet_name, acb_pack_name, awb_pack_name, pm1.file_size, pm2.file_size FROM {for_rule.table_name}
                LEFT JOIN m_asset_package_mapping AS pm1 ON (acb_pack_name = pm1.pack_name)
                LEFT JOIN m_asset_package_mapping AS pm2 ON (awb_pack_name = pm2.pack_name)
            """).fetchall():
            if acb_name:
                yield Job(
                    for_rule.table_name, 
                    f"{sheet_name}.acb",
                    acbsz,
                    (acb_name,)
                )
            if awb_name:
                yield Job(
                    for_rule.table_name, 
                    f"{sheet_name}.awb",
                    awbsz,
                    (awb_name,)
                )

    def perform_jobs(self, job_list: List[Job], manager: pkg.PackageManager, stage_dir: str):
        for job in job_list:
            real_pkg = manager.lookup_file(job.extra[0])
            if not real_pkg:
                #LOGGER.warning("Missing package %s for job %s, skipping.", job.extra[0], job.asset_name)
                continue

            dest_file = os.path.join(stage_dir, job.asset_name)
            # if os.path.exists(dest_file):
            #     continue
        
            shutil.copyfile(real_pkg, dest_file)

class CopyMovieFile(Action):
    """Specific for m_movie table. Copies USM files.
        Configuration: None.
    """
    def get_instances(self, sql: sqlite3.Connection, for_rule: "UnpackRule", name_mapping: Dict[str, str]):
        cur = sql.cursor()
        for dest, src, sz in cur.execute(f"""SELECT DISTINCT pavement, pack_name, file_size FROM {for_rule.table_name}
                                             LEFT JOIN m_asset_package_mapping USING (pack_name)""").fetchall():
            mapped = name_mapping.get(dest)
            if mapped is None:
                asset_name = base64.b32encode(dest.encode("utf8")).decode("ascii").strip("=") + ".usm"
            else:
                asset_name = os.path.join("mapped", mapped + ".usm")

            yield Job(
                for_rule.table_name, 
                asset_name,
                sz,
                (src,)
            )
    
    def perform_jobs(self, job_list: List[Job], manager: pkg.PackageManager, stage_dir: str):
        for job in job_list:
            real_pkg = manager.lookup_file(job.extra[0])
            if not real_pkg:
                #LOGGER.warning("Missing package %s for job %s, skipping.", job.extra[0], job.asset_name)
                continue

            dest_file = os.path.join(stage_dir, job.asset_name)
            # if os.path.exists(dest_file):
            #     continue
        
            shutil.copyfile(real_pkg, dest_file)

@dataclass
class UnpackRule:
    table_name: str
    action: Action

BASE_RULES = [
    UnpackRule("m_asset_sound",             CopyAudioBankFilePair()),
    UnpackRule("m_movie",                   CopyMovieFile()),
    UnpackRule("adv_script",                DecryptFileSegment(ext="advscript", encode_filenames=False)),
    UnpackRule("texture",                   DecryptTexture()),
    UnpackRule("live_prop_skeleton",        DecryptFileSegment(ext="unity3d")),
    UnpackRule("live_timeline",             DecryptFileSegment(ext="unity3d")),
    UnpackRule("stage",                     DecryptFileSegment(ext="unity3d")),
    UnpackRule("member_model",              DecryptFileSegment(ext="unity3d")),
    UnpackRule("member_facial_animation",   DecryptFileSegment(ext="unity3d")),
    UnpackRule("member_facial",             DecryptFileSegment(ext="unity3d")),
    UnpackRule("navi_motion",               DecryptFileSegment(ext="unity3d")),
    UnpackRule("navi_timeline",             DecryptFileSegment(ext="unity3d")),
    UnpackRule("skill_wipe",                DecryptFileSegment(ext="unity3d")),
    UnpackRule("skill_timeline",            DecryptFileSegment(ext="unity3d")),
    UnpackRule("skill_effect",              DecryptFileSegment(ext="unity3d")),
    UnpackRule("stage_effect",              DecryptFileSegment(ext="unity3d")),
    UnpackRule("member_sd_model",           DecryptFileSegment(ext="unity3d")),
    UnpackRule("live2d_sd_model",           DecryptFileSegment(ext="unity3d")),
    UnpackRule("background",                DecryptFileSegment(ext="unity3d")),
    UnpackRule("shader",                    DecryptFileSegment(ext="unity3d")),
    UnpackRule("gacha_performance",         DecryptFileSegment(ext="unity3d")),
]

### MARK: Asset name mapping from masterdata.db

@dataclass
class AssetNameMapperRule:
    table_name: str
    raw_path_field: str
    format: str

class AssetNameMapper:
    def __init__(self, rules: List[AssetNameMapperRule]):
        self.rules = rules
    
    def build(self, sql: sqlite3.Connection):
        ret: Dict[str, str] = {}
        sql.row_factory = sqlite3.Row
        for rule in self.rules:
            for row in sql.execute(f"SELECT * FROM {rule.table_name} WHERE {rule.raw_path_field} IS NOT NULL"):
                ret[row[rule.raw_path_field]] = rule.format.format(**row)

        return ret

MAPPER_RULES = AssetNameMapper([
    # This is an incomplete list! You can add your own rules below:
    #                    Table name from masterdata.db           Column in                                   Destination template, {column names} in braces will be 
    #                                                            <- table containing asset path              substituted with the column contents.
    AssetNameMapperRule("m_accessory",                          "thumbnail_asset_path",                     "accessory/icon/{accessory_no}"),
    AssetNameMapperRule("m_accessory_level_up_item",            "thumbnail_asset_path",                     "accessory/material/{id}"),
    AssetNameMapperRule("m_card_appearance",                    "image_asset_path",                         "card/full/{card_m_id}_{appearance_type}"),
    AssetNameMapperRule("m_card_appearance",                    "thumbnail_asset_path",                     "card/thumb/{card_m_id}_{appearance_type}"),
    AssetNameMapperRule("m_card_appearance",                    "still_thumbnail_asset_path",               "card/still_thumb/{card_m_id}_{appearance_type}"),
    AssetNameMapperRule("m_card_appearance",                    "background_asset_path",                    "card/commonbg/{card_m_id}_{appearance_type}"),
    AssetNameMapperRule("m_coop_stamp",                         "stamp_asset_path",                         "ui/stamp/{id}"),
    AssetNameMapperRule("m_decoration_texture",                 "path",                                     "ui/decoration/{id}"),
    AssetNameMapperRule("m_emblem",                             "emblem_asset_path",                        "ui/title/{id}"),
    AssetNameMapperRule("m_emblem",                             "emblem_sub_asset_path",                    "ui/title/{id}_sub"),
    AssetNameMapperRule("m_event_movie",                        "asset_path",                               "event/{id}"),
    AssetNameMapperRule("m_gacha_card_performance",             "sign_movie_asset_path",                    "gacha/sign/{card_master_id}"),
    AssetNameMapperRule("m_gacha_member_performance",           "name_base_path",                           "ui/gacha/name_base_{member_master_id}"),
    AssetNameMapperRule("m_gacha_member_performance",           "name_attribute_color_path",                "ui/gacha/name_color_{member_master_id}"),
    AssetNameMapperRule("m_gacha_member_performance",           "name_romaji_base_path",                    "ui/gacha/name_roma_base_{member_master_id}"),
    AssetNameMapperRule("m_gacha_member_performance",           "name_romaji_attribute_color_path",         "ui/gacha/name_roma_color_{member_master_id}"),
    AssetNameMapperRule("m_inline_image",                       "path",                                     "ui/inline_image/{id}"),
    AssetNameMapperRule("m_jacket",                             "jacket_asset_path",                        "ui/live/jacket/{music_id}"),
    AssetNameMapperRule("m_live_movie",                         "movie_asset_path",                         "movie/live/{live_id}"),
    AssetNameMapperRule("m_still",                              "thumbnail_asset_path",                     "still/{still_master_id}_thumb"),
    AssetNameMapperRule("m_still_texture",                      "still_asset_path",                         "still/{still_master_id}_full_{display_order}"),
    AssetNameMapperRule("m_ui_navi_motion",                     "animation_clip_path",                      "model/ui_navi/animation_{motion_key}"),
    AssetNameMapperRule("m_ui_movie",                           "asset_path",                               "movie/ui/{id}"),
    AssetNameMapperRule("m_ui_texture",                         "asset_path",                               "ui/texture/{id}"),
])


def unpack_all(context: ctx.ASContext, master: str, lang: str, table_list: Optional[List[str]], output_root: str, skip_confirmation: bool):
    """Download or validate package groups."""
    path = os.path.join(context.masters, master, f"asset_i_{lang}_0.db")
    if not os.path.exists(path):
        path = os.path.join(context.masters, master, f"asset_i_{lang}.db")

    if not os.path.exists(path):
        LOGGER.critical("Can't find asset DB.")
        return

    manager = pkg.PackageManager(path, (context.cache,))

    LOGGER.info("Master: %s", master)
    LOGGER.info("Packages on disk: %d", len(manager.package_state))

    masterdata_path = os.path.join(context.masters, master, f"masterdata.db")
    if os.path.exists(masterdata_path):
        sql = sqlite3.connect(masterdata_path)
        mapping = MAPPER_RULES.build(sql)
        sql.close()
    else:
        mapping = {}

    if table_list:
        filtered_rules = [r for r in BASE_RULES if r.table_name in table_list]
    else:
        filtered_rules = BASE_RULES

    for rule in filtered_rules:
        jobs: List[Job] = list(rule.action.get_instances(manager.asset_db, rule, mapping))
        print(f"{rule.table_name}:", len(jobs), "files to extract. Est. size:", sum(job.size for job in jobs) / 1024 ** 2, "MB.")
        
    if not skip_confirmation:
        ok = input("Proceed (\"y\")? ")
        if ok.lower() != "y":
            return

    for rule in filtered_rules:
        print(f"Unpacking table {rule.table_name}...")
        jobs = list(rule.action.get_instances(manager.asset_db, rule, mapping))
        need_dirs = set(os.path.dirname(x.asset_name) for x in jobs)
        for dir in need_dirs:
            os.makedirs(os.path.join(output_root, rule.table_name, dir), exist_ok=True)

        rule.action.perform_jobs(jobs, manager, os.path.join(output_root, rule.table_name))

@plac.opt("region", "The astool region to use (default: jp)")
@plac.opt("master", "Master version (default: latest known via dl_master)")
@plac.opt("lang", "Asset language (default: default for server region)")
@plac.opt("table_list", "Comma-separated list of tables to extract (default: all). Pass 'list' to see available.")
@plac.flg("skip_confirmation", "Don't ask before extracting", abbrev="y")
@plac.pos("output", "Output folder.")
def main(
    output: Optional[str] = None,
    region: Optional[str] = None,
    master: Optional[str] = None,
    lang: Optional[str] = None,
    table_list: Optional[str] = None,
    skip_confirmation: bool = False
):
    context = ctx.ASContext(region or "jp", None, None)

    if not master:
        with context.enter_memo() as memo:
            eff_master = memo["master_version"]
    else:
        eff_master = master
    
    if not lang:
        eff_lang = context.server_config.get("language", "ja")
    else:
        eff_lang = lang

    if table_list == "list":
        print("Tables:")
        for rule in sorted(BASE_RULES, key=lambda x: x.table_name):
            print(rule.table_name)
        return
    elif table_list:
        tables = [x.strip() for x in table_list.split(",")]
    else:
        tables = None

    if not output:
        print("An output directory must be provided.")
        return

    unpack_all(context, eff_master, eff_lang, tables, output, skip_confirmation)


if __name__ == "__main__":
    plac.call(main)
