from datetime import date
import psycopg2
from psycopg2.extras import Json
from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Synchronise la table centres entre bases locales et distantes (CentreVaccination)"

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

        try:
            local = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote = psycopg2.connect(**REMOTE_DB_CONFIG)
            local_cursor = local.cursor()
            remote_cursor = remote.cursor()

            local_table = 'centres'
            remote_table = 'inhp_centrevaccination'

            field_mapping = {
                'id': 'id',
                'name': 'name',
                'longitude': 'longitude',
                'latitude': 'latitude',
                'addresse': 'adresse',
                'district_id': 'district_id',
                'created_at': 'created_at',
                'updated_at': 'updated_at',
                'deleted_at': 'deleted_at',
            }

            # Vérification des colonnes existantes
            local_cursor.execute(f"""
                SELECT column_name FROM information_schema.columns WHERE table_name = '{local_table}'
            """)
            local_columns = {row[0] for row in local_cursor.fetchall()}

            remote_cursor.execute(f"""
                SELECT column_name FROM information_schema.columns WHERE table_name = '{remote_table}'
            """)
            remote_columns = {row[0] for row in remote_cursor.fetchall()}

            columns_to_select = [
                local_col for local_col, remote_col in field_mapping.items()
                if local_col in local_columns and remote_col in remote_columns
            ]

            if not columns_to_select:
                logger.error("Aucune colonne commune trouvée entre les tables")
                return

            logger.info(f"Colonnes synchronisées: {columns_to_select}")

            def clean_date(value):
                if isinstance(value, date) and value.year < 1900:
                    return None
                return value

            def clean_coordinates(value):
                try:
                    val = float(value)
                    if abs(val) > 1000:  # Seuil de sécurité pour longitude/latitude
                        logger.warning(f"Valeur géographique anormale ignorée: {val}")
                        return None
                    return round(val, 6)
                except Exception as e:
                    logger.warning(f"Erreur conversion coordonnées: {value} → {e}")
                    return None

            local_cursor.execute(f"SELECT {', '.join(columns_to_select)} FROM {local_table}")
            rows = []
            for row in local_cursor:
                try:
                    cleaned_row = []
                    for i, value in enumerate(row):
                        if columns_to_select[i] in ['created_at', 'updated_at', 'deleted_at']:
                            value = clean_date(value)
                        if columns_to_select[i] in ['longitude', 'latitude']:
                            value = clean_coordinates(value)
                        cleaned_row.append(Json(value) if isinstance(value, (dict, list)) else value)
                    rows.append(cleaned_row)
                except Exception as e:
                    logger.warning(f"Erreur traitement ligne: {e}")

            if not rows:
                logger.info("Aucune donnée à synchroniser")
                return

            remote_columns_str = ', '.join(field_mapping[col] for col in columns_to_select)
            placeholders = ', '.join(['%s'] * len(columns_to_select))
            update_fields = [col for col in columns_to_select if col != 'id']
            update_clause = ', '.join(
                [f"{field_mapping[col]} = EXCLUDED.{field_mapping[col]}" for col in update_fields]
            )

            logger.info(f"\U0001f4e4 Transfert de {local_table} → {remote_table}")

            count = 0
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    query = f"""
                        INSERT INTO {remote_table} ({remote_columns_str})
                        VALUES {','.join(['(' + placeholders + ')'] * len(batch))}
                        ON CONFLICT (id) DO UPDATE SET {update_clause}
                    """
                    values = [item for sublist in batch for item in sublist]
                    remote_cursor.execute(query, values)
                    count += len(batch)
                    remote.commit()
                except Exception as e:
                    remote.rollback()
                    logger.error(f"Erreur lot {i}-{i + batch_size}: {e}")

            logger.info(f"✅ {count} centres transférés avec succès")

        except Exception as e:
            logger.error(f"Erreur globale : {e}", exc_info=True)
        finally:
            if 'local_cursor' in locals():
                local_cursor.close()
            if 'remote_cursor' in locals():
                remote_cursor.close()
            if 'local' in locals():
                local.close()
            if 'remote' in locals():
                remote.close()
