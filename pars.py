#!/usr/bin/env python3
"""
TGPars — Scrape members from ALL Telegram supergroups into members.csv.
Usage: python3 pars.py
"""

import configparser
import csv
import os
import sys
import time

from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.errors import FloodWaitError, RPCError

# ── ANSI colours ──────────────────────────────────────────────────────────────
RED = "\033[1;31m"
GRN = "\033[1;32m"
CYN = "\033[1;36m"
YLW = "\033[1;33m"
RST = "\033[0m"

CHUNK_SIZE  = 200   # диалогов за один запрос
OUTPUT_FILE = "members.csv"
DELAY       = 2     # секунд между группами
FLOOD_EXTRA = 10    # доп. секунд поверх требования Telegram при FloodWait
MAX_RETRIES = 3     # попыток повтора на одну группу


def banner() -> None:
    print(f"""
{RED}╔╦╗{CYN}┌─┐┌─┐┌─┐┌─┐┬─┐{RED}╔═╗
{RED} ║ {CYN}├─┤├┤ ├─┘├─┤├┬┘{RED}╚═╗
{RED} ╩ {CYN}└─┘└─┘┴  ┴ ┴┴└─{RED}╚═╝{RST}
by https://github.com/elizhabs
""")


def load_config() -> tuple[str, str, str]:
    """Читает credentials из config.data."""
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
        print(f"{RED}[!] Сначала выполни: python3 setup.py --config\n{RST}")
        sys.exit(1)


def flood_wait(seconds: int, label: str = "") -> None:
    """Ждёт нужное время при FloodWaitError с обратным отсчётом."""
    total  = seconds + FLOOD_EXTRA
    prefix = f"{YLW}[~] FloodWait{f' ({label})' if label else ''}: ждём"
    for remaining in range(total, 0, -1):
        print(f"\r{prefix} {remaining:>4}s …{RST}", end="", flush=True)
        time.sleep(1)
    print(f"\r{GRN}[✓] FloodWait снят, продолжаем.           {RST}")


def fetch_groups(client: TelegramClient) -> list:
    """Загружает все супергруппы из диалогов одним запросом."""
    print(f"{GRN}[+] Загружаю список групп …{RST}")

    result = client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=CHUNK_SIZE,
        hash=0,
    ))

    groups = [c for c in result.chats if getattr(c, "megagroup", False)]
    print(f"{GRN}[+] Найдено супергрупп: {CYN}{len(groups)}{RST}\n")
    return groups


def scrape_group(client: TelegramClient, group) -> list[dict]:
    """
    Возвращает участников группы с retry при FloodWait.

    Тихо пропускает:
      CHANNEL_MONOFORUM_UNSUPPORTED — Discussion-чат канала
      CHANNEL_PRIVATE               — нет доступа
      CHAT_ADMIN_REQUIRED           — нужны права администратора
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            participants = client.get_participants(group, aggressive=True)
            break
        except FloodWaitError as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"FloodWait {e.seconds}s — исчерпаны попытки")
            flood_wait(e.seconds, label=group.title)
        except RPCError as e:
            code = getattr(e, "message", str(e))
            if "CHANNEL_MONOFORUM_UNSUPPORTED" in code:
                raise RuntimeError("monoforum (Discussion-чат канала)")
            if "CHANNEL_PRIVATE" in code:
                raise RuntimeError("группа приватная — нет доступа")
            if "CHAT_ADMIN_REQUIRED" in code:
                raise RuntimeError("нужны права администратора")
            raise

    members: list[dict] = []
    for user in participants:
        if getattr(user, "deleted", False):
            continue
        if getattr(user, "bot", False):
            continue
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


def scrape_all(client: TelegramClient, groups: list) -> list[dict]:
    """Парсит все группы, дедуплицирует по user_id."""
    all_members: dict[int, dict] = {}
    total   = len(groups)
    skipped = 0
    failed  = 0

    for idx, group in enumerate(groups, 1):
        print(
            f"{GRN}[{CYN}{idx}/{total}{GRN}] "
            f"Парсю: {CYN}{group.title}{RST} … ",
            end="", flush=True,
        )
        try:
            members = scrape_group(client, group)
            new = 0
            for m in members:
                if m["id"] not in all_members:
                    all_members[m["id"]] = m
                    new += 1
            print(
                f"{GRN}+{new} участников  "
                f"(уникальных в базе: {CYN}{len(all_members)}{GRN}){RST}"
            )
        except RuntimeError as e:
            print(f"{YLW}пропущено — {e}{RST}")
            skipped += 1
        except Exception as exc:
            print(f"{RED}ошибка — {exc}{RST}")
            failed += 1

        if idx < total:
            time.sleep(DELAY)

    print(
        f"\n{GRN}Итог: обработано {CYN}{total - skipped - failed}{GRN} | "
        f"пропущено {CYN}{skipped}{GRN} | "
        f"ошибок {CYN}{failed}{RST}"
    )
    return list(all_members.values())


def save_members(members: list[dict], filepath: str) -> None:
    """Записывает список участников в CSV."""
    print(
        f"\n{GRN}[+] Сохраняю {CYN}{len(members)}{GRN} "
        f"участников → {CYN}{filepath}{RST}"
    )
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
    print(f"{GRN}[✓] Готово. Файл сохранён: {CYN}{filepath}{RST}")


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
        client.sign_in(phone, input(f"{GRN}[+] Введи код из Telegram: {RED}"))
        print(RST, end="")

    os.system("clear")
    banner()

    groups = fetch_groups(client)

    if not groups:
        print(f"{RED}[!] Супергрупп не найдено в аккаунте.{RST}")
        sys.exit(1)

    members = scrape_all(client, groups)
    save_members(members, OUTPUT_FILE)


if __name__ == "__main__":
    main()
