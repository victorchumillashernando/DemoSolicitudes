import streamlit as st
import json

# JSON recibido (puedes cargarlo desde un archivo o API)
data_json = """
{
  "SolicitudesEnProceso": [
    {
      "ID": 41571,
      "EstadoSolicitud": "Pendiente de autorización",
      "Recursos": ["Photoshop "],
      "FechaAlta": "2025-03-06 15h",
      "Detalles": {
        "Destinatarios": ["CECILIA MANGISCH .", "VICTOR CHUMILLAS HERNANDO"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {"Recurso": "Photoshop ", "Pasos": []}
        ]
      }
    },
    {
      "ID": 41576,
      "EstadoSolicitud": "Pendiente de autorización",
      "Recursos": ["Photoshop "],
      "FechaAlta": "2025-03-09 17h",
      "Detalles": {
        "Destinatarios": ["CECILIA MANGISCH .", "VICTOR CHUMILLAS HERNANDO"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {"Recurso": "Photoshop ", "Pasos": []}
        ]
      }
    },
    {
      "ID": 41610,
      "EstadoSolicitud": "Pendiente de autorización",
      "Recursos": ["Photoshop ", "WIFI ", "Photoshop "],
      "FechaAlta": "2025-06-17 19h",
      "Detalles": {
        "Destinatarios": ["VICTOR CHUMILLAS HERNANDO"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {"Recurso": "Photoshop ", "Pasos": []},
          {"Recurso": "WIFI ", "Pasos": [{"Seguridad": "JOSE RAMONLUJAN VILLEGAS", "Estado": "Pendiente de autorización"}]},
          {"Recurso": "Photoshop ", "Pasos": []}
        ]
      }
    }
  ],
  "SolicitudesFinalizadas": [
    {
      "ID": 36135,
      "EstadoSolicitud": "Finalizada",
      "Recursos": [" Solicitud de usuario genérico SSO de AWS"],
      "FechaAlta": "2024-06-26 16h",
      "Detalles": {
        "Destinatarios": ["vchumillas@megamedia.es"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {
            "Recurso": " Solicitud de usuario genérico SSO de AWS",
            "Pasos": [
              {"Aprobador inicial": "FAUSTINORODRIGUEZ PEREIRA", "Estado": "Pendiente"},
              {"Seguridad": "RamonOrtiz Gonzalez", "Estado": "Pendiente"}
            ]
          }
        ]
      }
    },
    {
      "ID": 38078,
      "EstadoSolicitud": "Finalizada",
      "Recursos": [" Solicitud de usuario genérico SSO de AWS"],
      "FechaAlta": "2024-10-24 12h",
      "Detalles": {
        "Destinatarios": ["vchumillas@megamedia.es"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {
            "Recurso": " Solicitud de usuario genérico SSO de AWS",
            "Pasos": [
              {"Aprobador inicial": "FAUSTINORODRIGUEZ PEREIRA", "Estado": "Pendiente"},
              {"Seguridad": "RamonOrtiz Gonzalez", "Estado": "Pendiente"}
            ]
          }
        ]
      }
    },
    {
      "ID": 38237,
      "EstadoSolicitud": "Finalizada",
      "Recursos": ["Acceso grupo del Directorio Activo "],
      "FechaAlta": "2024-11-05 10h",
      "Detalles": {
        "Destinatarios": ["VICTOR CHUMILLAS HERNANDO"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {"Recurso": "Acceso grupo del Directorio Activo ", "Pasos": []}
        ]
      }
    },
    {
      "ID": 41217,
      "EstadoSolicitud": "Finalizada",
      "Recursos": ["Confluence"],
      "FechaAlta": "Fecha inválida",
      "Detalles": {
        "Destinatarios": ["vchumillas@megamedia.es"],
        "Autorizador": "JORGE IZCUE JIMENEZ",
        "ObservacionAutorizador": null,
        "Resultado": [
          {
            "Recurso": "Confluence",
            "Pasos": [
              {"Aprobador inicial": "MONTSERRATGORDON VERGARA", "Estado": "Pendiente"}
            ]
          }
        ]
      }
    }
  ]
}
"""

data = json.loads(data_json)

st.title("Estado de Solicitudes")

def mostrar_solicitud(solicitud):
    st.subheader(f"Solicitud ID: {solicitud['ID']}")
    st.write(f"**Estado:** {solicitud['EstadoSolicitud']}")
    st.write(f"**Fecha Alta:** {solicitud['FechaAlta']}")
    recursos_str = ", ".join([r.strip() for r in solicitud["Recursos"]])
    st.write(f"**Recursos:** {recursos_str}")
    
    detalles = solicitud.get("Detalles", {})
    destinatarios = detalles.get("Destinatarios", [])
    st.write("**Destinatarios:**")
    for d in destinatarios:
        st.write(f"- {d.strip()}")
        
    st.write(f"**Autorizador:** {detalles.get('Autorizador', 'N/A')}")
    
    observacion = detalles.get("ObservacionAutorizador")
    if observacion:
        st.write(f"**Observación del autorizador:** {observacion}")
    else:
        st.write("**Observación del autorizador:** _Ninguna_")
    
    resultados = detalles.get("Resultado", [])
    if resultados:
        st.write("**Resultado:**")
        for res in resultados:
            st.write(f"- Recurso: {res.get('Recurso','')}")
            pasos = res.get("Pasos", [])
            if pasos:
                for idx, paso in enumerate(pasos, start=1):
                    paso_str = ", ".join(f"{k}: {v}" for k, v in paso.items())
                    st.write(f"  - Paso {idx}: {paso_str}")
            else:
                st.write("  - Sin pasos")
    st.markdown("---")

st.header("Solicitudes en Proceso")
for sol in data.get("SolicitudesEnProceso", []):
    with st.expander(f"ID {sol['ID']} - {sol['EstadoSolicitud']}"):
        mostrar_solicitud(sol)

st.header("Solicitudes Finalizadas")
for sol in data.get("SolicitudesFinalizadas", []):
    with st.expander(f"ID {sol['ID']} - {sol['EstadoSolicitud']}"):
        mostrar_solicitud(sol)
