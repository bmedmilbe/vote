import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

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
from poll.serializers import (
    AccumulatedResultSerializer,
    CandidateRegistrationSerializer,
    ConstituencySerializer,
    ContenderSerializer,
    DistrictSerializer,
    ElectoralCircleSerializer,
    PollingStationResultSerializer,
    PollingStationResultWithVotesSerializer,
    PollingStationSerializer,
    UserSerializer,
    VoteCountSerializer,
)

User = get_user_model()


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com"
    )

@pytest.fixture
def district():
    return District.objects.create(name="Água Grande")

@pytest.fixture
def electoral_circle(district):
    return ElectoralCircle.objects.create(
        district=district,
        name="Círculo 1"
    )

@pytest.fixture
def constituency(electoral_circle):
    return Constituency.objects.create(
        circle=electoral_circle,
        code="AG01",
        name="Constituição 1"
    )

@pytest.fixture
def polling_station(constituency):
    return PollingStation.objects.create(
        constituency=constituency,
        station_number=1,
        name="Escola Pantufo - Mesa 1"
    )

@pytest.fixture
def contender():
    return Contender.objects.create(
        name="Independent Democratic Action",
        slug="ADI"
    )

@pytest.fixture
def candidate_registration(contender):
    return CandidateRegistration.objects.create(
        contender=contender,
        election_type="Legislative",
        year=2026,
        representative_name="John Doe"
    )

@pytest.fixture
def polling_station_result(polling_station):
    return PollingStationResult.objects.create(
        polling_station=polling_station,
        election_type="Legislative",
        year=2026,
        abstentions=10,
        blank_votes=5,
        null_votes=3
    )

@pytest.fixture
def vote_count(polling_station_result, candidate_registration, user):
    return VoteCount.objects.create(
        polling_result=polling_station_result,
        candidate_registration=candidate_registration,
        total_votes=100,
        user=user
    )


# ==========================================
# USER SERIALIZER TESTS
# ==========================================

@pytest.mark.django_db
class TestUserSerializer:
    
    def test_user_serializer_fields(self, user):
        serializer = UserSerializer(user)
        data = serializer.data
        
        assert 'id' in data
        assert 'username' in data
        assert 'email' in data
        assert 'first_name' in data
        assert 'last_name' in data
        assert 'is_active' in data
        assert 'date_joined' in data
        assert 'password' not in data  # Should not be exposed
    
    def test_user_serializer_read_only_fields(self):
        data = {
            'id': 999,
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        serializer = UserSerializer(data=data)
        assert serializer.is_valid()
        
        # id should be ignored (read-only)
        assert 'id' not in serializer.validated_data


# ==========================================
# GEOGRAPHIC HIERARCHY SERIALIZER TESTS
# ==========================================

@pytest.mark.django_db
class TestGeographicSerializers:
    
    def test_district_serializer(self, district):
        serializer = DistrictSerializer(district)
        data = serializer.data
        
        assert data['id'] == district.id
        assert data['name'] == district.name
        assert 'circles_count' in data
        assert data['circles_count'] == 0
    
    def test_district_serializer_with_circles(self, district, electoral_circle):
        serializer = DistrictSerializer(district)
        data = serializer.data
        
        assert data['circles_count'] == 1
    
    def test_electoral_circle_serializer(self, electoral_circle):
        serializer = ElectoralCircleSerializer(electoral_circle)
        data = serializer.data
        
        assert data['id'] == electoral_circle.id
        assert data['district'] == electoral_circle.district.id
        assert data['district_name'] == electoral_circle.district.name
        assert data['name'] == electoral_circle.name
        assert data['constituencies_count'] == 0
    
    def test_constituency_serializer(self, constituency):
        serializer = ConstituencySerializer(constituency)
        data = serializer.data
        
        assert data['id'] == constituency.id
        assert data['circle'] == constituency.circle.id
        assert data['circle_name'] == constituency.circle.name
        assert data['district_name'] == constituency.circle.district.name
        assert data['code'] == constituency.code
        assert data['name'] == constituency.name
        assert data['polling_stations_count'] == 0
    
    def test_polling_station_serializer(self, polling_station):
        serializer = PollingStationSerializer(polling_station)
        data = serializer.data
        
        assert data['id'] == polling_station.id
        assert data['constituency'] == polling_station.constituency.id
        assert data['constituency_code'] == polling_station.constituency.code
        assert data['station_number'] == polling_station.station_number
        assert data['name'] == polling_station.name
        assert 'full_name' in data
        assert data['full_name'] == f"{polling_station.constituency.code} | Mesa {polling_station.station_number}"


# ==========================================
# CANDIDATES & ELECTION SERIALIZER TESTS
# ==========================================

@pytest.mark.django_db
class TestCandidatesAndElectionSerializers:
    
    def test_contender_serializer(self, contender):
        serializer = ContenderSerializer(contender)
        data = serializer.data
        
        assert data['id'] == contender.id
        assert data['name'] == contender.name
        assert data['slug'] == contender.slug
    
    def test_candidate_registration_serializer(self, candidate_registration):
        serializer = CandidateRegistrationSerializer(candidate_registration)
        data = serializer.data
        
        assert data['id'] == candidate_registration.id
        assert data['contender'] == candidate_registration.contender.id
        assert data['contender_name'] == candidate_registration.contender.name
        assert data['contender_slug'] == candidate_registration.contender.slug
        assert data['election_type'] == candidate_registration.election_type
        assert data['year'] == candidate_registration.year
        assert data['representative_name'] == candidate_registration.representative_name


# ==========================================
# TRANSACTION LAYER SERIALIZER TESTS
# ==========================================

@pytest.mark.django_db
class TestTransactionSerializers:
    
    def test_polling_station_result_serializer(self, polling_station_result):
        serializer = PollingStationResultSerializer(polling_station_result)
        data = serializer.data
        
        assert data['id'] == polling_station_result.id
        assert data['polling_station'] == polling_station_result.polling_station.id
        assert 'polling_station_full_name' in data
        assert 'constituency_code' in data
        assert data['election_type'] == polling_station_result.election_type
        assert data['year'] == polling_station_result.year
        assert data['abstentions'] == polling_station_result.abstentions
        assert data['blank_votes'] == polling_station_result.blank_votes
        assert data['null_votes'] == polling_station_result.null_votes
        assert 'total_votes' in data
        assert 'valid_votes' in data
    
    def test_polling_station_result_serializer_total_votes(self, polling_station_result, vote_count):
        serializer = PollingStationResultSerializer(polling_station_result)
        data = serializer.data
        
        assert data['total_votes'] == 100
        assert data['valid_votes'] == 100
    
    def test_vote_count_serializer(self, vote_count):
        serializer = VoteCountSerializer(vote_count)
        data = serializer.data
        
        assert data['id'] == vote_count.id
        assert data['polling_result'] == vote_count.polling_result.id
        assert data['candidate_registration'] == vote_count.candidate_registration.id
        assert data['contender_name'] == vote_count.candidate_registration.contender.name
        assert data['contender_slug'] == vote_count.candidate_registration.contender.slug
        assert data['total_votes'] == vote_count.total_votes
        assert data['user'] == vote_count.user.id
        assert data['user_username'] == vote_count.user.username
    
    def test_vote_count_serializer_validation(self, polling_station_result, contender):
        """Test that VoteCountSerializer validates election type match."""
        # Create a candidate registration with different election type
        different_registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Presidential",
            year=2026,
            representative_name="Jane Doe"
        )
        
        # Create data for the serializer
        data = {
            'candidate_registration': different_registration.id,
            'total_votes': 100
        }
        
        # We need to test validation at the model level or by creating a vote count
        # Since polling_result is read-only, the serializer won't validate it
        
        # Option 1: Test the model's clean method directly
        vote_count = VoteCount(
            polling_result=polling_station_result,
            candidate_registration=different_registration,
            total_votes=100
        )
        
        with pytest.raises(ValidationError) as excinfo:
            vote_count.full_clean()
        
        assert "not registered for this specific election type and year" in str(excinfo.value)
        
        


# ==========================================
# ACCUMULATED RESULT SERIALIZER TESTS
# ==========================================

@pytest.mark.django_db
class TestAccumulatedResultSerializer:
    
    def test_serializer_fields(self, candidate_registration):
        result = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000,
            estimated_seats=10
        )
        
        serializer = AccumulatedResultSerializer(result)
        data = serializer.data
        
        assert data['id'] == result.id
        assert data['scope'] == result.scope
        assert data['candidate_registration'] == result.candidate_registration.id
        assert data['contender_name'] == result.candidate_registration.contender.name
        assert data['contender_slug'] == result.candidate_registration.contender.slug
        assert data['election_type'] == result.election_type
        assert data['year'] == result.year
        assert data['total_votes'] == result.total_votes
        assert data['estimated_seats'] == result.estimated_seats
        assert data['district'] is None
        assert data['circle'] is None
        assert data['constituency'] is None
    
    def test_serializer_with_district(self, candidate_registration, district):
        result = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        serializer = AccumulatedResultSerializer(result)
        data = serializer.data
        
        assert data['district'] == district.id
        assert data['district_name'] == district.name
        assert data['circle'] is None
        assert data['constituency'] is None
    
    def test_serializer_validation_national(self, candidate_registration):
        """Test that National scope validation works."""
        data = {
            'scope': 'National',
            'candidate_registration': candidate_registration.id,
            'election_type': 'Legislative',
            'year': 2026,
            'total_votes': 1000,
            'district': None,
            'circle': None,
            'constituency': None
        }
        
        serializer = AccumulatedResultSerializer(data=data)
        assert serializer.is_valid()
    
    def test_serializer_validation_national_with_district(self, candidate_registration, district):
        """Test that National scope with district raises validation error."""
        data = {
            'scope': 'National',
            'candidate_registration': candidate_registration.id,
            'election_type': 'Legislative',
            'year': 2026,
            'total_votes': 1000,
            'district': district.id,
            'circle': None,
            'constituency': None
        }
        
        serializer = AccumulatedResultSerializer(data=data)
        assert not serializer.is_valid()
        assert 'non_field_errors' in serializer.errors
    
    def test_serializer_validation_district(self, candidate_registration, district):
        """Test that District scope validation works."""
        data = {
            'scope': 'District',
            'district': district.id,
            'candidate_registration': candidate_registration.id,
            'election_type': 'Legislative',
            'year': 2026,
            'total_votes': 500,
            'circle': None,
            'constituency': None
        }
        
        serializer = AccumulatedResultSerializer(data=data)
        assert serializer.is_valid()
    
    def test_serializer_validation_district_without_district(self, candidate_registration):
        """Test that District scope without district raises validation error."""
        data = {
            'scope': 'District',
            'candidate_registration': candidate_registration.id,
            'election_type': 'Legislative',
            'year': 2026,
            'total_votes': 500,
            'district': None,
            'circle': None,
            'constituency': None
        }
        
        serializer = AccumulatedResultSerializer(data=data)
        assert not serializer.is_valid()
        assert 'non_field_errors' in serializer.errors


# ==========================================
# POLLING STATION RESULT WITH VOTES TESTS
# ==========================================

@pytest.mark.django_db
class TestPollingStationResultWithVotesSerializer:
    
    def test_serializer_fields(self, polling_station_result):
        serializer = PollingStationResultWithVotesSerializer(polling_station_result)
        data = serializer.data
        
        assert data['id'] == polling_station_result.id
        assert data['polling_station'] == polling_station_result.polling_station.id
        assert data['election_type'] == polling_station_result.election_type
        assert data['year'] == polling_station_result.year
        assert data['abstentions'] == polling_station_result.abstentions
        assert data['blank_votes'] == polling_station_result.blank_votes
        assert data['null_votes'] == polling_station_result.null_votes
        assert 'votes' in data
        assert isinstance(data['votes'], list)
    
    def test_create_with_votes(self, polling_station, contender):
        """Test creating a PollingStationResult with nested VoteCounts."""
        registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="John Doe"
        )
        
        data = {
            'polling_station': polling_station.id,
            'election_type': 'Legislative',
            'year': 2026,
            'abstentions': 10,
            'blank_votes': 5,
            'null_votes': 3,
            'votes': [
                {
                    'candidate_registration': registration.id,
                    'total_votes': 100,
                    'user': None
                }
            ]
        }
        
        serializer = PollingStationResultWithVotesSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        result = serializer.save()
        
        assert result.id is not None
        assert result.votes.count() == 1
        assert result.votes.first().total_votes == 100
    
    def test_update_with_votes(self, polling_station_result, candidate_registration):
        """Test updating a PollingStationResult with nested VoteCounts."""
        # Create initial vote
        VoteCount.objects.create(
            polling_result=polling_station_result,
            candidate_registration=candidate_registration,
            total_votes=100
        )
        
        # Update data
        data = {
            'polling_station': polling_station_result.polling_station.id,
            'election_type': 'Legislative',
            'year': 2026,
            'abstentions': 20,
            'blank_votes': 10,
            'null_votes': 5,
            'votes': [
                {
                    'candidate_registration': candidate_registration.id,
                    'total_votes': 150,
                    'user': None
                }
            ]
        }
        
        serializer = PollingStationResultWithVotesSerializer(
            polling_station_result, 
            data=data,
            partial=True  # Allow partial updates
        )
        assert serializer.is_valid(), serializer.errors
        result = serializer.save()
        
        assert result.abstentions == 20
        assert result.votes.count() == 1
        assert result.votes.first().total_votes == 150
    
    def test_create_with_multiple_votes(self, polling_station, contender):
        """Test creating a PollingStationResult with multiple VoteCounts."""
        registration1 = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="Candidate A"
        )
        
        contender2 = Contender.objects.create(name="Party B", slug="PB")
        registration2 = CandidateRegistration.objects.create(
            contender=contender2,
            election_type="Legislative",
            year=2026,
            representative_name="Candidate B"
        )
        
        data = {
            'polling_station': polling_station.id,
            'election_type': 'Legislative',
            'year': 2026,
            'abstentions': 10,
            'blank_votes': 5,
            'null_votes': 3,
            'votes': [
                {
                    'candidate_registration': registration1.id,
                    'total_votes': 150,
                    'user': None
                },
                {
                    'candidate_registration': registration2.id,
                    'total_votes': 100,
                    'user': None
                }
            ]
        }
        
        serializer = PollingStationResultWithVotesSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        result = serializer.save()
        
        assert result.votes.count() == 2
        total = sum(vote.total_votes for vote in result.votes.all())
        assert total == 250


# ==========================================
# SUMMARY SERIALIZER TESTS
# ==========================================

@pytest.mark.django_db
class TestSummarySerializers:
    
    def test_election_summary_serializer(self):
        from poll.serializers import ElectionSummarySerializer
        
        data = {
            'election_type': 'Legislative',
            'year': 2026,
            'total_polling_stations': 10,
            'total_registered_voters': 1000,
            'total_abstentions': 100,
            'total_blank_votes': 50,
            'total_null_votes': 30,
            'total_valid_votes': 820,
            'total_votes': 900,
            'turnout_percentage': 90.0
        }
        
        serializer = ElectionSummarySerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        
        # Test serialization
        serialized = ElectionSummarySerializer(data).data
        assert serialized['election_type'] == 'Legislative'
        assert serialized['year'] == 2026
        assert serialized['turnout_percentage'] == 90.0
    
    def test_candidate_ranking_serializer(self, candidate_registration):
        from poll.serializers import CandidateRankingSerializer
        
        data = {
            'candidate_registration': candidate_registration,
            'total_votes': 1000,
            'percentage': 45.5,
            'estimated_seats': 25
        }
        
        # Note: This is a serializer for serializing data, not for deserializing
        # So we need to create the data structure differently
        ranking_data = {
            'candidate_registration': candidate_registration,
            'total_votes': 1000,
            'percentage': 45.5,
            'estimated_seats': 25
        }
        
        # For testing the serializer output, we need a properly structured object
        class MockObject:
            pass
        
        mock_obj = MockObject()
        mock_obj.candidate_registration = candidate_registration
        mock_obj.total_votes = 1000
        mock_obj.percentage = 45.5
        mock_obj.estimated_seats = 25
        
        serializer = CandidateRankingSerializer(mock_obj)
        serialized = serializer.data
        
        assert serialized['candidate'] == candidate_registration.contender.name
        assert serialized['slug'] == candidate_registration.contender.slug
        assert serialized['total_votes'] == 1000
        assert serialized['percentage'] == 45.5
        assert serialized['estimated_seats'] == 25


# ==========================================
# SERIALIZER INTEGRATION TESTS
# ==========================================

@pytest.mark.django_db
class TestSerializerIntegration:
    
    def test_full_workflow(self, polling_station, user):
        """Test the full workflow from creating a result with votes."""
        # Create contender and registration
        contender = Contender.objects.create(name="Party A", slug="PA")
        registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="Candidate A"
        )
        
        # Create polling station result with votes using nested serializer
        data = {
            'polling_station': polling_station.id,
            'election_type': 'Legislative',
            'year': 2026,
            'abstentions': 10,
            'blank_votes': 5,
            'null_votes': 3,
            'votes': [
                {
                    'candidate_registration': registration.id,
                    'total_votes': 100,
                    'user': user.id
                }
            ]
        }
        
        serializer = PollingStationResultWithVotesSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        result = serializer.save()
        
        # Verify everything was created
        assert PollingStationResult.objects.count() == 1
        assert VoteCount.objects.count() == 1
        
        # Retrieve and verify using serializers
        result_serializer = PollingStationResultSerializer(result)
        result_data = result_serializer.data
        assert result_data['total_votes'] == 100
        
        vote = VoteCount.objects.first()
        vote_serializer = VoteCountSerializer(vote)
        vote_data = vote_serializer.data
        assert vote_data['total_votes'] == 100
        assert vote_data['user_username'] == user.username
    
    def test_accumulated_result_workflow(self, candidate_registration, district):
        """Test creating accumulated results for different scopes."""
        # Create district result
        district_result = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        # Create national result
        national_result = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        
        # Serialize both
        district_serializer = AccumulatedResultSerializer(district_result)
        national_serializer = AccumulatedResultSerializer(national_result)
        
        assert district_serializer.data['total_votes'] == 500
        assert district_serializer.data['district_name'] == district.name
        assert national_serializer.data['total_votes'] == 1000
        assert national_serializer.data['district'] is None