# Informe de Cambios y Mejoras — Asistente UBA & Vero

> **Para antigravity**: estos cambios **ya fueron realizados, testeados, commiteados y pusheados**.
> Tu tarea es **revisarlos y actualizar tu conocimiento** del estado actual del proyecto.
> No es necesario implementar nada nuevo; solo familiarizarte con las modificaciones para
> que puedas continuar apoyando el desarrollo de forma coherente.

---

## 1. Resumen de cambios

### 1.1 `server.py`
1. **Enrutamiento de respuestas por `chat_id` de la request (multi-usuario).**
   Antes, los `sendMessage` de los webhooks usaban los globales `MI_CHAT_ID_UBA`/`MI_CHAT_ID_VERO`,
   por lo que cualquier respuesta podía ir al chat equivocado. Ahora cada respuesta se envía al
   `chat_id` de quien escribió.
2. **Helper `ahora_argentina()` centralizado** (UTC-3). Elimina la repetición de
   `datetime.now(timezone.utc) - timedelta(hours=3)` en los webhooks y alarmas.
3. **`WEBHOOK_BASE_URL` configurable por entorno** con fallback a
   `https://franklinzg.pythonanywhere.com`. Se usa en `/set_webhook` y `/set_webhook_vero`.
4. **Alarmas refactorizadas en ciclos idempotentes** (`ejecutar_ciclo_uba()` y `ejecutar_ciclo_vero()`),
   invocables tanto desde hilo como desde cron (ver scripts nuevos). El flag `buenos_dias_enviado`
   se reemplazó por condición de minuto exacto + persistencia en disco.
5. **Multi-usuario en alarmas**: registro de chat_ids en `chats.json` (lista JSON) con migración
   automática desde `chat_id.txt`. Los ciclos difunden el mensaje a TODOS los chats registrados.
6. **Idempotencia del "Buenos días"**: se persiste la fecha del último envío en
   `ultimo_buenos_dias.txt`; así el cron/hilo no duplica el mensaje aunque corra varias veces.
7. **`enviar_telegram_retry()`**: envío a Telegram con reintentos básicos (2 intentos con backoff),
   usado en los ciclos de alarmas.
8. **Validación robusta de la respuesta de Groq** en `llamar_llm` (status + parseo JSON controlado).

### 1.2 `Asistente Vero/buscador_ofertas.py`
9. **Caché de precios online con TTL de 30 min** (`cache_precios.json`). Evita golpear
   `superprecio.ar`/proxy en cada consulta (el scraping bloquea el webhook hasta ~15 s).
10. **Fallback al caché** si la red falla o la respuesta no es 200.

### 1.3 Archivos nuevos
11. `cron_alarmas_uba.py` — punto de entrada para PythonAnywhere (Tasks) / cron: ejecuta
    `ejecutar_ciclo_uba()` una vez y termina.
12. `cron_alarmas_vero.py` — idem para Vero.
13. **`cron_alarmas_diarias.py`** — tarea única que ejecuta ambos ciclos en una corrida.
    Es el script recomendado para el plan free de PythonAnywhere (que solo permite **1 tarea diaria**).
14. `tests/test_core.py` — smoke tests de funciones puras (fechas, idempotencia, registro de chats,
    caché). Ver sección 4.

### 1.4 `.gitignore`
14. Se ignoran los archivos runtime: `chats.json`, `ultimo_buenos_dias.txt`, `cache_precios.json`.
15. **Se ignoran `env_raiz.txt` y `env_vero.txt`** (backups planos del `.env` con secretos). No deben
    commitearse ni pushearse.

---

## 2. Detalle técnico

### 2.1 Registro multi-usuario de chats
```python
# chats.json: ["<chat_id>", ...]
def _cargar_chats(path, legacy_file):   # migra desde chat_id.txt la primera vez
def _guardar_chats(path, chats)
def _registrar_chat(path, legacy_file, chat_id)  # idempotente
```
`guardar_chat_id_uba/vero` siguen escribiendo `chat_id.txt` (compatibilidad) y además registran en
la lista. `ejecutar_ciclo_*` difunden a todos los chat_ids de la lista.

### 2.2 Idempotencia del Buenos Días
```python
BUENOS_DIAS_STATE_UBA  = <Bot Telegram>/ultimo_buenos_dias.txt
BUENOS_DIAS_STATE_VERO = <Asistente Vero>/ultimo_buenos_dias.txt
```
`buenos_dias_ya_enviado_hoy()` lee la fecha guardada; `marcar_buenos_dias_enviado()` la escribe.
Solo se envía si `hora == 8` y `minuto == 0` y no se envió hoy.

### 2.3 Ciclos de alarmas (hilo y cron)
- `revisar_alarmas_uba/vero()` = bucle `while True` que llama a `ejecutar_ciclo_*()` y `sleep(60)`.
- `ejecutar_ciclo_*()` = una pasada: buenos días (si corresponde) + recordatorios a 10 min (UBA).
  Termina sin hilos colgados, por eso es apto para cron.

### 2.4 Caché de precios online
```python
CACHE_FILE = <Asistente Vero>/cache_precios.json
CACHE_TTL  = 1800  # 30 min
```
- Clave = término normalizado (`termino.lower()`).
- Si hay entrada fresca → devuelve sin red.
- Si la red falla o status != 200 → devuelve caché viejo si existe.
- Si el parseo tiene éxito → actualiza el caché.

---

## 3. Configuración en PythonAnywhere (Tasks / cron)

**Limitación del plan free**: permite **1 (una) tarea programada diaria** (no horaria). Por eso se
creó `cron_alarmas_diarias.py`, que ejecuta UBA y Vero en la misma corrida.

Pestaña *Tasks* → *Add scheduled task* (`python3.10`):

| Tarea | Horario (UTC) | Equivale |
|-------|---------------|----------|
| `python3.10 /home/franklinzg/asistente-uba/cron_alarmas_diarias.py` | 11:00 UTC (daily) | 08:00 Argentina — buenos días UBA y Vero |

> **Recordatorios "10 min antes"**: el plan free no permite tareas cada minuto. Los recordatorios
> dentro del día siguen a cargo de los hilos de `server.py` (se activan cuando llega un webhook o se
> llama a `/ping`, y viven mientras el worker está cargado). Si se quiere recordatorios garantizados
> por cron, hay que pasar a un plan de pago (Hacker, ~USD 5, otorga 20 tareas horarias/diarias y
> 1 always-on task) o mover a proveedor con scheduler de 1 min.

Los scripts individuales `cron_alarmas_uba.py` / `cron_alarmas_vero.py` sirven si se usa un plan de
pago con más slots o un cron externo.

Variable opcional en `.env`:
```env
WEBHOOK_BASE_URL=https://franklinzg.pythonanywhere.com
```

---

## 4. Verificación

- `python -m py_compile server.py cron_alarmas_uba.py cron_alarmas_vero.py` → OK.
- Import completo de `server`, `cron_alarmas_*` y `buscador_ofertas` → OK (rutas Flask registradas).
- `tests/test_core.py` → 4/4 PASS:
  - `formatear_fecha_humana`
  - idempotencia del Buenos Días
  - registro/migración de chats
  - roundtrip del caché de precios

---

## 5. Recomendaciones pendientes para incorporar después

1. **Manejo de retries en Notion y Google Calendar** para escrituras (hoy solo Telegram tiene retry).
2. **Cache adicional**: considerar TTL más corto (15 min) si las promos cambian mucho; ajustar `CACHE_TTL`.
3. **Depuración**: el comando `diagnostico_proxy` sigue en el bot Vero (muestra prefijos de variables y
   nombres de archivos). Útil en dev; evaluar restringirlo si el bot se comparte.
4. **Pruebas de integración** con credenciales reales (webhook local vía túnel) para validar el flujo
   completo end-to-end antes de migrar a cron.

---

## Estado actual en producción (verificado 07/08/2026)

Todos los cambios ya están **deployados y funcionando**:
- `git pull` ejecutado en PythonAnywhere (commit `fdcc86e`).
- Web app recargada y sirviendo el código nuevo.
- cron-job.org ejecutando `/ping` cada 1 min → `OK - UBA Thread: True - Vero Thread: True`.
- Webhooks de Telegram respondiendo normalmente.
- `env_raiz.txt` y `env_vero.txt` (secretos) correctamente excluidos de git.
