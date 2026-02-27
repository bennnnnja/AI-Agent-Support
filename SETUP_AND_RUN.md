# Настройка и запуск Jira Agent

Полная инструкция для запуска интеграции агента с Jira через Redis, webhook и MCP Atlassian.

## Предусловия

Убедитесь, что у вас установлены:
- Python 3.11+ с venv
- Docker & Docker Compose (для Redis)
- `uv` или `uvx` для запуска MCP сервера
- Jira инстанс доступен по адресу `http://10.10.30.2:8080`

## 1. Активация Virtual Environment

```powershell
# Windows PowerShell
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
```

## 2. Запуск Redis и Webhook Gateway

В **отдельном терминале** поднимите контейнеры (уже запущены):

```powershell
# Проверить, что контейнеры запущены
docker ps
```

Убедитесь, что запущены:
- `redis` на `localhost:6379`
- `webhook-gateway` (слушает события от Jira и пушит в Redis Stream)

## 3. Запуск MCP Atlassian Сервера

В **отдельном терминале** запустите MCP сервер:

```powershell
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
uvx mcp-atlassian
```

Вывод должен быть примерно:
```
2026-02-27 14:05:00 - MCP Atlassian Server starting...
Connected to Jira: http://10.10.30.2:8080
Tool: get_issue
Tool: add_comment
Tool: search_issues
Server ready
```

## 4. Запуск Тестов Интеграции (опционально)

Перед запуском основного агента проверьте все компоненты:

```powershell
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
python test_integration.py
```

Ожидаемый результат:
```
✓ PASS   | Redis Connection
✓ PASS   | Redis Consumer Group
✓ PASS   | Event Format Parsing
✓ PASS   | LLM (Ollama) Connection
✓ PASS   | RAG API Connection
✓ PASS   | Jira MCP Connection
```

## 5. Запуск Jira Agent

В **третьем терминале** запустите основной агент:

```powershell
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
python -m app.main
```

Вывод должен быть:
```
Starting agent | stream=jira.events
Listening for events...
[INFO] Processing issue_created for TEST-37
[INFO] Invoking graph for TEST-37
[INFO]   Category: tech_support
[INFO]   Response: <generated response>
```

## 6. Создание Test Events

### Через Jira UI (рекомендуемо)
1. Создайте новую карточку в Jira
2. В описание напишите техническую проблему
3. Агент автоматически обработает событие и постит комментарий

### Через Redis CLI (для тестирования)
```powershell
# Запустите redis-cli
docker exec -it redis redis-cli

# Добавьте test событие
XADD jira.events * \
  issue_key "TEST-123" \
  event_type "issue_created" \
  payload '{"summary": "Test issue", "description": "Test description"}'
```

## 7. Структура Логирования

Все компоненты логируют в console с формата:
```
[YYYY-MM-DD HH:MM:SS] LEVEL - message
```

### Важные уровни логирования:
- `INFO` — нормальная работа
- `WARNING` — возможные проблемы (переданные данные неполные)
- `ERROR` — критические ошибки (требуют внимания)

## Конфигурация (.env)

Все параметры конфигурации находятся в `.env`:

```dotenv
# Redis Stream Configuration
REDIS_URL=redis://localhost:6379
REDIS_STREAM=jira.events
REDIS_GROUP=agent-group
REDIS_CONSUMER=agent-1

# Ollama (Local LLM)
OLLAMA_URL=http://10.60.18.220:11434/
OLLAMA_MODEL=qwen3:8b

# RAG API (Knowledge Base)
RAG_API_URL=http://10.10.10.5:9621
RAG_USERNAME=user4
RAG_API_KEY=y470fFRIq-

# Jira MCP Server
JIRA_URL=http://10.10.30.2:8080
JIRA_TOKEN=<your-personal-token>
```

## Структура Событий из Webhook

Webhook Gateway преобразует Jira события в Redis Stream сообщения:

```json
{
  "issue_key": "TEST-37",
  "event_type": "issue_created|comment_created|issue_updated",
  "payload": {
    "issue_key": "TEST-37",
    "summary": "Issue summary",
    "description": "Issue description",
    "status": "To Do",
    "assignee": "user@example.com",
    "priority": "High"
  }
}
```

## Поток Обработки

1. **Webhook Gateway** — слушает Jira события и пушит в Redis Stream
2. **Redis** — хранит очередь событий
3. **Agent (main.py)** — читает события из Redis
   - `ingest_event` — загружает полную информацию из Jira (комментарии, статус и т.д.)
   - `classify_request` — определяет категорию вопроса
   - `search_knowledge` — ищет ответ в базе знаний (RAG)
   - `generate_response` — генерирует финальный ответ
   - `post_comment` — постит ответ обратно в Jira
4. **Jira** — отображает комментарий от агента

## Troubleshooting

### Агент не видит события
- Проверьте, что webhook gateway запущен: `docker ps`
- Проверьте, что события попадают в Redis: `docker exec redis redis-cli XLEN jira.events`
- Проверьте логирование в main.py на ошибки валидации

### MCP Atlassian падает
```
Unknown tool: get_issue
```
- Убедитесь, что uvx правильно установлен: `uvx --version`
- Перезапустите MCP сервер
- Проверьте JIRA_URL и JIRA_TOKEN в `.env`

### RAG не возвращает результаты
- Проверьте логи RAG_API_URL доступна: `curl http://10.10.10.5:9621/login`
- Проверьте учетные данные RAG_USERNAME и RAG_API_KEY

### LLM медленно отвечает
- Это нормально для первого запроса (загрузка модели)
- Проверьте, что OLLAMA_URL доступна: `curl http://10.60.18.220:11434/api/tags`

## Нормальный Flow для Новой Карточки

1. Создаете карточку в Jira: "Не работает функция X"
2. Webhook отправляет событие в Redis
3. Agent:
   - Загружает полную информацию о карточке (через MCP)
   - Определяет, что это техническая поддержка
   - Ищет ответ в документации (RAG)
   - Генерирует полный ответ (LLM)
   - Постит комментарий в Jira
4. Вы видите ответ в комментариях к карточке

## Дебаг Mode

Для детального логирования измените уровень в [app/main.py](app/main.py):
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO
    format="[%(asctime)s] %(levelname)s - %(message)s"
)
```

Для дебага конкретного компонента:
```python
import logging
logger = logging.getLogger("app.nodes.generate")
logger.setLevel(logging.DEBUG)
```
