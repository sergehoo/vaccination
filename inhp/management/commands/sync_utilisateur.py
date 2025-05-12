import psycopg2
from psycopg2.extras import Json
from django.apps import apps
from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronise la table utilisateurs entre bases locales et distantes"

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

        try:
            # Établir les connexions
            local = psycopg2.connect(**LOCAL_DB_CONFIG)
            remote = psycopg2.connect(**REMOTE_DB_CONFIG)
            local_cursor = local.cursor()
            remote_cursor = remote.cursor()

            # Configuration des tables
            local_table = 'utilisateurs'
            remote_table = 'auth_user'  # Ou le nom de la table distante si différent

            # Mapping des champs entre la table locale et le modèle distant
            field_mapping = {
                # Champs de base
                'id': 'id',
                'created_at': 'date_joined',
                'email': 'email',
                'password': 'password',
                'nom': 'last_name',
                'prenoms': 'first_name',
                'telephone1': 'phone',
                'is_active': 'is_active',
                'centre_id': 'centre_id',

                # Champs qui n'ont pas de correspondance directe
                # 'role_id': 'role',  # À gérer séparément si nécessaire
                # 'active_otp': '',    # Pas d'équivalent dans le modèle
                # 'password_status': '' # Pas d'équivalent
            }

            # Vérifier les colonnes existantes dans la table locale
            local_cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{local_table}'
            """)
            existing_columns = {row[0] for row in local_cursor.fetchall()}

            # Filtrer les colonnes qui existent et ont une correspondance
            columns_to_select = [
                db_column for db_column, model_field in field_mapping.items()
                if db_column in existing_columns
            ]

            if not columns_to_select:
                logger.error("Aucune colonne commune trouvée entre les tables")
                return

            columns_str = ', '.join(columns_to_select)
            placeholders = ', '.join(['%s'] * len(columns_to_select))

            # Construction de la clause UPDATE (tous les champs sauf id)
            update_fields = [c for c in columns_to_select if c != 'id']
            update_clause = ', '.join([f"{field_mapping[c]} = EXCLUDED.{field_mapping[c]}"
                                       for c in update_fields])

            logger.info(f"📤 Transfert de {local_table} → {remote_table}")

            # Récupération des données locales
            local_cursor.execute(f"SELECT {columns_str} FROM {local_table}")
            rows = local_cursor.fetchall()

            count = 0
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    # Préparation des valeurs
                    values = []
                    for row in batch:
                        cleaned_row = [Json(v) if isinstance(v, (dict, list)) else v for v in row]
                        values.extend(cleaned_row)

                    # Insertion par lot
                    query = f"""
                        INSERT INTO {remote_table} ({', '.join(field_mapping[c] for c in columns_to_select)})
                        VALUES {','.join(['(' + placeholders + ')'] * len(batch))}
                        ON CONFLICT (id) DO UPDATE SET {update_clause}
                    """
                    remote_cursor.execute(query, values)
                    count += len(batch)
                    remote.commit()
                except Exception as e:
                    remote.rollback()
                    logger.error(f"Erreur lors du traitement du lot {i}-{i + batch_size}: {e}", exc_info=True)

            logger.info(f"✅ {count} lignes transférées avec succès")

        except Exception as e:
            logger.error(f"Erreur globale : {e}", exc_info=True)
        finally:
            # Fermeture propre des connexions
            if 'local_cursor' in locals():
                local_cursor.close()
            if 'remote_cursor' in locals():
                remote_cursor.close()
            if 'local' in locals():
                local.close()
            if 'remote' in locals():
                remote.close()