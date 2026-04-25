#!/usr/bin/env python3
"""
TGPars — Scrape ACTIVE members from one or ALL Telegram supergroups.
Filters out bots, deleted accounts, and users with no recent activity.
Usage: python3 pars.py
"""

import configparser
import csv
import os
import sys
import time

from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest, GetHistoryRequest
from telethon.tl.types import (
    InputPeerEmpty,
    InputPeerChannel,
    PeerUser,
)
from telethon.errors import (
    ChannelPrivateError,
    ChatAdminRequiredError,
    RPCError,
)

# ── ANSI colours ──────────────────────────────────────────────────────────────
RED = "\033[1;31m"
GRN = "\033[1;32m"
CYN = "\033[1;36m"
YLW = "\033[1;33m"
RST = "\033[0m"

CHUNK_SIZE   = 200    # диалогов за один запрос
MSG_LIMIT    = 500    # сообщений истории для поиска активных
OUTPUT_FILE  = "members.csv"
DELAY        = 2      # секунд между группами


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
    """Загружает ВСЕ супергруппы (пагинация через offset)."""
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

        if len(result.dialogs) < CHUNK_SIZE:
            break

        last_msg    = result.messages[-1]
        last_dlg    = result.dialogs[-1]
        offset_id   = last_msg.id
        offset_date = last_msg.date
        offset_peer = last_dlg.peer

    print(f"{GRN}[+] Найдено супергрупп: {CYN}{len(groups)}{RST}\n")
    return groups


def pick_mode(groups: list) -> tuple[str, list]:
    """Режим: одна группа или все сразу."""
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
    """Список групп → выбор одной."""
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


def is_active_user(user) -> bool:
    """
    Возвращает True если пользователь — живой активный человек.

    Отсеиваем:
      • bot=True           — официальные боты
      • deleted=True       — удалённые аккаунты
      • fake=True          — аккаунты помечены Telegram как фейк
      • scam=True          — скам-аккаунты
      • first_name is None — пустые/удалённые профили
    """
    if getattr(user, "bot", False):
        return False
    if getattr(user, "deleted", False):
        return False
    if getattr(user, "fake", False):
        return False
    if getattr(user, "scam", False):
        return False
    if not user.first_name and not user.last_name and not user.username:
        return False
    return True


def get_active_ids_from_history(
    client: TelegramClient,
    group,
    limit: int = MSG_LIMIT,
) -> set[int]:
    """
    Читает последние `limit` сообщений группы и собирает id тех,
    кто реально писал (оставлял сообщения/комментарии).
    """
    active_ids: set[int] = set()
    try:
        peer = InputPeerChannel(group.id, group.access_hash)
        result = client(GetHistoryRequest(
            peer=peer,
            offset_id=0,
            offset_date=None,
            add_offset=0,
            limit=limit,
            max_id=0,
            min_id=0,
            hash=0,
        ))
        for msg in result.messages:
            if msg.from_id and isinstance(msg.from_id, PeerUser):
                active_ids.add(msg.from_id.user_id)
    except Exception:
        pass  # если нет доступа к истории — пропускаем
    return active_ids


def scrape_group(
    client: TelegramClient,
    group,
    active_only: bool = True,
) -> list[dict]:
    """
    Возвращает участников группы.
    Если active_only=True — только те, кто писал в последних MSG_LIMIT сообщениях
    и прошёл базовую проверку (не бот, не удалён и т.д.).

    Возможные пропуски:
      CHANNEL_MONOFORUM_UNSUPPORTED — чат-комментарии канала (не супергруппа)
      CHANNEL_PRIVATE               — нет доступа к группе
      CHAT_ADMIN_REQUIRED           — нужны права администратора
    """
    try:
        participants = client.get_participants(group, aggressive=True)
    except RPCError as e:
        code = getattr(e, "message", str(e))
        if "CHANNEL_MONOFORUM_UNSUPPORTED" in code:
            raise RuntimeError("monoforum — пропускаем (Discussion-чат канала)")
        if "CHANNEL_PRIVATE" in code:
            raise RuntimeError("группа приватная — нет доступа")
        if "CHAT_ADMIN_REQUIRED" in code:
            raise RuntimeError("нужны права администратора")
        raise

    # ID тех, кто реально писал
    active_ids = get_active_ids_from_history(client, group) if active_only else set()

    members: list[dict] = []
    for user in participants:
        # 1. Базовая фильтрация (бот / удалён / скам / пустой)
        if not is_active_user(user):
            continue

        # 2. Если включён режим active_only — только писавшие в чат
        if active_only and active_ids and user.id not in active_ids:
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


def scrape_all(
    client: TelegramClient,
    groups: list,
    active_only: bool = True,
) -> list[dict]:
    """Парсит все группы, дедуплицирует по user_id."""
    all_members: dict[int, dict] = {}
    total    = len(groups)
    skipped  = 0
    failed   = 0

    for idx, group in enumerate(groups, 1):
        print(
            f"{GRN}[{CYN}{idx}/{total}{GRN}] "
            f"Парсю: {CYN}{group.title}{RST} … ",
            end="", flush=True,
        )
        try:
            members = scrape_group(client, group, active_only=active_only)
            new = 0
            for m in members:
                if m["id"] not in all_members:
                    all_members[m["id"]] = m
                    new += 1
            print(
                f"{GRN}+{new} активных  "
                f"(уникальных в базе: {CYN}{len(all_members)}{GRN}){RST}"
            )
        except RuntimeError as e:
            # Ожидаемые пропуски (monoforum, приватная и т.д.)
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

    groups = fetch_all_groups(client)

    if not groups:
        print(f"{RED}[!] Супергрупп не найдено в аккаунте.{RST}")
        sys.exit(1)

    # Режим фильтрации
    print(f"{GRN}Фильтр активности:{RST}")
    print(f"{GRN}[1]{CYN} Только активные (писали в последних {MSG_LIMIT} сообщениях) {YLW}← рекомендуется")
    print(f"{GRN}[2]{CYN} Все живые люди (без ботов и удалённых, без проверки активности){RST}\n")

    active_only = True
    while True:
        try:
            f = int(input(f"{GRN}Выбери фильтр: {RED}"))
            print(RST, end="")
            if f == 1:
                active_only = True
                break
            elif f == 2:
                active_only = False
                break
            print(f"{RED}[!] Введи 1 или 2.{RST}")
        except ValueError:
            print(f"{RED}[!] Введи число.{RST}")

    print()
    mode, selected = pick_mode(groups)
    print()

    if mode == "single":
        group = selected[0]
        print(f"{GRN}[+] Парсю: {CYN}{group.title}{RST}\n")
        raw     = scrape_group(client, group, active_only=active_only)
        members = list({m["id"]: m for m in raw}.values())
        print(f"{GRN}[+] Найдено активных участников: {CYN}{len(members)}{RST}")
    else:
        print(
            f"{GRN}[+] Запускаю парсинг всех {CYN}{len(selected)}{GRN} групп "
            f"(фильтр: {'активные' if active_only else 'все живые'}) …{RST}\n"
        )
        members = scrape_all(client, selected, active_only=active_only)

    save_members(members, OUTPUT_FILE)


if __name__ == "__main__":
    main()
