from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CertificadoTransporte, Cobranza

@receiver(post_save, sender=CertificadoTransporte)
def crear_cobranza_automatica(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'cobranza'):
        Cobranza.objects.create(
            certificado=instance,
            valor_fca=instance.tipo_mercancia.valor_fca,
            valor_flete=instance.tipo_mercancia.valor_flete,
        )
