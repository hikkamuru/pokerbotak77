# 🃏 Poker Club Bot

Telegram бот с Mini App для покерного клуба.  
Турниры · Рейтинг · Бронирование · Уведомления · Панель администратора

---

## Структура проекта

```
poker_bot/
├── main.py                        ← Точка входа (бот + веб-сервер)
├── seed.py                        ← Наполнить БД тестовыми данными
├── requirements.txt
├── .env.example                   ← Шаблон настроек
│
├── config/
│   └── settings.py                ← Настройки из .env
│
├── app/
│   ├── database.py                ← Вся работа с SQLite
│   ├── keyboards.py               ← Все кнопки бота
│   ├── middlewares/
│   │   └── auth.py                ← Авто-регистрация игроков
│   ├── handlers/
│   │   ├── start.py               ← /start
│   │   ├── tournament.py          ← Турниры и регистрация
│   │   ├── booking.py             ← Бронирование столиков
│   │   ├── profile.py             ← Профиль и рейтинг
│   │   └── admin.py               ← Панель /admin
│   └── services/
│       └── notifications.py       ← Авто-напоминания (24ч и 1ч)
│
├── mini_app/
│   ├── server.py                  ← aiohttp сервер + REST API
│   └── templates/
│       └── index.html             ← Mini App (тёмный дизайн)
│
└── deploy/
    ├── nginx.conf                 ← Конфиг Nginx (HTTPS)
    └── poker_bot.service          ← systemd unit-файл
```

---

## Быстрый старт

### 1. Получи токен бота

1. Открой [@BotFather](https://t.me/BotFather)
2. `/newbot` → введи имя и username
3. Скопируй токен

### 2. Узнай свой Telegram ID

Напиши [@userinfobot](https://t.me/userinfobot) — он пришлёт твой ID

### 3. Установка

```bash
# Клонируй / загрузи на сервер
cd poker_bot

# Создай виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установи зависимости
pip install -r requirements.txt

# Настрой .env
cp .env.example .env
nano .env
```

### 4. Заполни .env

```env
BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=123456789
CLUB_NAME=Мой Покер Клуб
CLUB_CITY=Москва
CLUB_ADDRESS=ул. Примерная, д.1
WEBAPP_URL=https://yourdomain.com
WEBAPP_PORT=8080
```

### 5. Запуск

```bash
# Первый запуск — заполни тестовые данные (опционально)
python seed.py

# Запуск бота
python main.py
```

---

## Деплой на VPS (Ubuntu/Debian)

### Шаг 1 — Nginx + SSL

```bash
sudo apt install nginx certbot python3-certbot-nginx -y

# Скопируй конфиг
sudo cp deploy/nginx.conf /etc/nginx/sites-available/poker_bot
sudo ln -s /etc/nginx/sites-available/poker_bot /etc/nginx/sites-enabled/

# Замени yourdomain.com на свой домен
sudo nano /etc/nginx/sites-available/poker_bot

# Получи SSL сертификат
sudo certbot --nginx -d yourdomain.com

# Проверь и перезапусти nginx
sudo nginx -t && sudo systemctl reload nginx
```

### Шаг 2 — systemd (автозапуск)

```bash
# Отредактируй пути в service-файле
nano deploy/poker_bot.service

# Установи
sudo cp deploy/poker_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable poker_bot
sudo systemctl start poker_bot

# Проверь статус
sudo systemctl status poker_bot

# Логи
journalctl -u poker_bot -f
```

### Шаг 3 — Подключи Mini App в BotFather

1. Открой [@BotFather](https://t.me/BotFather)
2. `/mybots` → выбери своего бота
3. `Bot Settings` → `Menu Button` → `Configure menu button`
4. Введи URL: `https://yourdomain.com`
5. Введи название кнопки: `🃏 Открыть приложение`

---

## Функционал

### Для игроков

| Команда / Кнопка | Действие |
|---|---|
| `/start` | Главное меню |
| 🏆 Турниры | Список, регистрация/отмена |
| 📅 Забронировать стол | Выбор даты, времени, мест |
| ⭐ Рейтинг | Топ-20 игроков |
| 👤 Мой профиль | Статистика, история |
| 🃏 Открыть приложение | Mini App |

### Для администратора (`/admin`)

| Действие | Описание |
|---|---|
| ➕ Создать турнир | Пошаговое создание через FSM |
| 📋 Заявки на бронь | Одобрить / отклонить заявки |
| 🏁 Завершить турнир | Записать результаты, пересчитать рейтинг |
| 📊 Экспорт рейтинга | Скачать CSV со всеми игроками |

### Mini App (4 экрана)

- **Главная** — ближайший турнир + баннер рейтинга
- **Турниры** — список с фильтром (текущие / прошедшие), регистрация
- **Рейтинг** — глобальный / сезонный, поиск по нику
- **Профиль** — статистика, город, free entry, уведомления

---

## Расчёт рейтинга

```
Рейтинг  = (max_players - место + 1) × 10  +  ноки × 5
PRO очки = ноки × 25
```

Пример: 1-е место в турнире на 100 человек + 5 ноков = `1000 + 25 = 1025 очков`

---

## REST API (для Mini App)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/tournaments?status=upcoming` | Список турниров |
| GET | `/api/tournament/{id}` | Детали турнира |
| GET | `/api/tournament/{id}/participants` | Участники |
| GET | `/api/leaderboard` | Топ-50 игроков |
| GET | `/api/my-profile` | Профиль текущего пользователя |
| GET | `/api/my-registration/{id}` | Статус регистрации |
| POST | `/api/register/{id}` | Зарегистрироваться |
| POST | `/api/unregister/{id}` | Отменить регистрацию |

Авторизация через заголовок `X-Telegram-Init-Data` (Telegram WebApp initData).

---

## Кастомизация

### Сменить название и оформление

В `.env`:
```env
CLUB_NAME=Название твоего клуба
CLUB_CITY=Твой город
```

### Сменить цветовую схему Mini App

В `mini_app/templates/index.html` найди `:root` и измени переменные:
```css
:root {
  --red: #d9232d;      /* основной акцент */
  --red2: #b01c25;     /* тёмный акцент */
  --bg: #0e0e0e;       /* фон */
  --card: #181818;     /* карточки */
}
```

### Добавить временные слоты для бронирования

В `app/handlers/booking.py` найди список `slots`:
```python
slots = ["18:00", "19:00", "20:00", "21:00", "22:00"]
```

### Изменить формулу рейтинга

В `app/database.py` функция `record_result()`:
```python
rating_delta = max(0, (max_players - place + 1) * 10) + knockouts * 5
pro_delta = knockouts * 25.0
```
