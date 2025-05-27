from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('clientes/', views.lista_clientes, name='clientes'),
    path('clientes/form/', views.form_cliente, name='form_cliente'),
    path('clientes/<int:pk>/editar/', views.editar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),
    path('ajax/ciudades/', views.obtener_ciudades, name='ajax_ciudades'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/form/', views.form_usuario, name='form_usuario'),
    path('usuarios/eliminar/<int:pk>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('usuarios/toggle-estado/<int:pk>/', views.toggle_estado_usuario, name='toggle_estado_usuario'),
    path('certificados/', views.crear_certificado, name='crear_certificado'),
    path('certificados/<int:pk>/pdf/', views.certificado_pdf, name='certificado_pdf'),
    path('certificados/<int:pk>/factura/', views.factura_pdf, name='factura_pdf'),
    path('certificados/<int:pk>/factura/confirmacion/', views.factura_confirmacion, name='factura_confirmacion'),
    path('cobranzas/', views.vista_cobranzas, name='vista_cobranzas'),
    path('cobranzas/pdf/<int:certificado_id>/', views.generar_pdf_cobranza, name='generar_pdf_cobranza'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
]
