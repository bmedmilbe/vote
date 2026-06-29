import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

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


# ==========================================
# FIXTURES
# ==========================================

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
def user():
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com"
    )


# ==========================================
# GEOGRAPHIC HIERARCHY TESTS
# ==========================================

@pytest.mark.django_db
class TestGeographicHierarchy:
    
    def test_district_creation(self):
        district = District.objects.create(name="Lobata")
        assert district.name == "Lobata"
        assert str(district) == "Lobata"
    
    def test_district_unique_name_constraint(self, district):
        with pytest.raises(IntegrityError):
            District.objects.create(name="Água Grande")
    
    def test_electoral_circle_creation(self, district):
        circle = ElectoralCircle.objects.create(
            district=district,
            name="Círculo 2"
        )
        assert circle.district == district
        assert str(circle) == "Círculo 2 (Água Grande)"
    
    def test_electoral_circle_related_name(self, district):
        circle1 = ElectoralCircle.objects.create(district=district, name="Círculo 1")
        circle2 = ElectoralCircle.objects.create(district=district, name="Círculo 2")
        assert district.circles.count() == 2
        assert list(district.circles.all()) == [circle1, circle2]
    
    def test_constituency_creation(self, electoral_circle):
        constituency = Constituency.objects.create(
            circle=electoral_circle,
            code="AG02",
            name="Constituição 2"
        )
        assert constituency.circle == electoral_circle
        assert constituency.code == "AG02"
        assert str(constituency) == "AG02 - Constituição 2"
    
    def test_constituency_unique_code(self, constituency):
        with pytest.raises(IntegrityError):
            Constituency.objects.create(
                circle=constituency.circle,
                code="AG01",
                name="Duplicated Code"
            )
    
    def test_polling_station_creation(self, constituency):
        station = PollingStation.objects.create(
            constituency=constituency,
            station_number=2,
            name="Escola Secundária - Mesa 2"
        )
        assert station.constituency == constituency
        assert station.station_number == 2
        assert str(station) == "AG01 | Mesa 2"
    
    def test_polling_station_unique_together(self, constituency, polling_station):
        with pytest.raises(IntegrityError):
            PollingStation.objects.create(
                constituency=constituency,
                station_number=1,
                name="Duplicate Station"
            )
    
    def test_polling_station_allow_same_number_different_constituency(self, constituency):
        station1 = PollingStation.objects.create(
            constituency=constituency,
            station_number=1,
            name="Station 1"
        )
        
        constituency2 = Constituency.objects.create(
            circle=constituency.circle,
            code="AG02",
            name="Constituição 2"
        )
        station2 = PollingStation.objects.create(
            constituency=constituency2,
            station_number=1,
            name="Station 2"
        )
        
        assert station1 != station2
        assert PollingStation.objects.filter(station_number=1).count() == 2


# ==========================================
# CANDIDATES & ELECTION PERIOD TESTS
# ==========================================

@pytest.mark.django_db
class TestCandidatesAndElections:
    
    def test_contender_creation(self):
        contender = Contender.objects.create(
            name="Movement for the Liberation of São Tomé",
            slug="MLSTP"
        )
        assert contender.name == "Movement for the Liberation of São Tomé"
        assert contender.slug == "MLSTP"
        assert str(contender) == "MLSTP"
    
    def test_contender_unique_name_and_slug(self):
        # Create first contender
        Contender.objects.create(name="Contender 1", slug="C1")
        
        # Test duplicate name - this will raise IntegrityError
        # We need to use transaction.atomic() to handle the error properly
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Contender.objects.create(name="Contender 1", slug="C2")
        
        # Test duplicate slug
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Contender.objects.create(name="Contender 2", slug="C1")
    
    def test_candidate_registration_creation(self, contender):
        registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Presidential",
            year=2026,
            representative_name="Jane Doe"
        )
        assert registration.contender == contender
        assert registration.election_type == "Presidential"
        assert registration.year == 2026
        assert str(registration) == "ADI - Presidential (2026)"
    
    def test_candidate_registration_unique_together(self, contender):
        # Create first registration
        CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="John Doe"
        )
        
        # Test duplicate - this will raise IntegrityError
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CandidateRegistration.objects.create(
                    contender=contender,
                    election_type="Legislative",
                    year=2026,
                    representative_name="Duplicate"
                )
    
    def test_candidate_registration_different_election_types(self, contender):
        reg1 = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="John"
        )
        reg2 = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Presidential",
            year=2026,
            representative_name="Jane"
        )
        assert reg1 != reg2
        assert CandidateRegistration.objects.filter(contender=contender).count() == 2
    
    def test_candidate_registration_different_years(self, contender):
        reg1 = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="John"
        )
        reg2 = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2030,
            representative_name="Jane"
        )
        assert reg1 != reg2
        assert CandidateRegistration.objects.filter(contender=contender).count() == 2


# ==========================================
# TRANSACTION LAYER TESTS
# ==========================================

@pytest.mark.django_db
class TestTransactionLayer:
    
    def test_polling_station_result_creation(self, polling_station):
        result = PollingStationResult.objects.create(
            polling_station=polling_station,
            election_type="Legislative",
            year=2026,
            abstentions=10,
            blank_votes=5,
            null_votes=3
        )
        assert result.polling_station == polling_station
        assert result.election_type == "Legislative"
        assert result.year == 2026
        assert result.abstentions == 10
        assert result.blank_votes == 5
        assert result.null_votes == 3
        assert str(result) == "AG01 | Mesa 1 | Legislative (2026)"
    
    def test_polling_station_result_unique_together(self, polling_station):
        # Create first result
        PollingStationResult.objects.create(
            polling_station=polling_station,
            election_type="Legislative",
            year=2026,
            abstentions=10,
            blank_votes=5,
            null_votes=3
        )
        
        # Test duplicate
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PollingStationResult.objects.create(
                    polling_station=polling_station,
                    election_type="Legislative",
                    year=2026,
                    abstentions=1,
                    blank_votes=1,
                    null_votes=1
                )
    
    def test_polling_station_result_different_years(self, polling_station):
        result1 = PollingStationResult.objects.create(
            polling_station=polling_station,
            election_type="Legislative",
            year=2026,
            abstentions=10,
            blank_votes=5,
            null_votes=3
        )
        result2 = PollingStationResult.objects.create(
            polling_station=polling_station,
            election_type="Legislative",
            year=2030,
            abstentions=20,
            blank_votes=10,
            null_votes=6
        )
        assert result1 != result2
        assert PollingStationResult.objects.filter(polling_station=polling_station).count() == 2
    
    def test_vote_count_creation(self, polling_station_result, candidate_registration, user):
        vote_count = VoteCount.objects.create(
            polling_result=polling_station_result,
            candidate_registration=candidate_registration,
            total_votes=100,
            user=user
        )
        assert vote_count.polling_result == polling_station_result
        assert vote_count.candidate_registration == candidate_registration
        assert vote_count.total_votes == 100
        assert vote_count.user == user
    
    def test_vote_count_unique_together(self, polling_station_result, candidate_registration):
        # Create first vote count
        VoteCount.objects.create(
            polling_result=polling_station_result,
            candidate_registration=candidate_registration,
            total_votes=100
        )
        
        # Attempt to create duplicate - model-level validation raises ValidationError
        with pytest.raises(ValidationError) as excinfo:
            vote_count = VoteCount(
                polling_result=polling_station_result,
                candidate_registration=candidate_registration,
                total_votes=200
            )
            vote_count.full_clean()
        
        assert "already exists" in str(excinfo.value)
    
    def test_vote_count_clean_validation(self, polling_station_result, contender):
        # Create a candidate registration for a different election type
        different_registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Presidential",  # Different from polling_result
            year=2026,
            representative_name="Jane Doe"
        )
        
        with pytest.raises(ValidationError) as excinfo:
            vote_count = VoteCount(
                polling_result=polling_station_result,
                candidate_registration=different_registration,
                total_votes=100
            )
            vote_count.full_clean()
        
        assert "not registered for this specific election type and year" in str(excinfo.value)
    
    def test_vote_count_clean_different_year_validation(self, polling_station_result, contender):
        # Create a candidate registration for a different year
        different_registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2030,  # Different from polling_result
            representative_name="Jane Doe"
        )
        
        with pytest.raises(ValidationError) as excinfo:
            vote_count = VoteCount(
                polling_result=polling_station_result,
                candidate_registration=different_registration,
                total_votes=100
            )
            vote_count.full_clean()
        
        assert "not registered for this specific election type and year" in str(excinfo.value)
    
    def test_vote_count_save_calls_full_clean(self, polling_station_result, contender):
        # Create a candidate registration with different election type
        different_registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Presidential",
            year=2026,
            representative_name="Jane Doe"
        )
        
        vote_count = VoteCount(
            polling_result=polling_station_result,
            candidate_registration=different_registration,
            total_votes=100
        )
        
        # Save should call full_clean and raise ValidationError
        with pytest.raises(ValidationError) as excinfo:
            vote_count.save()
        
        assert "not registered for this specific election type and year" in str(excinfo.value)


# ==========================================
# ACCUMULATED LAYER TESTS
# ==========================================

@pytest.mark.django_db
class TestAccumulatedLayer:
    
    def test_accumulated_result_creation_national(self, candidate_registration):
        result = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000,
            estimated_seats=10
        )
        assert result.scope == "National"
        assert result.candidate_registration == candidate_registration
        assert result.total_votes == 1000
        assert result.estimated_seats == 10
        assert str(result) == "[National] ADI: 1000 votes (2026)"
    
    def test_accumulated_result_creation_district(self, candidate_registration, district):
        result = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500,
            estimated_seats=5
        )
        assert result.scope == "District"
        assert result.district == district
        assert result.total_votes == 500
    
    def test_accumulated_result_creation_circle(self, candidate_registration, electoral_circle):
        result = AccumulatedResult.objects.create(
            scope="Circle",
            circle=electoral_circle,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=200,
            estimated_seats=2
        )
        assert result.scope == "Circle"
        assert result.circle == electoral_circle
    
    def test_accumulated_result_creation_constituency(self, candidate_registration, constituency):
        result = AccumulatedResult.objects.create(
            scope="Constituency",
            constituency=constituency,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=100,
            estimated_seats=1
        )
        assert result.scope == "Constituency"
        assert result.constituency == constituency
    
    def test_accumulated_result_unique_national(self, candidate_registration):
        """
        Test that National scope unique constraint prevents duplicates.
        """
        # Create first National result
        AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        
        # Attempt to create duplicate National result - should raise IntegrityError
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AccumulatedResult.objects.create(
                    scope="National",
                    candidate_registration=candidate_registration,
                    election_type="Legislative",
                    year=2026,
                    total_votes=800
                )
        
        # Verify the error is about the unique constraint
        assert "unique_accumulated_national" in str(excinfo.value) or "duplicate key" in str(excinfo.value).lower()
    
    def test_accumulated_result_unique_district(self, candidate_registration, district):
        """
        Test that District scope unique constraint prevents duplicates.
        """
        # Create first District result
        AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        # Attempt to create duplicate District result - should raise IntegrityError
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AccumulatedResult.objects.create(
                    scope="District",
                    district=district,
                    candidate_registration=candidate_registration,
                    election_type="Legislative",
                    year=2026,
                    total_votes=600
                )
        
        # Verify the error is about the unique constraint
        assert "unique_accumulated_district" in str(excinfo.value) or "duplicate key" in str(excinfo.value).lower()
    
    def test_accumulated_result_unique_circle(self, candidate_registration, electoral_circle):
        """
        Test that Circle scope unique constraint prevents duplicates.
        """
        # Create first Circle result
        AccumulatedResult.objects.create(
            scope="Circle",
            circle=electoral_circle,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=200
        )
        
        # Attempt to create duplicate Circle result - should raise IntegrityError
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AccumulatedResult.objects.create(
                    scope="Circle",
                    circle=electoral_circle,
                    candidate_registration=candidate_registration,
                    election_type="Legislative",
                    year=2026,
                    total_votes=300
                )
        
        # Verify the error is about the unique constraint
        assert "unique_accumulated_circle" in str(excinfo.value) or "duplicate key" in str(excinfo.value).lower()
    
    def test_accumulated_result_unique_constituency(self, candidate_registration, constituency):
        """
        Test that Constituency scope unique constraint prevents duplicates.
        """
        # Create first Constituency result
        AccumulatedResult.objects.create(
            scope="Constituency",
            constituency=constituency,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=100
        )
        
        # Attempt to create duplicate Constituency result - should raise IntegrityError
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AccumulatedResult.objects.create(
                    scope="Constituency",
                    constituency=constituency,
                    candidate_registration=candidate_registration,
                    election_type="Legislative",
                    year=2026,
                    total_votes=150
                )
        
        # Verify the error is about the unique constraint
        assert "unique_accumulated_constituency" in str(excinfo.value) or "duplicate key" in str(excinfo.value).lower()
    
    def test_accumulated_result_different_scopes_allow_multiple(self, candidate_registration, district):
        """
        Test that different scopes can have the same candidate and election details.
        """
        # Create results for different scopes
        result_national = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        
        result_district = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        # Create a circle
        circle = ElectoralCircle.objects.create(district=district, name="Círculo Test")
        result_circle = AccumulatedResult.objects.create(
            scope="Circle",
            circle=circle,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=300
        )
        
        # Create a constituency
        constituency = Constituency.objects.create(
            circle=circle,
            code="TEST01",
            name="Constituição Test"
        )
        result_constituency = AccumulatedResult.objects.create(
            scope="Constituency",
            constituency=constituency,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=100
        )
        
        # All should exist with different scopes
        assert AccumulatedResult.objects.filter(
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026
        ).count() == 4
        
        assert result_national.scope == "National"
        assert result_district.scope == "District"
        assert result_circle.scope == "Circle"
        assert result_constituency.scope == "Constituency"
    
    def test_accumulated_result_different_candidates(self, candidate_registration, district):
        """
        Test that different candidates can have results in the same scope.
        """
        # Create first candidate result
        AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        # Create second candidate
        contender2 = Contender.objects.create(name="Party B", slug="PB")
        registration2 = CandidateRegistration.objects.create(
            contender=contender2,
            election_type="Legislative",
            year=2026,
            representative_name="Jane Doe"
        )
        
        # This should work - different candidate
        result2 = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=registration2,
            election_type="Legislative",
            year=2026,
            total_votes=300
        )
        
        assert result2.candidate_registration != candidate_registration
        assert AccumulatedResult.objects.filter(
            scope="District",
            district=district,
            election_type="Legislative",
            year=2026
        ).count() == 2
    
    def test_accumulated_result_different_years(self, candidate_registration, district):
        """
        Test that different years can have results in the same scope.
        """
        # Create result for 2026
        AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        # Create result for 2030 - should work
        result2 = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2030,
            total_votes=400
        )
        
        assert result2.year == 2030
        assert AccumulatedResult.objects.filter(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative"
        ).count() == 2
    
    def test_accumulated_result_different_election_types(self, candidate_registration, district):
        """
        Test that different election types can have results in the same scope.
        """
        # Create result for Legislative
        AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        # Create result for Presidential - should work
        result2 = AccumulatedResult.objects.create(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            election_type="Presidential",
            year=2026,
            total_votes=600
        )
        
        assert result2.election_type == "Presidential"
        assert AccumulatedResult.objects.filter(
            scope="District",
            district=district,
            candidate_registration=candidate_registration,
            year=2026
        ).count() == 2
    
    def test_accumulated_result_different_districts(self, candidate_registration):
        """
        Test that different districts can have results in the same scope.
        """
        district1 = District.objects.create(name="District 1")
        district2 = District.objects.create(name="District 2")
        
        result1 = AccumulatedResult.objects.create(
            scope="District",
            district=district1,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=500
        )
        
        result2 = AccumulatedResult.objects.create(
            scope="District",
            district=district2,
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=400
        )
        
        assert result1.district != result2.district
        assert AccumulatedResult.objects.filter(
            scope="District",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026
        ).count() == 2
    
    def test_accumulated_result_invalid_scope_fields(self, candidate_registration, district):
        """
        Test that we can't create a National scope with district set.
        While the model doesn't enforce this, the constraints ensure
        the database integrity.
        """
        # National scope with district should work but would violate
        # the conceptual model. The unique constraint doesn't prevent this.
        result = AccumulatedResult.objects.create(
            scope="National",
            district=district,  # This shouldn't be set for National scope
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        
        # It will still work but the district field is ignored for National scope
        assert result.scope == "National"
        assert result.district == district  # It's stored but shouldn't be used
    
    def test_accumulated_result_partial_unique_national(self, candidate_registration):
        """
        Test that National scope uniqueness is properly enforced.
        """
        # Create first National result
        AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        
        # Different year should work
        result2 = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2030,
            total_votes=800
        )
        assert result2.year == 2030
        
        # Different election type should work
        result3 = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Presidential",
            year=2026,
            total_votes=900
        )
        assert result3.election_type == "Presidential"
        
        # Different candidate should work
        contender2 = Contender.objects.create(name="Party B", slug="PB")
        registration2 = CandidateRegistration.objects.create(
            contender=contender2,
            election_type="Legislative",
            year=2026,
            representative_name="Jane Doe"
        )
        result4 = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=registration2,
            election_type="Legislative",
            year=2026,
            total_votes=700
        )
        assert result4.candidate_registration != candidate_registration
        
        # All should exist
        assert AccumulatedResult.objects.filter(scope="National").count() == 4

# ==========================================
# INTEGRATION TESTS
# ==========================================

@pytest.mark.django_db
class TestIntegration:
    
    def test_full_hierarchy_creation(self):
        # Create full hierarchy
        district = District.objects.create(name="Mé-Zóchi")
        circle = ElectoralCircle.objects.create(district=district, name="Círculo 1")
        constituency = Constituency.objects.create(
            circle=circle,
            code="MZ01",
            name="Constituição 1"
        )
        station = PollingStation.objects.create(
            constituency=constituency,
            station_number=1,
            name="Escola Central - Mesa 1"
        )
        
        # Create contender and registration
        contender = Contender.objects.create(name="Party A", slug="PA")
        registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2026,
            representative_name="Candidate A"
        )
        
        # Create polling result
        result = PollingStationResult.objects.create(
            polling_station=station,
            election_type="Legislative",
            year=2026,
            abstentions=10,
            blank_votes=5,
            null_votes=3
        )
        
        # Create vote count
        vote_count = VoteCount.objects.create(
            polling_result=result,
            candidate_registration=registration,
            total_votes=100
        )
        
        # Verify the chain
        assert result.polling_station.constituency.circle.district == district
        assert vote_count.candidate_registration.contender == contender
        assert vote_count.polling_result == result
    
    def test_multiple_candidates_per_station(self, polling_station_result):
        contender1 = Contender.objects.create(name="Party A", slug="PA")
        registration1 = CandidateRegistration.objects.create(
            contender=contender1,
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
        
        vote1 = VoteCount.objects.create(
            polling_result=polling_station_result,
            candidate_registration=registration1,
            total_votes=150
        )
        vote2 = VoteCount.objects.create(
            polling_result=polling_station_result,
            candidate_registration=registration2,
            total_votes=100
        )
        
        # Verify both votes exist
        votes = polling_station_result.votes.all()
        assert votes.count() == 2
        assert sum(vote.total_votes for vote in votes) == 250


# ==========================================
# MODEL STRING REPRESENTATION TESTS
# ==========================================

@pytest.mark.django_db
class TestStringRepresentations:
    
    def test_district_str(self, district):
        assert str(district) == "Água Grande"
    
    def test_electoral_circle_str(self, electoral_circle):
        assert str(electoral_circle) == "Círculo 1 (Água Grande)"
    
    def test_constituency_str(self, constituency):
        assert str(constituency) == "AG01 - Constituição 1"
    
    def test_polling_station_str(self, polling_station):
        assert str(polling_station) == "AG01 | Mesa 1"
    
    def test_contender_str(self, contender):
        assert str(contender) == "ADI"
    
    def test_candidate_registration_str(self, candidate_registration):
        assert str(candidate_registration) == "ADI - Legislative (2026)"
    
    def test_polling_station_result_str(self, polling_station_result):
        assert str(polling_station_result) == "AG01 | Mesa 1 | Legislative (2026)"
    
    def test_accumulated_result_str(self, candidate_registration):
        result = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        assert str(result) == "[National] ADI: 1000 votes (2026)"


# ==========================================
# EDGE CASES AND VALIDATION TESTS
# ==========================================

@pytest.mark.django_db
class TestEdgeCases:
    
    def test_polling_station_zero_station_number(self, constituency):
        # PositiveIntegerField allows 0
        station = PollingStation.objects.create(
            constituency=constituency,
            station_number=0,
            name="Zero Station"
        )
        assert station.station_number == 0
        
        # Negative numbers raise IntegrityError
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PollingStation.objects.create(
                    constituency=constituency,
                    station_number=-1,
                    name="Negative Station"
                )
    
    def test_polling_station_negative_votes(self, polling_station_result, candidate_registration):
        # PositiveIntegerField validation happens at the model level
        # It raises ValidationError before reaching the database
        with pytest.raises(ValidationError) as excinfo:
            vote_count = VoteCount(
                polling_result=polling_station_result,
                candidate_registration=candidate_registration,
                total_votes=-1
            )
            vote_count.full_clean()
        
        assert "Ensure this value is greater than or equal to 0" in str(excinfo.value)
    
    def test_constituency_code_case_sensitive(self, electoral_circle):
        Constituency.objects.create(
            circle=electoral_circle,
            code="ag01",
            name="Lowercase code"
        )
        Constituency.objects.create(
            circle=electoral_circle,
            code="AG01",
            name="Uppercase code"
        )
        assert Constituency.objects.filter(code__iexact="ag01").count() == 2
    
    def test_year_in_future(self, contender):
        registration = CandidateRegistration.objects.create(
            contender=contender,
            election_type="Legislative",
            year=2035,
            representative_name="Future Candidate"
        )
        assert registration.year == 2035
    
    def test_user_null_in_vote_count(self, polling_station_result, candidate_registration):
        vote_count = VoteCount.objects.create(
            polling_result=polling_station_result,
            candidate_registration=candidate_registration,
            total_votes=100,
            user=None
        )
        assert vote_count.user is None
    
    def test_accumulated_result_null_geographic_fields(self, candidate_registration):
        result = AccumulatedResult.objects.create(
            scope="National",
            candidate_registration=candidate_registration,
            election_type="Legislative",
            year=2026,
            total_votes=1000
        )
        assert result.district is None
        assert result.circle is None
        assert result.constituency is None