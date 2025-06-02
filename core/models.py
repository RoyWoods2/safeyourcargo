from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from datetime import date


class Usuario(AbstractUser):
    pendiente_aprobacion = models.BooleanField(default=False)
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='usuarios', null=True, blank=True)
    rol = models.CharField(max_length=50, choices=[
        ('Administrador', 'Administrador'),
        ('Usuario', 'Usuario'),
        ('Revendedor', 'Revendedor')
    ], default='Usuario')

    # ⚡️ Campo que indica quién creó este usuario
    creado_por = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='usuarios_creados')

    def __str__(self):
        return f"{self.username} - {self.rol}"

    
    
class Cliente(models.Model):
    TIPO_CLIENTE = [
        ('empresa', 'Empresa'),
        ('persona', 'Persona'),
    ]
    TIPO_ALCANCE = [
        ('minorista', 'Minorista'),
    ]

    tipo_cliente = models.CharField(max_length=10, choices=TIPO_CLIENTE, default='empresa')
    nombre = models.CharField(max_length=255, unique=True)
    rut = models.CharField(max_length=15, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20)
    direccion = models.TextField()
    pais = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)
    region = models.CharField(max_length=100)

    tasa = models.DecimalField(max_digits=10, decimal_places=3)
    valor_minimo = models.DecimalField(max_digits=10, decimal_places=3)

    tasa_congelada = models.DecimalField(max_digits=10, decimal_places=3)
    valor_minimo_congelado = models.DecimalField(max_digits=10, decimal_places=3)

    tramo_cobro = models.PositiveIntegerField()
    tipo_alcance = models.CharField(max_length=20, choices=TIPO_ALCANCE, default='minorista')
    creado_por = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name='clientes_creados')

    def __str__(self):
        return self.nombre
    
class Pais(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Ciudad(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE, related_name='ciudades')
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} ({self.pais.nombre})"


    
    
class CertificadoTransporte(models.Model):
    poliza = models.CharField(default="01930324AA", max_length=20)
    compania = models.CharField(default="SafeYourCargo", max_length=50)

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha_partida = models.DateField()
    fecha_llegada = models.DateField()

    # Relación uno a uno con otros modelos
    ruta = models.OneToOneField('Ruta', on_delete=models.CASCADE)
    metodo_embarque = models.OneToOneField('MetodoEmbarque', on_delete=models.CASCADE)
    tipo_mercancia = models.OneToOneField('TipoMercancia', on_delete=models.CASCADE)
    viaje = models.OneToOneField('Viaje', on_delete=models.CASCADE)
    notas = models.OneToOneField('NotasNumeros', on_delete=models.CASCADE)

    def calcular_valor_asegurado(self):
        return (self.tipo_mercancia.valor_fca + self.tipo_mercancia.valor_flete) * Decimal('1.10')

    def calcular_valor_prima(self):
        prima = self.calcular_valor_asegurado() * self.cliente.tasa
        return max(prima, 20.00)
    
    
    
class Ruta(models.Model):
    pais_origen = models.CharField(max_length=100)
    ciudad_origen = models.CharField(max_length=100)
    pais_destino = models.CharField(max_length=100)
    ciudad_destino = models.CharField(max_length=100)
    
class MetodoEmbarque(models.Model):
    MODO_CHOICES = [
        ('Aereo', 'Aéreo'),
        ('Maritimo', 'Marítimo'),
        ('TerrestreFerroviario', 'Terrestre y/o Ferroviario'),
        ('MarRojo', 'Marítimo vía Mar Rojo')
    ]
    TIPO_CARGA_CHOICES = [
        ('PolizaGeneral', 'Póliza para Carga General y/o Carga Seca'),
        ('PolizaCongelada', 'Póliza para Carga Congelada'),
    ]
    CLAUSULA_CHOICES = [('A', 'Tipo A'), ('C', 'Tipo C')]

    modo_transporte = models.CharField(max_length=50, choices=MODO_CHOICES)
    tipo_carga = models.CharField(max_length=50, choices=TIPO_CARGA_CHOICES)
    clausula = models.CharField(max_length=10, choices=CLAUSULA_CHOICES)

    # AÉREO
    tipo_embalaje_aereo = models.CharField(max_length=100, blank=True, null=True)
    otro_embalaje_aereo = models.CharField(max_length=100, blank=True, null=True)

    # MARÍTIMO
    embalaje_maritimo = models.CharField(max_length=10, choices=[('FCL', 'FCL'), ('LCL', 'LCL')], blank=True, null=True)
    tipo_container_maritimo = models.CharField(max_length=50, blank=True, null=True)
    tipo_embalaje_lcl = models.CharField(max_length=100, blank=True, null=True)
    otro_embalaje_lcl = models.CharField(max_length=100, blank=True, null=True)

    # TERRESTRE
    tipo_embalaje_terrestre = models.CharField(max_length=100, blank=True, null=True)
    otro_embalaje_terrestre = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.modo_transporte} - {self.tipo_carga}"

class TipoMercancia(models.Model):
    TIPO_CHOICES = [
        ('Maquinaria', 'Maquinaria y aparatos mecánicos, equipos electrónicos en FCL o LCL'),
        ('General', 'Mercancía General'),
        ('Aeronaves', 'Piezas de Aeronaves'),
        ('Hierro', 'Productos de hierro y acero'),
    ]

    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    valor_fca = models.DecimalField(max_digits=12, decimal_places=2)
    valor_flete = models.DecimalField(max_digits=12, decimal_places=2)
    valor_prima = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_asegurado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_prima = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def calcular_monto_asegurado(self):
        return (self.valor_fca + self.valor_flete) * Decimal("1.10")
    
    def save(self, *args, **kwargs):
        self.monto_asegurado = self.calcular_monto_asegurado()
        super().save(*args, **kwargs)

class Viaje(models.Model):
    nombre_avion = models.CharField(max_length=100)
    numero_viaje = models.CharField(max_length=100)
    vuelo_origen_pais = models.CharField(max_length=100)
    vuelo_origen_ciudad = models.CharField(max_length=100)
    aeropuerto_origen = models.CharField(max_length=100)
    vuelo_destino_pais = models.CharField(max_length=100)
    vuelo_destino_ciudad = models.CharField(max_length=100)
    aeropuerto_destino = models.CharField(max_length=100)
    descripcion_carga = models.TextField()

class NotasNumeros(models.Model):
    referencia = models.CharField(max_length=100)
    guia_carga = models.CharField(max_length=100)
    numero_factura = models.CharField(max_length=100)
    notas = models.TextField()


class Factura(models.Model):
    certificado = models.OneToOneField('CertificadoTransporte', on_delete=models.CASCADE, related_name='factura')
    numero = models.PositiveIntegerField(unique=True)
    fecha_emision = models.DateField(default=date.today)

    valor_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.0'))
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('950.0'))
    valor_clp = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.0'))

    razon_social = models.CharField(max_length=255)
    rut = models.CharField(max_length=20)
    direccion = models.CharField(max_length=255)
    comuna = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)

    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Factura N° {self.numero} - Certificado C-{self.certificado.id}"
    
class Cobranza(models.Model):
    certificado = models.OneToOneField('CertificadoTransporte', on_delete=models.CASCADE, related_name='cobranza')

    fecha_cobro = models.DateField(blank=True, null=True)
    valor_fca = models.DecimalField(max_digits=12, decimal_places=2)
    valor_flete = models.DecimalField(max_digits=12, decimal_places=2)
    monto_asegurado = models.DecimalField(max_digits=12, decimal_places=2)
    
    valor_prima_estimado = models.DecimalField(max_digits=12, decimal_places=2)
    valor_prima_cobro = models.DecimalField(max_digits=12, decimal_places=2)  # Lo que realmente se cobra
    valor_prima_pago = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    estado = models.CharField(max_length=20, choices=[
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
        ('vencido', 'Vencido'),
    ], default='pendiente')

    def calcular_monto_asegurado(self):
        return (self.valor_fca + self.valor_flete) * Decimal('1.10')

    def calcular_prima(self):
        tasa = self.certificado.cliente.tasa
        minimo = self.certificado.cliente.valor_minimo
        prima = self.monto_asegurado * tasa
        return max(prima, minimo)

    def save(self, *args, **kwargs):
        if not self.monto_asegurado:
            self.monto_asegurado = self.calcular_monto_asegurado()
        if not self.valor_prima_estimado:
            self.valor_prima_estimado = self.calcular_prima()
        if not self.valor_prima_cobro:
            self.valor_prima_cobro = self.valor_prima_estimado
        super().save(*args, **kwargs)
        
        
class LogActividad(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.mensaje} - {self.fecha}"
