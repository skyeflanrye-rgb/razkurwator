#!/usr/bin/env python3
"""
setup.py — TeleGram-Scraper configuration & utility tool.
Re-run at any time to fix a wrong config value.
"""

import os
import sys
import time
import argparse

# ── ANSI colour helpers ────────────────────────────────────────────────────────
RE = "\033[1;31m"   # red
GR = "\033[1;32m"   # green
CY = "\033[1;36m"   # cyan
RS = "\033[0m"      # reset

def ok(msg: str) -> str:
    """Green [+] prefix."""
    return f"{GR}[{CY}+{GR}]{CY} {msg}{RS}"

def warn(msg: str) -> str:
    """Red [!] prefix."""
    return f"{GR}[{RE}!{GR}]{CY} {msg}{RS}"


# ── Banner ─────────────────────────────────────────────────────────────────────
def banner() -> None:
    os.system("clear")
    print(f"""
    {RE}╔═╗{CY}┌─┐┌┬┐┬ ┬┌─┐
    {RE}╚═╗{CY}├┤  │ │ │├─┘
    {RE}╚═╝{CY}└─┘ ┴ └─┘┴
    {RS}""")


# ── Install requirements ───────────────────────────────────────────────────────
def requirements() -> None:
    def install_csv_libs() -> None:
        banner()
        print(ok("Installing CSV libraries — this may take a while …"))
        os.system("pip3 install cython numpy pandas")

    banner()
    print(ok("CSV merge support requires an extra ~10 min to install."))
    choice = input(ok("Enable CSV merge? (y/n): ")).strip().lower()
    if choice == "y":
        install_csv_libs()

    print(ok("Installing core requirements …"))
    os.system(
        "pip3 install telethon requests configparser && "
        "touch config.data"
    )
    banner()
    print(ok("All requirements installed.\n"))


# ── API config setup ───────────────────────────────────────────────────────────
def config_setup() -> None:
    import configparser

    banner()
    cfg = configparser.RawConfigParser()
    cfg.add_section("cred")

    api_id    = input(f"{GR}[+] Enter API ID    : {RE}").strip()
    api_hash  = input(f"{GR}[+] Enter hash ID   : {RE}").strip()
    phone     = input(f"{GR}[+] Enter phone no. : {RE}").strip()

    cfg.set("cred", "id",    api_id)
    cfg.set("cred", "hash",  api_hash)
    cfg.set("cred", "phone", phone)

    with open("config.data", "w") as fh:
        cfg.write(fh)

    print(f"\n{ok('Configuration saved to config.data!')}{RS}")


# ── Merge two CSV files ────────────────────────────────────────────────────────
def merge_csv(file1_path: str, file2_path: str) -> None:
    try:
        import pandas as pd
    except ImportError:
        print(warn("pandas is not installed. Run: python3 setup.py --install"))
        sys.exit(1)

    banner()
    print(ok(f"Merging '{file1_path}' & '{file2_path}' …"))
    print(ok("Large files may take a while …"))

    f1 = pd.read_csv(file1_path)
    f2 = pd.read_csv(file2_path)
    merged = f1.merge(f2, on="username")
    merged.to_csv("output.csv", index=False)

    print(ok(f"Saved merged file as output.csv  ({len(merged)} rows)\n"))


# ── Self-update ────────────────────────────────────────────────────────────────
LATEST_VERSION = "3"
BASE_URL = "https://raw.githubusercontent.com/th3unkn0n/TeleGram-Scraper/master"
SCRIPTS  = ["add2group.py", "scraper.py", "setup.py", "smsbot.py"]

def update_tool() -> None:
    try:
        import requests
    except ImportError:
        print(warn("requests is not installed. Run: python3 setup.py --install"))
        sys.exit(1)

    banner()
    print(ok("Checking for updates …"))

    try:
        resp = requests.get(f"{BASE_URL}/.image/.version", timeout=10)
        resp.raise_for_status()
        remote_version = resp.text.strip()
    except Exception as exc:
        print(warn(f"Could not reach update server: {exc}"))
        sys.exit(1)

    if remote_version == LATEST_VERSION:
        print(ok("Already on the latest version.\n"))
        return

    print(ok(f"New version {remote_version} found — updating …"))

    print(ok("Removing old files …"))
    os.system("rm -f *.py")
    time.sleep(2)

    print(ok("Downloading latest files …"))
    for script in SCRIPTS:
        os.system(f"curl -s -O {BASE_URL}/{script}")
    os.system("chmod 755 *.py")
    time.sleep(2)

    print(ok("Update complete.\n"))


# ── CLI ────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="TeleGram-Scraper — setup & utility tool",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 setup.py --install\n"
            "  python3 setup.py --config\n"
            "  python3 setup.py --merge contacts.csv members.csv\n"
            "  python3 setup.py --update\n"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-i", "--install", action="store_true",
                       help="Install required Python packages")
    group.add_argument("-c", "--config",  action="store_true",
                       help="Set up API credentials (id / hash / phone)")
    group.add_argument("-m", "--merge",   nargs=2, metavar=("FILE1", "FILE2"),
                       help="Merge two CSV files on the 'username' column")
    group.add_argument("-u", "--update",  action="store_true",
                       help="Update tool to the latest version")
    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if args.install:
        requirements()
    elif args.config:
        config_setup()
    elif args.merge:
        merge_csv(*args.merge)
    elif args.update:
        update_tool()


if __name__ == "__main__":
    main()
