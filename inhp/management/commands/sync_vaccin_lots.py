import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import Json
from django.core.management.base import BaseCommand
from dateutil.parser import parse as date_parse
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Command(BaseCommand):
    help = "Synchronise les tables vaccins et lots entre les bases locales et distantes"

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

        TABLES = [
            {
                'local_table': 'vaccins',
                'remote_table': 'inhp_vaccin',
                'field_mapping': {
                    'id': 'id',
                    'name': 'nom',
                    'code_vaccin': 'code_vaccin',
                    'commentaire': 'commentaire',
                    'type_vaccin': 'type_vaccin',
                    'nbr_dose': 'doses_requises',
                    'maladie_id': 'maladie_id',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at'
                }
            },
            {
                'local_table': 'lots',
                'remote_table': 'inhp_lotvaccin',
                'field_mapping': {
                    'id': 'id',
                    'numero_lot': 'numero_lot',
                    'stock_initial': 'quantite_initiale',
                    'stock': 'quantite_disponible',
                    'date_expiration': 'date_expiration',
                    'vaccin_id': 'vaccin_id',
                    'centre_id': 'centre_id',
                    'recu': 'recu',
                    'is_for_all': 'is_for_all',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at'
                }
            }
        ]

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
            if isinstance(value, bool): return value
            return str(value).strip().lower() in ['1', 'true', 'vrai', 'oui']

        def reconnect():
            local = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote = psycopg2.connect(**REMOTE_DB_CONFIG)
            return local, remote, local.cursor(), remote.cursor()

        try:
            local, remote, local_cursor, remote_cursor = reconnect()

            for table_info in TABLES:
                local_table = table_info['local_table']
                remote_table = table_info['remote_table']
                field_mapping = table_info['field_mapping']

                local_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [local_table])
                local_columns = {row[0] for row in local_cursor.fetchall()}

                remote_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [remote_table])
                remote_columns = {row[0] for row in remote_cursor.fetchall()}

                columns_to_select = [lc for lc, rc in field_mapping.items() if lc in local_columns and rc in remote_columns]
                logger.info(f"Synchronisation de {local_table} → {remote_table} avec colonnes : {columns_to_select}")

                local_cursor.execute(f"SELECT {', '.join(columns_to_select)} FROM {local_table}")
                rows = []
                for raw_row in local_cursor.fetchall():
                    row_dict = dict(zip(columns_to_select, raw_row))
                    cleaned_row = []
                    for col in columns_to_select:
                        value = row_dict.get(col)
                        if 'date' in col and value:
                            value = clean_date(value)
                        if isinstance(value, str) and value.strip() == '':
                            value = None
                        if col in ['recu', 'is_for_all']:
                            value = clean_boolean(value)
                        cleaned_row.append(Json(value) if isinstance(value, (dict, list)) else value)
                    rows.append(cleaned_row)

                logger.info(f"🧾 {len(rows)} lignes à synchroniser pour {local_table}")

                if not rows:
                    continue

                remote_columns_str = ', '.join([field_mapping[col] for col in columns_to_select])
                placeholders = ', '.join(['%s'] * len(columns_to_select))
                update_clause = ', '.join([f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}" for col in columns_to_select if col != 'id'])

                batch_size = 50
                for i in tqdm(range(0, len(rows), batch_size), desc=f"🔁 Sync {local_table}"):
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
                        logger.info(f"✅ Lot {i}-{i + len(batch)} inséré dans {remote_table}")
                    except Exception as e:
                        remote.rollback()
                        logger.error(f"❌ Erreur lot {i}-{i + len(batch)} : {e}")

            logger.info("🎯 Synchronisation terminée")

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
