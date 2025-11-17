import logging
from datetime import datetime
import time

import psycopg2
from psycopg2.extras import Json, execute_values
from dateutil.parser import parse as date_parse
from django.core.management import BaseCommand


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronise la table des vaccinations entre TRACEDB.vaccines et vaccination.inhp_vaccination (via code_patient)"

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
        remote_patient_table = 'inhp_patient'

        # ⚠️ Mapping des colonnes VACCINATION (sans code_patient)
        # -> ce sont uniquement les colonnes réellement présentes dans inhp_vaccination
        field_mapping = {
            'id': 'id',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'deleted_at': 'deleted_at',
            'date_vacc': 'date_vaccination',
            'numero_dose': 'dose',
            # on va écraser patient_id avec l'ID distant (via code_patient)
            'patient_id': 'patient_id',
            'vaccin_id': 'vaccin_id',
            'lot_id': 'lot_id',
            'centre_id': 'centre_id',
            'utilisateur_id': 'created_by_id',
        }

        # Colonnes "helper" qu'on lit en plus mais qu'on n’insère pas dans inhp_vaccination
        helper_columns = ['code_patient']

        FETCH_BATCH_SIZE = 50_000
        INSERT_BATCH_SIZE = 5_000

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

        def connect_both():
            local = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote = psycopg2.connect(**REMOTE_DB_CONFIG)
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

            # --- Récupération des colonnes disponibles ---
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

            # Colonnes de vaccination réellement communes entre les 2 tables
            vaccination_cols = [
                lc for lc, rc in field_mapping.items()
                if lc in local_columns and rc in remote_columns
            ]

            # On ajoute les colonnes helpers si présentes côté local
            extra_helpers = [c for c in helper_columns if c in local_columns]
            columns_to_select = vaccination_cols + extra_helpers

            if not vaccination_cols:
                logger.error("❌ Aucun champ commun de vaccination trouvé entre %s et %s", local_table, remote_table)
                return

            logger.info(f"✅ Colonnes vaccination utilisées : {vaccination_cols}")
            logger.info(f"ℹ️ Colonnes helper : {extra_helpers}")

            # Construction de la requête SELECT streamée
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

            local_cursor = local_conn.cursor(name="vacc_sync_cursor")
            local_cursor.itersize = FETCH_BATCH_SIZE
            logger.info("▶️ Lancement du SELECT streamé sur la table locale…")
            local_cursor.execute(select_sql)

            # Colonnes à insérer réellement dans inhp_vaccination (on enlève les helpers)
            columns_for_remote = vaccination_cols  # ordre = field_mapping keys filtrés plus haut
            remote_columns = [field_mapping[col] for col in columns_for_remote]
            remote_columns_str = ', '.join(remote_columns)

            update_clause = ', '.join(
                f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}"
                for col in columns_for_remote
                if col != 'id'
            )

            insert_query = f"""
                INSERT INTO {remote_table} ({remote_columns_str})
                VALUES %s
                ON CONFLICT (id) DO UPDATE
                SET {update_clause}
            """

            # indices utiles
            col_index = {c: i for i, c in enumerate(columns_to_select)}
            has_code_patient = 'code_patient' in col_index
            has_patient_id = 'patient_id' in col_index

            if not has_code_patient:
                logger.error("❌ La colonne 'code_patient' n'est pas présente dans %s, impossible de mapper les patients.", local_table)
                return

            if not has_patient_id:
                logger.error("❌ La colonne 'patient_id' n'est pas présente dans %s, nécessaire pour inhp_vaccination.patient_id.", local_table)
                return

            idx_code_patient = col_index['code_patient']
            idx_patient_id = col_index['patient_id']

            # indices des colonnes de vaccination dans columns_to_select
            indices_for_remote = [col_index[c] for c in columns_for_remote]

            total_processed = 0
            total_skipped_no_patient = 0
            batch_number = 0

            while True:
                raw_rows = local_cursor.fetchmany(FETCH_BATCH_SIZE)
                if not raw_rows:
                    break

                logger.info(f"📥 Chunk brut récupéré : {len(raw_rows)} lignes")

                # 1) Nettoyage brut (dates, strings vides, JSON, etc.)
                cleaned_rows = []
                for raw in raw_rows:
                    row_dict = dict(zip(columns_to_select, raw))
                    row_vals = []
                    for col in columns_to_select:
                        val = row_dict.get(col)

                        if col in ['created_at', 'updated_at', 'deleted_at', 'date_vacc']:
                            val = clean_date(val)

                        if isinstance(val, str) and val.strip() == '':
                            val = None

                        if isinstance(val, (dict, list)):
                            val = Json(val)

                        row_vals.append(val)

                    cleaned_rows.append(row_vals)

                # 2) Résolution des patient_id distants via code_patient
                #    -> on récupère tous les code_patient du chunk
                codes = {row[idx_code_patient] for row in cleaned_rows if row[idx_code_patient]}
                if not codes:
                    logger.warning("⚠️ Chunk sans code_patient, tout sera ignoré.")
                    continue

                # Lookup en une seule requête côté remote
                try:
                    with remote_conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT id, code_patient
                            FROM {remote_patient_table}
                            WHERE code_patient = ANY(%s)
                            """,
                            [list(codes)]
                        )
                        mapping_rows = cur.fetchall()
                except Exception as e:
                    logger.error(f"❌ Erreur lors du lookup inhp_patient : {e}")
                    remote_conn.rollback()
                    # On ne peut rien insérer pour ce chunk
                    continue

                code_to_remote_id = {cp: pid for (pid, cp) in mapping_rows}
                logger.info(f"🔗 Patients trouvés dans inhp_patient pour ce chunk : {len(code_to_remote_id)}")

                # 3) Construction des lignes finales (avec patient_id distant)
                rows_ready = []
                skipped_in_chunk = 0

                for row in cleaned_rows:
                    cp = row[idx_code_patient]
                    if not cp:
                        skipped_in_chunk += 1
                        continue

                    remote_pid = code_to_remote_id.get(cp)
                    if not remote_pid:
                        # patient non trouvé côté Django => on ignore cette vaccination
                        skipped_in_chunk += 1
                        continue

                    # Remplace l'ancien patient_id (local) par l'ID distant
                    row[idx_patient_id] = remote_pid

                    # On ne garde que les colonnes de vaccination (sans code_patient)
                    row_remote = [row[i] for i in indices_for_remote]
                    rows_ready.append(row_remote)

                if skipped_in_chunk:
                    total_skipped_no_patient += skipped_in_chunk
                    logger.info(
                        f"⚠️ {skipped_in_chunk} lignes ignorées dans ce chunk (patients inexistants dans inhp_patient)"
                    )

                if not rows_ready:
                    logger.info("ℹ️ Aucun enregistrement prêt à être inséré pour ce chunk.")
                    continue

                # 4) Envoi vers la base distante par sous-batches
                start_idx = 0
                while start_idx < len(rows_ready):
                    sub_batch = rows_ready[start_idx:start_idx + INSERT_BATCH_SIZE]
                    sub_left = start_idx
                    sub_right = start_idx + len(sub_batch)

                    retry = 0
                    while retry < 3:
                        try:
                            if not is_connection_alive(remote_conn):
                                logger.warning("🔌 Connexion distante perdue, reconnexion…")
                                time.sleep(2 ** retry)
                                _, remote_conn = connect_both()

                            with remote_conn.cursor() as remote_cursor:
                                execute_values(remote_cursor, insert_query, sub_batch)

                            remote_conn.commit()
                            logger.info(
                                f"✅ Chunk {batch_number} sous-batch {sub_left}-{sub_right} inséré ({len(sub_batch)} lignes)"
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

                total_processed += len(rows_ready)
                batch_number += 1
                logger.info(f"📊 Total traité jusqu'ici (insérés/mis à jour) : {total_processed} lignes")

            logger.info("🎯 Synchronisation des vaccinations terminée.")
            logger.info(f"📦 Total lignes synchronisées : {total_processed}")
            logger.info(f"🙈 Total lignes ignorées (patient manquant) : {total_skipped_no_patient}")

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