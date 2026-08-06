# Hermes Agent для DEEPUTIN: настройка и рабочий процесс

> Практический гайд для этого репозитория. Проверено по текущей документации Hermes Agent и структуре DEEPUTIN на 2026-08-06. Hermes Agent быстро развивается: перед обновлением сверяйте команды с [официальной документацией](https://hermes-agent.nousresearch.com/docs/).

## 1. Что именно мы настраиваем

[Hermes Agent](https://github.com/NousResearch/hermes-agent) здесь следует использовать как **контролируемого инженерного ассистента для кода, тестов и документации**, а не как автономный исследовательский оператор.

В этой конфигурации Hermes должен уметь:

- читать архитектуру и правила репозитория;
- изменять код только после явного задания;
- запускать небольшие проверки и тесты;
- помогать с Python/FastAPI, `ui-v5` и документацией;
- выполнять `git`/`gh`-операции только после просмотра diff и подтверждения владельца;
- при необходимости искать актуальную документацию в интернете, не отправляя туда фото и runtime-данные.

По умолчанию Hermes **не должен**:

- запускать полный Stage 1/2/3 на реальном фотоархиве;
- читать оригиналы фотографий, calibration dataset, facial vectors, mesh и runtime-артефакты;
- менять научную политику, пороги, calibration или private-hypothesis boundary без отдельного method study;
- превращать `candidate`, `cluster`, threshold exceedance или любой другой статус в вывод об identity;
- создавать mock/random measurements или подменять отсутствующие веса synthetic-данными;
- публиковать результат без human, technical, provenance, legal и editorial review;
- работать в `--yolo`, через неограниченный gateway или unattended cron.

### Почему это важно для DEEPUTIN

DEEPUTIN — не обычный CRUD-проект. В репозитории зафиксированы научные и privacy-инварианты:

- канонический backend и pipeline находятся в `app6/`;
- целевой интерфейс находится в `ui-v5/`;
- Stage 1 запускается на CPU на MacBook M1, пока MPS отдельно не валидирован;
- runtime-данные, фото и результаты находятся вне рабочей копии по проектному контракту; веса могут быть локально в игнорируемом `assets/`, но не версионируются;
- primary pair analysis использует фиксированные pose bins, visibility/applicability gates и calibration;
- система показывает технические наблюдения и не выносит автоматический verdict о личности.

Hermes должен помогать сохранять эти свойства, а не обходить их.

### Короткий путь

Если нужен только рабочий минимум, выполните команды ниже вручную, а затем переходите к разделам 6–10:

```bash
# 1. Один раз установить Hermes по официальной инструкции, затем:
cd /absolute/path/to/facproject
hermes profile create deeputin --no-skills

# 2. Открыть новый shell, если alias ещё не виден:
export PATH="$HOME/.local/bin:$PATH"

# 3. Привязать профиль к корню проекта:
PROJECT_ROOT="$(pwd)"
deeputin config set terminal.backend local
deeputin config set terminal.cwd "$PROJECT_ROOT"
deeputin config set terminal.timeout 180
deeputin config set approvals.mode manual
deeputin config set approvals.cron_mode deny

# 4. Выбрать провайдера/модель (Portal — самый короткий путь):
deeputin setup --portal
# либо: deeputin model

# 5. Проверить конфигурацию и начать интерактивную сессию:
deeputin doctor
deeputin tools
deeputin --tui
```

В коротком пути намеренно нет gateway, cron, vision, MCP и запуска реальных стадий анализа. Сначала добейтесь одной чистой code-only сессии.

---

## 2. Архитектура, которую следует получить

```text
~/.hermes/profiles/deeputin/       ← отдельный профиль Hermes:
  config.yaml                         модель, toolsets, terminal, approvals
  .env                                API keys/OAuth/bot tokens; не в git
  SOUL.md                             стиль и роль ассистента
  sessions/ memories/ skills/ logs/  состояние Hermes

/home/.../facproject/              ← workspace, в котором запускается Hermes
  AGENTS.md                         главный project context
  app6/AGENTS.md                    scoped context, подхватывается при входе в app6
  SKILL.md                          правила качества проекта; Hermes читает по указанию AGENTS.md
  README.md, docs/, ui-v5/          исходники и документация

/Volumes/SDCARD/...                ← private runtime/data, не workspace Hermes
  storage/                          Stage 1/2/2B/3 outputs
  calibration/                     calibration artifacts
  ...                               исходные фото и другие локальные данные
```

**Профиль Hermes и workspace — разные вещи.** Профиль изолирует конфигурацию, сессии, память и skills, но не ограничивает доступ к файлам. Локальный terminal backend по умолчанию имеет права текущего пользователя.

Не запускайте Hermes из `~/.hermes` или из каталога с данными. Запускайте его из корня репозитория либо задайте абсолютный `terminal.cwd`.

---

## 3. Установка Hermes Agent

### 3.1. Предварительные условия

Нужны:

- macOS/Linux/WSL2 и рабочий shell;
- Git и доступ к этому checkout;
- Python 3.11, если планируется запускать Python-проверки;
- Node.js/npm для `ui-v5`;
- настроенное локальное окружение проекта (`.venv`, если оно уже создано владельцем);
- LLM с tool calling и контекстом **не менее 64K токенов**. Это обязательное требование текущего Hermes, а не рекомендация для DEEPUTIN.

Проверьте проект до установки ассистента:

```bash
cd /absolute/path/to/facproject
git status --short --branch
ls AGENTS.md README.md SKILL.md RUN_PROJECT.sh
```

`/absolute/path/to/facproject` замените на настоящий путь. Не копируйте в документ или в prompt приватные абсолютные пути, если они не нужны.

### 3.2. Установка CLI

Для Linux/macOS/WSL2 официальный путь:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.zshrc       # либо source ~/.bashrc
hermes --version
```

Для Windows native используется PowerShell-команда из [официального Quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart).

Если политика безопасности запрещает запускать скачанный shell-скрипт напрямую, сначала скачайте его, просмотрите и только затем выполните вручную:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh \
  -o /tmp/hermes-install.sh
less /tmp/hermes-install.sh
bash /tmp/hermes-install.sh
```

Не просите уже запущенного Hermes устанавливать или обновлять самого себя. Установка, OAuth и ввод API keys должны выполняться владельцем в интерактивном shell.

Официальный установщик хранит managed installation и состояние Hermes в `~/.hermes`; не добавляйте его внутрь этого git-репозитория и не включайте `.hermes/` в проектные результаты.

---

## 4. Отдельный профиль для проекта

Не смешивайте рабочие сессии DEEPUTIN с личным ассистентом или другим coding-проектом. Профили Hermes разделяют `config.yaml`, `.env`, `SOUL.md`, sessions, memory, skills и gateway state.

Создайте профиль без автоматического набора bundled skills. Это уменьшает поверхность prompt injection и делает набор возможностей явным:

```bash
hermes profile create deeputin --no-skills
```

Команда создаёт alias `deeputin`. Если `~/.local/bin` не входит в `PATH`, добавьте его в shell profile и перезапустите shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Проверьте профиль:

```bash
hermes profile show deeputin
deeputin doctor
```

Если вам нужны bundled skills, создайте профиль без `--no-skills` или позже явно включите их:

```bash
deeputin skills opt-in --sync
```

Для первого запуска проекта я рекомендую оставить профиль минимальным и добавлять skills по одному после просмотра их содержимого.

### 4.1. Рабочая директория

```bash
PROJECT_ROOT="$(git -C /absolute/path/to/facproject rev-parse --show-toplevel)"
deeputin config set terminal.cwd "$PROJECT_ROOT"
deeputin config set terminal.backend local
deeputin config set terminal.timeout 180
deeputin config set terminal.home_mode auto
deeputin config check
```

Вместо `PROJECT_ROOT` можно указать реальный абсолютный путь напрямую. Для интерактивного CLI Hermes также использует каталог, из которого его запустили, но явный `terminal.cwd` важен для gateway/cron и защищает от случайного запуска из другой директории.

Для этого проекта **не** задавайте cwd равным `/Volumes/SDCARD/storage`: тогда Hermes потеряет проектный контекст и начнёт воспринимать runtime-данные как workspace. Пути к Stage 1/2/3 передаются командам явно.

### 4.2. Роль и стиль ассистента

`SOUL.md` — profile-wide personality, а не замена `AGENTS.md`. Его можно создать вручную:

```bash
cat > "$HOME/.hermes/profiles/deeputin/SOUL.md" <<'EOF'
Ты — инженерный ассистент проекта DEEPUTIN.

Отвечай на русском языке, сохраняя точные имена файлов, команд, schema и
научных терминов. Всегда отделяй: что изменено в коде, какие проверки реально
запущены, что не проверено и какие есть внешние prerequisites.

Перед изменением сначала проверь git status, найди существующий source of
truth и предложи короткий план. Работай минимальным связным diff.

Без явного подтверждения владельца не запускай полный Stage 1/2/2B/3, не
читай исходные фотографии или private runtime, не меняй calibration/thresholds
и не выполняй destructive git/filesystem commands.

Никогда не называй candidate, cluster, similarity, threshold exceedance или
private hypothesis доказательством identity. Не создавай synthetic fallback,
random measurements или значения 0 вместо missing.
EOF
```

Не записывайте API keys, bot tokens, фото, содержимое `.env` или personal data в `SOUL.md`.

---

## 5. Провайдер, модель и секреты

После создания профиля выберите модель интерактивно:

```bash
deeputin model
```

Самый быстрый вариант для Nous Portal:

```bash
deeputin setup --portal
```

Альтернатива — `deeputin setup` с собственным провайдером или custom OpenAI-compatible endpoint. Для проекта выбирайте модель, которая:

1. имеет context window от 64K;
2. поддерживает tool calling;
3. стабильно работает с длинным Python/TypeScript контекстом;
4. соответствует вашей политике конфиденциальности.

### Что хранится где

Hermes разделяет настройки и секреты:

- обычные параметры — `~/.hermes/profiles/deeputin/config.yaml`;
- API keys, OAuth и bot tokens — `~/.hermes/profiles/deeputin/.env` или `auth.json`;
- ничего из этого не должно попадать в git, prompt, issue или `docs/`.

Используйте CLI, чтобы Hermes положил значение в правильный файл:

```bash
deeputin config set OPENROUTER_API_KEY '***введите-ключ-вместо-звёздочек***'
```

Вставляйте настоящий секрет только локально в интерактивном shell; приведённая команда — шаблон. Никогда не вставляйте ключ в этот документ или в сообщение агенту.

### Политика приватности

`terminal.backend: local` означает, что команды выполняются на вашем компьютере. Это **не означает**, что модель локальная: содержимое tool calls и их результаты может увидеть выбранный LLM-провайдер.

Поэтому:

- не просите Hermes читать фото, `calibration_dataset/photos`, `/Volumes/SDCARD/storage`, facial vectors, mesh или private hypothesis;
- для задач по коду используйте внешний provider только на обезличенном коде и документации;
- для задач, где нужен доступ к чувствительным данным, используйте локальную/self-hosted модель либо не передавайте данные агенту вовсе;
- не включайте `vision`, если вы не проводите отдельный разрешённый тест с privacy policy;
- не подключайте photo/runtime directories к MCP или Docker mount без отдельного решения о data handling.

---

## 6. Project context: что Hermes подхватит автоматически

Текущая структура уже хорошо подходит Hermes; новый `.hermes.md` для неё не нужен.

### Приоритет контекстных файлов

Текущий Hermes ищет в workspace только **один** основной тип project context, в таком порядке:

```text
.hermes.md / HERMES.md → AGENTS.md → CLAUDE.md → .cursorrules
```

В корне DEEPUTIN есть `AGENTS.md`, поэтому он будет основным контекстом. Не добавляйте небольшой `.hermes.md` или `HERMES.md` «для удобства»: такой файл станет более приоритетным и скроет от Hermes корневой `AGENTS.md`, если вы не продублируете в нём все обязательные правила.

`SOUL.md` загружается отдельно как профильная identity/personality-инструкция.

### Progressive discovery

Когда Hermes по инструментам входит в `app6/`, он постепенно обнаруживает `app6/AGENTS.md`. Это полезно: корневые правила применяются сразу, а backend-specific contracts появляются, когда агент работает с backend.

`ui-v5/` не имеет отдельного `AGENTS.md`, поэтому там продолжают действовать корневые правила.

### Роль файлов проекта

- `AGENTS.md` — основной operational/scientific contract для Hermes;
- `app6/AGENTS.md` — scoped backend contract;
- `README.md` — описание продукта и запуска;
- `SKILL.md` — implementation workflow и 25-factor quality gate. Это **не** автоматически загружаемый Hermes Skill: корневой `AGENTS.md` требует прочитать его по необходимости;
- `CLAUDE.md` — Claude-specific context. При наличии корневого `AGENTS.md` Hermes не обязан загружать `CLAUDE.md` автоматически. Если задача зависит от его деталей, явно попросите прочитать файл.

Первое сообщение после запуска полезно сделать таким:

```text
Работай из корня текущего репозитория. Ничего не меняй.

1. Покажи pwd и git status --short --branch.
2. Прочитай README.md, AGENTS.md и SKILL.md.
3. Если задача касается app6, прочитай app6/AGENTS.md.
4. Кратко перечисли применимые ограничения и команды проверки.
5. Отдельно отметь, что полный Stage 1/2/3 и доступ к private runtime
   запрещены без моего явного подтверждения.
```

Если ответ показывает, что Hermes работает не из этого repo, остановите сессию и запустите её после `cd "$PROJECT_ROOT"`.

---

## 7. Базовый `config.yaml`

Сначала задайте простые значения через CLI:

```bash
deeputin config set terminal.backend local
deeputin config set terminal.cwd "$PROJECT_ROOT"
deeputin config set terminal.timeout 180
deeputin config set terminal.home_mode auto
deeputin config set approvals.mode manual
deeputin config set approvals.timeout 300
deeputin config set approvals.cron_mode deny
deeputin config check
```

Для списков и комментариев откройте профильную конфигурацию:

```bash
deeputin config edit
```

Минимальная основа должна быть эквивалентна следующему YAML. Абсолютный путь замените на свой; этот фрагмент **не** нужно коммитить в репозиторий:

```yaml
terminal:
  backend: local
  cwd: /absolute/path/to/facproject
  timeout: 180
  home_mode: auto

approvals:
  mode: manual
  timeout: 300
  cron_mode: deny
  deny:
    - 'git push --force*'
    - 'git reset --hard*'
    - 'git clean -fd*'
    - 'rm -rf*'
    - '*curl*|*sh*'
    - '*wget*|*sh*'
    - 'docker -H*'
    - 'docker --host*'
    - 'docker context use*'

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20
```

`approvals.deny` использует case-insensitive `fnmatch` по всей команде. Это дополнительный fail-closed слой, а не полноценный sandbox. В частности, `rm -rf*` может блокировать даже удаление временной папки — это ожидаемая цена безопасного профиля.

### `HERMES_WRITE_SAFE_ROOT`

В интерактивном shell можно добавить дополнительное ограничение для `write_file`/`patch`:

```bash
export HERMES_WRITE_SAFE_ROOT="$PROJECT_ROOT:$HOME/.hermes/profiles/deeputin"
```

Оно разрешает записи только в workspace и профиль Hermes. Важно: это **не** ограничивает чтение и не блокирует shell-команды, которые напрямую выполняет `terminal`; для настоящей изоляции нужен Docker/SSH/другой sandbox backend. Не записывайте эту переменную в проектный `.env` и не считайте её заменой approvals.

Перед началом работы полезно проверить:

```bash
hermes profile show deeputin
deeputin config check
deeputin doctor
git -C "$PROJECT_ROOT" status --short --branch
```

---

## 8. Toolsets: включить минимум, остальное — по запросу

Запустите интерактивный выбор:

```bash
deeputin tools
```

Начальный профиль для coding workflow:

| Toolset | Рекомендация | Причина |
|---|---:|---|
| `terminal` | включить | `git`, Python, pytest, npm, `RUN_PROJECT.sh` |
| `file` | включить | чтение и точечные patch/write в workspace |
| `search` | включить | поиск по коду и документации |
| `todo`, `clarify` | включить | планирование и уточнение задачи |
| `web` | опционально | актуальные upstream docs; включать без private data |
| `skills` | опционально | только просмотренные доверенные workflow |
| `memory`, `session_search` | сначала выключить | не сохранять лишние project/private details до понятной политики |
| `delegation` | сначала выключить | subagent получает собственные tool capabilities и может усложнить контроль |
| `code_execution` | сначала выключить | обычного terminal достаточно; включить только при необходимости |
| `browser`, `vision`, `image_gen`, `tts` | выключить | для coding workflow не нужны, vision увеличивает privacy-риск |
| `cronjob`, `messaging`, `homeassistant`, `spotify` | выключить | не нужны для локальной разработки, создают unattended/integration surface |

Названия toolsets могут расширяться между версиями Hermes; authoritative список — текущий вывод `deeputin tools` и [официальный reference](https://hermes-agent.nousresearch.com/docs/reference/toolsets-reference).

Не включайте всё «на всякий случай». Добавляйте один toolset, выполняйте `deeputin doctor`, проводите безопасный smoke test и только затем переходите к следующему.

---

## 9. Проектные команды и границы запуска

### 9.1. Безопасные read-only и code-only проверки

Hermes можно попросить запустить их после просмотра плана:

```bash
# Из корня репозитория
python -m compileall -q app6
./RUN_PROJECT.sh check
```

Для UI v5:

```bash
cd ui-v5
npm ci
npm run lint
npm run typecheck
npm run test -- --run
npm run build
```

`npm run test:e2e` требует установленного Playwright browser (`npx playwright install chromium`). Если browser binary или внешний dataset отсутствует, результат должен быть зафиксирован как environment blocker, а не заменён фиктивным успехом.

Обязательное правило для ответа Hermes: он должен перечислить **точные команды, которые действительно выполнил**, и отдельно назвать пропущенные проверки.

### 9.2. UI и API

Проектный runner уже задаёт переносимую Python-команду и внешние runtime roots:

```bash
./RUN_PROJECT.sh api
./RUN_PROJECT.sh ui
```

Для UI/API:

- браузерный код использует относительные `/api` URLs;
- Vite proxy настроен в `ui-v5/vite.config.ts`;
- при необходимости адрес backend задаётся оператором через `DEEPUTIN_API_URL`, а не хардкодится в frontend;
- Hermes не должен создавать второй backend внутри `ui-v5` — канонический API находится в root `app6/`;
- долгоживущие процессы запускайте вручную или через контролируемый process manager, а не оставляйте как unattended child process агента.

### 9.3. Предзапуск и реальные данные

`RUN_PROJECT.sh` использует внешнее хранилище по умолчанию:

```bash
export DEEPUTIN_STORAGE_ROOT=/Volumes/SDCARD/storage
export DEEPUTIN_CALIBRATION_ROOT=/Volumes/SDCARD/calibration
```

Проверьте путь до реального запуска:

```bash
test -d "$DEEPUTIN_STORAGE_ROOT"
test -d "$DEEPUTIN_CALIBRATION_ROOT"
test -f assets/face_model.npy
test -f assets/net_recon.pth || test -f assets/net_recon_mbnet.pth
```

Веса, фото и runtime могут отсутствовать именно в текущем checkout; это не повод создавать fallback. `app6/run_preflight.py` должен завершить запуск с понятным `blocked`, если обязательные assets/calibration отсутствуют.

### 9.4. Stage 1 — только явное подтверждение

По текущей политике MacBook M1 используйте CPU. Если владелец явно попросил smoke run на конкретном наборе данных, команда имеет вид:

```bash
./RUN_PROJECT.sh stage1 \
  --input /absolute/path/to/sanitized-or-approved-photos \
  --output "$DEEPUTIN_STORAGE_ROOT/stage1/hermes_smoke" \
  --device cpu \
  --limit 2 \
  --fail-fast
```

Перед такой командой Hermes обязан показать:

1. точный input и output path;
2. `limit`, `device` и ожидаемую стоимость запуска;
3. что вывод находится вне git;
4. что это не full dataset и не identity verdict;
5. что пользователь явно подтвердил запуск.

Никогда не давайте общую инструкцию «обработай все фото» в unattended session. Не запускайте параллельные копии Stage 1 на одном output root. Не переходите к Stage 2, пока Stage 1 не прошёл structural validation и соответствующий gate.

### 9.5. Stage 2/2B/3

Запуск этих стадий требует отдельного подтверждения, известных artifact paths и понимания того, какой versioned profile/schema используется. Для scientific changes Hermes должен сначала прочитать `docs/final/*`, `app6/AGENTS.md` и профильный contract, затем предложить plan/method decision. Private Stage 2B никогда не должен автоматически попадать в Stage 3/public export.

---

## 10. Рабочий цикл для каждой задачи

### Шаг 1. Сначала read-only диагностика

Prompt-шаблон:

```text
Работай из корня DEEPUTIN. Ничего не изменяй и не запускай Stage 1/2/2B/3.

Проверь git status --short --branch, прочитай README.md и AGENTS.md.
Для области [app6 | ui-v5 | docs] найди source of truth, существующие tests,
API/schema и применимый scoped context. Сформулируй:

- какую сущность мы меняем (photo/pair/event/interval/run/hypothesis или UI);
- acceptance criteria;
- какие файлы будут изменены;
- какие команды проверки нужны;
- какие данные/weights/external prerequisites отсутствуют.

Не предлагай mock/random fallback. Если source contract не найден, остановись
и обозначь это как blocker.
```

### Шаг 2. План и минимальный diff

Для реализации попросите:

```text
Покажи короткий план и дождись моего подтверждения перед изменением файлов.
Сохрани scientific invariants, provenance и null/missing semantics. Не дублируй
scientific logic во frontend. Не трогай runtime data, weights, generated bulk
artifacts и secrets. После изменений покажи git diff --stat и git diff --check.
```

### Шаг 3. Проверки

Порядок по умолчанию:

1. точечный unit/contract test;
2. `compileall`/lint/typecheck;
3. полный релевантный gate;
4. E2E или real-data gate — только если prerequisites есть и запуск подтверждён.

Hermes не должен говорить «тесты прошли», если команда не выполнялась в этой сессии.

### Шаг 4. Self-review

Перед завершением попросите проверить:

```text
Сделай read-only self-review по AGENTS.md и SKILL.md. Проверь:

- null не превращён в 0;
- нет mock/random production path;
- нет unsupported identity wording;
- private/public boundary сохранён;
- API/schema/version и tests синхронизированы;
- UI не вычисляет scientific result сам;
- изменения не включают runtime, веса, фото, secrets или generated bulk files.

Верни изменённые файлы, точные команды и результаты, ограничения и оставшиеся
external prerequisites. Не объявляй production-ready без достаточного gate.
```

---

## 11. Задачные профили

### Code-only профиль — основной

Используйте для Python, FastAPI, TypeScript, CSS, tests и docs. Включены `terminal`, `file`, `search`, `todo`, `clarify`; web и memory — только при необходимости.

### Documentation/research профиль

Web search можно включить для проверки текущих upstream API/репозиториев. В prompt явно напишите:

```text
Используй web только для публичной документации. Не отправляй во внешний
provider содержимое фото, calibration, runtime, `.env`, private hypothesis или
локальные credentials. Цитируй URL источника и отделяй upstream fact от факта
из текущего checkout.
```

### Scientific-change профиль

Не включайте его автоматически. Для изменения pose policy, coordinate space, calibration, FDR, thresholds, clustering или hypothesis validation требуются method study, decision record, schema/config version bump и regression tests согласно `AGENTS.md` и `SKILL.md`.

### Gateway/бот

Для этого проекта не включайте gateway на первом этапе. Если позже понадобится Telegram/Discord/Slack:

- создайте отдельный Hermes profile и отдельный bot token;
- задайте allowlist пользователей, не `ALLOW_ALL`;
- держите gateway на отдельной машине/VM или используйте SSH backend;
- оставьте `approvals.cron_mode: deny`;
- не предоставляйте bot доступ к `/Volumes/SDCARD`;
- сначала протестируйте обычный CLI;
- запускайте cron только после audit prompt, paths и delivery.

Официальная справка: [Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging) и [Security](https://hermes-agent.nousresearch.com/docs/user-guide/security).

---

## 12. Skills и MCP

### Skills

Hermes Skills — это отдельная система из `~/.hermes/profiles/deeputin/skills/`. Корневой `SKILL.md` DEEPUTIN не становится slash-command автоматически.

Для проекта безопаснее начать так:

1. оставить профиль `--no-skills`;
2. полагаться на `AGENTS.md`, который направляет агента к `SKILL.md`;
3. добавлять только просмотренные skills;
4. не давать skill scripts доступ к private data без отдельного решения.

Если нужен повторяемый проектный workflow, создайте короткий отдельный `SKILL.md` в profile skills или в external skill directory и держите его без секретов. Hermes поддерживает `skills.external_dirs`; путь можно задать в profile `config.yaml`:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/trusted-skills
```

Не указывайте в `external_dirs` каталог с фото, runtime или случайно скачанными skill bundles. Перед установкой стороннего skill просмотрите все его `SKILL.md`, scripts и references.

Официальная справка: [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).

### MCP

MCP не нужен для базовой работы DEEPUTIN. GitHub CLI уже предоставляет понятный путь для git/PR-задач; не добавляйте PAT в проектный YAML.

Подключайте MCP только при конкретной потребности и после проверки:

- какая capability реально отсутствует;
- какие команды и файлы сервер может читать/менять;
- где хранятся credentials;
- можно ли ограничить env и filesystem;
- как отключить сервер и проверить audit/logs.

Никогда не храните MCP secrets в `README.md`, `AGENTS.md`, `.hermes.md` или репозитории.

---

## 13. Docker/SSH: когда выбирать sandbox

### Local

Подходит для ежедневной разработки, потому что видит `.venv`, npm, `git`, `gh` и локальные project paths. Требует ручных approvals и дисциплины с private data.

### Docker

Подходит для code-only задач и защиты host filesystem. Для DEEPUTIN он не станет автоматически рабочим Stage 1 окружением: потребуется явно собрать Python/Node dependencies и смонтировать только необходимые каталоги. Не монтируйте `/Volumes/SDCARD/storage`, calibration или фото в контейнер без отдельного security decision.

Если контейнер использует hosted LLM, mount isolation не предотвращает передачу в provider тех файлов, которые модель попросила прочитать.

### SSH

Подходит, если coding workspace и данные должны находиться на отдельном сервере. Секреты SSH хранятся в profile `.env`, а на сервере должна быть отдельная рабочая копия и свой набор permissions. Не используйте сервер как способ обойти privacy policy.

Настройка backend:

```bash
deeputin config set terminal.backend docker
# либо
deeputin config set terminal.backend ssh
```

Переключайте backend только после того, как обычная code-only сессия на local успешно проверена.

---

## 14. Типичные проблемы

| Симптом | Причина | Исправление |
|---|---|---|
| Hermes не знает правил проекта | Запущен не из корня или использован `.hermes.md`, скрывший `AGENTS.md` | `cd "$PROJECT_ROOT"`; уберите случайный `.hermes.md`; повторите новую сессию |
| Hermes путает проекты/память | Использован default profile | `hermes profile show deeputin`; запускайте `deeputin ...` |
| Команда не выполняется из-за approvals | Это ожидаемый fail-closed режим | Проверьте команду вручную; разрешайте только конкретный безопасный запуск один раз, не включайте `--yolo` |
| Веса или calibration не найдены | Они локальные/external и отсутствуют в checkout | Запустите `run_preflight`; не создавайте fallback и не коммитьте веса |
| UI не видит API | API не запущен или изменён proxy contract | Запустите `./RUN_PROJECT.sh api`; проверьте `DEEPUTIN_API_URL`; оставьте browser URLs относительными |
| Hermes пишет в repo runtime outputs | Неправильный output path или агент не понял boundary | Остановите задачу, проверьте `git status`, перенесите output под `DEEPUTIN_STORAGE_ROOT`, добавьте явный prompt |
| `npm ci`/Playwright не проходит | Нет Node/browser/network или lockfile conflict | Зафиксируйте environment blocker; не объявляйте E2E успешным |
| Provider отвечает с ошибкой или ломает tool calls | Неподходящая модель/context/auth | `deeputin doctor`, `deeputin model`; проверьте context >=64K и tool calling |
| В profile неожиданно появились skills | Профиль создан без `--no-skills` или выполнен `opt-in` | Просмотрите `deeputin skills list`; удалите/отключите только после проверки |
| Агент предлагает identity verdict | Нарушен проектный contract | Остановите; сослитесь на `AGENTS.md`; потребуйте observation/candidate/inconclusive wording и evidence refs |

После существенной ошибки начинайте с официальной recovery-последовательности:

```bash
deeputin doctor
deeputin model
deeputin config check
hermes profile show deeputin
deeputin sessions list
deeputin --continue
```

---

## 15. Checklist перед ежедневной работой

```text
[ ] Я нахожусь в корне facproject.
[ ] Активен профиль deeputin, а не default/personal profile.
[ ] `AGENTS.md` найден; случайного `.hermes.md` нет.
[ ] Модель имеет context >=64K и tool calling.
[ ] `approvals.mode` не `off`; `--yolo` не используется.
[ ] Не включены vision/browser/messaging/cron без отдельной причины.
[ ] API keys находятся только в profile `.env`/auth, не в repo.
[ ] `/Volumes/SDCARD`, calibration и фото не являются обычным workspace для агента.
[ ] `terminal.cwd` указывает на корень проекта.
[ ] Перед patch выполнены git status, source-of-truth search и plan.
[ ] Stage 1/2/2B/3 запускаются только после явного подтверждения.
[ ] После работы проверены `git diff --check`, tests и отсутствие runtime/secret files в diff.
```

## 16. Ссылки на первоисточники Hermes

- [GitHub: NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [Quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)
- [Profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
- [Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)
- [Context Files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)
- [Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)
- [Tools and Toolsets](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)
- [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)
- [Environment Variables](https://hermes-agent.nousresearch.com/docs/reference/environment-variables)

Связанные документы DEEPUTIN:

- [`README.md`](../README.md)
- [`AGENTS.md`](../AGENTS.md)
- [`SKILL.md`](../SKILL.md)
- [`app6/AGENTS.md`](../app6/AGENTS.md)
- [`app6/README.md`](../app6/README.md)
- [`docs/final/04_DATA_CONTRACTS.md`](final/04_DATA_CONTRACTS.md)
- [`docs/final/07_TESTING_AND_ACCEPTANCE.md`](final/07_TESTING_AND_ACCEPTANCE.md)
- [`docs/PUBLICATION_PIPELINE.md`](PUBLICATION_PIPELINE.md)
