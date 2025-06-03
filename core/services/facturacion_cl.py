import base64
import os
import re
import sys
from zeep import Client
from zeep.helpers import serialize_object
from core.models import Factura
from lxml import etree
# Configuración de conexión a facturacion.cl
FACTURACION_WSDL = 'http://ws.facturacion.cl/WSDS/wsplano.asmx?wsdl'
FACTURACION_USUARIO = 'SAFEYOURCARGOSPA'
FACTURACION_RUT = '78087058-3'
FACTURACION_CLAVE = '818bb129c1'
FACTURACION_PUERTO = '0'

# 🔧 Limpieza de RUT para cumplir formato requerido
def limpiar_rut(rut: str) -> str:
    """
    Elimina puntos y normaliza el formato del RUT chileno.
    Ejemplo: '78.087.058-3' => '78087058-3'
    """
    rut = rut.replace(".", "").replace(" ", "").upper()
    if "-" not in rut and len(rut) > 1:
        return f"{rut[:-1]}-{rut[-1]}"
    return rut

# ------------------------------------------
# 🧾 Generar archivo plano de FACTURA EXENTA (DTE 34)
# ------------------------------------------
def generar_txt_factura_exenta(factura: Factura) -> str:
    certificado = factura.certificado
    cliente = certificado.cliente

    # Datos del receptor
    rut_receptor = limpiar_rut(cliente.rut or "11111111-1")
    nombre = cliente.nombre or "CLIENTE"
    giro = "PARTICULAR"
    direccion = cliente.direccion or "SIN DIRECCION"
    comuna = cliente.region or "SANTIAGO"
    ciudad = cliente.ciudad or "SANTIAGO"
    correo = cliente.correo or "correo@cliente.cl"
    fecha = factura.fecha_emision.strftime("%Y-%m-%d")
    valor = int(factura.valor_clp)

    # ✅ ENCABEZADO
    encabezado = f"34;0;{fecha};0;0;{rut_receptor};{nombre};{giro};{direccion};{comuna};{ciudad};{correo};"

    # ✅ TOTALES
    totales = f"0;0;0;0;0;{valor};0;0;{valor};0;0;"

    # ✅ DETALLE
    descripcion = f"Despacho {certificado.ruta.ciudad_destino or 'Destino'} - C-{certificado.id}"
    desc_larga = f"Seguro de carga internacional - PRIMA USD ${factura.valor_usd}"
    detalle = f"1;SEG001;Seguro de Carga;1;{valor};0;0;0;0;{valor};0;INT1;UN;{desc_larga};"

    # ✅ FORMATO FINAL
    lineas = [
        "->Encabezado<-",
        encabezado,
        "->Totales<-", 
        totales,
        "->Detalle<-",
        detalle
    ]

    return "\r\n".join(lineas)

# ------------------------------------------
# 🚀 Enviar archivo a facturacion.cl vía WebService
# ------------------------------------------
def emitir_factura_exenta_cl(factura: Factura) -> dict:
    try:
        txt_data = generar_txt_factura_exenta(factura)

        # Guardar archivo temporal para debug
        ruta_debug = os.path.join(os.path.expanduser("~"), "Desktop", "DEBUG_FACTURA.TXT")
        with open(ruta_debug, "w", encoding="latin-1", newline='\r\n') as f:
            f.write(txt_data)

        print(f"✅ Archivo de debug guardado en: {ruta_debug}")

        # Codificar archivo en base64
        with open(ruta_debug, 'rb') as f:
            encoded_file = base64.b64encode(f.read()).decode()

        # Login codificado
        login_info = {
            'Usuario': base64.b64encode(FACTURACION_USUARIO.encode()).decode(),
            'Rut': base64.b64encode(FACTURACION_RUT.encode()).decode(),
            'Clave': base64.b64encode(FACTURACION_CLAVE.encode()).decode(),
            'Puerto': base64.b64encode(FACTURACION_PUERTO.encode()).decode(),
            'IncluyeLink': "1"
        }

        # Cliente SOAP
        client = Client(FACTURACION_WSDL)
        response = client.service.Procesar(login=login_info, file=encoded_file, formato="1")

        # Log completo
        print("🧾 CONTENIDO DEL ARCHIVO DEBUG:", file=sys.stderr)
        print(txt_data, file=sys.stderr)
        print("-" * 40)
        print("📦 XML devuelto por Facturacion.cl:")
        print(response)

        return {'success': True, 'respuesta': serialize_object(response)}

    except Exception as e:
        return {'success': False, 'error': str(e)}

# ------------------------------------------
# 🔗 Obtener el PDF oficial desde facturacion.cl
# ------------------------------------------
def obtener_link_pdf_boleta(folio: int, tipo_dte: int = 34) -> dict:
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
def normalizar_rut(rut: str) -> str:
    """
    Devuelve el RUT con guion y sin puntos. Ej: '60.905.000-K' -> '60905000-K'
    """
    rut = rut.replace(".", "").replace(" ", "").upper()
    if "-" not in rut and len(rut) > 1:
        return f"{rut[:-1]}-{rut[-1]}"
    return rut

def generar_xml_factura_exenta(factura: Factura) -> str:
    certificado = factura.certificado
    cliente = factura.certificado.cliente

    # RUT limpio y normalizado
    rut_limpio = "76000555-0"
    cdg_int = "760005550"

    root = etree.Element("DTE", version="1.0")
    documento = etree.SubElement(root, "Documento", ID="F1T34")

    # Encabezado
    encabezado = etree.SubElement(documento, "Encabezado")
    iddoc = etree.SubElement(encabezado, "IdDoc")
    etree.SubElement(iddoc, "TipoDTE").text = "34"
    etree.SubElement(iddoc, "Folio").text = str(factura.folio_sii)
    etree.SubElement(iddoc, "FchEmis").text = factura.fecha_emision.strftime("%Y-%m-%d")

    emisor = etree.SubElement(encabezado, "Emisor")
    etree.SubElement(emisor, "RUTEmisor").text = "78087058-3"
    etree.SubElement(emisor, "RznSoc").text = "SAFE YOUR CARGO"
    etree.SubElement(emisor, "GiroEmis").text = "Servicios Logísticos"
    etree.SubElement(emisor, "Acteco").text = "515009"
    etree.SubElement(emisor, "DirOrigen").text = "Pedro de Valdivia 25"
    etree.SubElement(emisor, "CmnaOrigen").text = "Providencia"
    etree.SubElement(emisor, "CiudadOrigen").text = "Santiago"

    receptor = etree.SubElement(encabezado, "Receptor")
    etree.SubElement(receptor, "RUTRecep").text = "78087058-3"
    etree.SubElement(receptor, "CdgIntRecep").text = "780870583"  # sin guión ni puntos
    etree.SubElement(receptor, "RznSocRecep").text = "supercliente"
    etree.SubElement(receptor, "GiroRecep").text = "PARTICULAR"
    etree.SubElement(receptor, "DirRecep").text = "Agustinas 1234"
    etree.SubElement(receptor, "CmnaRecep").text = "Santiago"
    etree.SubElement(receptor, "CiudadRecep").text = "Santiago"

    totales = etree.SubElement(encabezado, "Totales")
    etree.SubElement(totales, "MntExe").text = str(int(factura.valor_clp))
    etree.SubElement(totales, "MntTotal").text = str(int(factura.valor_clp))

    # Detalle
    detalle = etree.SubElement(documento, "Detalle")
    etree.SubElement(detalle, "NroLinDet").text = "1"
    cdgitem = etree.SubElement(detalle, "CdgItem")
    etree.SubElement(cdgitem, "TpoCodigo").text = "INT1"
    etree.SubElement(cdgitem, "VlrCodigo").text = "SEG001"
    etree.SubElement(detalle, "IndExe").text = "1"
    etree.SubElement(detalle, "NmbItem").text = "Seguro de Carga"
    etree.SubElement(detalle, "QtyItem").text = "1"
    etree.SubElement(detalle, "UnmdItem").text = "UN"
    etree.SubElement(detalle, "PrcItem").text = str(int(factura.valor_clp))
    etree.SubElement(detalle, "MontoItem").text = str(int(factura.valor_clp))

    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True).decode("utf-8")