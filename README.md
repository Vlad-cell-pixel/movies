# Фільми

Список фільмів з оцінками і статусами: консольна програма і вебсервіс на Flask з базою SQLite.

    Назва:         Фільми
    Для кого:      для мене, щоб пам'ятати, що я подивився, як мені сподобалось і що хочу подивитись
    Запис:         назва, рік, статус, оцінка, дата
    Операції:      додати, показати всі, знайти за назвою/статусом/роком/оцінкою, видалити, звіт
    Звіти:         кількість за статусом, середня оцінка, топ-3 фільми

Статуси: `переглянуто`, `дивлюсь`, `заплановано`.
Оцінка від 0 до 10, де 0 означає «ще не оцінено». Дата у форматі РРРР-ММ-ДД, якщо не вказана, береться сьогоднішня.

## Встановлення

Потрібен Python 3.10 або новіший.

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python3 seed.py          # необов'язково: 22 фільми-приклади з example.txt

Дані зберігаються у файлі `data.db` (SQLite). Він створюється сам при першому запуску і в git не йде.

## Вебсервіс

    python3 app.py

Сервер працює на http://127.0.0.1:5000. Усі відповіді у форматі JSON.

| Метод і адреса | Що робить | Код відповіді |
|---|---|---|
| `GET /movies` | усі фільми | 200 |
| `GET /movies?status=...` | фільтр за статусом (також `title`, `year`, `rating`) | 200 / 400 |
| `POST /movies` | додати фільм, JSON у тілі | 201 / 400 |
| `DELETE /movies/<id>` | видалити фільм | 200 / 404 |
| `GET /report` | звіт | 200 |

### Приклади curl

Усі фільми:

    curl http://127.0.0.1:5000/movies

Фільтри (кирилицю зручно передавати через `-G --data-urlencode`):

    curl -G http://127.0.0.1:5000/movies --data-urlencode "status=заплановано"
    curl -G http://127.0.0.1:5000/movies --data-urlencode "title=дюна"
    curl "http://127.0.0.1:5000/movies?year=1999"
    curl "http://127.0.0.1:5000/movies?rating=9"

Додати фільм (`rating` і `date` необов'язкові):

    curl -X POST http://127.0.0.1:5000/movies \
         -H "Content-Type: application/json" \
         -d '{"title": "Інтерстеллар", "year": 2014, "status": "переглянуто", "rating": 9}'

Видалити фільм з id 1:

    curl -X DELETE http://127.0.0.1:5000/movies/1

Звіт (`-i` показує код відповіді і заголовки):

    curl -i http://127.0.0.1:5000/report

### Перевірка помилок

Сервер на неправильні запити відповідає кодом 400, 404 або 405 і поясненням, а не падає з 500:

    curl -i -X POST http://127.0.0.1:5000/movies
    # 400 {"error": "очікується JSON-об'єкт у тілі запиту"}

    curl -i -X POST http://127.0.0.1:5000/movies -H "Content-Type: application/json" \
         -d '{"title": "Фільм", "year": "абв", "status": "переглянуто"}'
    # 400 {"error": "рік має бути цілим числом, а не 'абв'"}

    curl -i -X POST http://127.0.0.1:5000/movies -H "Content-Type: application/json" \
         -d '{"title": "Фільм", "year": 2000, "status": "переглянуто", "rating": 15}'
    # 400 {"error": "оцінка має бути від 0 до 10 (0 = ще не оцінено)"}

    curl -i -G http://127.0.0.1:5000/movies --data-urlencode "status=колись"
    # 400 {"error": "статус має бути одним із: переглянуто, дивлюсь, заплановано"}

    curl -i -X DELETE http://127.0.0.1:5000/movies/999
    # 404 {"error": "фільм з id 999 не знайдено"}

## Консольна програма

Працює з тією самою базою `data.db`:

    python3 cli.py add "Інтерстеллар" 2014 переглянуто 9 2026-10-03
    python3 cli.py list
    python3 cli.py find title дюна
    python3 cli.py find status заплановано
    python3 cli.py report
    python3 cli.py delete 5

## Тести

    python3 tests.py

Перевіряють `logic.py`, роботу з базою (`storage.py`) і маршрути вебсервісу (`app.py`).

## Безпека

Усі SQL-запити використовують підстановку через `?`, тому SQL-ін'єкція неможлива.


## Розгортання

Сервіс працює в інтернеті: https://api.vhritsun.pp.ua/movies

Сервер: Oracle Cloud Always Free (Frankfurt), Ubuntu 24.04, shape VM.Standard.A1.Flex.
Замість Google Cloud обрано Oracle Cloud, бо Google вимагав передоплату.

Схема: інтернет → nginx (80/443, HTTPS) → gunicorn (127.0.0.1:8000) → Flask (app.py) → SQLite (data.db).

### Безпека
- вхід лише за ssh-ключем: `PasswordAuthentication no`, `PermitRootLogin no`
- фаєрвол ufw: порт 22 відкритий, 80 і 443 лише з адрес Cloudflare
- у мережі Oracle (Network Security Group) відкрито вхідні порти 80 і 443

### Команди на сервері

    sudo apt update && sudo apt upgrade -y
    sudo apt install -y git python3-venv python3-pip nginx sqlite3

    git clone https://github.com/Vlad-cell-pixel/movies.git
    cd movies
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python3 tests.py
    python3 seed.py

    sudo cp deploy/movies.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now movies

    sudo cp deploy/nginx.conf /etc/nginx/sites-available/movies
    sudo ln -s /etc/nginx/sites-available/movies /etc/nginx/sites-enabled/
    sudo rm /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx

    sudo apt install -y certbot python3-certbot-nginx
    sudo certbot --nginx -d api.vhritsun.pp.ua
    sudo certbot renew --dry-run

### Оновлення коду

    cd ~/movies && git pull && sudo systemctl restart movies

### Перевірка

    curl https://api.vhritsun.pp.ua/report
    curl -i -X POST https://api.vhritsun.pp.ua/movies \
         -H "Content-Type: application/json" \
         -d '{"title": "Дюна", "year": 2021, "status": "переглянуто", "rating": 8}'


## Cloudflare і фронтенд

Сайт: https://vhritsun.pp.ua (Netlify, папка `frontend/`). API: https://api.vhritsun.pp.ua (через Cloudflare).

- DNS домену обслуговує Cloudflare; запис `api` проксується (IP сервера прихований)
- SSL/TLS: Full (strict), Always Use HTTPS
- rate limiting: шлях `/movies`, більше 20 запитів за 10 секунд — блок
- Bot Fight Mode увімкнено, кеш для `api.vhritsun.pp.ua` вимкнено
- CORS дозволяє запити лише з https://vhritsun.pp.ua
- у фронтенді дані виводяться через `textContent` (захист від XSS)

Фаєрвол сервера (порти 80 і 443 лише для Cloudflare):

    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow OpenSSH
    for ip in $(curl -s https://www.cloudflare.com/ips-v4); do
        sudo ufw allow proto tcp from $ip to any port 80,443
    done
    sudo ufw enable

Справжній IP відвідувача для nginx (`/etc/nginx/conf.d/cloudflare.conf`):

    curl -s https://www.cloudflare.com/ips-v4 | sed 's/.*/set_real_ip_from &;/' | sudo tee /etc/nginx/conf.d/cloudflare.conf
    echo "real_ip_header CF-Connecting-IP;" | sudo tee -a /etc/nginx/conf.d/cloudflare.conf


## Адмінка

Адміністративні маршрути доступні лише через VPN Tailscale і лише з токеном у заголовку `X-Admin-Token`:

- `DELETE /admin/movies/<id>` — видалити фільм
- `GET /admin/export` — усі фільми одним списком
- `POST /admin/import` — додати список фільмів (спершу перевіряються всі, потім додаються)

Токен лежить у `.env` на сервері (`ADMIN_TOKEN=...`), systemd підхоплює його через
`EnvironmentFile` у `deploy/movies.service`. `.env` є в `.gitignore` і в git не потрапляє.
Згенерувати новий токен:

    python3 -c "import secrets; print('ADMIN_TOKEN=' + secrets.token_urlsafe(32))" > .env

Виклик (з пристрою, підключеного до Tailscale):

    curl -H "X-Admin-Token: $TOKEN" http://АДРЕСА_СЕРВЕРА_В_TAILSCALE/admin/export

nginx: за доменом `/admin/` закрито (`deny all`), окремий блок `deploy/nginx-admin.conf`
пропускає `/admin/` лише з мережі Tailscale `100.64.0.0/10`.

Застереження: статичний токен — навчальне спрощення; у реальній системі адмін входить
під власним обліковим записом з роллю і журналом дій, а секрети лежать у менеджері секретів.

## Супровід

- fail2ban: 5 невдалих спроб входу за 10 хвилин — бан на 1 годину (`/etc/fail2ban/jail.local`)
- резервні копії: cron щодня о 3:00 (UTC) робить `sqlite3 data.db ".backup ..."` у `~/backups`,
  копії старші за 14 днів видаляються; відновлення перевірено

## Безпека: аудит

| Загроза | Як перевірено | Результат | Чим закрито |
|---|---|---|---|
| SQL-ін'єкція | POST з назвою `x'); DROP TABLE movies; --` → 400; тест `test_storage` з `'; DROP TABLE movies; --` | закрито | валідація в `logic.py` + параметри `?` у всіх SQL-запитах |
| XSS у фронтенді | фільм з назвою `<img src=x onerror=alert(1)>` показано як текст | закрито | `textContent` замість `innerHTML` |
| зайвий вхід на сервер | `ssh root@IP`, `ssh` без ключа → Permission denied | закрито | `PermitRootLogin no`, `PasswordAuthentication no` |
| обхід Cloudflare | `curl -k https://IP` → timed out | закрито | ufw: 80 і 443 лише з адрес Cloudflare |
| обхід Cloudflare через старий DNS | кеш роутера давав прямий IP → curl: timed out | закрито | ufw: 80 і 443 лише з адрес Cloudflare |
| флуд запитами | 60 паралельних GET → частина відповідей 429 | закрито | rate limiting у Cloudflare |
| видалення даних сторонніми | `DELETE /admin/movies/1` за доменом → 403 | закрито | nginx `deny` для /admin/ за доменом, доступ лише з Tailscale, токен |
| секрети в git | `git log -p \| grep -c ТОКЕН` → 0 | закрито | `.env`, `.gitignore` |
| втрата даних | копію з `~/backups` відкрито на ноутбуці, 23 фільми | закрито | cron щодня, `.backup`, копії 14 днів |
| відкриті порти | `nc -zv IP 22 80 443 8000` → відкритий лише 22 | закрито | ufw |
| застарілі пакети | `apt list --upgradable` | закрито | `apt upgrade`, unattended-upgrades |
| підбір пароля ssh | `fail2ban-client status sshd` | закрито | fail2ban |

Відкрите і прийнятне: порт 22 доступний з інтернету (потрібен для керування сервером),
але вхід лише за ключем, а підбір блокує fail2ban.## Лабораторна 11: класи, друга таблиця, журнал дій, pytest

- `models.py`: клас `Movie`. Усередині програми фільм — об'єкт, словник лише для JSON (`to_dict`) і бази (`from_row`).
- Друга таблиця `statuses`; у `movies` зберігається `status_id REFERENCES statuses(id)`, перевірка зв'язків увімкнена (`PRAGMA foreign_keys = ON`).
- Звіт через JOIN: `GET /report/statuses`.
- Журнал дій `audit_log`: кожне додавання і видалення з часом; перегляд `GET /admin/log`.
- `migrate.py`: перенесення старої бази без втрат (id зберігаються, кількість перевіряється, все в одній транзакції).
- Тести: `pytest -v` (папка `tests/`, окремо логіка, база, міграція, маршрути; кожен тест на тимчасовій базі).

## Лабораторна 12: користувачі, вхід і права

- Таблиця `users`: логін, **хеш** пароля (`werkzeug.security`, scrypt), `is_admin`. Паролів відкритим текстом у базі немає.
- `POST /register`, `POST /login`, `POST /logout`, `GET /me`. Сесія — підписаний cookie (`SECRET_KEY` у `.env`), `Secure`, `HttpOnly`, `SameSite=Lax`, домен `.vhritsun.pp.ua`.
- На неправильний пароль і неіснуючий логін — однакова відповідь 401, щоб не підказувати, які логіни є.
- Кожен фільм має `user_id`. Усі запити до бази мають `WHERE user_id = ?`: користувач бачить і видаляє лише своє. Чужий фільм → 404 (як неіснуючий).
- Адміністратор: `is_admin = 1`, призначається лише вручну через `sqlite3` на сервері. Статичний `ADMIN_TOKEN` видалено з коду і `.env`. Обмеження nginx на `/admin/` (лише Tailscale) лишилось: два шари захисту.
- У журналі дій є `user_id` (хто зробив дію).
- Фронтенд: форма входу і реєстрації, кнопка виходу, видалення своїх фільмів; усі запити з `credentials: "include"`, CORS з `supports_credentials=True`.
- Захист від підбору пароля: правило rate limiting у Cloudflare охоплює також `/login` і `/register`.

Перевірка через curl:

```
curl -c jar.txt -X POST https://api.vhritsun.pp.ua/login -H "Content-Type: application/json" -d '{"login": "...", "password": "..."}'
curl -b jar.txt https://api.vhritsun.pp.ua/movies     # свої фільми
curl https://api.vhritsun.pp.ua/movies                # без cookie: 401
```

## Лабораторна 13: Docker, автоматичні тести і деплой, моніторинг

### Розгортання (актуальне, з лабораторної 13)

Сервіс працює в Docker-контейнері, nginx і Cloudflare перед ним не змінилися:

```
браузер → Cloudflare → nginx (443) → 127.0.0.1:8000 → контейнер api (gunicorn + Flask) → ~/movies/data/data.db
```

- `Dockerfile` — образ: Python 3.12 + бібліотеки з `requirements.txt` + код.
- `.dockerignore` — у образ не потрапляють `.env`, база, `venv`, `.git`, тести, фронтенд.
- `compose.yaml` — запуск: порт лише `127.0.0.1:8000` (ззовні не видно), `SECRET_KEY` з `.env`, база в томі `./data:/data`.

Команди на сервері (у `~/movies`):

```
docker compose up -d --build      # зібрати і запустити
docker compose ps                 # чи працює
docker compose logs -f api        # логи (вихід: Ctrl+C)
docker compose down               # зупинити і прибрати контейнер (база в ./data лишається)
```

Бекап (cron, щодня 03:00 UTC) тепер копіює `~/movies/data/data.db`.

**Автоматичний деплой (GitHub Actions, `.github/workflows/ci.yml`):** кожен `git push` у `master` запускає `pytest`; лише якщо тести зелені, другий етап заходить на сервер по SSH окремим ключем деплою (секрети `SSH_HOST`, `SSH_USER`, `SSH_KEY` у GitHub), робить `git pull`, `docker compose up -d --build` і перевіряє `/health`. Червоний тест блокує деплой.

**Моніторинг:** `GET /health` → `{"status": "ok"}` або `503 {"status": "db_error"}`. UptimeRobot перевіряє `https://api.vhritsun.pp.ua/health` кожні 5 хвилин і надсилає лист, коли сервіс падає і коли відновлюється.

### Застаріле (лабораторні 8–12)

~~systemd-юніт `deploy/movies.service` з gunicorn у `venv`~~ — вимкнений (`sudo systemctl disable --now movies`), файл лишається в репозиторії як історія. Ручний деплой `ssh` → `git pull` → `systemctl restart` більше не потрібен.
