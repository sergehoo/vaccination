import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import Json, execute_values
from dateutil.parser import parse as date_parse
from django.core.management import BaseCommand
from tqdm import tqdm
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronise la table des vaccinations entre les bases locales et distantes"

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

        local_table = 'vaccines2'
        remote_table = 'inhp_vaccination'

        field_mapping = {
            'id': 'id',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'deleted_at': 'deleted_at',
            'date_vacc': 'date_vaccination',
            'numero_dose': 'dose',
            'patient_id': 'patient_id',
            'vaccin_id': 'vaccin_id',
            'lot_id': 'lot_id',
            'centre_id': 'centre_id',
            'utilisateur_id': 'created_by_id',
        }

        def clean_date(value):
            try:
                if not value or 'BC' in str(value):
                    return datetime(1900, 1, 1)
                dt = date_parse(str(value).replace(' BC', ''))
                return dt if dt.year >= 1900 else datetime(1900, dt.month, dt.day)
            except Exception:
                return datetime(1900, 1, 1)

        def reconnect():
            try:
                local = psycopg2.connect(**LOCAL_DB_CONFIG)
                remote = psycopg2.connect(**REMOTE_DB_CONFIG)
                return local, remote, local.cursor(), remote.cursor()
            except Exception as e:
                logger.error(f"❌ Échec de connexion à la base : {e}")
                raise

        def is_connection_alive(conn):
            try:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                return True
            except Exception:
                return False

        try:
            local, remote, local_cursor, remote_cursor = reconnect()

            # Vérifie les colonnes valides
            local_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                                 [local_table])
            local_columns = {r[0] for r in local_cursor.fetchall()}
            remote_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                                  [remote_table])
            remote_columns = {r[0] for r in remote_cursor.fetchall()}

            columns_to_select = [lc for lc, rc in field_mapping.items() if lc in local_columns and rc in remote_columns]
            logger.info(f"Champs communs utilisés : {columns_to_select}")

            casted_cols = [f"CAST({col} AS TEXT) AS {col}" if col in ['created_at', 'updated_at', 'deleted_at',
                                                                      'date_vacc'] else col for col in
                           columns_to_select]
            local_cursor.execute(f"SELECT {', '.join(casted_cols)} FROM {local_table}")
            raw_rows = local_cursor.fetchall()

            rows = []
            for row in raw_rows:
                row_dict = dict(zip(columns_to_select, row))
                cleaned_row = []
                for col in columns_to_select:
                    val = row_dict.get(col)
                    if col in ['created_at', 'updated_at', 'deleted_at', 'date_vacc']:
                        val = clean_date(val)
                    if isinstance(val, str) and val.strip() == '':
                        val = None
                    cleaned_row.append(Json(val) if isinstance(val, (dict, list)) else val)
                rows.append(cleaned_row)

            logger.info(f"🧾 Total lignes à synchroniser : {len(rows)}")
            if not rows:
                return

            remote_columns_str = ', '.join([field_mapping[col] for col in columns_to_select])
            update_clause = ', '.join(
                [f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}" for col in columns_to_select if col != 'id'])

            insert_query = f"""
                INSERT INTO {remote_table} ({remote_columns_str})
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET {update_clause}
            """

            batch_size = 250
            for i in tqdm(range(0, len(rows), batch_size), desc="🔁 Sync vaccinations"):
                batch = rows[i:i + batch_size]
                retry_count = 0
                while retry_count < 3:
                    try:
                        if not is_connection_alive(remote):
                            logger.warning("🔌 Connexion perdue, reconnexion en cours...")
                            time.sleep(2 ** retry_count)
                            _, remote, _, remote_cursor = reconnect()

                        execute_values(remote_cursor, insert_query, batch)
                        remote.commit()
                        logger.info(f"✅ Lot {i}-{i + len(batch)} inséré")
                        break
                    except Exception as e:
                        retry_count += 1
                        remote.rollback()
                        logger.error(f"❌ Échec lot {i}-{i + len(batch)} : {e}")
                        if retry_count == 3:
                            logger.critical("🚫 Abandon après 3 tentatives.")
                            break
                        time.sleep(2 ** retry_count)

            logger.info("🎯 Synchronisation des vaccinations terminée avec succès.")

        except Exception as e:
            logger.error("❌ Erreur globale", exc_info=True)

        finally:
            for obj in ['local_cursor', 'remote_cursor', 'local', 'remote']:
                try:
                    if obj in locals() and locals()[obj]:
                        locals()[obj].close()
                except Exception as e:
                    logger.warning(f"⚠️ Erreur fermeture {obj} : {e}")
