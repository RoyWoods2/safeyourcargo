# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Cliente,Ciudad, CertificadoTransporte, Factura, Cobranza, Usuario, LogActividad, obtener_siguiente_folio 
from .forms import *
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponse
from django.core.paginator import Paginator
from weasyprint import HTML
from django.template.loader import render_to_string
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import requests
from django.utils.formats import date_format
from num2words import num2words
from core.services.facturacion_cl import emitir_factura_exenta_cl, generar_txt_factura_exenta,generar_xml_factura_exenta
from core.services.unlocode_utils import get_ports_by_country,get_airports_by_country,pais_a_codigo # 🔹 IMPORTA AQUÍ
import logging
import tempfile
import io
import os
from django.core.mail import send_mail
from django.contrib.auth.decorators import user_passes_test, login_required
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model
import json
from django.db.models import Q, Count, Sum
from .utils import registrar_actividad, obtener_dolar_observado
from xml.etree.ElementTree import Element, SubElement, tostring


Usuario = get_user_model()

@login_required
def dashboard(request):
  

    user = request.user

    # Inicialización
    certificados_data = []
    certificados_clientes = []
    certificados_totales = []
    total_certificados_sum = 0
    total_prima_usd = Decimal('0.0')
    total_prima_clp = Decimal('0.0')
    total_clientes = 0
    ultimos_certificados = []

    # Obtener tipo de cambio actual (USD a CLP)
    resultado = obtener_dolar_observado("hans.arancibia@live.com", "Rhad19326366.")
    if "valor" in resultado:
        dolar = Decimal(resultado["valor"])
    else:
        dolar = Decimal('950.00')

    if user.is_superuser or user.rol == "Administrador":
        # Datos globales
        certificados_data = (
            Cliente.objects
            .annotate(total_certificados=Count('certificadotransporte'))
            .filter(total_certificados__gt=0)
            .order_by('-total_certificados')
        )
        certificados_clientes = [c.nombre for c in certificados_data]
        certificados_totales = [c.total_certificados for c in certificados_data]
        total_certificados_sum = sum(certificados_totales)

        # Total prima USD
        total_prima_usd = (
            CertificadoTransporte.objects
            .aggregate(total=Sum('tipo_mercancia__valor_prima'))['total'] or Decimal('0.0')
        )

        # Calcular prima total CLP
        total_prima_clp = total_prima_usd * dolar

        # Total clientes con certificados
        total_clientes = Cliente.objects.filter(certificadotransporte__isnull=False).distinct().count()

        # Últimos certificados emitidos
        ultimos_certificados = (
            CertificadoTransporte.objects
            .select_related('cliente', 'ruta', 'tipo_mercancia')
            .order_by('-id')[:5]
        )

    elif user.rol == "Revendedor":
        # Solo sus certificados
        propios_certificados = CertificadoTransporte.objects.filter(cliente=user.cliente)
        certificados_data = (
            Cliente.objects
            .filter(id=user.cliente.id)
            .annotate(total_certificados=Count('certificadotransporte'))
        )
        certificados_clientes = [user.cliente.nombre]
        certificados_totales = [propios_certificados.count()]
        total_certificados_sum = propios_certificados.count()

        # Total prima USD (solo sus certificados)
        total_prima_usd = (
            propios_certificados
            .aggregate(total=Sum('tipo_mercancia__valor_prima'))['total'] or Decimal('0.0')
        )
        total_prima_clp = total_prima_usd * dolar

    # Datos dinámicos para origen de países
    origen_data = (
        CertificadoTransporte.objects
        .values('ruta__pais_origen')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')
    )
    origen_paises = [item['ruta__pais_origen'] for item in origen_data]
    origen_cantidades = [item['cantidad'] for item in origen_data]

    # Redondear y eliminar comas innecesarias (al entero más cercano)
    total_prima_usd = total_prima_usd.quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
    total_prima_clp = total_prima_clp.quantize(Decimal('1.'), rounding=ROUND_HALF_UP)

    context = {
        'certificados_clientes': certificados_clientes,
        'certificados_totales': certificados_totales,
        'total_certificados_sum': total_certificados_sum,
        'total_prima_usd': total_prima_usd,
        'total_prima_clp': total_prima_clp,
        'total_clientes': total_clientes,
        'ultimos_certificados': ultimos_certificados,
        'origen_paises': origen_paises,
        'origen_cantidades': origen_cantidades,
    }
    return render(request, 'core/dashboard.html', context)




def home_redirect(request):
    return redirect('login')
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')  # O la vista que quieras mostrar al entrar
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, 'core/login.html')
@login_required
def lista_clientes(request):
    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    else:
        if request.user.rol == 'Administrador':
            # Clientes creados por él o por sus revendedores
            revendedores = Usuario.objects.filter(creado_por=request.user)
            clientes = Cliente.objects.filter(
                models.Q(creado_por=request.user) |
                models.Q(creado_por__in=revendedores)
            )
        else:
            # Solo los clientes que él mismo creó
            clientes = Cliente.objects.filter(creado_por=request.user)

    return render(request, 'core/clientes.html', {'clientes': clientes})

@login_required
def form_cliente(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponseBadRequest("Solo se acepta AJAX aquí")

    cliente_id = request.POST.get("cliente_id")
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        form = ClienteForm(request.POST, instance=cliente)
    else:
        form = ClienteForm(request.POST)

    if form.is_valid():
        cliente = form.save()
        # 🔥 Registrar actividad
        if cliente_id:
            registrar_actividad(request.user, f"Editó cliente: {cliente.nombre}")
        else:
            registrar_actividad(request.user, f"Creó cliente: {cliente.nombre}")
        return JsonResponse({'success': True})
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            # 🔥 Registrar actividad
            registrar_actividad(request.user, f"Editó cliente: {cliente.nombre}")
            return JsonResponse({
                'success': True,
                'cliente': {
                    'nombre': cliente.nombre,
                    'rut': cliente.rut,
                    'correo': cliente.correo,
                    'telefono': cliente.telefono,
                    'ciudad': cliente.ciudad,
                    'pais': cliente.pais,
                }
            })
        else:
            html = render(request, 'core/form_cliente.html', {'form': form}).content.decode()
            return JsonResponse({'success': False, 'html': html})
    else:
        form = ClienteForm(instance=cliente)
        return render(request, 'core/form_cliente.html', {'form': form})

@require_POST
@login_required
def eliminar_cliente(request, pk):
    try:
        cliente = Cliente.objects.get(pk=pk)
        nombre_cliente = cliente.nombre
        cliente.delete()
        # 🔥 Registrar actividad
        registrar_actividad(request.user, f"Eliminó cliente: {nombre_cliente}")
        return JsonResponse({'success': True})
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cliente no encontrado'}, status=404)

def obtener_ciudades(request):
    pais_id = request.GET.get('pais_id')
    ciudades = Ciudad.objects.filter(pais_id=pais_id).values('id', 'nombre')
    return JsonResponse(list(ciudades), safe=False)



@login_required
def lista_usuarios(request):
    if request.user.is_superuser:
        usuarios = Usuario.objects.filter(is_superuser=False).select_related('cliente')
        clientes = Cliente.objects.all()
    elif request.user.rol == "Administrador":
        # Ver los suyos y los de sus revendedores
        usuarios_subordinados = Usuario.objects.filter(cliente=request.user.cliente, rol="Revendedor")
        usuarios = Usuario.objects.filter(
            cliente__in=[request.user.cliente] + list(usuarios_subordinados.values_list('cliente', flat=True)),
            is_superuser=False
        ).select_related('cliente')
        clientes = Cliente.objects.filter(id__in=[request.user.cliente.id] + list(usuarios_subordinados.values_list('cliente', flat=True)))
    elif request.user.rol == "Revendedor":
        # 🔹 Solo ve usuarios que él creó
        usuarios = Usuario.objects.filter(cliente=request.user.cliente, is_superuser=False).select_related('cliente')
        clientes = Cliente.objects.filter(id=request.user.cliente.id)
    else:
        usuarios = Usuario.objects.none()
        clientes = Cliente.objects.none()

    rol_actual = "Superusuario" if request.user.is_superuser else request.user.rol

    return render(request, 'core/usuarios.html', {
        'usuarios': usuarios,
        'clientes': clientes,
        'rol_actual': rol_actual,
    })


@require_POST
@login_required
def form_usuario(request):
    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponseBadRequest("Solo se acepta AJAX aquí")

    usuario_id = request.POST.get("usuario_id")
    username = request.POST.get("username")
    password = request.POST.get("password")
    rol = request.POST.get("rol")
    cliente_id = request.POST.get("cliente")

    if usuario_id:
        usuario = get_object_or_404(Usuario, pk=usuario_id)
        usuario.username = username
        if password:
            usuario.set_password(password)
    else:
        usuario = Usuario(username=username)
        usuario.set_password(password or "123456")  # Contraseña por defecto

    # 🔹 Lógica de permisos y asignación de roles
    if request.user.is_superuser:
        usuario.rol = rol
    elif request.user.rol == "Administrador":
        usuario.rol = "Revendedor"
    elif request.user.rol == "Revendedor":
        usuario.rol = "Usuario"  # 🔥 El revendedor solo puede crear usuarios normales
    else:
        return JsonResponse({'success': False, 'error': 'No tienes permiso para crear usuarios.'}, status=403)

    usuario.is_active = True
    usuario.pendiente_aprobacion = False
    usuario.cliente_id = cliente_id
    usuario.save()
    
    return JsonResponse({'success': True})

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        cliente_id = request.POST.get('cliente')

        # Crear usuario pendiente de aprobación
        usuario = Usuario.objects.create_user(username=username, password=password, email=email)
        usuario.is_active = False
        usuario.pendiente_aprobacion = True
        usuario.save()

        usuario.rol = "Usuario"  # Rol básico por defecto
        usuario.cliente_id = cliente_id
        usuario.save()

        # Notificar a los superusuarios
        superusuarios = Usuario.objects.filter(is_superuser=True)
        for su in superusuarios:
            send_mail(
                "Nueva solicitud de cuenta",
                f"El usuario {username} ha solicitado una cuenta y espera tu aprobación.",
                settings.DEFAULT_FROM_EMAIL,
                [su.email]
            )

        return render(request, 'registro_exitoso.html')

    clientes = Cliente.objects.all()
    return render(request, 'register.html', {'clientes': clientes})

@user_passes_test(lambda u: u.is_superuser)
def aprobar_usuario(request, user_id):
    usuario = get_object_or_404(Usuario, id=user_id, pendiente_aprobacion=True)
    usuario.is_active = True
    usuario.pendiente_aprobacion = False
    usuario.save()
    registrar_actividad(request.user, f"Aprobó al usuario: {usuario.username}")
    send_mail(
        "Tu cuenta fue aprobada",
        f"Hola {usuario.username}, tu cuenta ha sido aprobada. ¡Ya puedes acceder!",
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email]
    )
    
    return JsonResponse({'success': True, 'mensaje': 'Usuario aprobado y notificado.'})


@login_required

@require_POST
def eliminar_usuario(request, pk):
    logger.info(f"Intentando eliminar usuario con ID {pk}")

    try:
        user = Usuario.objects.get(pk=pk)
        user.delete()
        logger.info(f"Usuario con ID {pk} eliminado correctamente.")
        return JsonResponse({'success': True})
    except User.DoesNotExist:
        logger.warning(f"Usuario con ID {pk} no encontrado.")
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado'})
    

@login_required
@require_POST
def toggle_estado_usuario(request, pk):
    try:
        user = Usuario.objects.get(pk=pk)
        user.is_active = not user.is_active
        user.save()
        estado = "activado" if user.is_active else "desactivado"
        registrar_actividad(request.user, f"Cambió estado de usuario: {user.username} a {estado}")

        
        return JsonResponse({
            'success': True,
            'estado': user.is_active,
        })
    except User.DoesNotExist:
        raise Http404("Usuario no encontrado")
    
@login_required
def crear_certificado(request):
    if request.method == 'POST':
        cert_form = CertificadoTransporteForm(request.POST)
        ruta_form = RutaForm(request.POST)
        metodo_form = MetodoEmbarqueForm(request.POST)
        mercancia_form = TipoMercanciaForm(request.POST)
        viaje_form = ViajeForm(request.POST)
        notas_form = NotasNumerosForm(request.POST)

        if all([
            cert_form.is_valid(),
            ruta_form.is_valid(),
            metodo_form.is_valid(),
            mercancia_form.is_valid(),
            viaje_form.is_valid(),
            notas_form.is_valid()
        ]):
            # Guardar relacionados
            ruta = ruta_form.save()
            metodo = metodo_form.save()
            mercancia = mercancia_form.save()
            viaje = viaje_form.save(commit=False)

            # Buscar países por sigla
            from core.models import Pais
            origen_pais = Pais.objects.filter(sigla__iexact=viaje.vuelo_origen_pais).first()
            destino_pais = Pais.objects.filter(sigla__iexact=viaje.vuelo_destino_pais).first()
            if origen_pais:
                viaje.vuelo_origen_pais = origen_pais.nombre
                viaje.vuelo_origen_pais_fk = origen_pais
            if destino_pais:
                viaje.vuelo_destino_pais = destino_pais.nombre
                viaje.vuelo_destino_pais_fk = destino_pais
            viaje.save()

            notas = notas_form.save()

            certificado = cert_form.save(commit=False)
            certificado.ruta = ruta
            certificado.metodo_embarque = metodo
            certificado.tipo_mercancia = mercancia
            certificado.viaje = viaje
            certificado.notas = notas
            certificado.save()

            registrar_actividad(request.user, f"Creó certificado: C-{certificado.id}")

            # Crear la factura automáticamente
            from decimal import Decimal
            from datetime import date
            import requests
            from core.services.facturacion_cl import emitir_factura_exenta_cl

            try:
                folio_disponible = obtener_siguiente_folio()
            except Exception as e:
                return JsonResponse({'success': False, 'error': f"❌ Error al obtener folio: {str(e)}"})

            factura, created = Factura.objects.get_or_create(
                certificado=certificado,
                defaults={
                    'numero': Factura.objects.count() + 1,
                    'folio_sii': folio_disponible,
                    'razon_social': certificado.cliente.nombre,
                    'rut': certificado.cliente.rut,
                    'direccion': certificado.cliente.direccion,
                    'comuna': certificado.cliente.region or 'Por definir',
                    'ciudad': certificado.cliente.ciudad,
                    'valor_usd': certificado.tipo_mercancia.valor_prima,
                    'fecha_emision': date.today()
                }
            )

            factura.valor_usd = certificado.tipo_mercancia.valor_prima

            resultado = obtener_dolar_observado("hans.arancibia@live.com", "Rhad19326366.")
            if "valor" in resultado:
                dolar = Decimal(resultado["valor"])
            else:
                dolar = Decimal('950.00')

            factura.tipo_cambio = dolar
            factura.valor_clp = factura.valor_usd * dolar
            factura.save()

            resultado_emision = emitir_factura_exenta_cl(factura)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'factura_emitida': True,
                    'resultado': resultado_emision
                })

            return redirect('crear_certificado')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': {
                    'cert_form': cert_form.errors,
                    'ruta_form': ruta_form.errors,
                    'metodo_form': metodo_form.errors,
                    'mercancia_form': mercancia_form.errors,
                    'viaje_form': viaje_form.errors,
                    'notas_form': notas_form.errors,
                }
            })

    # GET
    cert_form = CertificadoTransporteForm()
    ruta_form = RutaForm()
    metodo_form = MetodoEmbarqueForm()
    mercancia_form = TipoMercanciaForm()
    viaje_form = ViajeForm()
    notas_form = NotasNumerosForm()

    certificados_list = CertificadoTransporte.objects.select_related('cliente', 'notas').order_by('-id')
    paginator = Paginator(certificados_list, 10)
    certificados = paginator.get_page(request.GET.get('page'))

    context = {
        'cert_form': cert_form,
        'ruta_form': ruta_form,
        'metodo_form': metodo_form,
        'mercancia_form': mercancia_form,
        'viaje_form': viaje_form,
        'notas_form': notas_form,
        'certificados': certificados,
    }
    return render(request, 'certificados/crear_certificado.html', context)




@login_required
def clean_valor_prima(self):
    prima = self.cleaned_data.get('valor_prima')
    asegurado = (self.cleaned_data.get('valor_fca', 0) + self.cleaned_data.get('valor_flete', 0)) * 1.10
    minimo = max(asegurado * 0.0015, 20.0)

    if prima < minimo:
        raise forms.ValidationError(f"La prima debe ser al menos ${minimo:.2f}")
    return prima

@login_required
def certificado_pdf(request, pk):
    certificado = get_object_or_404(CertificadoTransporte, pk=pk)

    html_string = render_to_string('certificados/certificado_pdf.html', {
        'certificado': certificado,
    })

    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="certificado-C{certificado.id}.pdf"'
    return response

@login_required
def factura_pdf(request, pk):
    from decimal import Decimal
    from datetime import date
    import requests
    from num2words import num2words
    from django.utils.formats import date_format

    certificado = get_object_or_404(CertificadoTransporte, pk=pk)

    # Obtener o crear la factura usando el valor prima real de la mercancía (no recalculado)
    factura, created = Factura.objects.get_or_create(
        certificado=certificado,
        defaults={
            'numero': Factura.objects.count() + 1,
            'razon_social': certificado.cliente.nombre,
            'rut': certificado.cliente.rut,
            'direccion': certificado.cliente.direccion,
            'comuna': certificado.cliente.region or 'Por definir',
            'ciudad': certificado.cliente.ciudad,
            'valor_usd': certificado.tipo_mercancia.valor_prima,  # ✅ valor prima real
            'fecha_emision': date.today()
        }
    )
    factura.valor_usd = certificado.tipo_mercancia.valor_prima  # ✅ actualiza el valor prima real

    # Obtener tipo de cambio dinámico
    resultado = obtener_dolar_observado("hans.arancibia@live.com", "Rhad19326366.")
    if "valor" in resultado:
        dolar = Decimal(resultado["valor"])
    else:
        dolar = Decimal('950.00')


    # Calcular valor CLP
    factura.tipo_cambio = dolar
    factura.valor_clp = (factura.valor_usd or Decimal('0.0')) * dolar
    factura.save()

    # Calcular total en palabras
    total_palabras = num2words(int(factura.valor_clp), lang='es').replace("coma cero cero", "")

    # Formatear fecha
    fecha_formateada = date_format(factura.fecha_emision, "d \d\e F \d\e Y")

    # Renderizar el template a HTML
    html_string = render_to_string('certificados/factura_pdf.html', {
        'factura': factura,
        'total_palabras': total_palabras,
        'fecha_formateada': fecha_formateada,
    })

    # Convertir HTML a PDF
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf_file = html.write_pdf()

    # Devolver respuesta PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="factura-C{certificado.id}.pdf"'
    return response





@login_required
def factura_confirmacion(request, pk):
    factura = get_object_or_404(Factura, pk=pk)
    resultado = request.session.pop('factura_emitida_resultado', None)

    return render(request, 'certificados/factura_confirmacion.html', {
        'factura': factura,
        'resultado': resultado
    })


@login_required
def vista_cobranzas(request):
    cobranzas = Cobranza.objects.select_related('certificado', 'certificado__cliente', 'certificado__metodo_embarque').all()
    return render(request, 'core/cobranzas.html', {'cobranzas': cobranzas})


@login_required
def generar_pdf_cobranza(request, certificado_id):
    cobro = Cobranza.objects.select_related('certificado', 'certificado__cliente', 'certificado__metodo_embarque').get(certificado_id=certificado_id)

    # Ruta absoluta del logo para WeasyPrint
    logo_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', 'safe_logo.png')
    logo_fixed = logo_path.replace("\\", "/")
    html_string = render_to_string('core/pdf_cobranza.html', {
        'cobro': cobro,
        
        'logo_path': f'file:///{logo_fixed}',

    })

    pdf_file = io.BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(pdf_file)

    response = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=cobranza_C{cobro.certificado.id}.pdf'
    return response

def obtener_paises(request):
    response = requests.get("https://restcountries.com/v3.1/all")
    if response.ok:
        data = response.json()
        paises = sorted([{
            "nombre": c["name"]["common"],
            "codigo": c["cca2"],
            "bandera": c["flags"]["svg"]
        } for c in data], key=lambda x: x["nombre"])
        return JsonResponse({"paises": paises})
    return JsonResponse({"error": "No se pudieron obtener los países"}, status=500)


@csrf_exempt
def obtener_ciudades(request):
    if request.method == "POST":
        import json
        datos = json.loads(request.body)
        pais = datos.get("pais")

        # 👉 La API externa espera GET, no POST
        response = requests.get(
            f"https://countriesnow.space/api/v0.1/countries/cities/q?country={pais}"
        )

        if response.ok:
            data = response.json()
            return JsonResponse({"ciudades": data.get("data", [])})
        return JsonResponse({"error": "No se pudieron obtener las ciudades"}, status=500)
    
    return JsonResponse({"error": "Método no permitido"}, status=405)
@csrf_exempt
def obtener_aeropuertos(request):
    if request.method == "POST":
        try:
            datos = json.loads(request.body)
            pais = datos.get("pais")
            print(f"📡 Recibido país: {pais}")
            aeropuertos = get_airports_by_country(pais)
            print(f"✅ Aeropuertos encontrados: {len(aeropuertos)}")
            return JsonResponse({"aeropuertos": aeropuertos})
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Método no permitido"}, status=405)

def obtener_paises(request):
    response = requests.get("https://restcountries.com/v3.1/all")
    if response.ok:
        data = response.json()
        paises = sorted([{
            "nombre": c["name"]["common"],
            "codigo": c["cca2"],
            "bandera": c["flags"]["svg"]
        } for c in data], key=lambda x: x["nombre"])
        return JsonResponse({"paises": paises})
    return JsonResponse({"error": "No se pudieron obtener los países"}, status=500)


@csrf_exempt
def obtener_ciudades(request):
    if request.method == "POST":
        import json
        datos = json.loads(request.body)
        pais = datos.get("pais")

        # 👉 La API externa espera GET, no POST
        response = requests.get(
            f"https://countriesnow.space/api/v0.1/countries/cities/q?country={pais}"
        )

        if response.ok:
            data = response.json()
            return JsonResponse({"ciudades": data.get("data", [])})
        return JsonResponse({"error": "No se pudieron obtener las ciudades"}, status=500)
    
    return JsonResponse({"error": "Método no permitido"}, status=405)
@csrf_exempt
def obtener_aeropuertos(request):
    if request.method == "POST":
        try:
            datos = json.loads(request.body)
            pais = datos.get("pais")
            print(f"📡 Recibido país: {pais}")
            aeropuertos = get_airports_by_country(pais)
            print(f"✅ Aeropuertos encontrados: {len(aeropuertos)}")
            return JsonResponse({"aeropuertos": aeropuertos})
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Método no permitido"}, status=405)

@csrf_exempt
def obtener_unlocode(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            pais = data.get("pais")
            funcion = data.get("function", "1")

            if not pais:
                return JsonResponse({"error": "País no proporcionado"}, status=400)

            ubicaciones = get_ports_by_country(pais, funcion)
            return JsonResponse({"ubicaciones": ubicaciones})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método no permitido"}, status=405)



@login_required
def obtener_clientes_disponibles(request):
    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    elif request.user.rol == "Administrador":
        usuarios_subordinados = Usuario.objects.filter(cliente=request.user.cliente, rol="Revendedor")
        clientes_ids = [request.user.cliente.id] + list(usuarios_subordinados.values_list('cliente', flat=True))
        clientes = Cliente.objects.filter(id__in=clientes_ids)
    else:
        clientes = Cliente.objects.filter(id=request.user.cliente_id)

    data = [{'id': c.id, 'nombre': c.nombre} for c in clientes]
    return JsonResponse({'clientes': data})
@login_required
def obtener_datos_modal_usuario(request):
    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponseBadRequest("Solo se acepta AJAX aquí")

    # CLIENTES según el rol actual
    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    elif request.user.rol == "Administrador":
        usuarios_sub = Usuario.objects.filter(cliente=request.user.cliente, rol="Revendedor")
        clientes_ids = [request.user.cliente.id] + list(usuarios_sub.values_list('cliente', flat=True))
        clientes = Cliente.objects.filter(id__in=clientes_ids)
    else:
        clientes = Cliente.objects.filter(id=request.user.cliente_id)

    clientes_data = [{'id': c.id, 'nombre': c.nombre} for c in clientes]

    # ROLES permitidos
    if request.user.is_superuser:
        roles = ['Usuario', 'Administrador', 'Revendedor']
    else:
        roles = ['Revendedor']

    return JsonResponse({'clientes': clientes_data, 'roles': roles})


@login_required
def obtener_logs_actividad(request):
    # Filtra los logs según la jerarquía
    if request.user.is_superuser:
        logs = LogActividad.objects.all()
    elif request.user.rol == "Administrador":
        usuarios_sub = Usuario.objects.filter(creado_por=request.user)
        logs = LogActividad.objects.filter(
            usuario__in=[request.user] + list(usuarios_sub)
        )
    elif request.user.rol == "Revendedor":
        logs = LogActividad.objects.filter(usuario=request.user)
    else:
        logs = LogActividad.objects.none()

    logs_data = [{
        'usuario': log.usuario.username,
        'mensaje': log.mensaje,
        'fecha': log.fecha.strftime("%d-%m-%Y %H:%M")
    } for log in logs.order_by('-fecha')[:15]]

    return JsonResponse({'logs': logs_data})


@login_required
def probar_envio_factura(request):
    logs = []
    try:
        logs.append("🔍 Iniciando prueba de envío de factura...")

        # Usamos el último certificado creado para pruebas
        certificado = CertificadoTransporte.objects.select_related('cliente', 'ruta', 'tipo_mercancia').last()
        if not certificado:
            messages.error(request, "❌ No hay certificados disponibles para simular el envío.")
            return redirect('crear_certificado')

        logs.append(f"✅ Certificado seleccionado: C-{certificado.id}")

        # Crear o recuperar factura asociada
        factura, created = Factura.objects.get_or_create(
            certificado=certificado,
            defaults={
                'numero': Factura.objects.count() + 1,
                'razon_social': certificado.cliente.nombre,
                'rut': certificado.cliente.rut,
                'direccion': certificado.cliente.direccion,
                'comuna': certificado.cliente.region or 'Por definir',
                'ciudad': certificado.cliente.ciudad,
                'valor_usd': certificado.tipo_mercancia.valor_prima,
                'fecha_emision': date.today()
            }
        )

        # Reasignar valor prima por seguridad
        factura.valor_usd = certificado.tipo_mercancia.valor_prima

        # Obtener tipo de cambio actual
        resultado = obtener_dolar_observado("hans.arancibia@live.com", "Rhad19326366.")
        if "valor" in resultado:
            dolar = Decimal(resultado["valor"])
        else:
            dolar = Decimal('950.00')


        factura.tipo_cambio = dolar
        factura.valor_clp = (factura.valor_usd or Decimal('0.0')) * dolar
        factura.save()

        logs.append(f"📦 Factura generada (USD {factura.valor_usd} → CLP {factura.valor_clp})")

        # Enviar a facturacion.cl
        resultado = emitir_factura_exenta_cl(factura)
        if resultado.get('success'):
            logs.append("✅ ENVÍO EXITOSO a Facturacion.cl")
            logs.append(f"📨 Respuesta: {resultado['respuesta']}")
        else:
            logs.append("❌ ERROR en el envío a Facturacion.cl")
            logs.append(f"🧨 Detalle: {resultado.get('error')}")

    except Exception as ex:
        logs.append("❌ Excepción no controlada:")
        logs.append(str(ex))

    return render(request, 'certificados/prueba_envio_resultado.html', {'logs': logs})


@login_required
def probar_envio(request):
    try:
        factura = Factura.objects.select_related('certificado').order_by('-id').first()

        if not factura:
            return HttpResponse("No hay facturas disponibles para prueba.", status=404)

        contenido_xml = generar_xml_factura_exenta(factura)
        filename = f"factura_exenta_C{factura.certificado.id}.xml"

        response = HttpResponse(contenido_xml, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        return HttpResponse(f"❌ Error al generar archivo XML de prueba: {str(e)}", status=500)

    
    
def descargar_xml_dte(request):
    factura = Factura.objects.select_related('certificado', 'certificado__cliente', 'certificado__ruta').last()
    if not factura:
        return HttpResponse("No hay factura para generar XML", status=400)

    certificado = factura.certificado
    cliente = certificado.cliente

    # XML base
    root = Element("DTE", version="1.0")
    doc = SubElement(root, "Documento", ID="F1T34")

    encabezado = SubElement(doc, "Encabezado")
    id_doc = SubElement(encabezado, "IdDoc")
    SubElement(id_doc, "TipoDTE").text = "34"
    SubElement(id_doc, "Folio").text = "1"
    SubElement(id_doc, "FchEmis").text = factura.fecha_emision.strftime("%Y-%m-%d")

    emisor = SubElement(encabezado, "Emisor")
    SubElement(emisor, "RUTEmisor").text = "76000555-0"
    SubElement(emisor, "RznSoc").text = "Roberto Gomez"
    SubElement(emisor, "GiroEmis").text = "Importación"
    SubElement(emisor, "Acteco").text = "515009"
    SubElement(emisor, "DirOrigen").text = "Pedro de Valdivia 25"
    SubElement(emisor, "CmnaOrigen").text = "Providencia"
    SubElement(emisor, "CiudadOrigen").text = "SANTIAGO"

    receptor = SubElement(encabezado, "Receptor")
    SubElement(receptor, "RUTRecep").text = cliente.rut or "11111111-1"
    SubElement(receptor, "CdgIntRecep").text = "123123123"
    SubElement(receptor, "RznSocRecep").text = cliente.nombre or "CLIENTE"
    SubElement(receptor, "GiroRecep").text = "SERVICIO"
    SubElement(receptor, "DirRecep").text = cliente.direccion or "SIN DIRECCIÓN"
    SubElement(receptor, "CmnaRecep").text = cliente.region or "SANTIAGO"
    SubElement(receptor, "CiudadRecep").text = cliente.ciudad or "SANTIAGO"

    totales = SubElement(encabezado, "Totales")
    total_valor = int(factura.valor_clp or 0)
    SubElement(totales, "MntExe").text = str(total_valor)
    SubElement(totales, "MntTotal").text = str(total_valor)

    detalle = SubElement(doc, "Detalle")
    SubElement(detalle, "NroLinDet").text = "1"
    cdg_item = SubElement(detalle, "CdgItem")
    SubElement(cdg_item, "TpoCodigo").text = "INT1"
    SubElement(cdg_item, "VlrCodigo").text = "PE"
    SubElement(detalle, "IndExe").text = "1"
    SubElement(detalle, "NmbItem").text = "PRODUCTO EXENTO"
    SubElement(detalle, "QtyItem").text = "1"
    SubElement(detalle, "UnmdItem").text = "UN"
    SubElement(detalle, "PrcItem").text = str(total_valor)
    SubElement(detalle, "MontoItem").text = str(total_valor)

    xml_string = tostring(root, encoding="utf-8", method="xml")

    # Devolver XML como descarga
    response = HttpResponse(xml_string, content_type='application/xml')
    response['Content-Disposition'] = 'attachment; filename=DTE_factura_exenta.xml'
    return response