# SIFAS Tools

Requires a recent version of Python 3.

## Changelog

15/01/2020

- New: IceAPI's api_return_t now exposes the server time in the response.
  api_return_t.server_time is a Unix timestamp corresponding to that.

14/01/2020

- New: You can automate the tutorial on a new account which unlocks features
  on KLab's side. See the astool documentation below for info.

08/01/2020

- Migrated to hwdecrypt.

17/12/2019

- Changed: Fast resume no longer calls bootstrap to check the session.
  Instead, IceAPI will automatically restart the session if the next API call fails
  with a 403, or it detects a master version change. Fast resume will still return
  False for invalid resume data.
  You can get the old behaviour back by passing revalidate_immediately=True
  to fast_resume().
- Added decryption keys for 1.3.0.

30/11/2019

- New: AS_LIBPENGUIN_PATH for customizing libpenguin
  dylib path
- Fixed: Calls with empty payload would result in 403

31/10/2019

- New: multi-config support in karstool.
- Issue: there is no way to select the configuration in astool/package_list_tool.
  Workaround: Make sure the profile you want has the highest bundle version
  in sv_config.py.
- Issue: package_list_tool's gc command doesn't delete retired packages.
- Issue: IceAPI won't fail fast resume for a bundle version change.
  The master version should always change between versions, so a workaround is probably
  not needed.

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

## astool

astool is used to talk to the AS API server. Currently, it has two user commands:

- `astool.py [server] bootstrap` - Create an account and save its credentials. Needed for
  all other commands.
- `astool.py [server] sign_package_urls [package_name] [other_package_name]...` -
  Get a download link for the named package(s). These are signed CloudFront links
  that will eventually expire.
- `astool.py [server] promote` - With a bootstrapped account, complete the tutorial
  based on the playlist in `ex_bootstrap_script`. This allows the account to access
  event rankings, among other things.
- `astool.py [server] resolve` - Print the app version as specified in the config file.

## karstool

karstool is used to download master/asset databases. An account is not strictly
required, but karstool can use it to automatically fetch the latest version.

Usage: `karstool.py [-r server_region] [-m optional_master_version] [-b optional_bundle_version]`
* If you don't provide a master version, it either checks the API or uses the
  last recorded one from the astool memo.
* Export `LIVE_MASTER_CHECK_ALLOWED=1` to allow karstool to do a master check
  against the API.
* DBs are stored to the folders as mentioned under Storage above.

## `package_list_tool`

package_list_tool is for downloading assets.

Usage: `package_list_tool.py [optional flags] sync [group_name] [group_name]...`
Usage: `package_list_tool.py [optional flags] gc`

package_list_tool will check the downloaded package cache and see if the
named groups are complete. If not, and you haven't told it to validate only,
it will download the missing parts. An account, which is created via astool
bootstrap, is required for this.

The `gc` command cleans up any files that are not referenced by the current asset database.

Flags:
- `-m/--master [version]`: Use the specified master databases. If this is not
  given, it'll use the version from the astool memo (**but it won't check online,
  you should run karstool first if you want to get the latest one**).
- `-n/--validate-only`: Don't download anything. For `gc`, don't delete anything.
- `-r/--server`: Same as karstool, choose the server to resolve against.

## Bootstrapping from zero

```python
# Virtualenv setup, etc.
python3 -m venv rt
source rt/bin/activate
pip install -r requirements.txt
export ASTOOL_STORAGE=/mnt/storage/as-cache/data
export LIVE_MASTER_CHECK_ALLOWED=1

pushd hwdecrypt_src
python3 setup.py install
popd

# Create account
python3 astool.py jp bootstrap
# Get master
python3 karstool.py -r jp
# Initial download (>1GB!)
python3 package_list_tool.py -r jp sync main card:%
```

## Decryption

Assets are encrypted using a LCRNG-based stream cipher. See libpenguin/penguin_tool.c
for the algorithm. The RNG seeds are stored in the manifest (see karstool) or in
the asset database.

Audio files are stored as CRI HCA like every other game. The key for them is
`0x5a2f6f6f0192806d`, or `-a 0192806d -b 5a2f6f6f`.

## API Protocol

tbd, see iceapi.py...

## Updating to new application versions

The master keys usually change with each App Store release. (As of 1.1.0 they are
the same across iOS and Android so examining both is no longer necessary.) To add
new keys, edit sv_config.py and add the new configuration to the top of SERVER_CONFIG.
If the -b flag is not passed to karstool, it will pick up the new configuration
automatically as long as the bundle version is higher than previous.

### Guidance for recovering configuration data

- Look in Constant$$.cctor in libil2cpp.so. Keys are assignments to +0, +4, +8 of
  the class static object.
- New endpoint urls can usually found by searching for "v4tadlicuqeeumke" in
  global-metadata.dat.
- The bootstrap key is right next to the endpoint URL. It is, as far as we know,
  always 16 characters. Strings in the file are not separated so you will need
  to identify boundaries yourself.