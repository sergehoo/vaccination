import psycopg2
from django.core.management.base import BaseCommand
from django.apps import apps

# 🗄️ Connexions à la base locale et distante
LOCAL_DB_CONFIG = {
    'dbname': 'local_db_name',
    'user': 'local_user',
    'password': 'local_password',
    'host': 'localhost',
    'port': '5432',
}

REMOTE_DB_CONFIG = {
    'dbname': 'remote_db_name',
    'user': 'remote_user',
    'password': 'remote_password',
    'host': 'remote.host.com',
    'port': '5432',
}

# 🧭 Mapping des modèles Django vers les noms des tables SQL dans la base
MODEL_TABLE_MAP = {
    'TemplateConsultation': 'template_consultations',
    'Maladie': 'maladies',
    'Vaccin': 'vaccins',
    'LotVaccin': 'lots',
    'Consultation': 'consultations',
    'Vaccination': 'vaccinations',
    'Mapi': 'mapis',
    'Message': 'messages',
    'VaccineExt': 'vaccine_exts',
    'Equipement': 'equipements',
    'FactureCentral': 'facture_centrals',
    'FactureDistrict': 'facture_districts',
    'FactureRegion': 'facture_regions',
    'Facture': 'factures',
    'FatureParametre': 'fature_parametres',
    'FicheRetro': 'fiche_retros',
    'CallCenter': 'call_centers',
}


class Command(BaseCommand):
    help = "Transfère les données de la base locale vers la base distante (modèle par modèle)"

    def handle(self, *args, **kwargs):
        try:
            local_conn = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote_conn = psycopg2.connect(**REMOTE_DB_CONFIG)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erreur de connexion aux bases de données : {e}"))
            return

        local_cursor = local_conn.cursor()
        remote_cursor = remote_conn.cursor()

        for model_name, remote_table in MODEL_TABLE_MAP.items():
            model = apps.get_model('yourapp', model_name)
            model_fields = [f.name for f in model._meta.fields]
            columns_str = ', '.join(model_fields)
            placeholders = ', '.join(['%s'] * len(model_fields))
            update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in model_fields if f != 'id'])

            self.stdout.write(f"📤 Transfert `{model_name}` → `{remote_table}`")

            try:
                local_cursor.execute(f"SELECT {columns_str} FROM {model._meta.db_table}")
                rows = local_cursor.fetchall()

                count = 0
                for row in rows:
                    try:
                        remote_cursor.execute(
                            f"""
                            INSERT INTO {remote_table} ({columns_str})
                            VALUES ({placeholders})
                            ON CONFLICT (id) DO UPDATE SET {update_clause}
                            """,
                            row
                        )
                        count += 1
                    except Exception as e:
                        self.stderr.write(f"❌ Erreur ligne ID {row[0]}: {e}")

                remote_conn.commit()
                self.stdout.write(self.style.SUCCESS(f"✅ {count} lignes transférées dans {remote_table}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Erreur pour `{remote_table}` : {e}"))

        local_cursor.close()
        remote_cursor.close()
        local_conn.close()
        remote_conn.close()
        self.stdout.write(self.style.SUCCESS("🎉 Synchronisation complète terminée."))