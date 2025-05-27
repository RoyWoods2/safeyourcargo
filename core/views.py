# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Cliente,Ciudad, CertificadoTransporte, Factura, Cobranza, Usuario  
from .forms import *
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponse
from django.core.paginator import Paginator
from weasyprint import HTML
from django.template.loader import render_to_string
from datetime import date
from decimal import Decimal
import requests
from django.utils.formats import date_format
from num2words import num2words
from core.services.facturacion_cl import emitir_boleta_facturacion_cl
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

logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

Usuario = get_user_model()

@login_required
def dashboard(request):
    certificados_data = (
        Cliente.objects
        .annotate(total_certificados=Count('certificadotransporte'))
        .filter(total_certificados__gt=0)
        .order_by('-total_certificados')
    )

    certificados_clientes = [c.nombre for c in certificados_data]
    certificados_totales = [c.total_certificados for c in certificados_data]
    total_certificados_sum = sum(certificados_totales)

    origen_paises = ['Chile', 'China', 'España']
    origen_cantidades = [1, 5, 2]

    context = {
        'certificados_clientes': certificados_clientes,
        'certificados_totales': certificados_totales,
        'total_certificados_sum': total_certificados_sum,  # SUMA EN LA VISTA
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
            return redirect('lista_usuarios')  # O la vista que quieras mostrar al entrar
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, 'core/login.html')
@login_required
def lista_clientes(request):
    clientes = Cliente.objects.all()
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
        form.save()
        return JsonResponse({'success': True})
    else:
        # Si deseas mostrar errores específicos, puedes devolverlos aquí
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
def eliminar_cliente(request, pk):
    try:
        cliente = Cliente.objects.get(pk=pk)
        cliente.delete()
        return JsonResponse({'success': True})
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cliente no encontrado'}, status=404)
def obtener_ciudades(request):
    pais_id = request.GET.get('pais_id')
    ciudades = Ciudad.objects.filter(pais_id=pais_id).values('id', 'nombre')
    return JsonResponse(list(ciudades), safe=False)



@login_required
def lista_usuarios(request):
    # Excluye superusuarios de la lista
    usuarios = Usuario.objects.filter(is_superuser=False).select_related('cliente')
    clientes = Cliente.objects.all()

    if request.user.is_authenticated:
        rol_actual = "Superusuario" if request.user.is_superuser else request.user.rol
    else:
        rol_actual = "Anónimo"

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
    rol = request.POST.get("role")
    cliente_id = request.POST.get("cliente")

    if usuario_id:
        usuario = get_object_or_404(Usuario, pk=usuario_id)
        usuario.username = username
        if password:
            usuario.set_password(password)
    else:
        usuario = Usuario(username=username)
        usuario.set_password(password or "123456")  # Contraseña por defecto

    if request.user.is_superuser:
        usuario.rol = rol
    elif hasattr(request.user, "rol") and request.user.rol == "Administrador":
        usuario.rol = "Revendedor"
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
            ruta = ruta_form.save()
            metodo = metodo_form.save()
            mercancia = mercancia_form.save()
            viaje = viaje_form.save()
            notas = notas_form.save()

            certificado = cert_form.save(commit=False)
            certificado.ruta = ruta
            certificado.metodo_embarque = metodo
            certificado.tipo_mercancia = mercancia
            certificado.viaje = viaje
            certificado.notas = notas
            certificado.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('crear_certificado')

        # Si hay errores y es AJAX
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

    # Método GET (carga de página inicial)
    cert_form = CertificadoTransporteForm()
    ruta_form = RutaForm()
    metodo_form = MetodoEmbarqueForm()
    mercancia_form = TipoMercanciaForm()
    viaje_form = ViajeForm()
    notas_form = NotasNumerosForm()

    certificados_list = CertificadoTransporte.objects.select_related(
        'cliente', 'notas'
    ).order_by('-id')

    paginator = Paginator(certificados_list, 10)
    page = request.GET.get('page')
    certificados = paginator.get_page(page)

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
    certificado = get_object_or_404(CertificadoTransporte, pk=pk)

    # Obtener o crear la factura
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

    # Obtener tipo de cambio
    try:
        response = requests.get("https://mindicador.cl/api/dolar")
        dolar = Decimal(str(response.json()['dolar']['valor']))
    except Exception:
        dolar = Decimal('950.00')

    # Calcular valor CLP
    factura.tipo_cambio = dolar
    factura.valor_clp = (factura.valor_usd or Decimal('0.0')) * dolar
    factura.save()

    # Emitir la BOLETA EXENTA a facturacion.cl
    resultado_emision = emitir_boleta_facturacion_cl(factura)

    # Mostrar el resultado en un HTML temporal (depuración)
    html = f"""
    <h1>Resultado de Emisión</h1>
    <pre>{resultado_emision}</pre>
    <p>✅ Revisa la carpeta Escritorio por el archivo <strong>DEBUG_BOLETA.TXT</strong> para ver el archivo plano enviado.</p>
    """
    return HttpResponse(html)




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

    html_string = render_to_string('core/pdf_cobranza.html', {
        'cobro': cobro,
        'logo_path': f'file:///{logo_path.replace("\\", "/")}',
    })

    pdf_file = io.BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(pdf_file)

    response = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=cobranza_C{cobro.certificado.id}.pdf'
    return response