import base64
from zeep import Client
from core.models import Factura
from zeep.helpers import serialize_object
import tempfile
import os
import sys

# Configuración de conexión a facturacion.cl
FACTURACION_WSDL = 'http://ws.facturacion.cl/WSDS/wsplano.asmx?wsdl'
FACTURACION_USUARIO = 'SAFEYOURCARGOSPA'
FACTURACION_RUT = '78087058-3'
FACTURACION_CLAVE = '818bb129c1'
FACTURACION_PUERTO = '0'

# ------------------------------------------
# 🧾 Generar archivo plano de BOLETA EXENTA (DTE 41)
# ------------------------------------------
def generar_txt_boleta_exenta(factura: Factura) -> str:
    certificado = factura.certificado
    cliente = certificado.cliente

    rut_emisor = "78087058-3"
    rut_receptor = cliente.rut or "11111111-1"
    nombre = cliente.nombre or "CLIENTE"
    direccion = cliente.direccion or "SIN DIRECCION"
    ciudad = cliente.ciudad or "SANTIAGO"
    comuna = cliente.region or "SANTIAGO"
    correo = "correo@cliente.cl"
    fecha = factura.fecha_emision.strftime("%Y-%m-%d")
    valor = int(factura.valor_clp)

    # Encabezado de la boleta
    encabezado = f"41;0;{fecha};3;0;;;;{rut_emisor};{rut_receptor};{nombre};PARTICULAR;{direccion};{ciudad};{comuna};{correo};"

    # Totales
    totales = f"0;{valor};0;{valor};0;0;0;0;"

    # Detalle (11 campos exactos)
    descripcion = f"Despacho {certificado.ruta.ciudad_destino or 'Destino'} - C-{certificado.id} - PRIMA USD ${factura.valor_usd}"
    detalle = f"1;Seguro de Carga;{descripcion};1;1;{valor};{valor};{valor};INT1;UN;;"

    # Armar el archivo plano final
    lineas = [
        "->Boleta<-",
        encabezado,
        "->BoletaTotales<-",
        totales,
        "->BoletaDetalle<-",
        detalle
    ]

    return "\r\n".join(lineas)


# ------------------------------------------
# 🚀 Emitir archivo TXT a facturacion.cl vía WebService
# ------------------------------------------
def emitir_boleta_facturacion_cl(factura: Factura) -> dict:
    try:
        txt_data = generar_txt_boleta_exenta(factura)

        # Guardar archivo temporalmente en el escritorio para verificación
        ruta_debug = os.path.join(os.path.expanduser("~"), "Desktop", "DEBUG_BOLETA.TXT")
        with open(ruta_debug, "w", encoding="latin-1", newline='\r\n') as f:
            f.write(txt_data)

        print(f"✅ Archivo de debug guardado en: {ruta_debug}")

        # Codificar archivo a base64
        with open(ruta_debug, 'rb') as f:
            encoded_file = base64.b64encode(f.read()).decode()

        # Construir login en base64
        login_info = {
            'Usuario': base64.b64encode(FACTURACION_USUARIO.encode()).decode(),
            'Rut': base64.b64encode(FACTURACION_RUT.encode()).decode(),
            'Clave': base64.b64encode(FACTURACION_CLAVE.encode()).decode(),
            'Puerto': base64.b64encode(FACTURACION_PUERTO.encode()).decode(),
            'IncluyeLink': "1"
        }

        # Enviar al WebService
        client = Client(FACTURACION_WSDL)
        response = client.service.Procesar(login=login_info, file=encoded_file, formato="1")

        # Mostrar resultados
        print("🧾 CONTENIDO DEL ARCHIVO DEBUG:", file=sys.stderr)
        print(txt_data, file=sys.stderr)
        print("-" * 40)
        print(txt_data)
        print("-" * 40)
        print("📦 XML devuelto por Facturacion.cl:")
        print(response)

        return {'success': True, 'respuesta': serialize_object(response)}

    except Exception as e:
        return {'success': False, 'error': str(e)}

# ------------------------------------------
# 🔗 Obtener el link oficial PDF desde Facturacion.cl
# ------------------------------------------
def obtener_link_pdf_boleta(folio: int, tipo_dte: int = 41) -> dict:
    try:
        client = Client(FACTURACION_WSDL)

        login_info = {
            'Usuario': base64.b64encode(FACTURACION_USUARIO.encode()).decode(),
            'Rut': base64.b64encode(FACTURACION_RUT.encode()).decode(),
            'Clave': base64.b64encode(FACTURACION_CLAVE.encode()).decode(),
            'Puerto': base64.b64encode(FACTURACION_PUERTO.encode()).decode()
        }

        response = client.service.ObtenerLink(
            login=login_info,
            tipoDte=str(tipo_dte),
            folio=str(folio)
        )

        if hasattr(response, 'Mensaje'):
            url_base64 = response.Mensaje
            url_decodificada = base64.b64decode(url_base64.encode()).decode()
            return {'success': True, 'url': url_decodificada}

        return {'success': False, 'error': 'No se encontró el campo Mensaje en la respuesta.'}

    except Exception as e:
        return {'success': False, 'error': str(e)}
