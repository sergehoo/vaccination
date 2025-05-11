import csv

from django.core.management import BaseCommand

from inhp.models import Maladie, Vaccin


class Command(BaseCommand):
    help = "Importe les vaccins depuis un fichier CSV."

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help="Chemin du fichier CSV des vaccins")

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']

        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Vérifier si la maladie existe, sinon la créer
                    maladie_nom = row.get('maladie', '').strip()
                    maladie, _ = Maladie.objects.get_or_create(nom=maladie_nom)

                    # Vérification et création/mise à jour du vaccin
                    vaccin, created = Vaccin.objects.update_or_create(
                        nom=row['nom'].strip(),
                        defaults={
                            'fabricant': row.get('fabricant', '').strip() or None,
                            'type_vaccin': row.get('type_vaccin', '').strip(),
                            'doses_requises': int(row.get('doses_requises', 1)),
                            'intervalle_doses': int(row.get('intervalle_doses', 0)) if row.get(
                                'intervalle_doses') else None,
                            'pays_origine': row.get('pays_origine', '').strip() or None,
                            'statut_approbation': row.get('statut_approbation', 'True').lower() in ['true', '1', 'yes'],
                            'maladie': maladie,
                        }
                    )

                    if created:
                        self.stdout.write(self.style.SUCCESS(f"✅ Vaccin {vaccin.nom} importé."))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"🔄 Vaccin {vaccin.nom} mis à jour."))
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"❌ Fichier non trouvé : {csv_file_path}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur lors de l'importation : {str(e)}"))
