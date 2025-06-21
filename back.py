import streamlit as st
import time
import asyncio
from openai import OpenAI
from openai import AzureOpenAI
import requests
import json
from requests.auth import HTTPBasicAuth
from datetime import datetime

client = AzureOpenAI(
    api_key=st.secrets["AZURE_OPENAI_KEY"],
    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"],
    api_version="2024-05-01-preview"
)

estados_solicitud = {
    1: "Pendiente de autorización",
    2: "Pendiente",
    3: "En progreso",
    4: "Rechazada",
    5: "Finalizada",
    6: "Cancelada"
}


# Inicializar estado
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

st.title("📡 Asistente de Solicitudes")

# Mostrar historial de mensajes
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

def formatear_fecha(fecha_str):
    try:
        fecha_obj = datetime.fromisoformat(fecha_str[:-1])  # Quitar el último carácter "Z" si lo hubiera
        return fecha_obj.strftime("%Y-%m-%d %Hh")  # Formato YYYY-MM-DD HHh
    except ValueError:
        return "Fecha inválida"

def generarToken(usuario):
    # URL a la que deseas hacer el POST
    url = "https://apisolicitudesonlinepre.cinconet.local/api/Auth/login"

    # Credenciales para BasicAuth
    username = usuario
    password = "tu_contraseña"

    # Realizar el POST con autenticación básica
    response = requests.post(url, auth=HTTPBasicAuth(username, password),verify=False)

    #print(response.content)
    response_json = response.json()
    # Analizar el contenido HTML
    validtoken = response_json.get("validToken")
    refreshtoken = response_json.get("refreshToken")
    return validtoken

def imprimir_solicitudes(lista, titulo, usuario,validToken):
    solicitudes_data = []
    
    if lista:
        for solicitud in lista:
            solicitud_id = solicitud.get("id", "N/A")
            estado_id = solicitud.get("estadoSolicitudId", "N/A")
            estado = estados_solicitud.get(estado_id, "Desconocido")

            autorizador = solicitud.get("autorizador", {})
            autorizador_nombre = autorizador.get("nombre", "N/A")
            autorizador_apellidos = autorizador.get("apellidos", "N/A")

            justificacion = solicitud.get("justificacion", "N/A")
            observaciones = solicitud.get("observaciones", "N/A")

            fecha_alta_raw = solicitud.get("fechaAlta", "N/A")
            fecha_alta = formatear_fecha(fecha_alta_raw) if fecha_alta_raw != "N/A" else "N/A"

            observacion_autorizador = solicitud.get("observacionAutorizador", "N/A")

            # Obtener destinatarios (si hay)
            destinatarios = solicitud.get("destinatarios", [])
            destinatarios_lista = [
                f"{dest.get('nombre', 'N/A')} {dest.get('apellidos', 'N/A')}" for dest in destinatarios
            ]
            url = f"https://apisolicitudesonlinepre.cinconet.local/api/Solicitud/Detalle/{solicitud_id}"
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'Authorization': f'Bearer {validToken}'
            }

            response2 = requests.get(url, headers=headers, verify=False)
            response2 = response2.json()
            nombres = []
            # Extraer el campo "nombre"
            for tarea in response2:
                nombres.append(tarea.get("nombre", "Nombre no encontrado"))

            resultado = []

            # Extraer los datos requeridos
            for tarea in response2:
                tarea_data = {
                    "Recurso": tarea.get('nombre', 'Nombre no encontrado'),
                    "Pasos": []
                }
                
                # Iterar sobre los pasos de cada tarea
                for paso in tarea.get('pasos', []):
                    paso_data = {
                        
                        paso.get("descripcion", "N/A"): paso.get("nombre", "N/A") + paso.get("apellidos", "N/A"),
                        
                        "Estado": estados_solicitud.get(paso.get("estadoId", "N/A"), "Desconocido")
                    }
                    tarea_data["Pasos"].append(paso_data)

                resultado.append(tarea_data)

            # Crear diccionario de la solicitud
            solicitud_data = {
                "ID": solicitud_id,
                "EstadoSolicitud": estado,
                "Recursos": nombres,
                "FechaAlta": fecha_alta,
                "Detalles": {
                    "Destinatarios": destinatarios_lista if destinatarios_lista else [usuario],
                    "Autorizador": f"{autorizador_nombre} {autorizador_apellidos}",
                    "ObservacionAutorizador": observacion_autorizador,
                    "Resultado": resultado
                }
            }
            solicitudes_data.append(solicitud_data)
    
    return solicitudes_data

async def chat_with_assistant(prompt):
    # Añadir el mensaje del usuario al hilo
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )

    # Crear la ejecución
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=st.secrets["AZURE_ASSISTANT_ID"]
    )

    # Esperar estado del run
    while True:
        run_status = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread_id,
            run_id=run.id
        )
        if run_status.status in ["completed", "failed", "cancelled", "requires_action"]:
            break
        time.sleep(1)

    # Si requiere herramientas
    if run_status.status == "requires_action":
        user="vchumillas@megamedia.es"
        tool_outputs = []
        for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
            func_name = tool_call.function.name
            args = eval(tool_call.function.arguments)

            if func_name == "CheckStatus":
                validToken=generarToken("vchumillas@megamedia.es")
                url = "https://apisolicitudesonlinepre.cinconet.local/api/Solicitud/Solicitadas"
                headers = {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Authorization': f'Bearer {validToken}'
                }

                response = requests.get(url, headers=headers, verify=False)
                #print(response.text)
                response=response.json()

                # Separar solicitudes en tres listas según su estado
                en_proceso = []
                finalizadas = []
                rechazadas_canceladas = []

                # Clasificar las solicitudes en las listas adecuadas
                for solicitud in response:
                    estado_id = solicitud.get("estadoSolicitudId", "N/A")
                    if estado_id in [1, 2, 3]:
                        en_proceso.append(solicitud)
                    elif estado_id == 5:
                        finalizadas.append(solicitud)
                    elif estado_id in [4, 6]:
                        rechazadas_canceladas.append(solicitud)
                solicitudes_json = {
                    "SolicitudesEnProceso": imprimir_solicitudes(en_proceso, "SOLICITUDES EN PROCESO", user,validToken),
                    "SolicitudesFinalizadas": imprimir_solicitudes(finalizadas, "SOLICITUDES FINALIZADAS", user,validToken),
                    "SolicitudesRechazadasOCanceladas": imprimir_solicitudes(rechazadas_canceladas, "SOLICITUDES RECHAZADAS O CANCELADAS", user,validToken)
                }
                json_output = json.dumps(solicitudes_json, indent=4)
                result=f"Este es el estado actual de tus solicitudes:\n\n{json_output}"
                
            elif func_name == "CreateSolicitudWifi":
                tipo_red = args.get("tipo_red")
                observaciones = args.get("observaciones", "")
                result = f"📶 Solicitud WiFi creada para red '{tipo_red}' con observaciones: '{observaciones}'."
            elif func_name == "CreateSolicitudOfimatica":
                result = (
                    f"🖥️ Solicitud de accesorio '{args.get('tipo_accesorio')}' para el CC {args.get('cc')}, "
                    f"descripción: {args.get('descripcion')}, fecha necesidad: {args.get('fecha_necesidad')}, "
                    f"cantidad: {args.get('cantidad')}."
                )
            else:
                result = "⚠️ Función desconocida."

            tool_outputs.append({
                "tool_call_id": tool_call.id,
                "output": result
            })

        # Enviar resultados al assistant
        submitted_run = client.beta.threads.runs.submit_tool_outputs(
            thread_id=st.session_state.thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )

        # Esperar a que termine
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread_id,
                run_id=submitted_run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)

    # Mostrar la respuesta del assistant
    messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
    for msg in messages.data:
        if msg.role == "assistant":
            response = msg.content[0].text.value
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            break


# Entrada del usuario
if prompt := st.chat_input("Escribe tu solicitud..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    asyncio.run(chat_with_assistant(prompt))
