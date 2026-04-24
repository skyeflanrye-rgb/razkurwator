#!/usr/bin/env python3
"""
TelegramS — Add members to a Telegram group from a CSV file.
Usage: python3 add_members.py members.csv
"""

import configparser
import csv
import os
import random
import sys
import time
import traceback

from telethon.errors.rpcerrorlist import PeerFloodError, UserPrivacyRestrictedError
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerChannel, InputPeerEmpty, InputPeerUser

# ── ANSI colours ────────────────────────────────────────────────────────────
RED  = "\033[1;31m"
GRN  = "\033[1;32m"
CYN  = "\033[1;36m"
RST  = "\033[0m"

CHUNK_SIZE   = 200
FLOOD_LIMIT  = 50          # pause after this many successful adds
MIN_DELAY    = 10
MAX_DELAY    = 30


def banner() -> None:
    print(f"""
{RED}╔╦╗{CYN}┌─┐┌─┐┌─┐┌─┐┬─┐{RED}╔═╗
{RED} ║ {CYN}├─┤├┤ ├─┘├─┤├┬┘{RED}╚═╗
{RED} ╩ {CYN}└─┘└─┘┴  ┴ ┴┴└─{RED}╚═╝{RST}
by https://github.com/elizhabs
""")


def load_config() -> tuple[str, str, str]:
    """Read credentials from config.data; exit with a hint if missing."""
    cpass = configparser.RawConfigParser()
    cpass.read("config.data")
    try:
        return (
            cpass["cred"]["id"],
            cpass["cred"]["hash"],
            cpass["cred"]["phone"],
        )
    except KeyError:
        os.system("clear")
        banner()
        print(f"{RED}[!] Run  python3 setup.py  first!\n{RST}")
        sys.exit(1)


def load_users(filepath: str) -> list[dict]:
    """Parse a CSV produced by the scraper script."""
    users: list[dict] = []
    try:
        with open(filepath, encoding="UTF-8") as f:
            rows = csv.reader(f, delimiter=",", lineterminator="\n")
            next(rows, None)          # skip header
            for row in rows:
                if len(row) < 4:
                    continue
                users.append({
                    "username":    row[0].strip(),
                    "id":          int(row[1]),
                    "access_hash": int(row[2]),
                    "name":        row[3].strip(),
                })
    except FileNotFoundError:
        print(f"{RED}[!] File not found: {filepath}{RST}")
        sys.exit(1)
    except ValueError as exc:
        print(f"{RED}[!] Bad CSV data: {exc}{RST}")
        sys.exit(1)
    return users


def pick_group(client: TelegramClient) -> object:
    """Fetch megagroups and let the user choose one."""
    result = client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=CHUNK_SIZE,
        hash=0,
    ))

    groups = [c for c in result.chats if getattr(c, "megagroup", False)]

    if not groups:
        print(f"{RED}[!] No supergroups found in your account.{RST}")
        sys.exit(1)

    for i, g in enumerate(groups):
        print(f"{GRN}[{CYN}{i}{GRN}]{CYN} {g.title}{RST}")

    while True:
        try:
            idx = int(input(f"\n{GRN}[+] Choose a group number: {RED}"))
            return groups[idx]
        except (ValueError, IndexError):
            print(f"{RED}[!] Invalid choice, try again.{RST}")


def choose_mode() -> int:
    print(f"\n{GRN}[1] Add by username")
    print(f"{GRN}[2] Add by user ID")
    while True:
        try:
            mode = int(input(f"{GRN}Select mode: {RED}"))
            if mode in (1, 2):
                return mode
            print(f"{RED}[!] Enter 1 or 2.{RST}")
        except ValueError:
            print(f"{RED}[!] Enter a number.{RST}")


def add_members(
    client: TelegramClient,
    target: InputPeerChannel,
    users: list[dict],
    mode: int,
) -> None:
    added = 0
    skipped = 0

    for i, user in enumerate(users, 1):
        try:
            # resolve the peer
            if mode == 1:
                if not user["username"]:
                    print(f"{RED}[-] No username for ID {user['id']}, skipping.{RST}")
                    skipped += 1
                    continue
                peer = client.get_input_entity(user["username"])
            else:
                peer = InputPeerUser(user["id"], user["access_hash"])

            display = user["username"] or str(user["id"])
            print(f"{GRN}[{i}/{len(users)}] Adding {CYN}{display}{RST} … ", end="", flush=True)

            client(InviteToChannelRequest(target, [peer]))
            added += 1
            print(f"{GRN}OK{RST}")

            # take a longer break every FLOOD_LIMIT successful adds
            if added % FLOOD_LIMIT == 0:
                pause = random.randint(60, 120)
                print(f"{GRN}[~] {added} members added — cooling down for {pause}s …{RST}")
                time.sleep(pause)
            else:
                delay = random.randint(MIN_DELAY, MAX_DELAY)
                print(f"{GRN}[~] Waiting {delay}s …{RST}")
                time.sleep(delay)

        except PeerFloodError:
            print(f"\n{RED}[!] Flood error — Telegram rate-limited this account.")
            print(f"[!] Stopping. Resume after some time.{RST}")
            break

        except UserPrivacyRestrictedError:
            print(f"{RED}skipped (privacy settings){RST}")
            skipped += 1

        except KeyboardInterrupt:
            print(f"\n{RED}[!] Interrupted by user.{RST}")
            break

        except Exception:
            traceback.print_exc()
            print(f"{RED}[!] Unexpected error — skipping.{RST}")
            skipped += 1

    print(f"\n{GRN}[✓] Done. Added: {added}  |  Skipped: {skipped}{RST}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(f"{RED}Usage: python3 {sys.argv[0]} members.csv{RST}")
        sys.exit(1)

    os.system("clear")
    banner()

    api_id, api_hash, phone = load_config()

    client = TelegramClient(phone, api_id, api_hash)
    client.connect()

    if not client.is_user_authorized():
        client.send_code_request(phone)
        os.system("clear")
        banner()
        client.sign_in(phone, input(f"{GRN}[+] Enter the code: {RED}"))

    os.system("clear")
    banner()

    users = load_users(sys.argv[1])
    if not users:
        print(f"{RED}[!] No users found in the CSV file.{RST}")
        sys.exit(1)

    print(f"{GRN}[+] Loaded {CYN}{len(users)}{GRN} users from CSV.{RST}\n")

    group       = pick_group(client)
    target_peer = InputPeerChannel(group.id, group.access_hash)
    mode        = choose_mode()

    print(f"\n{GRN}[+] Starting to add members to {CYN}{group.title}{RST}\n")
    add_members(client, target_peer, users, mode)


if __name__ == "__main__":
    main()