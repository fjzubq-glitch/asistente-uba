# Guía de Configuración para Google Calendar API

Para que **Asistente Vero** pueda agendar eventos y leer su agenda diaria, necesitas habilitar Google Calendar API en Google Cloud Console y descargar el archivo `credentials.json`. Sigue estos sencillos pasos:

---

## Paso 1: Crear un proyecto en Google Cloud Console
1. Entra a [Google Cloud Console](https://console.cloud.google.com/).
2. Inicia sesión con tu cuenta de Google.
3. Arriba a la izquierda, haz clic en el selector de proyectos y luego haz clic en **"Proyecto Nuevo"** (New Project).
4. Dale un nombre al proyecto (ej. `Asistente Vero`) y haz clic en **"Crear"**.

## Paso 2: Habilitar Google Calendar API
1. En el menú de navegación izquierdo o en el buscador superior, ve a **"API y servicios"** > **"Biblioteca"** (Library).
2. En la barra de búsqueda escribe **"Google Calendar API"**.
3. Haz clic sobre ella y luego presiona el botón azul **"Habilitar"** (Enable).

## Paso 3: Configurar la Pantalla de Consentimiento OAuth (OAuth Consent Screen)
Google requiere que configures esta pantalla antes de darte credenciales:
1. Ve a **"API y servicios"** > **"Pantalla de consentimiento de OAuth"** (OAuth Consent Screen).
2. Selecciona Tipo de Usuario: **"Externo"** (External) y haz clic en **"Crear"**.
3. Completa los datos requeridos básicos:
   - **Nombre de la aplicación:** `Asistente Vero`
   - **Correo de soporte del usuario:** Tu correo electrónico.
   - **Información de contacto del desarrollador:** Tu correo electrónico.
4. Haz clic en **"Guardar y continuar"** en todos los pasos (no necesitas agregar alcances/scopes especiales ni subir la app a producción, déjala en modo "Prueba/Testing").
5. En el paso de **"Usuarios de prueba"** (Test Users), es **MUY IMPORTANTE** hacer clic en **"Add Users"** (Agregar usuarios) y agregar tu correo electrónico y el de tu esposa (las cuentas de Google de los calendarios que vas a usar). Haz clic en **"Guardar y continuar"**.

## Paso 4: Crear Credenciales de Cliente OAuth 2.0
1. Ve a **"API y servicios"** > **"Credenciales"** (Credentials).
2. Haz clic en **"Crear credenciales"** (Create Credentials) en la barra superior y selecciona **"ID de cliente de OAuth"** (OAuth client ID).
3. En **Tipo de aplicación** (Application type), elige **"Aplicación de escritorio"** (Desktop App).
4. Nombre: `Asistente Vero Client`
5. Haz clic en **"Crear"**.
6. Te aparecerá un cuadro con tus claves. Haz clic en **"Aceptar"** y luego busca tu credencial recién creada en la lista.
7. Haz clic en el botón de **descarga** (flecha apuntando hacia abajo en el extremo derecho de tu credencial) para descargar el archivo JSON.
8. **Cambia el nombre del archivo descargado a `credentials.json`** y colócalo dentro de la carpeta `Proyecto 3 - Asistente Vero` (al lado de `bot.py`).

---

## Paso 5: Primer Inicio y Autorización
La primera vez que ejecutes el bot en tu máquina:
1. El script abrirá automáticamente una ventana del navegador pidiendo iniciar sesión en tu cuenta de Google.
2. Selecciona la cuenta de Google correspondiente.
3. Te aparecerá una pantalla de advertencia ("Google no ha verificado esta aplicación"). Haz clic en **"Configuración avanzada"** (Advanced) y luego haz clic en **"Ir a Asistente Vero (no seguro)"**.
4. Haz clic en **"Permitir"** (Allow) para dar acceso a tu calendario.
5. El navegador mostrará un mensaje confirmando que la autorización fue exitosa.
6. En tu carpeta se creará automáticamente un archivo llamado `token.json`. ¡Listo! El bot ya podrá usar el calendario en segundo plano sin pedir autorización de nuevo.
