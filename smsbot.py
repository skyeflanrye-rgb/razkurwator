#!/usr/bin/env python3
"""
TelegramS — Send a message to every user listed in a CSV file.
Usage: python3 sender.py members.csv
"""

import configparser
import csv
import os
import sys
import time

from telethon.errors.rpcerrorlist import PeerFloodError
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerUser

# ── ANSI colours ──────────────────────────────────────────────────────────────
RED = "\033[1;31m"
GRN = "\033[1;32m"
CYN = "\033[1;36m"
RST = "\033[0m"

SLEEP_TIME = 30          # seconds between messages


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


def choose_mode() -> int:
    print(f"\n{GRN}[1] Send by user ID")
    print(f"{GRN}[2] Send by username")
    while True:
        try:
            mode = int(input(f"{GRN}Select mode: {RED}"))
            print(RST, end="")
            if mode in (1, 2):
                return mode
            print(f"{RED}[!] Enter 1 or 2.{RST}")
        except ValueError:
            print(f"{RED}[!] Enter a number.{RST}")


def send_messages(
    client: TelegramClient,
    users: list[dict],
    message: str,
    mode: int,
) -> None:
    sent    = 0
    skipped = 0

    for i, user in enumerate(users, 1):
        # ── resolve peer ──────────────────────────────────────────────────────
        if mode == 2:
            if not user["username"]:
                print(f"{RED}[-] No username for ID {user['id']}, skipping.{RST}")
                skipped += 1
                continue
            receiver = client.get_input_entity(user["username"])
        else:
            receiver = InputPeerUser(user["id"], user["access_hash"])

        # ── send ──────────────────────────────────────────────────────────────
        try:
            display = user["name"] or user["username"] or str(user["id"])
            print(f"{GRN}[{i}/{len(users)}] Sending to {CYN}{display}{GRN} … ", end="", flush=True)

            client.send_message(receiver, message.format(user["name"]))
            sent += 1
            print(f"{GRN}OK{RST}")

            print(f"{GRN}[~] Waiting {SLEEP_TIME}s …{RST}")
            time.sleep(SLEEP_TIME)

        except PeerFloodError:
            print(f"\n{RED}[!] Flood error — Telegram rate-limited this account.")
            print(f"[!] Stopping. Resume after some time.{RST}")
            break

        except KeyboardInterrupt:
            print(f"\n{RED}[!] Interrupted by user.{RST}")
            break

        except Exception as exc:
            print(f"{RED}failed ({exc}){RST}")
            print(f"{RED}[!] Skipping and continuing …{RST}")
            skipped += 1

    print(f"\n{GRN}[✓] Done. Sent: {sent}  |  Skipped: {skipped}{RST}")


# ── Entry point ───────────────────────────────────────────────────────────────

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
        print(RST, end="")

    os.system("clear")
    banner()

    users = load_users(sys.argv[1])
    if not users:
        print(f"{RED}[!] No users found in the CSV file.{RST}")
        client.disconnect()
        sys.exit(1)

    print(f"{GRN}[+] Loaded {CYN}{len(users)}{GRN} users from CSV.{RST}")

    mode    = choose_mode()
    message = input(f"{GRN}[+] Enter your message: {RED}")
    print(RST, end="")

    print(f"\n{GRN}[+] Starting to send messages …{RST}\n")

    try:
        send_messages(client, users, message, mode)
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()