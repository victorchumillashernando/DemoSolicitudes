import streamlit as st
import asyncio
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import openai
import time
import json
import re

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
        return {"error": "No se encontró el usuario principal"}

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
        return {"error": "No se encontró el usuario principal"}

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
        f"- ID de solicitud: {solicitud_id}"
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
            f"- ID de solicitud: {solicitud_id}"
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
        f"- ID de solicitud: {solicitud_id}"
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
            f"- ID de solicitud: {solicitud_id}"
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
                # Devolver tipo especial para renderizar expanders
                return {"tipo": "solicitudes", "data": resultado}
            elif func_name == "CreateSolicitudWifi":
                tipo_red = args.get("tipo_red", "")
                observaciones = args.get("observaciones", "")
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                print(tipo_red)
                resultado = create_solicitud_wifi(tipo_red,observaciones,destinatarios_internos,destinatarios_externos)
                await client.beta.threads.runs.submit_tool_outputs(
                        thread_id=st.session_state.thread_id,
                        run_id=run.id,
                        tool_outputs=[{
                            "tool_call_id": tool_call.id,
                            "output": resultado
                        }]
                )
            elif func_name == "CreateSolicitudOffice365":
                observaciones = args.get("observaciones", "")
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                resultado = create_solicitud_office_365(observaciones,destinatarios_internos,destinatarios_externos)
                await client.beta.threads.runs.submit_tool_outputs(
                        thread_id=st.session_state.thread_id,
                        run_id=run.id,
                        tool_outputs=[{
                            "tool_call_id": tool_call.id,
                            "output": resultado
                        }]
                )
            elif func_name == "CreateSolicitudVPN":
                observaciones = args.get("observaciones", "")
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                resultado = create_solicitud_VPN(observaciones,destinatarios_internos,destinatarios_externos)
                await client.beta.threads.runs.submit_tool_outputs(
                        thread_id=st.session_state.thread_id,
                        run_id=run.id,
                        tool_outputs=[{
                            "tool_call_id": tool_call.id,
                            "output": resultado
                        }]
                )
            elif func_name == "CreateSolicitudOfimatica":
                tipo_accesorio = args.get("tipo_accesorio", "")
                cc = args.get("cc", "")
                descripcion = args.get("descripcion", "")
                fecha_necesidad = args.get("fecha_necesidad", None)
                cantidad = args.get("cantidad", 1)
                destinatarios_internos = args.get("destinatarios_internos", "")
                destinatarios_externos = args.get("destinatarios_externos", "")
                print(tipo_accesorio, cc, descripcion, fecha_necesidad, cantidad)
                resultado = create_solicitud_ofimatica(tipo_accesorio, cc, descripcion, fecha_necesidad, cantidad,destinatarios_internos,destinatarios_externos)
                await client.beta.threads.runs.submit_tool_outputs(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id,
                    tool_outputs=[{
                        "tool_call_id": tool_call.id,
                        "output": resultado
                    }]
                )
            else:
                resultado = "⚠️ Función desconocida."
            respuesta_total += resultado + "\n\n"
        
        return respuesta_total.strip()
    else:
        messages = await client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        for msg in messages.data:
            if msg.role == "assistant":
                return msg.content[0].text.value

# Interfaz chat
# Crea una cabecera con el logo alineado a la izquierda
col1, col2 = st.columns([1, 5])
with col1:
    st.image("m.png", width=100)

with col2:
    st.title("Asistente Solicitudes Online")
if "mensaje_inicial_mostrado" not in st.session_state:
    st.session_state.mensaje_inicial_mostrado = True
    time.sleep(1)    
    st.session_state.messages.append({"role": "assistant", "content": "👋 ¡Hola! Soy tu asistente de Solicitudes Online ¿En que puedo ayudarte?"})

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