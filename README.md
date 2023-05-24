# astool: All Stars Utility Toolkit
### forked for readme documentation additions
### Original: https://github.com/kirara-research/astool

Requires Python 3.7+.

## Installation

It's recommended that you install using pip (`pip install .`) over using setup.py.
To enable the use of async for downloading packages (massive speedup over requests
if you have a high bandwidth internet connection), do `pip install '.[async_pkg]'`.

You also need to install the hwdecrypt extension module the same way
(`pip install ./hwdecrypt_src`), unless you're arposandra and include your own copy.

## Storage

You can set the `ASTOOL_STORAGE` environment variable to change where data gets
stored. The default is the current directory, so it's recommended to choose a
better place.

Files:
- [server]/astool_store.json - Contains the account credentials used by astool, as well
  as the last known master version.
- [server]/cache/pkg... - Encrypted asset packages. Assets are retrieved from them as needed.
- [server]/masters/.../... - Contains asset databases. Each master version has its own folder
  with its collection of databases.

## Command-Line Usage

### astool

All commands start with the common invocation:

```sh
python -m astool [common args] [server] [command args...]
```

Common args can include:

- `-b (bundle ver)` sets the app version, which affects DB encryption keys and server URLs.
- `-f (name)` sets the memo's filename. The actual path used will be `$ASTOOL_STORAGE/[server]/[name].json`.
- `-q` quiets some logs.

Commands and their arguments:

- `accept_tos` - Accepts the TOS, only needs to be used if not done by `bootstrap`. Currently not working for
  EN.
- `bootstrap` - Creates an account and saves the login info to the memo. Currently only partially working for EN.
- `current_master` - Prints the current master from the memo to stdout.
- `decrypt_master (file)` - Decrypts the database (file) to (file).dec. The directory that (file)
  is in will be consulted for the appropriate keys.
- `dl_master [-m version] [-f]` - Downloads the databases associated with version (version).
  If (version) is not given, will ask the API for the latest version. If -f is given, databases
  will be redownloaded even if they exist.
- `invalidate` - Removes fast resume data from the memo. This will force a relogin on the next API call.
- `master_gc` - Deletes decrypted databases that can be recreated. The latest master will not be deleted.
- `pkg_sync [flags] (groups...)` - Check the downloaded package cache and see if the named groups are
  complete. If not, and you haven't told it to validate only, it will download the missing parts.
  Flags:
  - `-m/--master [version]` - Use the specified master databases. If this is not given, it'll use the 
    current version from the astool memo.
  - `-sfd/--signal-cts [path]` - The string "ready\n" will be written to this path when all API calls
    are finished, before any packages are downloaded.
  - `-n/--validate-only` - Don't download anything. For `pkg_gc`, don't delete anything.
  - `-g/--lang [language]`: Use the specified language's asset database.
- `pkg_gc` - Deletes any packages files that are not referenced by the current asset database.
  Flags:
  - `-m/--master [version]` - Use the specified master databases. If this is not given, it'll use the 
    current version from the astool memo.
  - `-n/--dry-run` - Don't delete anything. Note that this is a different long option from pkg_sync.
  - `-g/--lang [language]`: Use the specified language's asset database.

### astool_extra (Data Extraction)

```sh
python -m astool_extra.unpack_fs [common args] [output]
```

Common args can include:

- `-h (--help)` - Shows the help menu.
- `-r (--region)` - Tells astool what region to use (`en` or `jp`).
- `-m None, --master` - Master version (default: latest known via dl_master)
- `-l (--lang)` - Tells astool what language to use (default: default for server region).
- `-t (--table-list) `- Comma-separated list of tables to extract (default: all). Pass 'list' to see available.
- `-y (--skip-confirmation)` - Don't ask before extracting

- `[output]` - Data output folder

List of tables:

- `adv_script`
- `background`
- `gacha_performance`
- `live2d_sd_model`
- `live_prop_skeleton`
- `live_timeline`
- `m_asset_sound`
- `m_movie`
- `member_facial`
- `member_facial_animation`
- `member_model`
- `member_sd_model`
- `navi_motion`
- `navi_timeline`
- `shader`
- `skill_effect`
- `skill_timeline`
- `skill_wipe`
- `stage`
- `stage_effect`
- `texture`

## Guide

## Mac/Linux/WSL
### - Set up workspace in the "astool-ws" directory (located in the $home folder)
```sh
mkdir astool-ws && cd astool-ws`
mkdir data
```
### - Clone repo
```sh
git clone https://github.com/kirara-research/astool.git astool-dist
```
### - Create and activate virtual environment
```sh
python3 -m venv .env
source .env/bin/activate
```
### - Install packages
```sh
pip install -e './astool-dist[async_pkg]'
pip install './astool-dist/hwdecrypt_src'
```

### - Run every time you want to use the workspace
```sh
source .env/bin/activate
export ASTOOL_STORAGE=$(pwd)/data
export LIVE_MASTER_CHECK_ALLOWED=1
```

### - Now you can run your commands - replace "jp" with "en" for global server
```sh
python -m astool jp bootstrap
```
### -  If the above command fails with a 500 Internal Server Error, that's fine; the following commands will still work. 
```sh
python -m astool jp dl_master
```
### - A package id of '%' will download everything
```sh
python -m astool jp pkg_sync '%'
```

## Windows (Native)
### Prerequisites:
- Upgrade pip
```sh
pip install --upgrade pip
```
- Install virtualenv
```sh
pip install virtualenv
```
- Download hwdecrypt binary for win_32 or win_amd64: https://github.com/kirara-research/astool/releases/tag/v1.2.6.0
- Save hwdecrypt somewhere for later

### - Set up workspace in the "astool-ws" directory, which gets put in C:/Users/[User] folder
```sh
mkdir astool-ws && cd astool-ws
```
Alternatively, you could make astool-ws on the desktop, then do cd C:/Users/[User]/Desktop/astool-ws
### - Clone repo
```sh
git clone https://github.com/kirara-research/astool.git astool-dist
```
# - Create and activate virtual environment
```sh
python3 -m venv .env
.env\scripts\activate
```
### - Install scripts
```sh
pip install -e C:/Users/[Userfolder]/astool-ws/astool-dist/
```
- pip install and copy hwdecrypt path
Example:
```sh
pip install C:/Users/[Userfolder]/Downloads/hwdecrypt-1.1.0-cp311-cp311-win_amd64.whl
```

### - Run every time you want to use the workspace
```sh
.env\scripts\activate
SET ASTOOL_STORAGE=$(pwd)/data
SET LIVE_MASTER_CHECK_ALLOWED=1
```
You can replace $(pwd)/data with a path of your choice

### - Now you can run your commands - replace "jp" with "en" for global server
```sh
python -m astool jp bootstrap
```
### -  If the above command fails with a 500 Internal Server Error, that's fine; the following commands will still work. 
```sh
python -m astool jp dl_master
```
### - A package id of '%' will download everything (here the double spaces are VERY IMPORTANT for downloading, else it won't do much of anything)
```sh
python -m astool jp pkg_sync '%'
```

## Programmatic Usage

Most APIs in the astool.pkg, astool.ctx, astool.masters, and astool.iceapi modules are available
for public use.

## Decryption

Assets are encrypted using a LCRNG-based stream cipher. See libpenguin/penguin_tool.c
for the algorithm. The RNG seeds are stored in the manifest (see karstool) or in
the asset database.

Audio files are stored as CRI HCA like every other game. The key for them is
`0x5a2f6f6f0192806d`, or `-a 0192806d -b 5a2f6f6f`.
