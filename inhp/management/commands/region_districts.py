import csv

from django.core.management import BaseCommand

from inhp.models import HealthRegion, DistrictSanitaire


class Command(BaseCommand):
    help = "Importe les régions et districts sanitaires depuis des fichiers CSV."

    def add_arguments(self, parser):
        parser.add_argument('regions_csv', type=str, help="Chemin du fichier CSV des régions")
        parser.add_argument('districts_csv', type=str, help="Chemin du fichier CSV des districts")

    def handle(self, *args, **kwargs):
        regions_csv_path = kwargs['regions_csv']
        districts_csv_path = kwargs['districts_csv']

        # Importation des Régions
        try:
            with open(regions_csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    region, created = HealthRegion.objects.get_or_create(
                        id=row['id'],
                        defaults={'name': row['nom']}
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"✅ Région {region.name} importée."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur lors de l'importation des régions: {str(e)}"))

        # Importation des Districts
        try:
            with open(districts_csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        region = HealthRegion.objects.get(id=row['region_id'])
                        district, created = DistrictSanitaire.objects.get_or_create(
                            id=row['id'],
                            defaults={
                                'nom': row['nom'],
                                'region': region
                            }
                        )
                        if created:
                            self.stdout.write(self.style.SUCCESS(f"✅ District {district.nom} importé."))
                    except HealthRegion.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"⚠️ Région ID {row['region_id']} introuvable pour le district {row['nom']}, ignoré."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur lors de l'importation des districts: {str(e)}"))
