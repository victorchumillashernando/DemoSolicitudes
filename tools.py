from datetime import datetime

def CheckStatus():
    solicitudes = [
        {"id": "SOL-001", "tipo": "WiFi", "estado": "Aprobada", "fecha": "2025-06-19"},
        {"id": "SOL-002", "tipo": "Ofimática", "estado": "Pendiente", "fecha": "2025-06-20"},
        {"id": "SOL-003", "tipo": "WiFi", "estado": "Rechazada", "fecha": "2025-06-18"},
    ]
    return solicitudes

def CreateSolicitudWifi(tipo_red, observaciones=None):
    return f"Solicitud de acceso a red WiFi tipo '{tipo_red}' creada con éxito. Observaciones: {observaciones or 'Ninguna'}"

def CreateSolicitudOfimatica(tipo_accesorio, cc, descripcion, fecha_necesidad, cantidad):
    fecha = datetime.strptime(fecha_necesidad, "%Y-%m-%d")
    return (f"Solicitud de ofimática recibida:\n"
            f"- Tipo: {tipo_accesorio}\n"
            f"- CC: {cc}\n"
            f"- Descripción: {descripcion}\n"
            f"- Fecha de necesidad: {fecha.strftime('%d/%m/%Y')}\n"
            f"- Cantidad: {cantidad}")
