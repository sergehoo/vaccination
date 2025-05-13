import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOCAL_DB_CONFIG = {
    'dbname': 'localdb',
    'user': 'user',
    'password': 'pass',
    'host': 'localhost',
    'port': '5432',
}

REMOTE_DB_CONFIG = {
    'dbname': 'remotedb',
    'user': 'user',
    'password': 'pass',
    'host': 'remote.host',
    'port': '5432',
}

field_mapping = {
    'id': 'id',
    'created_at': 'created_at',
    'updated_at': 'updated_at',
    'deleted_at': 'deleted_at',
    'centre_id': 'centre_id',
    'code_patient': 'code_patient',
    'patient_id': 'patient_id',
    'consultation': 'consultation',
    'utilisateur_id': 'utilisateur_id',
    'maladie_id': 'maladie_id',
}

local_table = 'consultations'
remote_table = 'inhp_consultation'

def clean_date(value):
    try:
        if not value or 'BC' in str(value):
            return datetime(1900, 1, 1)
        dt = datetime.fromisoformat(str(value).replace(' ', 'T'))
        return dt if dt.year >= 1900 else datetime(1900, dt.month, dt.day)
    except Exception:
        return datetime(1900, 1, 1)

def reconnect():
    local = psycopg2.connect(**LOCAL_DB_CONFIG)
    remote = psycopg2.connect(**REMOTE_DB_CONFIG)
    return local, remote, local.cursor(), remote.cursor()

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
        cleaned_row = []
        for i, col in enumerate(columns_to_select):
            value = row[i]
            if col in ['created_at', 'updated_at', 'deleted_at']:
                value = clean_date(value)
            cleaned_row.append(value)
        rows.append(cleaned_row)

    logger.info(f"🧾 Total consultations à synchroniser : {len(rows)}")

    if rows:
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

        batch_size = 1000
        count = 0

        for i in tqdm(range(0, len(rows), batch_size), desc="🔁 Sync consultations"):
            batch = rows[i:i + batch_size]
            try:
                execute_values(remote_cursor, query, batch)
                remote.commit()
                count += len(batch)
            except Exception as e:
                remote.rollback()
                logger.error(f"❌ Échec lot {i}-{i + len(batch)} : {e}")

        logger.info(f"🎯 Fin : {count} consultations synchronisées avec succès")

except Exception as e:
    logger.error("❌ Erreur globale", exc_info=True)

finally:
    try:
        if 'local_cursor' in locals(): local_cursor.close()
        if 'remote_cursor' in locals(): remote_cursor.close()
        if 'local' in locals(): local.close()
        if 'remote' in locals(): remote.close()
    except Exception as e:
        logger.warning(f"⚠️ Erreur fermeture : {e}")