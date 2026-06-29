import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import (
    models,  # Add this import at the top
    transaction,
)
from poll.models import (
    AccumulatedResult,
    CandidateRegistration,
    Constituency,
    Contender,
    District,
    ElectoralCircle,
    PollingStation,
    PollingStationResult,
    VoteCount,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate test data for the election system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scale',
            type=float,
            default=1.0,
            help='Scale factor for data generation (default: 1.0)'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2026,
            help='Election year (default: 2026)'
        )
        parser.add_argument(
            '--election-type',
            type=str,
            default='Legislative',
            choices=['Legislative', 'Presidential', 'Autarchic'],
            help='Election type (default: Legislative)'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        scale = options['scale']
        year = options['year']
        election_type = options['election_type']
        
        self.stdout.write(f"Generating test data for {election_type} {year} (scale: {scale})")
        
        # Create users
        users = self.create_users()
        self.stdout.write(f"✓ Created {len(users)} users")
        
        # Create geographic hierarchy
        districts = self.create_districts()
        self.stdout.write(f"✓ Created {len(districts)} districts")
        
        circles = self.create_circles(districts)
        self.stdout.write(f"✓ Created {len(circles)} electoral circles")
        
        constituencies = self.create_constituencies(circles, scale)
        self.stdout.write(f"✓ Created {len(constituencies)} constituencies")
        
        polling_stations = self.create_polling_stations(constituencies, scale)
        self.stdout.write(f"✓ Created {len(polling_stations)} polling stations")
        
        # Create contenders and registrations
        contenders = self.create_contenders()
        self.stdout.write(f"✓ Created {len(contenders)} contenders")
        
        registrations = self.create_registrations(contenders, election_type, year)
        self.stdout.write(f"✓ Created {len(registrations)} candidate registrations")
        
        # Create results and votes
        results_count = 0
        vote_count = 0
        for station in polling_stations[:int(50 * scale)]:  # Limit for performance
            result = self.create_polling_station_result(
                station, election_type, year, registrations, users
            )
            if result:
                results_count += 1
                vote_count += result.votes.count()
        
        self.stdout.write(f"✓ Created {results_count} polling station results")
        self.stdout.write(f"✓ Created {vote_count} vote counts")
        
        # Create accumulated results
        self.create_accumulated_results(election_type, year, registrations, districts, circles, constituencies)
        self.stdout.write("✓ Created accumulated results")
        
        self.stdout.write("\n✅ Data generation complete!")
        self.stdout.write("Summary:")
        self.stdout.write(f"  - Users: {len(users)}")
        self.stdout.write(f"  - Districts: {len(districts)}")
        self.stdout.write(f"  - Electoral Circles: {len(circles)}")
        self.stdout.write(f"  - Constituencies: {len(constituencies)}")
        self.stdout.write(f"  - Polling Stations: {len(polling_stations)}")
        self.stdout.write(f"  - Contenders: {len(contenders)}")
        self.stdout.write(f"  - Candidate Registrations: {len(registrations)}")
        self.stdout.write(f"  - Polling Results: {results_count}")
        self.stdout.write(f"  - Vote Counts: {vote_count}")

    def create_users(self, count=5):
        users = []
        user_data = [
            ('admin', 'admin@example.com', 'Admin', 'User', True),
            ('manager1', 'manager1@example.com', 'Manager', 'One', True),
            ('manager2', 'manager2@example.com', 'Manager', 'Two', True),
            ('operator1', 'operator1@example.com', 'Operator', 'One', False),
            ('operator2', 'operator2@example.com', 'Operator', 'Two', False),
        ]
        
        for username, email, first_name, last_name, is_staff in user_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_staff': is_staff,
                    'is_active': True,
                    'is_superuser': is_staff
                }
            )
            if created:
                user.set_password('password123')
                user.save()
            users.append(user)
        return users

    def create_districts(self):
        district_names = [
            'Água Grande', 'Mé-Zóchi', 'Cantagalo', 'Caué', 'Lembá',
            'Lobata', 'Pagué', 'Príncipe', 'Trindade', 'Neves'
        ]
        
        districts = []
        for name in district_names:
            district, created = District.objects.get_or_create(name=name)
            districts.append(district)
        return districts

    def create_circles(self, districts):
        circles = []
        circle_names = [
            ('Água Grande', ['Círculo 1', 'Círculo 2', 'Círculo 3']),
            ('Mé-Zóchi', ['Círculo 1', 'Círculo 2']),
            ('Lobata', ['Círculo 1', 'Círculo 2']),
            ('Príncipe', ['Círculo Único']),
        ]
        
        for district_name, names in circle_names:
            district = next((d for d in districts if d.name == district_name), None)
            if district:
                for name in names:
                    circle, created = ElectoralCircle.objects.get_or_create(
                        district=district,
                        name=name
                    )
                    circles.append(circle)
        return circles

    def create_constituencies(self, circles, scale):
        constituencies = []
        constituency_data = [
            ('AG01', 'Constituição 1', 'Água Grande'),
            ('AG02', 'Constituição 2', 'Água Grande'),
            ('AG03', 'Constituição 3', 'Água Grande'),
            ('MZ01', 'Constituição 1', 'Mé-Zóchi'),
            ('MZ02', 'Constituição 2', 'Mé-Zóchi'),
            ('LB01', 'Constituição 1', 'Lobata'),
            ('LB02', 'Constituição 2', 'Lobata'),
            ('PR01', 'Constituição Única', 'Príncipe'),
            ('CA01', 'Constituição 1', 'Cantagalo'),
            ('CA02', 'Constituição 2', 'Cantagalo'),
        ]
        
        # Limit based on scale
        max_constituencies = int(len(constituency_data) * min(scale, 1.0))
        constituency_data = constituency_data[:max_constituencies]
        
        for code, name, district_name in constituency_data:
            # Find the appropriate circle
            circle = None
            for c in circles:
                if c.district.name == district_name:
                    circle = c
                    break
            
            if circle:
                constituency, created = Constituency.objects.get_or_create(
                    code=code,
                    defaults={
                        'circle': circle,
                        'name': name
                    }
                )
                constituencies.append(constituency)
        return constituencies

    def create_polling_stations(self, constituencies, scale):
        polling_stations = []
        school_names = [
            'Escola Pantufo', 'Escola Secundária', 'Escola Central',
            'Escola Municipal', 'Colégio Nacional', 'Escola Primária',
            'Instituto Educacional', 'Centro de Ensino'
        ]
        
        station_count = int(2 * scale)  # 2 stations per constituency base
        
        for constituency in constituencies:
            for i in range(station_count):
                station_number = i + 1
                school = random.choice(school_names)
                name = f"{school} - Mesa {station_number}"
                
                station, created = PollingStation.objects.get_or_create(
                    constituency=constituency,
                    station_number=station_number,
                    defaults={'name': name}
                )
                polling_stations.append(station)
        return polling_stations

    def create_contenders(self):
        contenders_data = [
            ('Independent Democratic Action', 'ADI'),
            ('MLSTP/PSD', 'MLSTP'),
            ('Democratic Convergence Party', 'PCD'),
            ('Union for Democracy and Development', 'UDD'),
            ('Social Democratic Party', 'PSD'),
            ('Movement for the Liberation', 'MLP'),
            ('Green Party', 'PV'),
            ('Socialist Party', 'PS'),
            ('Liberal Party', 'PL'),
            ('National Unity Party', 'PUN'),
        ]
        
        contenders = []
        for name, slug in contenders_data:
            contender, created = Contender.objects.get_or_create(
                slug=slug,
                defaults={'name': name}
            )
            contenders.append(contender)
        return contenders

    def create_registrations(self, contenders, election_type, year):
        registrations = []
        representatives = [
            'Carlos Alberto', 'Maria Santos', 'João Silva', 'Ana Costa',
            'Pedro Fernandes', 'Marta Oliveira', 'José Almeida', 'Sofia Rodrigues',
            'António Barbosa', 'Isabel Gomes'
        ]
        
        for i, contender in enumerate(contenders[:7]):  # Limit to 7 for performance
            rep_name = representatives[i % len(representatives)]
            registration, created = CandidateRegistration.objects.get_or_create(
                contender=contender,
                election_type=election_type,
                year=year,
                defaults={'representative_name': rep_name}
            )
            registrations.append(registration)
        return registrations

    def create_polling_station_result(self, station, election_type, year, registrations, users):
        try:
            # Check if result already exists
            if PollingStationResult.objects.filter(
                polling_station=station,
                election_type=election_type,
                year=year
            ).exists():
                return None
            
            # Generate random votes
            abstentions = random.randint(5, 50)
            blank_votes = random.randint(0, 10)
            null_votes = random.randint(0, 10)
            
            result = PollingStationResult.objects.create(
                polling_station=station,
                election_type=election_type,
                year=year,
                abstentions=abstentions,
                blank_votes=blank_votes,
                null_votes=null_votes
            )
            
            # Create vote counts for each registration
            for registration in registrations:
                # Random total votes between 10 and 200
                total_votes = random.randint(10, 200)
                user = random.choice(users) if users else None
                
                VoteCount.objects.create(
                    polling_result=result,
                    candidate_registration=registration,
                    total_votes=total_votes,
                    user=user
                )
            
            return result
        except Exception as e:
            self.stdout.write(f"Error creating polling station result: {e}")
            return None

    def create_accumulated_results(self, election_type, year, registrations, districts, circles, constituencies):
        # National level
        for registration in registrations:
            # Calculate total votes from all polling stations
            total_votes = VoteCount.objects.filter(
                candidate_registration=registration,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).aggregate(total=models.Sum('total_votes'))['total'] or 0
            
            AccumulatedResult.objects.get_or_create(
                scope='National',
                candidate_registration=registration,
                election_type=election_type,
                year=year,
                defaults={
                    'total_votes': total_votes,
                    'estimated_seats': random.randint(0, 5)
                }
            )
        
        # District level
        for district in districts[:5]:  # Limit to 5 districts
            for registration in registrations[:5]:  # Limit to 5 registrations
                total_votes = VoteCount.objects.filter(
                    candidate_registration=registration,
                    polling_result__election_type=election_type,
                    polling_result__year=year,
                    polling_result__polling_station__constituency__circle__district=district
                ).aggregate(total=models.Sum('total_votes'))['total'] or 0
                
                if total_votes > 0:
                    AccumulatedResult.objects.get_or_create(
                        scope='District',
                        district=district,
                        candidate_registration=registration,
                        election_type=election_type,
                        year=year,
                        defaults={
                            'total_votes': total_votes,
                            'estimated_seats': random.randint(0, 2)
                        }
                    )

        # Circle level
        for circle in circles[:5]:
            for registration in registrations[:5]:
                total_votes = VoteCount.objects.filter(
                    candidate_registration=registration,
                    polling_result__election_type=election_type,
                    polling_result__year=year,
                    polling_result__polling_station__constituency__circle=circle
                ).aggregate(total=models.Sum('total_votes'))['total'] or 0
                
                if total_votes > 0:
                    AccumulatedResult.objects.get_or_create(
                        scope='Circle',
                        circle=circle,
                        candidate_registration=registration,
                        election_type=election_type,
                        year=year,
                        defaults={
                            'total_votes': total_votes,
                            'estimated_seats': random.randint(0, 1)
                        }
                    )

        # Constituency level
        for constituency in constituencies[:10]:
            for registration in registrations[:5]:
                total_votes = VoteCount.objects.filter(
                    candidate_registration=registration,
                    polling_result__election_type=election_type,
                    polling_result__year=year,
                    polling_result__polling_station__constituency=constituency
                ).aggregate(total=models.Sum('total_votes'))['total'] or 0
                
                if total_votes > 0:
                    AccumulatedResult.objects.get_or_create(
                        scope='Constituency',
                        constituency=constituency,
                        candidate_registration=registration,
                        election_type=election_type,
                        year=year,
                        defaults={
                            'total_votes': total_votes,
                            'estimated_seats': random.randint(0, 1)
                        }
                    )


