from django.db.models.signals import pre_save
from django.dispatch import receiver
from dateutil.relativedelta import relativedelta

from inhp.models import Vaccination


@receiver(pre_save, sender=Vaccination)
def set_date_rappel(sender, instance, **kwargs):
    if instance.vaccin and instance.vaccin.besoin_rappel and instance.vaccin.duree_immunite:
        instance.date_rappel = instance.date_vaccination + relativedelta(months=instance.vaccin.duree_immunite)