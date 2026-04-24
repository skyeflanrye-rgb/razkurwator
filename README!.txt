Установка RAZKURWATOR

**Termux (Android)**

```
pkg update && pkg upgrade -y
pkg install python3 python3-pip git -y
git clone https://github.com/skyeflanrye-rgb/razkurwator/
cd TGPars
python3 setup.py --install
```

---

**Получение API-ключей**

* Открой [my.telegram.org](https://my.telegram.org) и войди в аккаунт
* Перейди в **API Development Tools**
* Создай приложение — получишь `api_id` и `api_hash`

---

**Настройка конфига**

```
python3 setup.py --config
```
* Введи `api_id`
* Введи `api_hash`
* Введи номер телефона в формате `+79001234567`

---

**Использование**

```
# 1. Собрать участников группы → members.csv
python3 pars.py

# 2. Пригласить участников в свою группу
python3 invite.py members.csv

# 3. Разослать сообщения
python3 smsbot.py members.csv
```

---

**Опционально**

```
# Объединить два CSV-файла
python3 setup.py --merge file1.csv file2.csv

# Обновить скрипты до последней версии
python3 setup.py --update

# Для первого запуска выполни:

python3 setup.py --install   # установить зависимости
python3 setup.py --config    # ввести api_id / hash / phone
python3 pars.py              # собрать участников → members.csv
python3 invite.py members.csv   # пригласить в группу
python3 smsbot.py members.csv   # разослать сообщения