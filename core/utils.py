# core/utils.py

from .models import LogActividad

def registrar_actividad(usuario, mensaje):
    LogActividad.objects.create(usuario=usuario, mensaje=mensaje)
