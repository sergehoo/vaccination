import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from dateutil.parser import parse as date_parse
from tqdm import tqdm

# Logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOCAL_DB_CONFIG = {
    'dbname': 'ta_base_locale',
    'user': 'ton_user_local',
    'password': 'ton_pass_local',
    'host': 'localhost',
    'port': '5432',
}

REMOTE_DB_CONFIG = {
    'dbname': 'ta_base_distant',
    'user': 'ton_user_distant',
    'password': 'ton_pass_distant',
    'host': 'ip.serveur.distant',
    'port': '5432',
}

local_table = 'vaccine_exts'
remote_table = 'vaccine_exts'

field_mapping = {
    'id': 'id',
    'created_at': 'created_at',
    'updated_at': 'updated_at',
    'deleted_at': 'deleted_at',
    'pays': 'pays',
    'ville': 'ville',
    'numero_dose': 'numero_dose',
    'lot': 'lot',
    'patient_id': 'patient_id',
    'vaccin_id': 'vaccin_id',
    'date': 'date',
    'utilisateur_id': 'utilisateur_id',
    'code_patient': 'code_patient',
}

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

def reconnect():
    local = psycopg2.connect(**LOCAL_DB_CONFIG)
    remote = psycopg2.connect(**REMOTE_DB_CONFIG)
    return local, remote, local.cursor(), remote.cursor()

class Command:
    def handle(self, *args, **options):
        try:
            local, remote, local_cursor, remote_cursor = reconnect()

            local_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [local_table])
            local_columns = {row[0] for row in local_cursor.fetchall()}
            remote_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [remote_table])
            remote_columns = {row[0] for row in remote_cursor.fetchall()}

            columns_to_select = [lc for lc, rc in field_mapping.items() if lc in local_columns and rc in remote_columns]
            logger.info(f"Champs communs utilisés : {columns_to_select}")

            local_cursor.execute(f"SELECT {', '.join(columns_to_select)} FROM {local_table}")
            raw_rows = local_cursor.fetchall()

            rows = []
            for row in raw_rows:
                row_dict = dict(zip(columns_to_select, row))
                cleaned = []
                for col in columns_to_select:
                    val = row_dict[col]
                    if col in ['created_at', 'updated_at', 'deleted_at', 'date']:
                        val = clean_date(val)
                    if col in ['lot', 'code_patient'] and val == '':
                        val = None
                    cleaned.append(val)
                rows.append(cleaned)

            logger.info(f"🧾 {len(rows)} lignes à synchroniser")

            if not rows:
                return

            remote_columns_str = ', '.join([field_mapping[col] for col in columns_to_select])
            placeholders = ', '.join(['%s'] * len(columns_to_select))
            update_clause = ', '.join([
                f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}"
                for col in columns_to_select if col != 'id'
            ])

            query = f"""
                INSERT INTO {remote_table} ({remote_columns_str})
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET {update_clause}
            """

            batch_size = 500
            count = 0

            for i in tqdm(range(0, len(rows), batch_size), desc="🔁 Synchronisation vaccine_exts"):
                batch = rows[i:i + batch_size]
                try:
                    execute_values(remote_cursor, query, batch)
                    remote.commit()
                    count += len(batch)
                    logger.info(f"✅ Lot {i}-{i + len(batch)} transféré")
                except Exception as e:
                    remote.rollback()
                    logger.error(f"❌ Échec lot {i}-{i + len(batch)} : {e}")

            logger.info(f"🎯 Fin : {count} vaccine_exts synchronisés")

        except Exception as e:
            logger.error("❌ Erreur globale", exc_info=True)
        finally:
            for conn in ['local_cursor', 'remote_cursor', 'local', 'remote']:
                try:
                    if conn in locals() and locals()[conn]:
                        locals()[conn].close()
                except Exception as e:
                    logger.warning(f"⚠️ Erreur fermeture {conn} : {e}")