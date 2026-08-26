# Informe de Recuperación — Proyecto en la PC (carpetas borradas)

> **Contexto**: En la PC se borraron todas las carpetas del proyecto. El proyecto está versionado
> en GitHub, así que se recupera íntegro con `git clone`. Este archivo viaja dentro del repo
> para que la PC (opencode) lo lea al sincronizar.

---

## 1. Qué se recupera con el clone

`git clone` trae **todo el código y los apuntes `.md`** (commits hasta `c1b53f4` inclusive):
- `server.py`, `cron_alarmas_*.py`, `tests/`
- `Bot Telegram/`, `Asistente Vero/` (código)
- `Fabrica de Apuntes/` (scripts + instrucciones)
- `Universidad/` (apuntes de Contratos II y Derecho Comercial)
- `Proyecto 4 - Transcriptor de Audio/`
- `.agents/AGENTS.md`, `.env.example`, `INFORME_CAMBIOS_*.md`

## 2. QUÉ NO viene en el clone (y hay que restaurar a mano)

Estos archivos están en `.gitignore` por seguridad, **no se versionan**:
- **`.env`** (raíz) — tokens de Telegram/Groq/Gemini, `NOTION_TOKEN`, `NOTION_DB_ID`, folder IDs de Notion.
- **`Asistente Vero/.env`** — `CALENDAR_ID`, `GOOGLE_SCRIPT_PROXY_URL`, tokens.
- `env_raiz.txt` / `env_vero.txt` (backups planos de secretos, tampoco versionados).
- `Bot Telegram/chat_id.txt`, `Asistente Vero/chat_id.txt` (se regeneran solos al escribir al bot).
- `chats.json`, `ultimo_buenos_dias.txt`, `cache_precios.json`, `__pycache__/`.

**Sin los `.env`, los bots no arrancan.** Hay que copiarlos desde la NETBOOK (donde sí existen).

---

## 3. Pasos en la PC

### 3.1 Prerrequisitos
- Tener **Git** instalado (https://git-scm.com) y **Python 3.10+**.
- Tener acceso al repo (la netbook ya tiene push; si la PC no tiene credenciales, clonar como
  HTTPS pide usuario/token de GitHub).

### 3.2 Clonar el repositorio
Abrir una terminal en la carpeta donde querés el proyecto (ej. `C:\Users\TU_USUARIO\Desktop\Proyectos\`)
y ejecutar:

```powershell
git clone https://github.com/fjzubq-glitch/asistente-uba.git "Asistente UBA 1.0"
cd "Asistente UBA 1.0"
git log --oneline -3
```

Esto recrea TODAS las carpetas borradas.

### 3.3 Restaurar los secretos (desde la netbook)
En la **netbook**, copiar estos dos archivos a un pendrive/OneDrive/mail y pegarlos en la PC:
- `C:\...\Asistente UBA 1.0\.env` → pegar en la raíz del proyecto en la PC.
- `C:\...\Asistente UBA 1.0\Asistente Vero\.env` → pegar en `Asistente Vero/` en la PC.

> Si en la netbook no encontrás el `.env` pero sí `env_raiz.txt` / `env_vero.txt`, podés reconstruirlos:
> - raíz `.env` = copiar `env_raiz.txt` y agregarle las líneas `NOTION_CONTRATOS_II_FICHAS`,
>   `NOTION_CONTRATOS_II_CUESTIONARIOS`, `NOTION_CONTRATOS_FICHAS`, `NOTION_CONTRATOS_CUESTIONARIOS`,
>   `NOTION_DERECHO_COMERCIAL_FICHAS`, `NOTION_DERECHO_COMERCIAL_CUESTIONARIOS`,
>   `NOTION_COMERCIAL_FICHAS`, `NOTION_COMERCIAL_CUESTIONARIOS`, `TELEGRAM_CHAT_ID=8703253040`
>   (esos últimos NO están en `env_raiz.txt`; pedilos a opencode de la netbook
>   o mirá el informe `INFORME_CAMBIOS_OPENCODE.md`).
> - `Asistente Vero/.env` = copiar `env_vero.txt`.

### 3.4 Verificar
```powershell
git status            # debe decir "nothing to commit, working tree clean"
python -c "import dotenv,os; dotenv.load_dotenv(); print('TELEGRAM_TOKEN' in os.environ)"
```

---

## 4. Después de recuperar

- Para subir nuevos apuntes (Plan B) ver `INFORME_CAMBIOS_OPENCODE.md` (mismo repo):
  ```powershell
  python "Fabrica de Apuntes\subir_apuntes_existentes.py" --ficha "ruta\Ficha_....md" --cuestionario "ruta\Cuestionario_....md" --materia "Nombre" --clase N --fecha DD-MM-AA --tema "Tema"
  ```
- Recordá: respetar las reglas de `.agents/AGENTS.md` (español, commit+push automático).
