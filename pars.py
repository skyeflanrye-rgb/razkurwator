#!/usr/bin/env python3
"""
TGPars — Scrape members from one or ALL Telegram supergroups into members.csv.
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

# ── ANSI colours ──────────────────────────────────────────────────────────────
RED = "\033[1;31m"
GRN = "\033[1;32m"
CYN = "\033[1;36m"
YLW = "\033[1;33m"
RST = "\033[0m"

CHUNK_SIZE  = 200   # диалогов за один запрос
OUTPUT_FILE = "members.csv"
DELAY       = 2     # секунд между группами (защита от flood-limit)


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


def fetch_all_groups(client: TelegramClient) -> list:
    """Загружает ВСЕ супергруппы из диалогов (обходит лимит 200 за запрос)."""
    groups      = []
    seen_ids    = set()
    offset_date = None
    offset_id   = 0
    offset_peer = InputPeerEmpty()

    print(f"{GRN}[+] Загружаю список групп …{RST}")

    while True:
        result = client(GetDialogsRequest(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=CHUNK_SIZE,
            hash=0,
        ))

        if not result.chats:
            break

        for chat in result.chats:
            if getattr(chat, "megagroup", False) and chat.id not in seen_ids:
                groups.append(chat)
                seen_ids.add(chat.id)

        # Если диалогов меньше chunk_size — все загружены
        if len(result.dialogs) < CHUNK_SIZE:
            break

        # Смещение для следующей страницы
        last_msg    = result.messages[-1]
        last_dlg    = result.dialogs[-1]
        offset_id   = last_msg.id
        offset_date = last_msg.date
        offset_peer = last_dlg.peer

    print(f"{GRN}[+] Найдено супергрупп: {CYN}{len(groups)}{RST}\n")
    return groups


def pick_mode(groups: list) -> tuple[str, list]:
    """Предлагает выбрать режим: одна группа или все сразу."""
    print(f"{GRN}[1]{CYN} Парсить одну группу")
    print(f"{GRN}[2]{CYN} Парсить ВСЕ группы ({YLW}{len(groups)}{CYN} шт.) → общая база{RST}\n")

    while True:
        try:
            mode = int(input(f"{GRN}Выбери режим: {RED}"))
            print(RST, end="")
            if mode == 1:
                return "single", pick_one_group(groups)
            elif mode == 2:
                return "all", groups
            print(f"{RED}[!] Введи 1 или 2.{RST}")
        except ValueError:
            print(f"{RED}[!] Введи число.{RST}")


def pick_one_group(groups: list) -> list:
    """Показывает список и возвращает одну выбранную группу."""
    print(f"\n{GRN}[+] Выбери группу:{RST}\n")
    for i, g in enumerate(groups):
        print(f"{GRN}[{CYN}{i:>3}{GRN}]{CYN} {g.title}{RST}")

    while True:
        try:
            idx = int(input(f"\n{GRN}[+] Введи номер: {RED}"))
            print(RST, end="")
            return [groups[idx]]
        except (ValueError, IndexError):
            print(f"{RED}[!] Неверный выбор, попробуй снова.{RST}")


def scrape_group(client: TelegramClient, group: object) -> list[dict]:
    """Возвращает список участников одной группы."""
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


def scrape_all(client: TelegramClient, groups: list) -> list[dict]:
    """Парсит все группы, дедуплицирует по user_id."""
    all_members: dict[int, dict] = {}   # id → member
    total = len(groups)

    for idx, group in enumerate(groups, 1):
        print(
            f"{GRN}[{CYN}{idx}/{total}{GRN}] "
            f"Парсю: {CYN}{group.title}{RST} … ",
            end="", flush=True,
        )
        try:
            members = scrape_group(client, group)
            new = sum(
                1 for m in members
                if m["id"] not in all_members
                and not all_members.update({m["id"]: m})  # type: ignore[func-returns-value]
            )
            print(f"{GRN}+{new} новых  (уникальных: {CYN}{len(all_members)}{GRN}){RST}")
        except Exception as exc:
            print(f"{RED}ошибка — {exc}{RST}")

        if idx < total:
            time.sleep(DELAY)

    return list(all_members.values())


def save_members(members: list[dict], filepath: str) -> None:
    """Записывает список участников в CSV."""
    print(
        f"\n{GRN}[+] Сохраняю {CYN}{len(members)}{GRN} "
        f"уникальных участников → {CYN}{filepath}{RST}"
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

    groups = fetch_all_groups(client)

    if not groups:
        print(f"{RED}[!] Супергрупп не найдено в аккаунте.{RST}")
        sys.exit(1)

    mode, selected = pick_mode(groups)
    print()

    if mode == "single":
        print(f"{GRN}[+] Парсю: {CYN}{selected[0].title}{RST}\n")
        raw     = scrape_group(client, selected[0])
        members = list({m["id"]: m for m in raw}.values())
    else:
        print(f"{GRN}[+] Запускаю парсинг всех {CYN}{len(selected)}{GRN} групп …{RST}\n")
        members = scrape_all(client, selected)

    save_members(members, OUTPUT_FILE)


if __name__ == "__main__":
    main()
