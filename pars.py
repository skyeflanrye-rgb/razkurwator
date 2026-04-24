#!/usr/bin/env python3
"""
TelegramS — Scrape members from a Telegram supergroup into members.csv.
Usage: python3 scraper.py
"""

import configparser
import csv
import os
import sys
import time

from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

# ── ANSI colours ─────────────────────────────────────────────────────────────
RED = "\033[1;31m"
GRN = "\033[1;32m"
CYN = "\033[1;36m"
RST = "\033[0m"

CHUNK_SIZE   = 200
OUTPUT_FILE  = "members.csv"


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


def pick_group(client: TelegramClient) -> object:
    """Fetch supergroups from dialogs and let the user choose one."""
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

    print(f"{GRN}[+] Choose a group to scrape members:{RST}\n")
    for i, g in enumerate(groups):
        print(f"{GRN}[{CYN}{i}{GRN}]{CYN} {g.title}{RST}")

    while True:
        try:
            idx = int(input(f"\n{GRN}[+] Enter a number: {RED}"))
            group = groups[idx]
            print(RST, end="")
            return group
        except (ValueError, IndexError):
            print(f"{RED}[!] Invalid choice, try again.{RST}")


def scrape_members(client: TelegramClient, group: object) -> list[dict]:
    """Return a list of member dicts for the given group."""
    print(f"\n{GRN}[+] Fetching members from {CYN}{group.title}{GRN} …{RST}")
    time.sleep(1)

    participants = client.get_participants(group, aggressive=True)

    members: list[dict] = []
    for user in participants:
        first = (user.first_name or "").strip()
        last  = (user.last_name  or "").strip()
        members.append({
            "username":    (user.username or "").strip(),
            "id":          user.id,
            "access_hash": user.access_hash,
            "name":        f"{first} {last}".strip(),
            "group":       group.title,
            "group_id":    group.id,
        })

    return members


def save_members(members: list[dict], filepath: str) -> None:
    """Write member list to a CSV file."""
    print(f"{GRN}[+] Saving {CYN}{len(members)}{GRN} members to {CYN}{filepath}{GRN} …{RST}")
    time.sleep(1)

    with open(filepath, "w", encoding="UTF-8", newline="") as f:
        writer = csv.writer(f, delimiter=",", lineterminator="\n")
        writer.writerow(["username", "user id", "access hash", "name", "group", "group id"])
        for m in members:
            writer.writerow([
                m["username"],
                m["id"],
                m["access_hash"],
                m["name"],
                m["group"],
                m["group_id"],
            ])

    print(f"{GRN}[✓] Members saved successfully.{RST}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
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
        print(RST, end="")

    os.system("clear")
    banner()

    group   = pick_group(client)
    members = scrape_members(client, group)
    save_members(members, OUTPUT_FILE)


if __name__ == "__main__":
    main()