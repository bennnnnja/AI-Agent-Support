# Диагностика и Запуск: Agent читает Summary и Description

Агент видит события из Jira, но не читает название и описание. Вот как это исправить.

## Проблема

Webhook gateway отправляет в Redis только `issue_key` и `event_type`, но не `summary` и `description`. 

Решение: Агент должен загружать полную информацию через MCP Atlassian сервер.

## Шаг 1: Диагностика MCP

**Откройте новый PowerShell терминал** и проверьте, работает ли MCP:

```powershell
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
python test_mcp_direct.py
```

### Ожидаемый вывод (успех):
```
✓ MCP call succeeded!
✓ Response parsed successfully!
  issue_key: TEST-1
  summary: ...
  description: ...
  comments: N items
```

### Если вывод содержит ошибку:

**Ошибка: "Connection refused"**
→ MCP сервер НЕ запущен. Переходите на Шаг 2.

**Ошибка: "Unknown tool: get_issue"**
→ MCP сервер запущен, но не видит инструменты. 
* Проверьте что вывод MCP сервера содержит `Tool: get_issue`
* Если нет - перезапустите: `Ctrl+C` и `uvx mcp-atlassian`

**Ошибка: "connection error" или timeout**
→ Проверьте `JIRA_URL` и `JIRA_TOKEN` в `.env`

## Шаг 2: Запуск MCP Atlassian Сервера

**В отдельном PowerShell терминале:**

```powershell
# Активировать virtual environment
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1

# Запустить MCP сервер
uvx mcp-atlassian
```

Должен появиться вывод типа:
```
MCP Atlassian Server starting...
Connected to Jira at: http://10.10.30.2:8080
Tools available:
  - get_issue
  - add_comment
  - search_issues
Server running on stdio...
```

**Если ошибка типа "Unable to find tool":**
```powershell
# Переустанавливаем
uvx --force-reinstall mcp-atlassian
```

## Шаг 3: Запуск Агента

**В третьем PowerShell терминале:**

```powershell
# Активировать virtual environment
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1

# Запустить агента
python -m app.main
```

Должны увидеть логи:
```
Starting agent | stream=jira.events
Listening for events...
[INFO] Processing issue_created for TEST-X
[INFO] [ingest] Fetching issue details for TEST-X
[INFO] [ingest] Loaded issue data: key=TEST-X, summary=...
[INFO] Invoking graph for TEST-X
[INFO] Classified as: tech_support
[INFO] Resolved answer...
```

## Шаг 4: Тестирование (создать новую карточку в Jira)

1. Откройте https://10.10.30.2:8080/
2. Создайте новую задачу в проекте TEST
3. Напишите:
   - **Summary:** "Как установить приложение?"
   - **Description:** "У меня Windows, не знаю как установить приложение X"
4. Создайте задачу

Через ~5-10 секунд агент должен:
- Загрузить информацию о задаче
- Поискать в базе знаний ответ
- Постить комментарий с решением

## Troubleshooting

### Агент по-прежнему говорит "No message content"

1. Убедитесь что MCP сервер запущен: `python test_mcp_direct.py`
2. Проверьте логи агента - должны быть `[ingest]` логи
3. Если видите `[ingest] ⚠️ Check if MCP Atlassian server is running` - запустите MCP
4. Если видите `[ingest] ⚠️ MCP Atlassian server is not running!` - запустите MCP

### Почему агент не видит комментарии в Jira?

- MCP сервер может быть не запущен
- JIRA_TOKEN может быть неверным
- Проверьте: `curl -H "Authorization: Bearer <TOKEN>" http://10.10.30.2:8080/rest/api/2/issue/TEST-1`

### LLM медленно отвечает

- Первый запрос медленный (загрузка модели)
- Это нормально, подождите 5-10 сек
- Последующие ответы будут быстрее

### RAG не возвращает результаты

- Это может быть, если в базе знаний нет релевантной информации
- Агент всё равно даст ответ типа "В документации нет информации..."

## Финальный Чеклист

- ✅ Redis запущен и слушает на `localhost:6379`
- ✅ Webhook gateway запущен и отправляет события в Redis
- ✅ MCP Atlassian сервер запущен
- ✅ Agent запущен
- ✅ Создана тестовая задача в Jira
- ✅ Через 10 сек агент постит комментарий

## Команды для быстрого Restart

Если что-то не работает, пересоздайте все:

```powershell
# Terminal 1: MCP Atlassian
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
uvx mcp-atlassian

# Terminal 2: Agent Main Loop
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
python -m app.main

# Terminal 3: (опционально) диагностика
& C:\ai-agent-support\myvenv\Scripts\Activate.ps1
python test_mcp_direct.py
```

Если по-прежнему не работает:
1. Сделайте Ctrl+C во всех терминалах
2. Подождите 2 сек
3. Распечатайте логи с ошибками
4. Отправьте в поддержку
