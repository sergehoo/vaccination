import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from faker import Faker

from inhp.models import Utilisateur, FicheRetro

fake = Faker('fr_FR')


class Command(BaseCommand):
    help = "Génère des fiches retro factices"

    def add_arguments(self, parser):
        parser.add_argument('--total', type=int, default=500, help='Nombre de fiches à créer')

    def handle(self, *args, **options):
        total = options['total']

        utilisateurs = list(Utilisateur.objects.all())

        for _ in range(total):
            sexe = random.choice(['Masculin', 'Féminin'])
            date_naissance = fake.date_of_birth(minimum_age=1, maximum_age=90)
            created_at = fake.date_time_this_year()
            date_test = created_at + timedelta(days=random.randint(0, 10))

            fiche = FicheRetro.objects.create(
                created_at=created_at,
                updated_at=created_at,
                nom=fake.last_name(),
                prenoms=fake.first_name(),
                date_naissance=date_naissance,
                sexe=sexe,
                situation_matrimoniale=random.choice(['Célibataire', 'Marié(e)', 'Divorcé(e)', None]),
                nombre_enfant=random.randint(0, 6),
                nationnalite=fake.country(),
                type_piece=random.choice(['CNI', 'Passeport', 'Permis', None]),
                num_piece=fake.ssn(),
                telephone1=fake.phone_number(),
                telephone2=fake.phone_number() if random.random() > 0.5 else None,
                commune=fake.city(),
                quatier=fake.street_name(),
                niveau_instruction=random.choice(['Primaire', 'Secondaire', 'Supérieur', 'Aucun']),
                profession=fake.job(),
                consentement_parental=random.choice(['Oui', 'Non', None]),
                email=fake.email() if random.random() > 0.3 else None,
                positif=random.choice([0, 1]),
                positif_date=date_test if random.random() > 0.7 else None,
                vaccin_autre=random.choice([0, 1, None]),
                temperature=round(random.uniform(36.0, 39.5), 2),
                pathologies=fake.sentence(nb_words=6) if random.random() > 0.6 else None,
                date_debut_obs=created_at + timedelta(days=1),
                date_fin_obs=created_at + timedelta(days=10),
                mapi=random.choice([0, 1]),
                date_mapi=date_test if random.random() > 0.8 else None,
                region1_id=random.randint(1, 31),
                district1_id=random.randint(1, 100),
                aire1=fake.word(),
                centre1_id=random.randint(1, 200),
                date_vac1=date_test,
                vaccin1_id=random.randint(1, 20),
                numero_lot1=fake.bothify(text='LOT-####'),
                region2_id=random.randint(1, 31),
                district2_id=random.randint(1, 100),
                aire2=fake.word(),
                centre2_id=random.randint(1, 200),
                date_vac2=date_test + timedelta(days=21),
                vaccin2_id=random.randint(1, 20),
                numero_lot2=fake.bothify(text='LOT-####'),
                region3_id=random.randint(1, 31),
                district3_id=random.randint(1, 100),
                aire3=fake.word(),
                centre3_id=random.randint(1, 200),
                date_vac3=date_test + timedelta(days=42),
                vaccin3_id=random.randint(1, 20),
                numero_lot3=fake.bothify(text='LOT-####'),
                region4_id=random.randint(1, 31),
                district4_id=random.randint(1, 100),
                aire4=fake.word(),
                centre4_id=random.randint(1, 200),
                date_vac4=date_test + timedelta(days=63),
                vaccin4_id=random.randint(1, 20),
                numero_lot4=fake.bothify(text='LOT-####'),
                utilisateur=random.choice(utilisateurs) if utilisateurs else None,
                is_valider=random.choice([0, 1]),
                date=created_at,
                numero_civ=fake.uuid4(),
                numero_unique=fake.uuid4()
            )

        self.stdout.write(self.style.SUCCESS(f"{total} fiches retro créées avec succès."))
