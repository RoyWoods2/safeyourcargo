from django import template

register = template.Library()

@register.filter
def formato_rut(rut):
    if not rut or "-" not in rut:
        return rut
    cuerpo, dv = rut.split("-")
    cuerpo = cuerpo[::-1]
    grupos = [cuerpo[i:i+3] for i in range(0, len(cuerpo), 3)]
    cuerpo_formateado = ".".join(grupos)[::-1]
    return f"{cuerpo_formateado}-{dv.upper()}"
