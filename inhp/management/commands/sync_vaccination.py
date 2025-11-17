import logging
from datetime import datetime, timedelta
import time

import psycopg2
from psycopg2.extras import Json, execute_values
from dateutil.parser import parse as date_parse
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronise la table des vaccinations entre les bases locales et distantes (10M+ lignes, mode streaming)"

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

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

        local_table = 'vaccines'
        remote_table = 'inhp_vaccination'

        # ⚠️ Ne mapper ici que les colonnes réellement présentes dans les 2 tables
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
            # si tu ajoutes d’autres colonnes communes, les déclarer ici
        }

        # Taille de lecture côté DB et taille d'insert côté remote
        FETCH_BATCH_SIZE = 50_000     # lignes lues en une fois depuis la locale
        INSERT_BATCH_SIZE = 5_000     # lignes envoyées par execute_values()

        def clean_date(value):
            """
            Normalise les dates :
            - remplace les valeurs invalides / BC par 1900-01-01
            - renvoie un datetime propre (PostgreSQL pourra caster vers DATE si besoin)
            """
            try:
                if not value or 'BC' in str(value):
                    return datetime(1900, 1, 1)
                dt = date_parse(str(value).replace(' BC', ''))
                if dt.year < 1900:
                    return datetime(1900, dt.month, dt.day)
                return dt
            except Exception:
                return datetime(1900, 1, 1)

        def connect_both():
            local = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote = psycopg2.connect(**REMOTE_DB_CONFIG)
            # On désactive l'autocommit côté remote pour gérer nous-mêmes les batchs
            remote.autocommit = False
            return local, remote

        def is_connection_alive(conn):
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            except Exception:
                return False

        try:
            logger.info("🔌 Connexion aux bases locale et distante…")
            local_conn, remote_conn = connect_both()

            # On utilise un *server-side cursor* (named cursor) pour streamer les 10M lignes
            local_cursor = local_conn.cursor(name="vacc_sync_cursor")

            # 1) Récupération des colonnes réellement présentes
            logger.info("🔍 Détection des colonnes communes…")
            tmp_cur = local_conn.cursor()
            tmp_cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
            """, [local_table])
            local_columns = {r[0] for r in tmp_cur.fetchall()}
            tmp_cur.close()

            tmp_cur = remote_conn.cursor()
            tmp_cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
            """, [remote_table])
            remote_columns = {r[0] for r in tmp_cur.fetchall()}
            tmp_cur.close()

            columns_to_select = [
                lc for lc, rc in field_mapping.items()
                if lc in local_columns and rc in remote_columns
            ]

            if not columns_to_select:
                logger.error("❌ Aucun champ commun trouvé entre %s et %s", local_table, remote_table)
                return

            logger.info(f"✅ Champs communs utilisés : {columns_to_select}")

            # 2) Préparation de la requête de SELECT streamée
            casted_cols = [
                f"CAST({col} AS TEXT) AS {col}"
                if col in ['created_at', 'updated_at', 'deleted_at', 'date_vacc']
                else col
                for col in columns_to_select
            ]

            select_sql = f"""
                SELECT {', '.join(casted_cols)}
                FROM {local_table}
                ORDER BY id
            """

            logger.info("▶️ Lancement du SELECT streamé sur la table locale…")
            local_cursor.itersize = FETCH_BATCH_SIZE
            local_cursor.execute(select_sql)

            # 3) Préparation de la requête d'UPSERT distante
            remote_columns = [field_mapping[col] for col in columns_to_select]
            remote_columns_str = ', '.join(remote_columns)

            update_clause = ', '.join(
                f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}"
                for col in columns_to_select
                if col != 'id'
            )

            insert_query = f"""
                INSERT INTO {remote_table} ({remote_columns_str})
                VALUES %s
                ON CONFLICT (id) DO UPDATE
                SET {update_clause}
            """

            total_processed = 0
            batch_number = 0

            while True:
                # Lecture d'un gros chunk depuis la DB locale
                raw_rows = local_cursor.fetchmany(FETCH_BATCH_SIZE)
                if not raw_rows:
                    break  # plus de données

                logger.info(f"📥 Chunk brut récupéré : {len(raw_rows)} lignes")

                # Nettoyage + préparation des données de ce chunk
                cleaned_rows = []
                for raw in raw_rows:
                    row_dict = dict(zip(columns_to_select, raw))
                    cleaned_row = []
                    for col in columns_to_select:
                        val = row_dict.get(col)

                        if col in ['created_at', 'updated_at', 'deleted_at', 'date_vacc']:
                            val = clean_date(val)

                        if isinstance(val, str) and val.strip() == '':
                            val = None

                        if isinstance(val, (dict, list)):
                            cleaned_row.append(Json(val))
                        else:
                            cleaned_row.append(val)

                    cleaned_rows.append(cleaned_row)

                # 4) Envoi vers la base distante par sous-batches
                start_idx = 0
                while start_idx < len(cleaned_rows):
                    sub_batch = cleaned_rows[start_idx:start_idx + INSERT_BATCH_SIZE]
                    sub_left = start_idx
                    sub_right = start_idx + len(sub_batch)

                    retry = 0
                    while retry < 3:
                        try:
                            if not is_connection_alive(remote_conn):
                                logger.warning("🔌 Connexion distante perdue, reconnexion…")
                                time.sleep(2 ** retry)
                                # On ne touche pas à local_conn ici
                                _, remote_conn = connect_both()

                            with remote_conn.cursor() as remote_cursor:
                                execute_values(remote_cursor, insert_query, sub_batch)

                            remote_conn.commit()
                            logger.info(
                                f"✅ Chunk {batch_number} sous-batch {sub_left}-{sub_right} inséré"
                            )
                            break
                        except Exception as e:
                            remote_conn.rollback()
                            retry += 1
                            logger.error(
                                f"❌ Échec insertion sous-batch {sub_left}-{sub_right} (tentative {retry}/3) : {e}"
                            )
                            if retry == 3:
                                logger.critical("🚫 Abandon de ce sous-batch après 3 échecs.")
                            else:
                                time.sleep(2 ** retry)

                    start_idx += INSERT_BATCH_SIZE

                total_processed += len(cleaned_rows)
                batch_number += 1
                logger.info(f"📊 Total traité jusqu'ici : {total_processed} lignes")

            logger.info("🎯 Synchronisation des vaccinations terminée avec succès.")
            logger.info(f"📦 Total lignes synchronisées : {total_processed}")

        except Exception:
            logger.exception("❌ Erreur globale pendant la synchronisation")
        finally:
            try:
                if 'local_cursor' in locals() and not local_cursor.closed:
                    local_cursor.close()
            except Exception:
                pass
            try:
                if 'local_conn' in locals() and not local_conn.closed:
                    local_conn.close()
            except Exception:
                pass
            try:
                if 'remote_conn' in locals() and not remote_conn.closed:
                    remote_conn.close()
            except Exception:
                pass
# import logging
# from datetime import datetime
# import psycopg2
# from psycopg2.extras import Json, execute_values
# from dateutil.parser import parse as date_parse
# from django.core.management import BaseCommand
# from tqdm import tqdm
# import time
#
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
#
#
# class Command(BaseCommand):
#     help = "Synchronise la table des vaccinations entre les bases locales et distantes"
#
#     def handle(self, *args, **options):
#         LOCAL_DB_CONFIG = {
#             'dbname': 'TRACEDB',
#             'user': 'postgres',
#             'password': 'weddingLIFE18',
#             'host': 'localhost',
#             'port': '5433',
#         }
#
#         REMOTE_DB_CONFIG = {
#             'dbname': 'vaccination',
#             'user': 'postgres',
#             'password': 'weddingLIFE18',
#             'host': '147.93.84.26',
#             'port': '5434',
#         }
#
#         local_table = 'vaccines'
#         remote_table = 'inhp_vaccination'
#
#         field_mapping = {
#             'id': 'id',
#             'created_at': 'created_at',
#             'updated_at': 'updated_at',
#             'deleted_at': 'deleted_at',
#             'date_vacc': 'date_vaccination',
#             'numero_dose': 'dose',
#             'patient_id': 'patient_id',
#             'vaccin_id': 'vaccin_id',
#             'lot_id': 'lot_id',
#             'centre_id': 'centre_id',
#             'utilisateur_id': 'created_by_id',
#         }
#
#         def clean_date(value):
#             try:
#                 if not value or 'BC' in str(value):
#                     return datetime(1900, 1, 1)
#                 dt = date_parse(str(value).replace(' BC', ''))
#                 return dt if dt.year >= 1900 else datetime(1900, dt.month, dt.day)
#             except Exception:
#                 return datetime(1900, 1, 1)
#
#         def reconnect():
#             try:
#                 local = psycopg2.connect(**LOCAL_DB_CONFIG)
#                 remote = psycopg2.connect(**REMOTE_DB_CONFIG)
#                 return local, remote, local.cursor(), remote.cursor()
#             except Exception as e:
#                 logger.error(f"❌ Échec de connexion à la base : {e}")
#                 raise
#
#         def is_connection_alive(conn):
#             try:
#                 with conn.cursor() as cur:
#                     cur.execute('SELECT 1')
#                 return True
#             except Exception:
#                 return False
#
#         try:
#             local, remote, local_cursor, remote_cursor = reconnect()
#
#             # Vérifie les colonnes valides
#             local_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
#                                  [local_table])
#             local_columns = {r[0] for r in local_cursor.fetchall()}
#             remote_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
#                                   [remote_table])
#             remote_columns = {r[0] for r in remote_cursor.fetchall()}
#
#             columns_to_select = [lc for lc, rc in field_mapping.items() if lc in local_columns and rc in remote_columns]
#             logger.info(f"Champs communs utilisés : {columns_to_select}")
#
#             casted_cols = [f"CAST({col} AS TEXT) AS {col}" if col in ['created_at', 'updated_at', 'deleted_at',
#                                                                       'date_vacc'] else col for col in
#                            columns_to_select]
#             local_cursor.execute(f"SELECT {', '.join(casted_cols)} FROM {local_table}")
#             raw_rows = local_cursor.fetchall()
#
#             rows = []
#             for row in raw_rows:
#                 row_dict = dict(zip(columns_to_select, row))
#                 cleaned_row = []
#                 for col in columns_to_select:
#                     val = row_dict.get(col)
#                     if col in ['created_at', 'updated_at', 'deleted_at', 'date_vacc']:
#                         val = clean_date(val)
#                     if isinstance(val, str) and val.strip() == '':
#                         val = None
#                     cleaned_row.append(Json(val) if isinstance(val, (dict, list)) else val)
#                 rows.append(cleaned_row)
#
#             logger.info(f"🧾 Total lignes à synchroniser : {len(rows)}")
#             if not rows:
#                 return
#
#             remote_columns_str = ', '.join([field_mapping[col] for col in columns_to_select])
#             update_clause = ', '.join(
#                 [f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}" for col in columns_to_select if col != 'id'])
#
#             insert_query = f"""
#                 INSERT INTO {remote_table} ({remote_columns_str})
#                 VALUES %s
#                 ON CONFLICT (id) DO UPDATE SET {update_clause}
#             """
#
#             batch_size = 250
#             for i in tqdm(range(0, len(rows), batch_size), desc="🔁 Sync vaccinations"):
#                 batch = rows[i:i + batch_size]
#                 retry_count = 0
#                 while retry_count < 3:
#                     try:
#                         if not is_connection_alive(remote):
#                             logger.warning("🔌 Connexion perdue, reconnexion en cours...")
#                             time.sleep(2 ** retry_count)
#                             _, remote, _, remote_cursor = reconnect()
#
#                         execute_values(remote_cursor, insert_query, batch)
#                         remote.commit()
#                         logger.info(f"✅ Lot {i}-{i + len(batch)} inséré")
#                         break
#                     except Exception as e:
#                         retry_count += 1
#                         remote.rollback()
#                         logger.error(f"❌ Échec lot {i}-{i + len(batch)} : {e}")
#                         if retry_count == 3:
#                             logger.critical("🚫 Abandon après 3 tentatives.")
#                             break
#                         time.sleep(2 ** retry_count)
#
#             logger.info("🎯 Synchronisation des vaccinations terminée avec succès.")
#
#         except Exception as e:
#             logger.error("❌ Erreur globale", exc_info=True)
#
#         finally:
#             for obj in ['local_cursor', 'remote_cursor', 'local', 'remote']:
#                 try:
#                     if obj in locals() and locals()[obj]:
#                         locals()[obj].close()
#                 except Exception as e:
#                     logger.warning(f"⚠️ Erreur fermeture {obj} : {e}")
