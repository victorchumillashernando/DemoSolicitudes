import streamlit as st
import asyncio
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import openai
import time
import json
import re
import urllib

estados_solicitud = {
    1: "Pendiente de autorización",
    2: "Pendiente",
    3: "En progreso",
    4: "Rechazada",
    5: "Finalizada",
    6: "Cancelada"
}

estados_pasos = {
    1: "Pendiente",
    2: "Finalizada",
    3: "En progreso",
    4: "Rechazada",
}

client = openai.AsyncAzureOpenAI(
    api_key=st.secrets["AZURE_OPENAI_KEY"],
    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"],
    api_version="2024-05-01-preview"
)

if "thread_id" not in st.session_state:
    thread = asyncio.run(client.beta.threads.create())
    st.session_state.thread_id = thread.id

if "messages" not in st.session_state:
    st.session_state.messages = []

def extraer_emails(texto):
    pattern = r'[\w\.-]+@[\w\.-]+'
    return re.findall(pattern, texto)

def getDataUserByMail(mail, is_destinatario=False):
    """
    Obtiene los datos del usuario a partir de su mail llamando a la API.
    Si is_destinatario es True, no incluye autorizadorId ni autorizadorApoyoId.
    """
    print(mail)
    usuario, dominio = mail.split('@')

    print("Usuario:", usuario)
    print("Dominio:", dominio)

    validToken = generarToken(mail)
    url = f"https://apisolicitudesonline.cinconet.local/api/Gestion/Usuario/Directorio/{usuario}"
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Authorization': f'Bearer {validToken}'
    }

    response = requests.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        return None  # Retorna None si hay un error

    data = response.json()
    nombre = data.get("nombre", "")
    apellidos = data.get("apellidos", "")
    empresa = data.get("empresa", "")
    # Extraer valores
    correo = mail
    login = usuario

    validToken = generarToken(correo)
    url = f"https://apisolicitudesonlinepre.cinconet.local/api/Solicitud/Ultima"
    headers['Authorization'] = f'Bearer {validToken}'

    response = requests.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        return None  # Retorna None si hay un error

    data = response.json()

    # Construir el diccionario base
    user_data = {
        "nombre": nombre,
        "apellidos": apellidos,
        "login": login,
        "email": correo,
        "telefono": data.get("telefono"),
        "departamento": data.get("departamento"),
        "empresa": empresa,
        "centro": data.get("centro"),
        "edificio": data.get("edificio"),
        "planta": data.get("planta")
    }
    
    # Si no es destinatario, agregar autorizadorId y autorizadorApoyoId
    if not is_destinatario:
        user_data["autorizadorId"] = data.get("autorizadorId")
        user_data["autorizadorApoyoId"] = data.get("autorizadorApoyoId")
    
    return user_data

def generar_jsonMails_externos(principal_mail, destinatarios_externos):
    """
    Genera el JSON con los datos del usuario principal y los destinatarios.
    """
    # Obtener datos del usuario principal
    principal_data = getDataUserByMail(principal_mail)
    if not principal_data:
        return {"error": f"No se encontró el usuario principal externos{principal_mail}"}

    formatted_externos = []
    for ext in destinatarios_externos:
            ext_payload = {
                "nombre": ext["nombre"],
                "apellidos": ext["apellidos"],
                "login": "",
                "departamento": ext["departamento"],
                "empresa": ext["empresa"],
                "centro": ext["centro"],
                "edificio": "" if ext.get("edificio", "").lower() == "ninguno" else ext["edificio"],
                "planta": "" if ext.get("planta", "").lower() == "ninguno" else ext["planta"]
            }
            formatted_externos.append(ext_payload)

    # Construir el JSON final
    resultado = {
        "autorizadorId": principal_data["autorizadorId"],
        "autorizadorApoyoId": principal_data["autorizadorApoyoId"],
        "telefono": principal_data["telefono"],
        "departamento": principal_data["departamento"],
        "destinatarios": formatted_externos,
        "observaciones": "test",
        "justificacion": "Test",
        "productoraId": None,
        "programa": "",
        "centro": principal_data["centro"],
        "edificio": principal_data["edificio"],
        "planta": principal_data["planta"]
    }

    return resultado

def generar_jsonMails(principal_mail, destinatarios_mails):
    """
    Genera el JSON con los datos del usuario principal y los destinatarios.
    """
    # Obtener datos del usuario principal
    principal_data = getDataUserByMail(principal_mail)
    if not principal_data:
        return {"error": f"No se encontró el usuario principal{principal_mail}"}

    # Obtener datos de los destinatarios (si la lista no está vacía)
    destinatarios = [getDataUserByMail(dest_mail, is_destinatario=True) for dest_mail in destinatarios_mails]
    destinatarios = [d for d in destinatarios if d]  # Filtrar valores None

    # Construir el JSON final
    resultado = {
        "autorizadorId": principal_data["autorizadorId"],
        "autorizadorApoyoId": principal_data["autorizadorApoyoId"],
        "telefono": principal_data["telefono"],
        "departamento": principal_data["departamento"],
        "destinatarios": destinatarios,
        "observaciones": "test",
        "justificacion": "Test",
        "productoraId": None,
        "programa": "",
        "centro": principal_data["centro"],
        "edificio": principal_data["edificio"],
        "planta": principal_data["planta"]
    }

    return resultado

def formatear_fecha(fecha_str):
    try:
        fecha_obj = datetime.fromisoformat(fecha_str[:-1])
        return fecha_obj.strftime("%Y-%m-%d %Hh")
    except:
        return "Fecha inválida"

def generarToken(usuario):
    url = "https://apisolicitudesonlinepre.cinconet.local/api/Auth/login"
    username = usuario
    password = "tu_contraseña"
    response = requests.post(url, auth=HTTPBasicAuth(username, password), verify=False)
    return response.json().get("validToken")

def imprimir_solicitudes(lista, usuario, validToken):
    solicitudes_data = []
    for solicitud in lista:
        solicitud_id = solicitud.get("id", "N/A")
        estado_id = solicitud.get("estadoSolicitudId", "N/A")
        estado = estados_solicitud.get(estado_id, "Desconocido")
        autorizador = solicitud.get("autorizador", {})
        autorizador_nombre = autorizador.get("nombre", "N/A")
        autorizador_apellidos = autorizador.get("apellidos", "N/A")
        fecha_alta_raw = solicitud.get("fechaAlta", "N/A")
        fecha_alta = formatear_fecha(fecha_alta_raw) if fecha_alta_raw != "N/A" else "N/A"
        destinatarios = solicitud.get("destinatarios", [])
        destinatarios_lista = [f"{d.get('nombre', '')} {d.get('apellidos', '')}".strip() for d in destinatarios]
        url = f"https://apisolicitudesonlinepre.cinconet.local/api/Solicitud/Detalle/{solicitud_id}"
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }
        detalles_response = requests.get(url, headers=headers, verify=False).json()
        print(detalles_response)
        # Formateamos detalle de cada solicitud para el despliegue
        detalles = []
        for tarea in detalles_response:
            pasos = tarea.get('pasos', [])
            pasos_fmt = []
            for idx, paso in enumerate(pasos, 1):
                desc = paso.get('descripcion', 'N/A')
                estado_paso = estados_pasos.get(paso.get('estadoId', 0), 'Desconocido')
                nombre_responsalble_paso = paso.get('nombre', 'N/A')
                apellido_responsalble_paso = paso.get('apellidos', 'N/A')
                pasos_fmt.append(f"Paso {idx}: {desc} - Estado: {estado_paso} - Responsable: {nombre_responsalble_paso} {apellido_responsalble_paso}")
            detalles.append({
                "nombre": tarea.get('nombre', 'N/A'),
                "pasos": pasos_fmt
            })
        solicitudes_data.append({
            "ID": solicitud_id,
            "Estado": estado,
            "FechaAlta": fecha_alta,
            "Destinatarios": destinatarios_lista or [usuario],
            "Autorizador": f"{autorizador_nombre} {autorizador_apellidos}",
            "Detalles": detalles,
            "ObservacionAutorizador": solicitud.get("observacionAutorizador", "")
        })
    return solicitudes_data


def create_solicitud_ofimatica(tipo_accesorio, cc, descripcion, fecha_necesidad, cantidad,destinatarios_internos,destinatarios_externos):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        print(tipo_accesorio)
        # Mapeo tipo_accesorio a nivel1Id correspondiente en niveles
        niveles_map = {
            "monitor": 346,
            "ratón": 347,
            "teclado": 348,
            "altavoces": 349,
            "cascos": 350,
            "pendrive": 351,
            "xdcam": 352,
            "escaner": 353,
            "Impresora B/N (láser)": 354,
            "ipad/tablet": 355,
            "otro material (indicar descripción)": 356,
            "camara web": 456,
            "mochila para portátil": 464
        }
        
        nivel1_id = niveles_map.get(tipo_accesorio.lower())
        if not nivel1_id:
            return f"⚠️ Tipo de accesorio no válido. Opciones: {', '.join(niveles_map.keys())}"

        payload_dict = {
            "idRecurso": 65574,
            "idRecursoCatalogo": 233,
            "nombre": "ACCESORIOS OFIMÁTICOS",
            "descripcion": "OTRO MATERIAL OFIMÁTICO (IPAD, TABLET, IMPRESORAS, RATÓN-TECLADO CARACTERÍSTICAS ESPECIALES, ESCANER..)",
            "urlImagen": "NO_IMAGE",
            "coste": 0.00,
            "activo": True,
            "nivelesRecurso": [
                {
                    "id": 28076,
                    "nivel1Id": nivel1_id,
                    "nivel1": None,
                    "nivel2Id": None,
                    "nivel2": None,
                    "nivel3": None
                }
            ],
            "niveles": [
                {
                    "id": 346,
                    "descripcion": "Monitor",
                    "nivel2": []
                },
                {
                    "id": 347,
                    "descripcion": "Ratón ",
                    "nivel2": []
                },
                {
                    "id": 348,
                    "descripcion": "Teclado",
                    "nivel2": []
                },
                {
                    "id": 349,
                    "descripcion": "Altavoces",
                    "nivel2": []
                },
                {
                    "id": 350,
                    "descripcion": "Cascos",
                    "nivel2": []
                },
                {
                    "id": 351,
                    "descripcion": "Pendrive",
                    "nivel2": []
                },
                {
                    "id": 352,
                    "descripcion": "XDCAM",
                    "nivel2": []
                },
                {
                    "id": 353,
                    "descripcion": "Escaner",
                    "nivel2": []
                },
                {
                    "id": 354,
                    "descripcion": "Impresora B/N (láser)",
                    "nivel2": []
                },
                {
                    "id": 355,
                    "descripcion": "Ipad/Tablet",
                    "nivel2": []
                },
                {
                    "id": 356,
                    "descripcion": "otro material (indicar descripción)",
                    "nivel2": []
                },
                {
                    "id": 456,
                    "descripcion": "Cámara Web",
                    "nivel2": []
                },
                {
                    "id": 464,
                    "descripcion": "Mochila para portátil",
                    "nivel2": []
                }
            ],
            "campos": [
                {
                    "id": 113035,
                    "maestroId": 2,
                    "valor": cc,
                    "recursoId": 0,
                    "obligatorio": True
                },
                {
                    "id": 113036,
                    "maestroId": 4,
                    "valor": descripcion,
                    "recursoId": 0,
                    "obligatorio": True
                },
                {
                    "id": 113037,
                    "maestroId": 7,
                    "valor": fecha_necesidad,
                    "recursoId": 0,
                    "obligatorio": False
                },
                {
                    "id": 113038,
                    "maestroId": 9,
                    "valor": str(cantidad),
                    "recursoId": 0,
                    "obligatorio": True
                }
            ],
            "baja": False,
            "bajaCatalogo": True,
            "descargaPlano": False,
            "nivel1": "Tipo de accesorio",
            "obligatorioNivel1": True,
            "nivel2": None,
            "obligatorioNivel2": False,
            "nivel3": None,
            "obligatorioNivel3": False
        }
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()
            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False) 
        except requests.exceptions.RequestException as e:
            return f"⚠️ Error al enviar la solicitud de ofimática: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        print(tipo_accesorio)
        # Mapeo tipo_accesorio a nivel1Id correspondiente en niveles
        niveles_map = {
            "monitor": 346,
            "ratón": 347,
            "teclado": 348,
            "altavoces": 349,
            "cascos": 350,
            "pendrive": 351,
            "xdcam": 352,
            "escaner": 353,
            "Impresora B/N (láser)": 354,
            "ipad/tablet": 355,
            "otro material (indicar descripción)": 356,
            "camara web": 456,
            "mochila para portátil": 464
        }
        
        nivel1_id = niveles_map.get(tipo_accesorio.lower())
        if not nivel1_id:
            return f"⚠️ Tipo de accesorio no válido. Opciones: {', '.join(niveles_map.keys())}"

        payload_dict = {
            "idRecurso": 65574,
            "idRecursoCatalogo": 233,
            "nombre": "ACCESORIOS OFIMÁTICOS",
            "descripcion": "OTRO MATERIAL OFIMÁTICO (IPAD, TABLET, IMPRESORAS, RATÓN-TECLADO CARACTERÍSTICAS ESPECIALES, ESCANER..)",
            "urlImagen": "NO_IMAGE",
            "coste": 0.00,
            "activo": True,
            "nivelesRecurso": [
                {
                    "id": 28076,
                    "nivel1Id": nivel1_id,
                    "nivel1": None,
                    "nivel2Id": None,
                    "nivel2": None,
                    "nivel3": None
                }
            ],
            "niveles": [
                {
                    "id": 346,
                    "descripcion": "Monitor",
                    "nivel2": []
                },
                {
                    "id": 347,
                    "descripcion": "Ratón ",
                    "nivel2": []
                },
                {
                    "id": 348,
                    "descripcion": "Teclado",
                    "nivel2": []
                },
                {
                    "id": 349,
                    "descripcion": "Altavoces",
                    "nivel2": []
                },
                {
                    "id": 350,
                    "descripcion": "Cascos",
                    "nivel2": []
                },
                {
                    "id": 351,
                    "descripcion": "Pendrive",
                    "nivel2": []
                },
                {
                    "id": 352,
                    "descripcion": "XDCAM",
                    "nivel2": []
                },
                {
                    "id": 353,
                    "descripcion": "Escaner",
                    "nivel2": []
                },
                {
                    "id": 354,
                    "descripcion": "Impresora B/N (láser)",
                    "nivel2": []
                },
                {
                    "id": 355,
                    "descripcion": "Ipad/Tablet",
                    "nivel2": []
                },
                {
                    "id": 356,
                    "descripcion": "otro material (indicar descripción)",
                    "nivel2": []
                },
                {
                    "id": 456,
                    "descripcion": "Cámara Web",
                    "nivel2": []
                },
                {
                    "id": 464,
                    "descripcion": "Mochila para portátil",
                    "nivel2": []
                }
            ],
            "campos": [
                {
                    "id": 113035,
                    "maestroId": 2,
                    "valor": cc,
                    "recursoId": 0,
                    "obligatorio": True
                },
                {
                    "id": 113036,
                    "maestroId": 4,
                    "valor": descripcion,
                    "recursoId": 0,
                    "obligatorio": True
                },
                {
                    "id": 113037,
                    "maestroId": 7,
                    "valor": fecha_necesidad,
                    "recursoId": 0,
                    "obligatorio": False
                },
                {
                    "id": 113038,
                    "maestroId": 9,
                    "valor": str(cantidad),
                    "recursoId": 0,
                    "obligatorio": True
                }
            ],
            "baja": False,
            "bajaCatalogo": True,
            "descargaPlano": False,
            "nivel1": "Tipo de accesorio",
            "obligatorioNivel1": True,
            "nivel2": None,
            "obligatorioNivel2": False,
            "nivel3": None,
            "obligatorioNivel3": False
        }
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()
            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            print(f"input cribado:{str(destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False) 
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            return f"⚠️ Error al enviar la solicitud de ofimática: {str(e)}" 
    lista_destinatarios=", ".join(lista_destinatarios)

    return (
        f"🖨️ Solicitud para '{tipo_accesorio}' registrada correctamente.\n"
        f"- CC: {cc}\n"
        f"- Descripción: {descripcion}\n"
        f"- Fecha: {fecha_necesidad}\n"
        f"- Cantidad: {cantidad}\n"
        f"- destinatarios: { nombres + str(lista_destinatarios) or 'tu'}\n"
    )
    

def create_solicitud_wifi(tipo_red, observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        red_opciones = {
            "corporativa": 344,
            "invitados": 345
        }

        nivel_id = red_opciones.get(tipo_red.lower())
        if not nivel_id:
            return f"⚠️ Tipo de red no válido. Usa 'corporativa' o 'invitados'."

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 101,
            "nivelesRecurso": [
                {
                    "id": 0,
                    "nivel1Id": nivel_id,
                    "nivel1": None,
                    "nivel2Id": None,
                    "nivel2": None,
                    "nivel3": None
                }
            ],
            "niveles": [
                {
                    "id": 344,
                    "descripcion": "Corporativa",
                    "nivel2": []
                },
                {
                    "id": 345,
                    "descripcion": "Invitados",
                    "nivel2": []
                }
            ],
            "campos": [
                {
                    "id": 0,
                    "maestroId": 10,
                    "valor": observaciones or "Sin observaciones",
                    "recursoId": 0,
                    "obligatorio": False
                }
            ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de WiFi: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        red_opciones = {
            "corporativa": 344,
            "invitados": 345
        }

        nivel_id = red_opciones.get(tipo_red.lower())
        if not nivel_id:
            return f"⚠️ Tipo de red no válido. Usa 'corporativa' o 'invitados'."

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 101,
            "nivelesRecurso": [
                {
                    "id": 0,
                    "nivel1Id": nivel_id,
                    "nivel1": None,
                    "nivel2Id": None,
                    "nivel2": None,
                    "nivel3": None
                }
            ],
            "niveles": [
                {
                    "id": 344,
                    "descripcion": "Corporativa",
                    "nivel2": []
                },
                {
                    "id": 345,
                    "descripcion": "Invitados",
                    "nivel2": []
                }
            ],
            "campos": [
                {
                    "id": 0,
                    "maestroId": 10,
                    "valor": observaciones or "Sin observaciones",
                    "recursoId": 0,
                    "obligatorio": False
                }
            ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de WiFi: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
            f"📡 Solicitud de WiFi enviada correctamente:\n"
            f"- Tipo de red: {tipo_red.capitalize()}\n"
            f"- Observaciones: {observaciones or 'Ninguna'}\n"
            f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
        )


def create_solicitud_Interplay(tipoAcceso,permisos,observaciones="",destinatarios_internos="", destinatarios_externos=None):
    niveles_con_ids = {
    "Supervivientes": {
        "id": 249,
        "roles": {
            "Media manager": 160,
            "Redactor": 161,
            "Dirección": 393,
            "Editor de vídeo": 394,
            "Realizador/Ayudante de Realización": 395,
            "Postproducción": 409
        }
    },
    "Fiesta": {
        "id": 502,
        "roles": {
            "Media Manager": 251,
            "Dirección": 385,
            "Editor de vídeo": 389,
            "Redactor": 391,
            "Realizador/Ayudante de Realización": 397,
            "Postproducción": 408
        }
    },
    "La vida sin filtros": {
        "id": 534,
        "roles": {
            "Editor de vídeo": 279,
            "Redactor": 383,
            "Realizador/Ayudante de Realización": 384,
            "Dirección": 388,
            "Postproducción": 407
        }
    },
    "Así es la vida": {
        "id": 535,
        "roles": {
            "Redactor": 386,
            "Realizador/Ayudante de Realización": 387,
            "Dirección": 390,
            "Editor de vídeo": 396,
            "Postproducción": 406
        }
    },
    "Vamos A Ver": {
        "id": 568,
        "roles": {
            "Redactor": 374,
            "Guionista": 375,
            "Dirección": 376,
            "Producción": 377,
            "Postproducción": 398,
            "Dirección (2)": 403,
            "Realizador/Ayudante de Realización": 405,
            "Editor de vídeo": 411
        }
    },
    "La Mirada Crítica": {
        "id": 569,
        "roles": {
            "Redactor": 370,
            "Guionista": 371,
            "Dirección": 372,
            "Producción": 373,
            "Postproducción": 399,
            "Editor de vídeo": 400,
            "Realizador/Ayudante de Realización": 401
        }
    },
    "TardeAR": {
        "id": 570,
        "roles": {
            "Redactor": 366,
            "Guionista": 367,
            "Dirección": 368,
            "Producción": 369,
            "Realizador/Ayudante de Realización": 402,
            "Postproducción": 404,
            "Editor de vídeo": 410
        }
    },
    "Vecinos": {
        "id": 615,
        "roles": {
            "Realizador/Ayudante de Realización": 510,
            "Redactor": 511,
            "Guionista": 512,
            "Dirección": 513,
            "Producción": 514,
            "Postproducción": 515,
            "Editor de vídeo": 516
        }
    },
    "El Programa de Ana Rosa": {
        "id": 683,
        "roles": {
            "Realizador/Ayudante de Realización": 557,
            "Redactor": 558,
            "Guionista": 559,
            "Dirección": 560,
            "Producción": 561,
            "Postproducción": 562,
            "Editor de vídeo": 563
        }
    }
}

    if tipoAcceso not in niveles_con_ids:
        return f"Programa no encontrado: {tipoAcceso}"
    nivel1_id = niveles_con_ids[tipoAcceso]["id"]
    nivel2_id = niveles_con_ids[tipoAcceso]["roles"].get(permisos)
    if nivel2_id is None:
        return f"Rol no encontrado: {permisos} en el programa {tipoAcceso}"
    id_programa=nivel1_id
    id_rol=nivel2_id

    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
        "idRecurso": 0,
        "idRecursoCatalogo": 161,
        "nombre": "Interplay (Usuarios red de programas (RDP) - Telecinco)",
        "descripcion": "Inteplay (Usuarios red de programas Telecinco)",
        "urlImagen": "NO_IMAGE",
        "coste": 0.00,
        "activo": True,
        "nivelesRecurso": [
            {
                "id": 28227,
                "nivel1Id": id_programa,
                "nivel1": None,
                "nivel2Id": id_rol,
                "nivel2": None,
                "nivel3": None
            }
        ],
        "niveles": [
            {
                "id": 249,
                "descripcion": "Supervivientes",
                "nivel2": [
                    {
                        "id": 160,
                        "descripcion": "Media manager",
                        "nivel3": ""
                    },
                    {
                        "id": 161,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 393,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 394,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 395,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 409,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 502,
                "descripcion": "Fiesta",
                "nivel2": [
                    {
                        "id": 251,
                        "descripcion": "Media Manager",
                        "nivel3": ""
                    },
                    {
                        "id": 385,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 389,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 391,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 397,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 408,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 534,
                "descripcion": "La vida sin filtros",
                "nivel2": [
                    {
                        "id": 279,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 383,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 384,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 388,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 407,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 535,
                "descripcion": "Así es la vida",
                "nivel2": [
                    {
                        "id": 386,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 387,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 390,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 396,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 406,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 568,
                "descripcion": "Vamos A Ver",
                "nivel2": [
                    {
                        "id": 374,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 375,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 376,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 377,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 398,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 403,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 405,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 411,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 569,
                "descripcion": "La Mirada Crítica",
                "nivel2": [
                    {
                        "id": 370,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 371,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 372,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 373,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 399,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 400,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 401,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 570,
                "descripcion": "TardeAR",
                "nivel2": [
                    {
                        "id": 366,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 367,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 368,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 369,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 402,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 404,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 410,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 615,
                "descripcion": "Vecinos",
                "nivel2": [
                    {
                        "id": 510,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 511,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 512,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 513,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 514,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 515,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 516,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 683,
                "descripcion": "El Programa de Ana Rosa",
                "nivel2": [
                    {
                        "id": 557,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 558,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 559,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 560,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 561,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 562,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 563,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            }
        ],
        "campos": [
            {
                "id": 113611,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113612,
                "maestroId": 12,
                "valor": None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
        "baja": False,
        "bajaCatalogo": True,
        "descargaPlano": False,
        "nivel1": "Tipo de acceso",
        "obligatorioNivel1": True,
        "nivel2": "Permisos",
        "obligatorioNivel2": True,
        "nivel3": None,
        "obligatorioNivel3": False
    }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
        "idRecurso": 0,
        "idRecursoCatalogo": 161,
        "nombre": "Interplay (Usuarios red de programas (RDP) - Telecinco)",
        "descripcion": "Inteplay (Usuarios red de programas Telecinco)",
        "urlImagen": "NO_IMAGE",
        "coste": 0.00,
        "activo": True,
        "nivelesRecurso": [
            {
                "id": 28227,
                "nivel1Id": id_programa,
                "nivel1": None,
                "nivel2Id": id_rol,
                "nivel2": None,
                "nivel3": None
            }
        ],
        "niveles": [
            {
                "id": 249,
                "descripcion": "Supervivientes",
                "nivel2": [
                    {
                        "id": 160,
                        "descripcion": "Media manager",
                        "nivel3": ""
                    },
                    {
                        "id": 161,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 393,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 394,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 395,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 409,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 502,
                "descripcion": "Fiesta",
                "nivel2": [
                    {
                        "id": 251,
                        "descripcion": "Media Manager",
                        "nivel3": ""
                    },
                    {
                        "id": 385,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 389,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 391,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 397,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 408,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 534,
                "descripcion": "La vida sin filtros",
                "nivel2": [
                    {
                        "id": 279,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 383,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 384,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 388,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 407,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 535,
                "descripcion": "Así es la vida",
                "nivel2": [
                    {
                        "id": 386,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 387,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 390,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 396,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 406,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 568,
                "descripcion": "Vamos A Ver",
                "nivel2": [
                    {
                        "id": 374,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 375,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 376,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 377,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 398,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 403,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 405,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 411,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 569,
                "descripcion": "La Mirada Crítica",
                "nivel2": [
                    {
                        "id": 370,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 371,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 372,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 373,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 399,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 400,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 401,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 570,
                "descripcion": "TardeAR",
                "nivel2": [
                    {
                        "id": 366,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 367,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 368,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 369,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 402,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 404,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 410,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 615,
                "descripcion": "Vecinos",
                "nivel2": [
                    {
                        "id": 510,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 511,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 512,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 513,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 514,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 515,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 516,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 683,
                "descripcion": "El Programa de Ana Rosa",
                "nivel2": [
                    {
                        "id": 557,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 558,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 559,
                        "descripcion": "Guionista",
                        "nivel3": ""
                    },
                    {
                        "id": 560,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 561,
                        "descripcion": "Producción",
                        "nivel3": ""
                    },
                    {
                        "id": 562,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 563,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    }
                ]
            }
        ],
        "campos": [
            {
                "id": 113611,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113612,
                "maestroId": 12,
                "valor": None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
        "baja": False,
        "bajaCatalogo": True,
        "descargaPlano": False,
        "nivel1": "Tipo de acceso",
        "obligatorioNivel1": True,
        "nivel2": "Permisos",
        "obligatorioNivel2": True,
        "nivel3": None,
        "obligatorioNivel3": False
    }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de Inews enviada correctamente:\n"
        f"- tipo de Acceso: {tipoAcceso}\n"
        f"- permisos: {permisos}\n"
        f"- observaciones: {observaciones or "sin observaciones"}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )

def create_solicitud_Inews(tipoAcceso,permisos,observaciones="",destinatarios_internos="", destinatarios_externos=None):
    niveles_con_ids = {
        598: {
            "descripcion": "Supervivientes",
            "roles": {
                433: "Redactor",
                434: "Realizador/Ayudante de Realización",
                435: "Editor de vídeo",
                436: "Dirección",
                437: "Postproducción",
                438: "Tituladora"
            }
        },
        599: {
            "descripcion": "Fiesta",
            "roles": {
                439: "Redactor",
                458: "Realizador/Ayudante de Realización",
                459: "Editor de vídeo",
                460: "Dirección",
                461: "Postproducción",
                462: "Tituladora"
            }
        },
        600: {
            "descripcion": "La vida sin filtros",
            "roles": {
                463: "Redactor",
                464: "Realizador/Ayudante de Realización",
                465: "Editor de vídeo",
                466: "Dirección",
                467: "Postproducción",
                468: "Tituladora"
            }
        },
        601: {
            "descripcion": "Así es la vida",
            "roles": {
                456: "Tituladora",
                457: "Postproducción",
                469: "Redactor",
                470: "Realizador/Ayudante de Realización",
                471: "Editor de vídeo",
                472: "Dirección"
            }
        },
        602: {
            "descripcion": "Vamos a ver",
            "roles": {
                440: "Editor de vídeo",
                441: "Dirección",
                442: "Postproducción",
                443: "Tituladora",
                446: "Realizador/Ayudante de Realización",
                455: "Redactor"
            }
        },
        603: {
            "descripcion": "La mirada crítica",
            "roles": {
                444: "Redactor",
                445: "Realizador/Ayudante de Realización",
                447: "Editor de vídeo",
                448: "Postproducción",
                449: "Dirección",
                454: "Dirección"
            }
        },
        604: {
            "descripcion": "TardeAR",
            "roles": {
                450: "Redactor",
                451: "Realizador/Ayudante de Realización",
                452: "Editor de vídeo",
                453: "Dirección",
                473: "Postproducción",
                474: "Dirección"
            }
        },
        644: {
            "descripcion": "El diario de Jorge",
            "roles": {
                522: "Redactor",
                523: "Realizador/Ayudante de Realización",
                524: "Editor de vídeo",
                525: "Dirección",
                526: "Postproducción",
                527: "Media Manager"
            }
        },
        682: {
            "descripcion": "El Programa de Ana Rosa",
            "roles": {
                551: "Redactor",
                552: "Realizador/Ayudante de Realización",
                553: "Editor de vídeo",
                554: "Dirección",
                555: "Postproducción",
                556: "Media Manager"
            }
        }
    }

    for nivel1_id, nivel_data in niveles_con_ids.items():
        if nivel_data["descripcion"].lower() == tipoAcceso.lower():
            for nivel2_id, nombre_rol in nivel_data["roles"].items():
                if nombre_rol.lower() == permisos.lower():
                    id_programa=nivel1_id
                    id_rol=nivel2_id

    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
        "idRecurso": 0,
        "idRecursoCatalogo": 340,
        "nombre": "INEWS (Usuarios red de programas (RDP) - Telecinco)",
        "descripcion": "INEWS (Usuarios red de programas Telecinco)",
        "urlImagen": "NO_IMAGE",
        "coste": 0.00,
        "activo": True,
        "nivelesRecurso": [
            {
                "id": 28225,
                "nivel1Id": id_programa,
                "nivel1": None,
                "nivel2Id": id_rol,
                "nivel2": None,
                "nivel3": None
            }
        ],
        "niveles": [
            {
                "id": 598,
                "descripcion": "Supervivientes",
                "nivel2": [
                    {
                        "id": 433,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 434,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 435,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 436,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 437,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 438,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 599,
                "descripcion": "Fiesta",
                "nivel2": [
                    {
                        "id": 439,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 458,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 459,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 460,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 461,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 462,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 600,
                "descripcion": "La vida sin filtros",
                "nivel2": [
                    {
                        "id": 463,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 464,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 465,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 466,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 467,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 468,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 601,
                "descripcion": "Así es la vida",
                "nivel2": [
                    {
                        "id": 456,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    },
                    {
                        "id": 457,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 469,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 470,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 471,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 472,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 602,
                "descripcion": "Vamos a ver",
                "nivel2": [
                    {
                        "id": 440,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 441,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 442,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 443,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    },
                    {
                        "id": 446,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 455,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 603,
                "descripcion": "La mirada crítica",
                "nivel2": [
                    {
                        "id": 444,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 445,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 447,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 448,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 449,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 454,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 604,
                "descripcion": "TardeAR",
                "nivel2": [
                    {
                        "id": 450,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 451,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 452,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 453,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 473,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 474,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 644,
                "descripcion": "El diario de Jorge",
                "nivel2": [
                    {
                        "id": 522,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 523,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 524,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 525,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 526,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 527,
                        "descripcion": "Media Manager",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 682,
                "descripcion": "El Programa de Ana Rosa",
                "nivel2": [
                    {
                        "id": 551,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 552,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 553,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 554,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 555,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 556,
                        "descripcion": "Media Manager",
                        "nivel3": ""
                    }
                ]
            }
        ],
        "campos": [
            {
                "id": 113601,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113602,
                "maestroId": 12,
                "valor": None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
        "baja": False,
        "bajaCatalogo": True,
        "descargaPlano": False,
        "nivel1": "Tipo de acceso",
        "obligatorioNivel1": True,
        "nivel2": "Permisos",
        "obligatorioNivel2": True,
        "nivel3": None,
        "obligatorioNivel3": False
    }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
        "idRecurso": 0,
        "idRecursoCatalogo": 340,
        "nombre": "INEWS (Usuarios red de programas (RDP) - Telecinco)",
        "descripcion": "INEWS (Usuarios red de programas Telecinco)",
        "urlImagen": "NO_IMAGE",
        "coste": 0.00,
        "activo": True,
        "nivelesRecurso": [
            {
                "id": 28225,
                "nivel1Id": id_programa,
                "nivel1": None,
                "nivel2Id": id_rol,
                "nivel2": None,
                "nivel3": None
            }
        ],
        "niveles": [
            {
                "id": 598,
                "descripcion": "Supervivientes",
                "nivel2": [
                    {
                        "id": 433,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 434,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 435,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 436,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 437,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 438,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 599,
                "descripcion": "Fiesta",
                "nivel2": [
                    {
                        "id": 439,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 458,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 459,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 460,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 461,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 462,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 600,
                "descripcion": "La vida sin filtros",
                "nivel2": [
                    {
                        "id": 463,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 464,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 465,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 466,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 467,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 468,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 601,
                "descripcion": "Así es la vida",
                "nivel2": [
                    {
                        "id": 456,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    },
                    {
                        "id": 457,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 469,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 470,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 471,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 472,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 602,
                "descripcion": "Vamos a ver",
                "nivel2": [
                    {
                        "id": 440,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 441,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 442,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 443,
                        "descripcion": "Tituladora",
                        "nivel3": ""
                    },
                    {
                        "id": 446,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 455,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 603,
                "descripcion": "La mirada crítica",
                "nivel2": [
                    {
                        "id": 444,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 445,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 447,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 448,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 449,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 454,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 604,
                "descripcion": "TardeAR",
                "nivel2": [
                    {
                        "id": 450,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 451,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 452,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 453,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 473,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 474,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 644,
                "descripcion": "El diario de Jorge",
                "nivel2": [
                    {
                        "id": 522,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 523,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 524,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 525,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 526,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 527,
                        "descripcion": "Media Manager",
                        "nivel3": ""
                    }
                ]
            },
            {
                "id": 682,
                "descripcion": "El Programa de Ana Rosa",
                "nivel2": [
                    {
                        "id": 551,
                        "descripcion": "Redactor",
                        "nivel3": ""
                    },
                    {
                        "id": 552,
                        "descripcion": "Realizador/Ayudante de Realización",
                        "nivel3": ""
                    },
                    {
                        "id": 553,
                        "descripcion": "Editor de vídeo",
                        "nivel3": ""
                    },
                    {
                        "id": 554,
                        "descripcion": "Dirección",
                        "nivel3": ""
                    },
                    {
                        "id": 555,
                        "descripcion": "Postproducción",
                        "nivel3": ""
                    },
                    {
                        "id": 556,
                        "descripcion": "Media Manager",
                        "nivel3": ""
                    }
                ]
            }
        ],
        "campos": [
            {
                "id": 113601,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113602,
                "maestroId": 12,
                "valor": None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
        "baja": False,
        "bajaCatalogo": True,
        "descargaPlano": False,
        "nivel1": "Tipo de acceso",
        "obligatorioNivel1": True,
        "nivel2": "Permisos",
        "obligatorioNivel2": True,
        "nivel3": None,
        "obligatorioNivel3": False
    }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de Inews enviada correctamente:\n"
        f"- tipo de Acceso: {tipoAcceso}\n"
        f"- permisos: {permisos}\n"
        f"- observaciones: {observaciones or "sin observaciones"}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )



def create_solicitud_aplicaciones_gratuitas(observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 235,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113603,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 235,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113603,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de Aplicaciones gratuitas enviada correctamente:\n"
        f"- observaciones: {observaciones or "sin observaciones"}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )

def create_solicitud_Acceso_Directorio_Activo(descripcion,observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 269,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113603,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113604,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 269,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113603,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113604,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de acceso a grupos del directorio acivo enviada correctamente:\n"
        f"- descripcion: {descripcion}\n"
        f"- observaciones: {observaciones or "sin observaciones"}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )


def create_solicitud_Portatil(descripcion,cc,fecha="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 264,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113603,
                "maestroId": 2,
                "valor": cc,
                "recursoId": 0,
                "obligatorio": True
            },
            {
                "id": 113604,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            },
            {
                "id": 113605,
                "maestroId": 7,
                "valor": fecha or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 264,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113603,
                "maestroId": 2,
                "valor": cc,
                "recursoId": 0,
                "obligatorio": True
            },
            {
                "id": 113604,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            },
            {
                "id": 113605,
                "maestroId": 7,
                "valor": fecha or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de portatil enviada correctamente:\n"
        f"- descripcion: {descripcion}\n"
        f"- centro de coste: {cc}\n"
        f"- fecha: {fecha or "Sin fecha"}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )


def create_solicitud_Baja_Usario(observaciones="",fecha="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 310,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 7,
                "valor": fecha or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }

        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 310,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 7,
                "valor": fecha or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }

        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de baja de usuario enviada correctamente:\n"
        f"- observaciones: {observaciones or "Sin observaciones"}\n"
        f"- fecha: {fecha or "Sin fecha"}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )


def create_solicitud_Lista_Distribucion_Correo(descripcion,destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 273,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 273,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de lista de distribucion de correo enviada correctamente:\n"
        f"- Descripcion: {descripcion}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )


def create_solicitud_Alta_Correo(observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 4,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 4,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de Alta de correo enviada correctamente:\n"
        f"- Observaciones: {observaciones or 'Ninguna'}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )



def create_solicitud_Karibu(observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 43,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 43,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de acceso a Karibu enviada correctamente:\n"
        f"- Observaciones: {observaciones or 'Ninguna'}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )

def create_solicitud_Unidades_Red(observaciones="",unidadesRed="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 258,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113594,
                "maestroId": 15,
                "valor": unidadesRed or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113595,
                "maestroId": 12,
                "valor": None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 258,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113593,
                "maestroId": 10,
                "valor": observaciones or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113594,
                "maestroId": 15,
                "valor": unidadesRed or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113595,
                "maestroId": 12,
                "valor": None,
                "recursoId": 0,
                "obligatorio": False
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de Unidades de red enviada correctamente:\n"
        f"- Observaciones: {observaciones or 'Ninguna'}\n"
        f"- Unidades de Red: {unidadesRed or 'Ninguna'}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )


def create_solicitud_Alta_Usuario(descripcion,unidadesRed="",fecha="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 1,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113587,
                "maestroId": 15,
                "valor": unidadesRed or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113588,
                "maestroId": 7,
                "valor": fecha or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113589,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 1,
            "nivelesRecurso": [],
            "campos": [
            {
                "id": 113587,
                "maestroId": 15,
                "valor": unidadesRed or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113588,
                "maestroId": 7,
                "valor": fecha or None,
                "recursoId": 0,
                "obligatorio": False
            },
            {
                "id": 113589,
                "maestroId": 4,
                "valor": descripcion,
                "recursoId": 0,
                "obligatorio": True
            }
        ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de Alta de Usuario enviada correctamente:\n"
        f"- Descripcion: {descripcion or 'Ninguna'}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )

def create_solicitud_VPN(observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 99,
            "nivelesRecurso": [],
            "campos": [
                {
                    "id": 0,
                    "maestroId": 10,
                    "valor": observaciones or "Sin observaciones",
                    "recursoId": 0,
                    "obligatorio": False
                },
                {
                    "id":0,
                    "maestroId":12,
                    "valor":None
                }
            ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 99,
            "nivelesRecurso": [],
            "campos": [
                {
                    "id": 0,
                    "maestroId": 10,
                    "valor": observaciones or "Sin observaciones",
                    "recursoId": 0,
                    "obligatorio": False
                },
                {
                    "id":0,
                    "maestroId":12,
                    "valor":None
                }
            ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
        f"📡 Solicitud de VPN enviada correctamente:\n"
        f"- Observaciones: {observaciones or 'Ninguna'}\n"
        f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
    )

def create_solicitud_office_365(observaciones="",destinatarios_internos="", destinatarios_externos=None):
    lista_destinatarios=[]
    nombres=""
    if destinatarios_internos:
        destinatarios=destinatarios_internos
        destinatarios = [
            "vchumillas@megamedia.es" if d.strip().lower() == "user" else d.strip()
            for d in destinatarios
        ]
        print(f"input usuarios:{destinatarios_internos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"


        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 64,
            "nivelesRecurso": [],
            "campos": [
                {
                    "id": 0,
                    "maestroId": 10,
                    "valor": observaciones or "Sin observaciones",
                    "recursoId": 0,
                    "obligatorio": False
                }
            ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            lista_destinatarios = [
                correo.strip() for correo in destinatarios
                if correo.strip() and "@" in correo.strip()
            ]
            print(f"input cribado:{str(lista_destinatarios)}")
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails(user, lista_destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de office365: {str(e)}"
    if destinatarios_externos:
        destinatarios=destinatarios_externos
        print(f"input usuarios:{destinatarios_externos}")
        user = "vchumillas@megamedia.es"
        validToken = generarToken(user)
        
        url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"

        payload_dict = {
            "idRecurso": 0,
            "idRecursoCatalogo": 64,
            "nivelesRecurso": [],
            "campos": [
                {
                    "id": 0,
                    "maestroId": 10,
                    "valor": observaciones or "Sin observaciones",
                    "recursoId": 0,
                    "obligatorio": False
                }
            ],
            "baja": False,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'Bearer {validToken}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload_dict, verify=False)
            response.raise_for_status()

            result = response.json()
            solicitud_id = result.get("id", "N/A")
            
            #lista_targets = [item.strip() for item in destinatarios.split(",")]
            data = generar_jsonMails_externos(user, destinatarios)
            print(f"data:{str(data)}")
            url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud"
            headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }
            response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            nombres=""
            for destinatario in destinatarios:
                nombres+=destinatario["nombre"]+" "+destinatario["apellidos"] + ", "
        except requests.exceptions.RequestException as e:
            resultado+= f"⚠️ Error al enviar la solicitud de Office365: {str(e)}"

        lista_destinatarios=", ".join(lista_destinatarios)
    return (
            f"📡 Solicitud de office 365 enviada correctamente:\n"
            f"- Observaciones: {observaciones or 'Ninguna'}\n"
            f"- destinatarios: {nombres + str(lista_destinatarios) or 'tu'}\n"
        )

    

def check_status():
    user = "vchumillas@megamedia.es"
    validToken = generarToken(user)
    url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud/Solicitadas"
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Authorization': f'Bearer {validToken}'
    }
    response = requests.get(url, headers=headers, verify=False).json()
    en_proceso = [s for s in response if s.get("estadoSolicitudId") in [1, 2, 3]]
    finalizadas = [s for s in response if s.get("estadoSolicitudId") == 5]

    solicitudes_proceso = imprimir_solicitudes(en_proceso, user, validToken)
    solicitudes_finalizadas = imprimir_solicitudes(finalizadas, user, validToken)
    return {
        "en_proceso": solicitudes_proceso,
        "finalizadas": solicitudes_finalizadas
    }


def clean_response(text, documentos):
    onedrive_folder_url = "https://grupomediaset.sharepoint.com/:f:/r/sites/Megamedia-MFETechLab/Shared%20Documents/SolicitudesOnline"
   
    # Elimina referencias tipo 【n:m†source】
    text = re.sub(r'【\d+:\d+†source】', '', text)
 
    # Elimina todas las referencias tipo [n:m†source]
    text = re.sub(r'\[\d+\]', '', text)
 
    # Elimina espacios redundantes
    text = text.strip()
    tarifas=False
    # Agrega los documentos al final con hipervínculos generados automáticamente
    if documentos:
        text += "\n\nDocumentos referenciados:\n"
        for doc in documentos:
            # Si el documento es {canal}_tarifas.pdf, redirigir a tarifas_TV.xlsx
            if re.match(r'.+_tarifas\.txt$', doc):
                if tarifas==False:
                    tarifas=True
                    display_name = "tarifas_TV"
                    target_doc = "tarifas_TV.xlsx"
                else:
                    continue
            else:
                display_name = doc
                target_doc = display_name
           
            encoded_doc_name = urllib.parse.quote(target_doc)
            url = f"{onedrive_folder_url}/{encoded_doc_name}?web=1"
            text += f"\n- {display_name}: {url}"
 
    return text

async def chat_with_assistant(prompt):
    await client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )
    run = await client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=st.secrets["AZURE_ASSISTANT_ID"]
    )
    while True:
        run_status = await client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread_id,
            run_id=run.id
        )
        if run_status.status in ["completed", "failed", "cancelled", "requires_action"]:
            break
        time.sleep(1)
    if run_status.status == "requires_action":
        respuesta_total = ""
        tool_outputs = []

        for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
            func_name = tool_call.function.name
            args = eval(tool_call.function.arguments)

            if func_name == "CheckStatus":
                resultado = check_status()
                await client.beta.threads.runs.submit_tool_outputs(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id,
                    tool_outputs=[{"tool_call_id": tc.id, "output": str(resultado)} for tc in run_status.required_action.submit_tool_outputs.tool_calls]
                )
                return {"tipo": "solicitudes", "data": resultado}

            elif func_name == "CreateSolicitudWifi":
                tipo_red = args.get("tipo_red", "")
                observaciones = args.get("observaciones", "")
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                resultado = create_solicitud_wifi(tipo_red, observaciones, destinatarios_internos, destinatarios_externos)
                respuesta_total += resultado + "\n\n"
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": resultado
                })

            elif func_name == "CreateSolicitudOffice365":
                observaciones = args.get("observaciones", "")
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                resultado = create_solicitud_office_365(observaciones, destinatarios_internos, destinatarios_externos)
                respuesta_total += resultado + "\n\n"
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": resultado
                })

            elif func_name == "CreateSolicitudVPN":
                observaciones = args.get("observaciones", "")
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                resultado = create_solicitud_VPN(observaciones, destinatarios_internos, destinatarios_externos)
                respuesta_total += resultado + "\n\n"
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": resultado
                })

            elif func_name == "CreateSolicitudOfimatica":
                tipo_accesorio = args.get("tipo_accesorio", "")
                cc = args.get("cc", "")
                descripcion = args.get("descripcion", "")
                fecha_necesidad = args.get("fecha_necesidad", None)
                cantidad = args.get("cantidad", 1)
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                resultado = create_solicitud_ofimatica(tipo_accesorio, cc, descripcion, fecha_necesidad, cantidad, destinatarios_internos, destinatarios_externos)
                respuesta_total += resultado + "\n\n"
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": resultado
                })

            else:
                resultado = "⚠️ Función desconocida."
                respuesta_total += resultado + "\n\n"
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": resultado
                })

        # ✅ Enviar todos los tool_outputs a la vez
        await client.beta.threads.runs.submit_tool_outputs(
            thread_id=st.session_state.thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )

        return respuesta_total.strip()

    else:
        messages = await client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        print(str(messages.data[0].content[0]))
        message_content = messages.data[0].content[0].text.value
        annotations = messages.data[0].content[0].text.annotations
        print(annotations)


        # Obtener las referencias de la respuesta
        assistant_response=message_content
        lista_limpia=[]
        file_ids = [item.file_citation.file_id for item in annotations]
        lista_sin_duplicados = []
        for item in file_ids:
            if item not in lista_sin_duplicados:
                lista_sin_duplicados.append(item)
        if lista_sin_duplicados:
            for file_id in lista_sin_duplicados:
                try:
                    print(file_id)
                    cited_file = await client.files.retrieve(file_id=file_id)
                    if cited_file.filename not in lista_limpia:
                        lista_limpia.append(cited_file.filename)
                except:
                    cited_file="Archivo no encontrado"


        assistant_response=clean_response(assistant_response,lista_limpia)
        return assistant_response
        # for msg in messages.data:
        #     if msg.role == "assistant":
        #         return msg.content[0].text.value

# Interfaz chat
# Crea una cabecera con el logo alineado a la izquierda
col1, col2 = st.columns([1, 5])
with col1:
    st.image("m.png", width=100)

with col2:
    st.title("MediaSolve")
if "mensaje_inicial_mostrado" not in st.session_state:
    st.session_state.mensaje_inicial_mostrado = True
    #time.sleep(1)    
    st.session_state.messages.append({"role": "assistant", "content": "👋 ¡Hola! Soy Sete tu asistente corporativo de Mediaset ¿En que puedo ayudarte?"})

if prompt := st.chat_input("¿En qué puedo ayudarte?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    respuesta = asyncio.run(chat_with_assistant(prompt))
    st.session_state.messages.append({"role": "assistant", "content": respuesta})

# Renderizar historial
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        contenido = msg["content"]
        # Si es tipo dict y solicitudes, renderizamos expanders
        if isinstance(contenido, dict) and contenido.get("tipo") == "solicitudes":
            print(contenido)
            st.markdown("### Solicitudes en Proceso")
            for sol in contenido["data"]["en_proceso"]:
                #print(sol)
                with st.expander(f"Solicitud ID {sol['ID']} - Estado: {sol['Estado']} - Fecha: {sol['FechaAlta']}"):
                    st.markdown(f"**Autorizador:** {sol['Autorizador']}")
                    st.markdown(f"**Destinatarios:** {', '.join(sol['Destinatarios'])}")
                    st.markdown(f"**Observación:** {sol['ObservacionAutorizador'] or '_Ninguna_'}")
                    for detalle in sol["Detalles"]:
                        st.markdown(f"**Recurso:** {detalle['nombre']}")
                        for paso in detalle["pasos"]:
                            st.markdown(f"- {paso}")
            st.markdown("### Solicitudes Finalizadas")
            for sol in contenido["data"]["finalizadas"]:
                #print(sol)
                with st.expander(f"Solicitud ID {sol['ID']} - Estado: {sol['Estado']} - Fecha: {sol['FechaAlta']}"):
                    st.markdown(f"**Autorizador:** {sol['Autorizador']}")
                    st.markdown(f"**Destinatarios:** {', '.join(sol['Destinatarios'])}")
                    st.markdown(f"**Observación:** {sol['ObservacionAutorizador'] or '_Ninguna_'}")
                    for detalle in sol["Detalles"]:
                        st.markdown(f"**Recurso:** {detalle['nombre']}")
                        for paso in detalle["pasos"]:
                            st.markdown(f"- {paso}")
        else:
            st.markdown(contenido)