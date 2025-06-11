import io
from weasyprint import HTML
from django.template.loader import render_to_string
from num2words import num2words
from django.utils.formats import date_format
from decimal import Decimal
from datetime import date
from .models import Factura
from .utils import obtener_dolar_observado


def generar_pdf_certificado(certificado, request):
    html_string = render_to_string('certificados/certificado_pdf.html', {
        'certificado': certificado,
    })
    pdf_buffer = io.BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer


def generar_pdf_factura(certificado, request):
    factura, _ = Factura.objects.get_or_create(
        certificado=certificado,
        defaults={
            'numero': Factura.objects.count() + 1,
            'razon_social': certificado.cliente.nombre,
            'rut': certificado.cliente.rut,
            'direccion': certificado.cliente.direccion,
            'comuna': certificado.cliente.region or 'Por definir',
            'ciudad': certificado.cliente.ciudad,
            'valor_usd': certificado.tipo_mercancia.valor_prima,
            'fecha_emision': certificado.fecha_partida or date.today(),
        }
    )

    factura.valor_usd = certificado.tipo_mercancia.valor_prima

    resultado = obtener_dolar_observado("hans.arancibia@live.com", "Rhad19326366.")
    dolar = Decimal(resultado.get("valor", '950.00'))
    factura.tipo_cambio = dolar
    factura.valor_clp = (factura.valor_usd or Decimal('0.0')) * dolar
    factura.save()

    total_palabras = num2words(int(factura.valor_clp), lang='es').replace("coma cero cero", "")
    fecha_formateada = date_format(factura.fecha_emision, "d \d\e F \d\e Y")

    html_string = render_to_string('certificados/factura_pdf.html', {
        'factura': factura,
        'total_palabras': total_palabras,
        'fecha_formateada': fecha_formateada,
    })

    pdf_buffer = io.BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer
