import os
import uuid
from django.core.mail import EmailMessage
from django.conf import settings

def enviar_certificado_y_factura(certificado, pdf_cert, pdf_fact, destinatarios_extra=None):
    """
    Recibe el certificado y los PDF en memoria, los guarda temporalmente,
    envía el correo a destinatarios fijos y opcionales, y limpia los archivos.
    """
    # Crear carpeta temporal
    temp_dir = os.path.join(settings.BASE_DIR, 'temp_pdfs')
    os.makedirs(temp_dir, exist_ok=True)

    # Crear archivos únicos
    uid = uuid.uuid4().hex[:6]
    cert_path = os.path.join(temp_dir, f'certificado_{certificado.id}_{uid}.pdf')
    fact_path = os.path.join(temp_dir, f'factura_{certificado.id}_{uid}.pdf')

    with open(cert_path, 'wb') as f:
        f.write(pdf_cert.getvalue())
    with open(fact_path, 'wb') as f:
        f.write(pdf_fact.getvalue())

    # Correos fijos
    correos_fijos = [
        "Contacto@safeyourcargo.com",
        "Finanzas@safeyourcargo.com",
        "Jgonzalez@safeyourcargo.com"
    ]

    # Agregar el correo del creador del certificado si existe
    if certificado.creado_por and certificado.creado_por.correo:
        correos_fijos.append(certificado.creado_por.correo)

    # Unir con destinatarios adicionales si hay
    destinatarios = list(set(correos_fijos + (destinatarios_extra or [])))

    # Crear y enviar email
    mensaje = EmailMessage(
        subject=f"📄 Certificado generado: C-{certificado.id}",
        body=f"Estimado/a,\n\nAdjunto se encuentran el certificado y la factura C-{certificado.id}.\n\nSaludos,\nSistema UniCloud",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios
    )
    mensaje.attach_file(cert_path)
    mensaje.attach_file(fact_path)

    try:
        mensaje.send(fail_silently=False)
        print(f"✅ Correo enviado a {destinatarios}")
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
    finally:
        try:
            os.remove(cert_path)
            os.remove(fact_path)
        except Exception as err:
            print(f"⚠️ No se pudo eliminar archivos temporales: {err}")
