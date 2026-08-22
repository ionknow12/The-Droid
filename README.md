# The Droid Repo

jinoy's personal F-Droid-compatible repo. Served from
`https://ionknow12.github.io/The-Droid/repo` (GitHub Pages on this git repo).
It delivers **The Droid** (the store app) and jinoy's other custom builds
(Kookie, …) to phones as ordinary store updates.

## Shipping a release

```
./ship <app|package> [--dry-run] [--no-push]   # build + publish one app
./ship status                                   # what's built vs what's published
./ship --all [--dry-run] [--no-push]            # ship every app whose build is newer than the repo
```

Bump `versionCode`/`versionName` in the app's gradle file, write
`fastlane/metadata/android/en-US/changelogs/<versionCode>.txt`, then `./ship <app>`.

What `ship <app>` does, in order — every step must positively succeed or it stops:

1. load `apps/<package>.yml`
2. `./gradlew <gradle_task>` in the project (JAVA_HOME / ANDROID_HOME set by the tool)
3. locate the APK; must exist and be newer than the build start
4. read package / versionCode / versionName from the APK (fdroidserver + androguard)
5. `apksigner verify --print-certs`; refuse unsigned or debug-signed APKs
6. refuse unless versionCode > the highest one already in `repo/index-v2.json` (`--dry-run` stops here)
7. copy to `repo/<package>_<versionCode>.apk`
8. write `metadata/<package>.yml` from the recipe's `repo_metadata` (hand-added keys are kept) and copy the project's fastlane dir to `metadata/<package>/`
9. `fdroid update`
10. re-read the index and check the new versionCode is really there
11. `git add -A && git commit && git push` (skip push with `--no-push`)

Exit code is non-zero on any failure. A missing changelog is a warning, not a failure.

## Recipes (`apps/<package>.yml`)

```yaml
package: com.kookie.music
name: kookie                      # short alias for the CLI
project: "/home/jino/The Music App/Kookie"
gradle_task: ":app:assembleRelease"
apk: app/build/outputs/apk/release/app-release.apk   # relative to project
metadata: fastlane/metadata/android                  # relative to project, optional
env_file: app/keystore/KEYSTORE_SECRETS.txt           # optional; KEY=VALUE lines exported to gradle (signing secrets, git-ignored)
repo_metadata:                    # goes into metadata/<package>.yml
  Name: Kookie
  Summary: Music player with its own ink
  License: GPL-3.0-only
  Categories: [Multimedia]
```

Projects sign themselves (each app's gradle has its own release keystore).
`ship` verifies signatures; it never signs. The repo index is signed with
the repo key in `~/TheDroid-keys` via `config.yml` (not committed).

## Tests

```
/home/jino/.local/share/fdroidserver-venv/bin/python -m unittest discover -s tests -v
```

## Caveats

- A phone running a **debug-signed** build of an app (e.g. an old sideloaded
  `Kookie-*-debug.apk`) cannot update in place to the release-signed repo
  build. Uninstall once, install from The Droid, and updates flow from then on.
- GitHub Pages takes a minute or so to serve a new index after `git push`.
