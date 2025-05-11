import csv

from django.contrib.gis.geos import Point
from django.core.management import BaseCommand

from inhp.models import CentreVaccination, DistrictSanitaire


class Command(BaseCommand):
    help = "Importe un fichier CSV contenant les centres de vaccination"

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help="Chemin du fichier CSV à importer")

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']

        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)

                for row in reader:
                    district_id = row.get('district_id')
                    try:
                        district = DistrictSanitaire.objects.get(id=district_id)
                    except DistrictSanitaire.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f"❌ District ID {district_id} introuvable, centre ignoré."))
                        continue

                    # Création du centre de vaccination
                    centre = CentreVaccination(
                        id=row.get('id'),
                        name=row.get('name'),
                        longitude=row.get('longitude'),
                        latitude=row.get('latitude'),
                        geom=Point(float(row.get('longitude')), float(row.get('latitude'))) if row.get(
                            'longitude') and row.get('latitude') else None,
                        adresse=row.get('addresse') if row.get('addresse') else '',
                        district=district,
                    )
                    centre.save()
                    self.stdout.write(self.style.SUCCESS(f"✅ Centre {centre.name} importé avec succès."))

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"❌ Fichier non trouvé : {csv_file_path}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur lors de l'importation : {str(e)}"))