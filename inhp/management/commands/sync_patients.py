import logging
from datetime import date, datetime
import psycopg2
from psycopg2.extras import Json, DictCursor
from django.core.management.base import BaseCommand
from dateutil.parser import parse as date_parse
from tqdm import tqdm
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Command(BaseCommand):
    help = "Synchronise la table des patients entre les bases locales et distantes"

    def handle(self, *args, **options):
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

        local_table = 'patients'
        remote_table = 'inhp_patient'

        field_mapping = {
            'id': 'id',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'deleted_at': 'deleted_at',
            'code_patient': 'code_patient',
            'nom': 'nom',
            'prenoms': 'prenoms',
            'date_naissance': 'date_naissance',
            'sexe': 'sexe',
            'situation_matrimoniale': 'situation_matrimoniale',
            'nombre_enfant': 'nombre_enfant',
            'nationnalite': 'nationalite',
            'type_piece': 'type_piece',
            'num_piece': 'num_piece',
            'telephone1': 'telephone1',
            'telephone2': 'telephone2',
            'commune': 'commune',
            'quatier': 'quartier',
            'niveau_instruction': 'niveau_instruction',
            'profession': 'profession',
            'consentement_parental': 'consentement_parental',
            'statut': 'statut',
            'email': 'email',
            'password': 'password',
            'is_modify_password': 'is_active',
            'centre_id': 'centre_id',
            'centre_actuel_id': 'centre_actuel_id',
            'utilisateur_id': 'created_by_id',
        }
        BOOLEAN_FIELDS = ['is_superuser', 'is_staff', 'is_active', 'consentement_parental']

        def clean_date(value):
            try:
                if not value or 'BC' in str(value):
                    return datetime(1900, 1, 1)
                dt = date_parse(str(value).replace(' BC', ''))
                if dt.year < 1900:
                    return datetime(1900, dt.month, dt.day)
                return dt
            except Exception:
                return datetime(1900, 1, 1)

        def clean_boolean(value):
            if isinstance(value, bool):
                return value
            if value in [1, '1', 'true', 'True', 'vrai', 'Vrai', 'oui', 'Oui']:
                return True
            if value in [0, '0', 'false', 'False', 'faux', 'Faux', 'non', 'Non', '', None]:
                return False
            return False  # valeur par défaut prudente

        def reconnect():
            local = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote = psycopg2.connect(**REMOTE_DB_CONFIG)
            return local, remote, local.cursor(), remote.cursor()

        try:
            local, remote, local_cursor, remote_cursor = reconnect()

            # Colonnes disponibles
            local_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [local_table])
            local_columns = {row[0] for row in local_cursor.fetchall()}

            remote_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                                  [remote_table])
            remote_columns = {row[0] for row in remote_cursor.fetchall()}

            columns_to_select = [lc for lc, rc in field_mapping.items() if lc in local_columns and rc in remote_columns]
            logger.info(f"Champs communs utilisés : {columns_to_select}")

            # Lecture brute sans parsing
            local_cursor = local.cursor()  # classique (sans DictCursor)
            casted_cols = [
                f"CAST({col} AS TEXT) AS {col}" if col in ['date_naissance', 'created_at', 'updated_at',
                                                           'deleted_at'] else col
                for col in columns_to_select
            ]
            local_cursor.execute(f"SELECT {', '.join(casted_cols)} FROM {local_table}")

            col_indices = {desc[0]: i for i, desc in enumerate(local_cursor.description)}

            rows = []
            for raw_row in local_cursor.fetchall():
                row_dict = dict(zip(columns_to_select, raw_row))
                cleaned_row = []
                try:
                    for col in columns_to_select:
                        value = row_dict.get(col)
                        # Pour les colonnes uniques mais nullables : convertir '' en None
                        if col in ['num_piece', 'email', 'code_patient'] and value == '':
                            value = None

                        if col in ['date_naissance', 'created_at', 'updated_at', 'deleted_at']:
                            value = clean_date(value)
                        elif col in BOOLEAN_FIELDS:
                            value = clean_boolean(value)
                        cleaned_row.append(Json(value) if isinstance(value, (dict, list)) else value)
                    rows.append(cleaned_row)
                except Exception as e:
                    logger.warning(f"⛔ Ligne ignorée ID={raw_row[col_indices.get('id')]} : {e}")

            logger.info(f"🧾 Nombre total de lignes à synchroniser : {len(rows)}")
            if not rows:
                logger.info("Aucune donnée à synchroniser.")
                return

            remote_columns_str = ', '.join([field_mapping[col] for col in columns_to_select])
            placeholders = ', '.join(['%s'] * len(columns_to_select))
            update_clause = ', '.join([
                f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}"
                for col in columns_to_select if col != 'id'
            ])

            count = 0
            batch_size = 20
            logger.info(f"📤 Début du transfert de {local_table} vers {remote_table} par lots de {batch_size}...")

            for i in tqdm(range(0, len(rows), batch_size), desc="🔁 Synchronisation en cours"):
                batch = rows[i:i + batch_size]
                try:
                    query = f"""
                           INSERT INTO {remote_table} ({remote_columns_str})
                           VALUES {','.join(['(' + placeholders + ')'] * len(batch))}
                           ON CONFLICT (id) DO UPDATE SET {update_clause}
                       """
                    values = [item for sublist in batch for item in sublist]
                    remote_cursor.execute(query, values)
                    remote.commit()
                    count += len(batch)
                    logger.info(f"✅ Lot {i}-{i + len(batch)} transféré")
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    logger.warning("🔁 Reconnexion après coupure...")
                    local, remote, _, remote_cursor = reconnect()
                except Exception as e:
                    remote.rollback()
                    logger.error(f"❌ Échec lot {i}-{i + len(batch)} : {e}")

            logger.info(f"🎯 Fin : {count} patients synchronisés avec succès")

        except Exception as e:
            logger.error("❌ Erreur globale", exc_info=True)
        finally:
            try:
                if 'local_cursor' in locals(): local_cursor.close()
                if 'remote_cursor' in locals(): remote_cursor.close()
                if 'local' in locals(): local.close()
                if 'remote' in locals(): remote.close()
            except Exception as e:
                logger.warning(f"⚠️ Erreur à la fermeture : {e}")