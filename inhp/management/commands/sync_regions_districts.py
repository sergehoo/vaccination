import psycopg2
from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronise les regions et districts entre deux bases Postgres"

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

            # Synchronisation des regions
            local_cursor.execute("SELECT id, nom FROM regions WHERE deleted_at IS NULL")
            regions = local_cursor.fetchall()
            for r in regions:
                try:
                    remote_cursor.execute("""
                        INSERT INTO inhp_healthregion (id, name)
                        VALUES (%s, %s)
                        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                    """, (r[0], r[1]))
                except Exception as e:
                    remote.rollback()
                    logger.error(f"Erreur Region ID {r[0]}: {e}")
            remote.commit()
            logger.info(f"✅ {len(regions)} regions synchronisées")

            # Synchronisation des districts
            local_cursor.execute("SELECT id, district, region_id FROM districts WHERE deleted_at IS NULL")
            districts = local_cursor.fetchall()
            for d in districts:
                try:
                    remote_cursor.execute("""
                        INSERT INTO inhp_districtsanitaire (id, nom, region_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET nom = EXCLUDED.nom, region_id = EXCLUDED.region_id
                    """, (d[0], d[1], d[2]))
                except Exception as e:
                    remote.rollback()
                    logger.error(f"Erreur District ID {d[0]}: {e}")
            remote.commit()
            logger.info(f"✅ {len(districts)} districts synchronisés")

        except Exception as e:
            logger.error(f"Erreur globale: {e}", exc_info=True)

        finally:
            if 'local_cursor' in locals():
                local_cursor.close()
            if 'remote_cursor' in locals():
                remote_cursor.close()
            if 'local' in locals():
                local.close()
            if 'remote' in locals():
                remote.close()
