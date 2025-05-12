import logging
from datetime import datetime

import psycopg2
from django.core.management.base import BaseCommand
from django.apps import apps
from psycopg2._json import Json

# 🗄️ Connexions à la base locale et distante
LOCAL_DB_CONFIG = {
    'dbname': 'TRACEDB',
    'user': 'postgres',
    'password': 'weddingLIFE18',
    'host': 'localhost',
    'port': '5433',
}

REMOTE_DB_CONFIG = {
    'dbname': 'vaccination',
    'user': 'postgres',
    'password': 'weddingLIFE18',
    'host': '147.93.84.26',
    'port': '5434',
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

FIELD_MAP = {
    'Maladie': ['id', 'name', 'code_maladie', 'formulaire_model_id', 'formulaire_name', 'template_consultation_id', 'created_at', 'updated_at', 'deleted_at'],
    'Vaccin': ['id', 'name', 'code_vaccin', 'commentaire', 'type_vaccin', 'nbr_dose', 'maladie_id', 'created_at', 'updated_at', 'deleted_at'],
    'LotVaccin': ['id', 'created_at', 'updated_at', 'deleted_at', 'numero_lot', 'quantite_initiale', 'stock', 'date_expiration', 'vaccin_id', 'centre_id', 'recu', 'is_for_all'],
    'Consultation': ['id', 'created_at', 'updated_at', 'deleted_at', 'centre_id', 'code_patient', 'patient_id', 'consultation', 'utilisateur_id', 'maladie_id'],
    'Vaccination': ['id', 'created_at', 'updated_at', 'deleted_at', 'patient_id', 'centre_id', 'date_vaccination', 'vaccin_id', 'lot_id', 'dose', 'date_rappel', 'created_by_id'],
    'Mapi': ['id', 'created_at', 'updated_at', 'deleted_at', 'symptome', 'commentaire', 'date', 'patient_id', 'centre_id', 'accination_id', 'utilisateur_id'],
    'Message': ['id', 'created_at', 'updated_at', 'deleted_at', 'message', 'type', 'is_active', 'utilisateur_id'],
    'VaccineExt': ['id', 'created_at', 'updated_at', 'deleted_at', 'pays', 'ville', 'numero_dose', 'lot', 'patient_id', 'vaccin_id', 'date', 'utilisateur_id', 'code_patient'],
    'Equipement': ['id', 'created_at', 'updated_at', 'deleted_at', 'type', 'numero_serie', 'marque', 'centre_id', 'utilisateur_id'],
    'FactureCentral': ['id', 'created_at', 'updated_at', 'deleted_at', 'numero_facture', 'total', 'created_by_id', 'date_debut', 'date_fin'],
    'FactureDistrict': ['id', 'created_at', 'updated_at', 'deleted_at', 'numero_facture', 'total', 'bonus', 'created_by_id', 'date_debut', 'date_fin', 'district_id', 'ref', 'total_centre'],
    'FactureRegion': ['id', 'created_at', 'updated_at', 'deleted_at', 'numero_facture', 'total', 'created_by_id', 'date_debut', 'date_fin', 'region_id', 'total_centre'],
    'Facture': ['id', 'created_at', 'updated_at', 'deleted_at', 'numero_facture', 'nbre_vaccine', 'prix_unitaire', 'total', 'bonus', 'total_diabete_hyper_acc', 'nbre_vaccine_acc', 'centre_id', 'created_by_id', 'date_debut', 'date_fin', 'ref'],
    'FatureParametre': ['id', 'created_at', 'updated_at', 'deleted_at', 'prix_unitaire'],
    'FicheRetro': ['id', 'created_at', 'updated_at', 'deleted_at', 'nom', 'prenoms', 'date_naissance', 'sexe', 'situation_matrimoniale', 'nombre_enfant', 'nationnalite', 'type_piece', 'num_piece', 'telephone1', 'telephone2', 'commune', 'quatier', 'niveau_instruction', 'profession', 'consentement_parental', 'email', 'positif', 'positif_date', 'vaccin_autre', 'temperature', 'pathologies', 'date_debut_obs', 'date_fin_obs', 'mapi', 'date_mapi', 'region1_id', 'district1_id', 'aire1', 'centre1_id', 'date_vac1', 'vaccin1_id', 'numero_lot1', 'region2_id', 'district2_id', 'aire2', 'centre2_id', 'date_vac2', 'vaccin2_id', 'numero_lot2', 'region3_id', 'district3_id', 'aire3', 'centre3_id', 'date_vac3', 'vaccin3_id', 'numero_lot3', 'region4_id', 'district4_id', 'aire4', 'centre4_id', 'date_vac4', 'vaccin4_id', 'numero_lot4', 'utilisateur_id', 'is_valider', 'date', 'numero_civ', 'numero_unique'],
    'CallCenter': ['id', 'created_at', 'updated_at', 'deleted_at', 'telephone', 'disponible']
}

# Configuration du logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_errors.log'),
        logging.StreamHandler()
    ]
)


class DatabaseSync:
    """Classe encapsulant la logique de synchronisation"""

    def __init__(self, local_config, remote_config, model_table_map):
        self.local_config = local_config
        self.remote_config = remote_config
        self.model_table_map = model_table_map
        self.connections = {}
        self.cursors = {}

    def __enter__(self):
        """Établit les connexions aux bases de données"""
        try:
            self.connections['local'] = psycopg2.connect(**self.local_config)
            self.connections['remote'] = psycopg2.connect(**self.remote_config)
            self.cursors['local'] = self.connections['local'].cursor()
            self.cursors['remote'] = self.connections['remote'].cursor()
            return self
        except psycopg2.Error as e:
            logger.error(f"Erreur de connexion aux bases de données: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme proprement les connexions"""
        for cursor in self.cursors.values():
            if cursor:
                cursor.close()
        for conn in self.connections.values():
            if conn:
                conn.close()

    def get_common_fields(self, model, remote_table):
        """Retourne les champs communs entre modèle local et table distante"""
        model_fields = {f.name: f for f in model._meta.fields}

        # Récupère les colonnes de la table distante
        self.cursors['remote'].execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            [remote_table]
        )
        remote_columns = {row[0] for row in self.cursors['remote'].fetchall()}

        # Récupère les colonnes de la table locale
        self.cursors['local'].execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            [model._meta.db_table]
        )
        local_columns = {row[0] for row in self.cursors['local'].fetchall()}

        # Intersection des champs
        common_fields = sorted(remote_columns.intersection(local_columns))

        if not common_fields:
            logger.warning(f"Aucun champ commun entre {model._meta.db_table} et {remote_table}")
            return None

        # S'assure que 'id' est présent et en première position
        if 'id' in common_fields:
            common_fields.remove('id')
            common_fields.insert(0, 'id')

        return common_fields

    def sync_model(self, model_name, remote_table):
        """Synchronise un modèle spécifique"""
        logger.info(f"📤 Début synchronisation {model_name} → {remote_table}")

        try:
            model = apps.get_model('inhp', model_name)
            common_fields = self.get_common_fields(model, remote_table)

            if not common_fields:
                return 0

            # Construction des clauses SQL
            columns_str = ', '.join(common_fields)
            placeholders = ', '.join(['%s'] * len(common_fields))
            update_fields = [f for f in common_fields if f != 'id']
            update_clause = ', '.join([f"{f} = EXCLUDED.{f}" for f in update_fields])

            # Récupération des données locales
            self.cursors['local'].execute(f"SELECT {columns_str} FROM {model._meta.db_table}")
            rows = self.cursors['local'].fetchall()

            count = 0
            batch_size = 100  # Traitement par lots pour meilleures performances
            batch = []

            for row in rows:
                try:
                    # Nettoyage des données (conversion des dict/list en JSON)
                    cleaned_row = [Json(v) if isinstance(v, (dict, list)) else v for v in row]
                    batch.append(cleaned_row)

                    if len(batch) >= batch_size:
                        self._process_batch(remote_table, columns_str, placeholders, update_clause, batch)
                        count += len(batch)
                        batch = []

                except Exception as e:
                    self.connections['remote'].rollback()
                    logger.error(f"Erreur ligne ID {row[0]}: {e}", exc_info=True)

            # Traitement du dernier lot
            if batch:
                self._process_batch(remote_table, columns_str, placeholders, update_clause, batch)
                count += len(batch)

            self.connections['remote'].commit()
            logger.info(f"✅ {count} lignes transférées dans {remote_table}")
            return count

        except Exception as e:
            self.connections['remote'].rollback()
            logger.error(f"Erreur lors de la synchronisation de {remote_table}: {e}", exc_info=True)
            return 0

    def _process_batch(self, table, columns, placeholders, update_clause, batch):
        """Traitement par lot pour optimisation des performances"""
        query = f"""
            INSERT INTO {table} ({columns})
            VALUES {','.join([f'({placeholders})' for _ in batch])}
            ON CONFLICT (id) DO UPDATE SET {update_clause}
        """
        flattened_values = [item for sublist in batch for item in sublist]
        self.cursors['remote'].execute(query, flattened_values)


class Command(BaseCommand):
    help = "Transfère les données locales vers la base distante (INSERT/UPDATE uniquement)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Nom du modèle à synchroniser (optionnel)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Taille des lots pour le traitement (défaut: 100)'
        )

    def handle(self, *args, **options):
        # Configuration des bases de données
        LOCAL_DB_CONFIG = {
            'dbname': 'TRACEDB',
            'user': 'postgres',
            'password': 'weddingLIFE18',
            'host': 'localhost',
            'port': '5433',
        }

        REMOTE_DB_CONFIG = {
            'dbname': 'vaccination',
            'user': 'postgres',
            'password': 'weddingLIFE18',
            'host': '147.93.84.26',
            'port': '5434',
        }

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
            'CallCenter': 'call_centers'
        }

        selected_model = options.get('model')
        models_to_sync = (
            {selected_model: MODEL_TABLE_MAP[selected_model]} if selected_model
            else MODEL_TABLE_MAP
        )

        total_synced = 0
        start_time = datetime.now()

        with DatabaseSync(LOCAL_DB_CONFIG, REMOTE_DB_CONFIG, MODEL_TABLE_MAP) as sync:
            for model_name, remote_table in models_to_sync.items():
                try:
                    total_synced += sync.sync_model(model_name, remote_table)
                except Exception as e:
                    logger.error(f"Échec critique pour {model_name}: {e}", exc_info=True)

        duration = datetime.now() - start_time
        logger.info(
            f"\n🎉 Synchronisation terminée. "
            f"Total: {total_synced} enregistrements. "
            f"Durée: {duration.total_seconds():.2f} secondes."
        )
