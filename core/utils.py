# core/utils.py

from .models import LogActividad
import requests
def registrar_actividad(usuario, mensaje):
    LogActividad.objects.create(usuario=usuario, mensaje=mensaje)

def obtener_dolar_observado(usuario: str, contrasena: str):
    url = (
        f"https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx?"
        f"user={usuario}&pass={contrasena}&function=GetSeries&timeseries=F073.TCO.PRE.Z.D"
    )

    try:
        response = requests.get(url)
        data = response.json()
        obs = data["Series"]["Obs"]
        ultimo = obs[-1]
        valor_dolar = float(ultimo["value"])
        fecha = ultimo["indexDateString"]
        return {"valor": valor_dolar, "fecha": fecha}
    except Exception as e:
        return {"error": str(e)}