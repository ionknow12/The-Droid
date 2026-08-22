#!/usr/bin/env python3
"""Release tool for jinoy's personal F-Droid repo. See README.md.

Pure pieces (recipes, index parsing, the release gate, metadata merge) are
plain functions so they can be unit-tested; `ship_app` is the one place that
shells out (gradle, apksigner, fdroid, git).
"""
from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO_DIR = Path(__file__).resolve().parent
APPS_DIR = REPO_DIR / "apps"
INDEX_V2 = REPO_DIR / "repo" / "index-v2.json"
FDROID = Path("/home/jino/.local/share/fdroidserver-venv/bin/fdroid")
JAVA_HOME = "/home/jino/.local/java/jdk-21.0.12+8"
ANDROID_HOME = "/home/jino/Android/Sdk"
APKSIGNER = Path(ANDROID_HOME, "build-tools", "37.0.0", "apksigner")
PUBLIC_URL = "https://ionknow12.github.io/The-Droid/repo"


class ShipError(Exception):
    """Anything that must stop a release. Message is user-facing."""


# --------------------------------------------------------------------------- recipes


@dataclasses.dataclass(frozen=True)
class Recipe:
    package: str
    name: str
    project: Path
    gradle_task: str
    apk: Path  # relative to project
    metadata: Path | None  # relative to project
    repo_metadata: dict
    env_file: Path | None = None  # relative to project; KEY=VALUE lines fed to gradle (signing secrets)


_REQUIRED = ("package", "name", "project", "gradle_task", "apk")


def load_recipes(apps_dir: Path) -> list[Recipe]:
    recipes = []
    for f in sorted(apps_dir.glob("*.yml")):
        data = yaml.safe_load(f.read_text()) or {}
        missing = [k for k in _REQUIRED if k not in data]
        if missing:
            raise ShipError(f"{f.name}: missing keys {missing}")
        recipes.append(
            Recipe(
                package=data["package"],
                name=data["name"],
                project=Path(data["project"]),
                gradle_task=data["gradle_task"],
                apk=Path(data["apk"]),
                metadata=Path(data["metadata"]) if data.get("metadata") else None,
                repo_metadata=dict(data.get("repo_metadata") or {}),
                env_file=Path(data["env_file"]) if data.get("env_file") else None,
            )
        )
    return recipes


def find_recipe(recipes: list[Recipe], key: str) -> Recipe:
    for r in recipes:
        if key in (r.name, r.package):
            return r
    known = ", ".join(r.name for r in recipes)
    raise ShipError(f"no recipe named '{key}' (known: {known})")


# --------------------------------------------------------------------------- index


def published_version_codes(index_path: Path) -> dict[str, int]:
    """package -> highest versionCode currently in the repo index ({} if no index yet)."""
    if not index_path.is_file():
        return {}
    data = json.loads(index_path.read_text())
    out: dict[str, int] = {}
    for pkg, entry in data.get("packages", {}).items():
        codes = [v["manifest"]["versionCode"] for v in entry.get("versions", {}).values()]
        if codes:
            out[pkg] = max(codes)
    return out


# --------------------------------------------------------------------------- apk


@dataclasses.dataclass(frozen=True)
class ApkInfo:
    package: str
    version_code: int
    version_name: str
    signer_dn: str


def parse_apksigner_certs(text: str) -> str:
    for line in text.splitlines():
        if "certificate DN:" in line:
            return line.split("DN:", 1)[1].strip()
    raise ShipError("apksigner printed no signer certificate — APK is unsigned?")


def inspect_apk(path: Path) -> ApkInfo:
    from fdroidserver import common  # heavy import, keep local

    try:
        pkg, vcode, vname = common.get_apk_id(str(path))
    except Exception as e:  # androguard raises a zoo of types
        raise ShipError(f"cannot read {path.name}: {e}") from e
    if not APKSIGNER.is_file():
        raise ShipError(f"apksigner not found at {APKSIGNER}")
    proc = subprocess.run(
        [str(APKSIGNER), "verify", "--print-certs", str(path)],
        capture_output=True,
        text=True,
        env=build_env(),  # apksigner is a shell wrapper that needs `java` on PATH
    )
    if proc.returncode != 0:
        raise ShipError(f"apksigner verify failed for {path.name}:\n{proc.stderr or proc.stdout}")
    return ApkInfo(pkg, int(vcode), str(vname), parse_apksigner_certs(proc.stdout))


# --------------------------------------------------------------------------- gate


@dataclasses.dataclass(frozen=True)
class Decision:
    ok: bool
    reason: str


def decide(recipe: Recipe, apk: ApkInfo, published: dict[str, int]) -> Decision:
    if apk.package != recipe.package:
        return Decision(False, f"APK is {apk.package}, recipe expects {recipe.package}")
    if "Android Debug" in apk.signer_dn:
        return Decision(False, f"APK is DEBUG-signed ({apk.signer_dn}); build a release")
    have = published.get(recipe.package)
    if have is not None and apk.version_code <= have:
        return Decision(
            False,
            f"versionCode {apk.version_code} is not newer than published {have} — bump it",
        )
    return Decision(True, f"{recipe.package} {apk.version_name} ({apk.version_code}) > published {have}")


# --------------------------------------------------------------------------- metadata


def merge_repo_metadata(existing: dict, recipe_meta: dict) -> dict:
    merged = dict(existing)
    merged.update(recipe_meta)
    return merged


def sync_metadata(recipe: Recipe, repo_dir: Path, version_code: int) -> list[str]:
    """Write metadata/<pkg>.yml and copy the project's fastlane dir in. Returns warnings."""
    warnings: list[str] = []
    meta_dir = repo_dir / "metadata"
    meta_dir.mkdir(exist_ok=True)
    yml = meta_dir / f"{recipe.package}.yml"
    existing = yaml.safe_load(yml.read_text()) if yml.is_file() else {}
    yml.write_text(
        yaml.safe_dump(
            merge_repo_metadata(existing or {}, recipe.repo_metadata),
            sort_keys=False,
            allow_unicode=True,
        )
    )
    if recipe.metadata is None:
        warnings.append("no fastlane metadata dir in recipe — app page will be bare")
        return warnings
    src = recipe.project / recipe.metadata
    if not src.is_dir():
        warnings.append(f"fastlane dir missing: {src}")
        return warnings
    dst = meta_dir / recipe.package
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    if not (src / "en-US" / "changelogs" / f"{version_code}.txt").is_file():
        warnings.append(f"no changelogs/{version_code}.txt — phones will show no 'what's new'")
    return warnings


# --------------------------------------------------------------------------- orchestration


def build_env() -> dict:
    env = dict(os.environ)
    env["JAVA_HOME"] = JAVA_HOME
    env["ANDROID_HOME"] = ANDROID_HOME
    env["PATH"] = f"{JAVA_HOME}/bin:" + env.get("PATH", "")
    return env


def load_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE per line; '#' comments, blank lines and a leading 'export ' are ignored.
    Values are never logged — they are signing secrets."""
    if not path.is_file():
        raise ShipError(f"env_file not found: {path}")
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> str:
    print(f"  $ {' '.join(cmd)}   (in {cwd})", flush=True)
    proc = subprocess.run(
        cmd, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.splitlines()[-40:])
        raise ShipError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{tail}")
    return proc.stdout


def status_rows(recipes, published, probe):
    rows = []
    for r in recipes:
        built = probe.get(r.package)
        pub = published.get(r.package)
        if built is None:
            state = "UNBUILT"
        elif pub is None or built > pub:
            state = "STALE"
        else:
            state = "CURRENT"
        rows.append((r.name, r.package, built, pub, state))
    return rows


def probe_built_codes(recipes) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for r in recipes:
        p = r.project / r.apk
        try:
            out[r.package] = inspect_apk(p).version_code if p.is_file() else None
        except ShipError:
            out[r.package] = None
    return out


def ship_app(recipe: Recipe, *, dry_run: bool, no_push: bool) -> None:
    print(f"==> {recipe.name}: building {recipe.gradle_task}")
    started = time.time()
    if not (recipe.project / "gradlew").is_file():
        raise ShipError(f"no gradlew in {recipe.project}")
    env = build_env()
    if recipe.env_file is not None:
        secrets = load_env_file(recipe.project / recipe.env_file)
        env.update(secrets)
        print(f"  (loaded {len(secrets)} env var(s) from {recipe.env_file})")
    run(["./gradlew", recipe.gradle_task], cwd=recipe.project, env=env)
    apk_path = recipe.project / recipe.apk
    if not apk_path.is_file() or apk_path.stat().st_mtime < started:
        raise ShipError(f"build finished but {apk_path} is missing or stale")
    info = inspect_apk(apk_path)
    published = published_version_codes(INDEX_V2)
    d = decide(recipe, info, published)
    print(f"==> gate: {d.reason}")
    if not d.ok:
        raise ShipError(d.reason)
    dest = REPO_DIR / "repo" / f"{recipe.package}_{info.version_code}.apk"
    if dry_run:
        print(f"==> DRY RUN: would copy to {dest.name}, sync metadata, fdroid update, commit+push")
        return
    shutil.copy2(apk_path, dest)
    for w in sync_metadata(recipe, REPO_DIR, info.version_code):
        print(f"  WARNING: {w}")
    run([str(FDROID), "update"], cwd=REPO_DIR, env=build_env())
    after = published_version_codes(INDEX_V2).get(recipe.package)
    if after != info.version_code:
        raise ShipError(
            f"fdroid update ran but index shows {after}, expected {info.version_code} — NOT published"
        )
    title = recipe.repo_metadata.get("Name", recipe.name)
    run(["git", "add", "-A"], cwd=REPO_DIR)
    run(["git", "commit", "-m", f"{title} {info.version_name} ({info.version_code})"], cwd=REPO_DIR)
    if no_push:
        print("==> committed, not pushed (--no-push)")
        return
    run(["git", "push"], cwd=REPO_DIR)
    print(f"==> published {recipe.package} {info.version_name} ({info.version_code}) → {PUBLIC_URL}")
    print("    phones see it on their next repo refresh")


USAGE = """usage: ship <app|package> [--dry-run] [--no-push]
       ship status
       ship --all [--dry-run] [--no-push]"""


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    unknown = flags - {"--dry-run", "--no-push", "--all"}
    if unknown:
        print(f"unknown flag(s): {' '.join(sorted(unknown))}\n{USAGE}", file=sys.stderr)
        return 2
    dry, nopush = "--dry-run" in flags, "--no-push" in flags
    try:
        recipes = load_recipes(APPS_DIR)
        if args == ["status"]:
            published = published_version_codes(INDEX_V2)
            rows = status_rows(recipes, published, probe_built_codes(recipes))
            for name, pkg, built, pub, state in rows:
                print(f"{name:10} {pkg:24} built={built!s:6} repo={pub!s:6} {state}")
            return 0
        if "--all" in flags:
            published = published_version_codes(INDEX_V2)
            probe = probe_built_codes(recipes)
            rows = status_rows(recipes, published, probe)
            targets = [r for r, row in zip(recipes, rows) if row[4] == "STALE"]
            if not targets:
                print("nothing stale")
                return 0
        elif len(args) == 1:
            targets = [find_recipe(recipes, args[0])]
        else:
            print(USAGE)
            return 2
        for r in targets:
            ship_app(r, dry_run=dry, no_push=nopush)
        return 0
    except ShipError as e:
        print(f"\nSHIP FAILED: {e}", file=sys.stderr)
        return 1
