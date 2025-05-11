import csv
import re
from datetime import datetime

from django.core.management import BaseCommand

from inhp.models import CentreVaccination, Utilisateur, Patient


class Command(BaseCommand):
    help = "Importe les patients depuis un fichier CSV."

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help="Chemin du fichier CSV des patients")

    def is_valid_email(self, email):
        """ Vérifie si l'email est valide """
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return re.match(email_regex, email)

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']

        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    centre = None
                    centre_actuel = None
                    created_by = None

                    # Vérification et récupération du centre de vaccination
                    if row.get('centre_id'):
                        try:
                            centre = CentreVaccination.objects.get(id=int(row['centre_id']))
                        except (CentreVaccination.DoesNotExist, ValueError):
                            self.stdout.write(
                                self.style.WARNING(f"⚠️ Centre ID {row['centre_id']} invalide ou introuvable."))

                    # Vérification et récupération du centre actuel
                    if row.get('centre_actuel_id'):
                        try:
                            centre_actuel = CentreVaccination.objects.get(id=int(row['centre_actuel_id']))
                        except (CentreVaccination.DoesNotExist, ValueError):
                            self.stdout.write(self.style.WARNING(
                                f"⚠️ Centre Actuel ID {row['centre_actuel_id']} invalide ou introuvable."))

                    # Vérification et récupération du créateur de l'enregistrement
                    if row.get('utilisateur_id'):
                        try:
                            created_by = Utilisateur.objects.get(id=int(row['utilisateur_id']))
                        except (Utilisateur.DoesNotExist, ValueError):
                            self.stdout.write(self.style.WARNING(
                                f"⚠️ Utilisateur ID {row['utilisateur_id']} invalide ou introuvable."))

                    # Correction du format de la date de naissance
                    try:
                        date_naissance = row['date_naissance'].strip()
                        date_naissance = datetime.strptime(date_naissance.split()[0], "%Y-%m-%d").date()
                    except ValueError:
                        self.stdout.write(self.style.WARNING(
                            f"⚠️ Format de date incorrect pour {row['nom']} {row['prenoms']}, ignoré."))
                        continue

                    # Vérification et nettoyage de l'email
                    email = row.get('email', '').strip()
                    if email.lower() in ["aucun", "1", "0", "null", "none", "undefined"] or not self.is_valid_email(
                            email):
                        self.stdout.write(
                            self.style.WARNING(f"⚠️ Email invalide détecté ({email}), remplacé par NULL."))
                        email = None

                    # Vérification et nettoyage du numéro de pièce d'identité
                    num_piece = row.get('num_piece', '').strip()
                    if num_piece.lower() == "aucun" or not num_piece:
                        num_piece = None

                    # Vérification si un patient avec cet email existe déjà
                    patient = None
                    if email:
                        patient = Patient.objects.filter(email=email).first()

                    if not patient:
                        # Vérification si un patient existe déjà avec code_patient ou num_piece
                        patient = Patient.objects.filter(code_patient=row['code_patient']).first()
                        if not patient and num_piece:
                            patient = Patient.objects.filter(num_piece=num_piece).first()

                    if patient:
                        self.stdout.write(
                            self.style.WARNING(f"🔄 Mise à jour du patient {patient.nom} {patient.prenoms} existant."))
                        patient.email = email  # Mise à jour sécurisée de l'email
                        patient.save()
                    else:
                        patient = Patient.objects.create(
                            code_patient=row['code_patient'],
                            nom=row['nom'],
                            prenoms=row['prenoms'],
                            date_naissance=date_naissance,
                            sexe=row['sexe'],
                            email=email,
                            num_piece=num_piece,
                            centre=centre,
                            centre_actuel=centre_actuel,
                            created_by=created_by,
                        )
                        self.stdout.write(self.style.SUCCESS(f"✅ Patient {patient.nom} {patient.prenoms} importé."))
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"❌ Fichier non trouvé : {csv_file_path}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur lors de l'importation : {str(e)}"))





