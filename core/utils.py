# core/utils.py

from .models import LogActividad
import requests

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from weasyprint import HTML
from io import BytesIO
from core.models import LogActividad
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
    
    
    
def enviar_factura_y_certificado(factura):
    certificado = factura.certificado

    # 📁 Ruta absoluta al directorio base de tu proyecto (para imágenes y CSS en PDF)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_path = os.path.join(base_dir, 'static')

    # Renderizar templates
    html_cert = render_to_string('pdf/certificado_pdf.html', {'certificado': certificado})
    html_fact = render_to_string('pdf/factura_pdf.html', {'factura': factura})

    # Generar PDFs
    pdf_cert = BytesIO()
    HTML(string=html_cert, base_url=static_path).write_pdf(target=pdf_cert)
    pdf_cert.seek(0)

    pdf_fact = BytesIO()
    HTML(string=html_fact, base_url=static_path).write_pdf(target=pdf_fact)
    pdf_fact.seek(0)

    # Correos destino
    destinatarios = [
        "Jgonzalez@safeyourcargo.com",
        "Contacto@safeyourcargo.com",
        "Finanzas@safeyourcargo.com",
    ]
    if certificado.creado_por and certificado.creado_por.correo:
        destinatarios.append(certificado.creado_por.correo)

    asunto = f"📄 Documentos: Certificado #{certificado.id} y Factura"
    mensaje = f"""
    Estimado/a,

    Se adjuntan los documentos correspondientes al Certificado #{certificado.id}:

    - Certificado de Transporte
    - Factura Exenta Electrónica

    Saludos cordiales,
    SAFEYOURCARGO SPA
    """

    email = EmailMessage(
        subject=asunto,
        body=mensaje,
        from_email="no-reply@nautics.cl",
        to=destinatarios
    )
    email.attach('certificado.pdf', pdf_cert.read(), 'application/pdf')
    email.attach('factura.pdf', pdf_fact.read(), 'application/pdf')
    email.send()

    # Registrar en LogActividad
    if certificado.creado_por:
        LogActividad.objects.create(
            usuario=certificado.creado_por,
            accion=f"Se envió por correo el Certificado C-{certificado.id} y la Factura #{factura.numero}."
        )
    