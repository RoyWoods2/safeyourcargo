from django.test import TestCase
from core.models import Cliente, Factura, CertificadoTransporte, Ruta, MetodoEmbarque, TipoMercancia, Viaje, NotasNumeros, Usuario
from core.services.facturacion_cl import generar_xml_factura_exenta
from decimal import Decimal
from datetime import date
import re

class XMLFacturaTest(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre="Cliente Test XML",
            rut="12.345.678-9",
            direccion="Av. Nueva 123",
            ciudad="Valparaíso",
            region="Valparaíso",
            pais="Chile",
            tipo_cliente="empresa",
            tasa=Decimal("0.015"),
            valor_minimo=Decimal("20"),
            tasa_congelada=Decimal("0.012"),
            valor_minimo_congelado=Decimal("15"),
            tramo_cobro=100
        )

        self.ruta = Ruta.objects.create(
            pais_origen="Chile",
            ciudad_origen="Santiago",
            pais_destino="Perú",
            ciudad_destino="Lima"
        )
        self.metodo = MetodoEmbarque.objects.create(
            modo_transporte="Aereo",
            tipo_carga="PolizaGeneral",
            clausula="A"
        )
        self.mercancia = TipoMercancia.objects.create(
            tipo="General",
            valor_fca=1000,
            valor_flete=500,
            valor_prima=22
        )
        self.viaje = Viaje.objects.create(
            nombre_avion="LAN123",
            numero_viaje="123",
            vuelo_origen_pais="Chile",
            vuelo_origen_ciudad="Santiago",
            aeropuerto_origen="SCL",
            vuelo_destino_pais="Perú",
            vuelo_destino_ciudad="Lima",
            aeropuerto_destino="LIM",
            descripcion_carga="Cajas de prueba"
        )
        self.notas = NotasNumeros.objects.create(
            guia_carga="GC-123",
            numero_factura="12345",
            notas="Nota de prueba"
        )
        self.usuario = Usuario.objects.create_user(username="tester", password="123456")

        self.certificado = CertificadoTransporte.objects.create(
            cliente=self.cliente,
            fecha_partida=date.today(),
            fecha_llegada=date.today(),
            ruta=self.ruta,
            metodo_embarque=self.metodo,
            tipo_mercancia=self.mercancia,
            viaje=self.viaje,
            notas=self.notas,
            creado_por=self.usuario
        )

        self.factura = Factura.objects.create(
            certificado=self.certificado,
            numero=999,
            folio_sii=599,
            fecha_emision=date.today(),
            valor_usd=22,
            tipo_cambio=950,
            valor_clp=20900,
            razon_social=self.cliente.nombre,
            rut=self.cliente.rut,
            direccion=self.cliente.direccion,
            comuna=self.cliente.region,
            ciudad=self.cliente.ciudad,
        )

    def test_xml_receptor_dinamico(self):
        xml_str = generar_xml_factura_exenta(self.factura)

        self.assertIn("<RznSocRecep>Cliente Test XML</RznSocRecep>", xml_str)
        self.assertIn("<DirRecep>Av. Nueva 123</DirRecep>", xml_str)
        self.assertIn("<CmnaRecep>Valparaíso</CmnaRecep>", xml_str)
        self.assertIn("<CiudadRecep>Valparaíso</CiudadRecep>", xml_str)

        # Validar RUT limpio
        self.assertIn("<RUTRecep>12345678-9</RUTRecep>", xml_str)
        self.assertIn("<CdgIntRecep>123456789</CdgIntRecep>", xml_str)

        print("✅ XML generado correctamente con receptor dinámico.")
