from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import *
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'rol', 'cliente', 'is_active', 'is_staff', 'pendiente_aprobacion')
    list_filter = ('rol', 'is_active', 'is_staff', 'pendiente_aprobacion', 'cliente')
    search_fields = ('username', 'email', 'cliente__nombre')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información personal'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
        (_('Información adicional'), {'fields': ('rol', 'cliente', 'pendiente_aprobacion')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'rol', 'cliente', 'pendiente_aprobacion'),
        }),
    )
    
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'correo', 'telefono', 'ciudad', 'pais')
    search_fields = ('nombre', 'rut', 'correo')
    list_filter = ('pais', 'ciudad', 'tipo_cliente')

@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais')
    list_filter = ('pais',)
    search_fields = ('nombre',)



@admin.register(CertificadoTransporte)
class CertificadoTransporteAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_partida', 'fecha_llegada', 'poliza', 'compania')
    search_fields = ('cliente__nombre', 'notas__numero_factura')
    list_filter = ('fecha_partida', 'fecha_llegada', 'cliente')
    date_hierarchy = 'fecha_partida'


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ('pais_origen', 'ciudad_origen', 'pais_destino', 'ciudad_destino')


@admin.register(MetodoEmbarque)
class MetodoEmbarqueAdmin(admin.ModelAdmin):
    list_display = (
        'modo_transporte',
        'tipo_carga',
        'clausula',
        'get_embalaje_resumen',
    )

    def get_embalaje_resumen(self, obj):
        if obj.modo_transporte == "Aereo":
            return f"Aéreo: {obj.tipo_embalaje_aereo or '-'}"
        elif obj.modo_transporte == "Maritimo":
            if obj.embalaje_maritimo == "FCL":
                return f"Marítimo FCL: {obj.tipo_container_maritimo or '-'}"
            elif obj.embalaje_maritimo == "LCL":
                return f"Marítimo LCL: {obj.tipo_embalaje_lcl or '-'}"
        elif obj.modo_transporte == "TerrestreFerroviario":
            return f"Terrestre: {obj.tipo_embalaje_terrestre or '-'}"
        return "-"
    get_embalaje_resumen.short_description = "Tipo de Embalaje"



@admin.register(TipoMercancia)
class TipoMercanciaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'valor_fca', 'valor_flete')
    readonly_fields = ('monto_asegurado',)  # Si usas @property


@admin.register(Viaje)
class ViajeAdmin(admin.ModelAdmin):
    list_display = ('nombre_avion', 'numero_viaje', 'vuelo_origen_pais', 'vuelo_destino_pais')


@admin.register(NotasNumeros)
class NotasNumerosAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'numero_factura', 'guia_carga')
    
@admin.register(Cobranza)
class CobranzaAdmin(admin.ModelAdmin):
    list_display = (
        'certificado', 'valor_fca', 'valor_flete', 'monto_asegurado',
        'valor_prima_estimado', 'valor_prima_cobro', 'valor_prima_pago',
        'fecha_cobro', 'estado',
    )
    list_filter = ('estado', 'fecha_cobro')
    search_fields = ('certificado__id', 'certificado__cliente__nombre')
    
    

@admin.register(LogActividad)
class LogActividadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'mensaje', 'fecha')
    search_fields = ('usuario__username', 'mensaje')
    list_filter = ('usuario', 'fecha')