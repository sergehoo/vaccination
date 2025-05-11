from django.contrib.auth.backends import BaseBackend

from inhp.models import Patient


class PatientAuthBackend(BaseBackend):
    def authenticate(self, request, code_patient=None, telephone=None):
        try:
            patient = Patient.objects.get(code_patient=code_patient, telephone1=telephone)
            if patient.is_active:
                return patient
        except Patient.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Patient.objects.get(pk=user_id)
        except Patient.DoesNotExist:
            return None