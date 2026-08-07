import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Si cambias estos alcances (scopes), elimina el archivo token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def obtener_servicio():
    """
    Inicializa y autentica el servicio de Google Calendar.
    Carga credenciales desde token.json o inicia el flujo OAuth2 si no existe.
    """
    creds = None
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, 'token.json')
    creds_path = os.path.join(base_dir, 'credentials.json')

    # El archivo token.json almacena los tokens de acceso y actualización del usuario.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    # Si no hay credenciales válidas disponibles, solicita al usuario que inicie sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"No se encontró el archivo '{creds_path}'. "
                    "Por favor, descarga las credenciales de cliente OAuth 2.0 (credentials.json) "
                    "desde Google Cloud Console y colócalas en la carpeta del proyecto."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Guarda las credenciales para la próxima ejecución
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def agendar_evento(summary, start_time, duration_minutes=60, description=None):
    """
    Agenda un evento en el Google Calendar.
    
    :param summary: Título del evento.
    :param start_time: Datetime o string ISO que indica el inicio.
    :param duration_minutes: Duración en minutos (por defecto 60).
    :param description: Descripción del evento.
    :return: El link HTML al evento creado en caso de éxito, o None si hay error.
    """
    try:
        service = obtener_servicio()
        calendar_id = os.environ.get("CALENDAR_ID", "primary")
        
        if isinstance(start_time, str):
            # Asegurar la zona horaria de Argentina (UTC-3) si no está definida
            if not ("+" in start_time or "-" in start_time or start_time.endswith("Z")):
                start_time = start_time + "-03:00"
            start_dt = datetime.datetime.fromisoformat(start_time)
        else:
            start_dt = start_time
            
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)
        
        event = {
            'summary': summary,
            'description': description or 'Agendado por Asistente Vero',
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'America/Argentina/Buenos_Aires',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'America/Argentina/Buenos_Aires',
            },
            'reminders': {
                'useDefault': True,
            }
        }
        
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        return created_event.get('htmlLink')
    except Exception as e:
        print(f"Error al agendar evento: {e}")
        return None

def listar_eventos_dia(fecha_str=None):
    """
    Retorna la lista de eventos para un día en formato YYYY-MM-DD.
    Si no se indica, usa la fecha actual en Argentina.
    """
    try:
        service = obtener_servicio()
        calendar_id = os.environ.get("CALENDAR_ID", "primary")
        
        if not fecha_str:
            # Obtener fecha actual en UTC-3
            ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
            fecha_str = ahora.strftime("%Y-%m-%d")
            
        time_min = f"{fecha_str}T00:00:00-03:00"
        time_max = f"{fecha_str}T23:59:59-03:00"
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    except Exception as e:
        print(f"Error al listar eventos: {e}")
        return None
