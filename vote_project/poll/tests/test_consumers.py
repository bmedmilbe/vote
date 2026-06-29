# poll/tests/test_consumers.py
import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken

from vote.asgi import application
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

# Use in-memory channel layer for testing
TEST_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}


# ==========================================
# HELPER FUNCTIONS
# ==========================================

@database_sync_to_async
def create_user(username, password, role='citizen', email=None):
    """Create a user with specified role and group."""
    if not email:
        email = f"{username}@example.com"
    
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        role=role
    )
    
    # Create user group (following taxi project pattern)
    user_group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(user_group)
    user.save()
    
    # Create access token
    access = AccessToken.for_user(user)
    
    return user, access


@database_sync_to_async
def create_geographic_data():
    """Create test geographic data."""
    district = District.objects.create(name="Água Grande")
    circle = ElectoralCircle.objects.create(
        district=district,
        name="Círculo 1"
    )
    constituency = Constituency.objects.create(
        circle=circle,
        code="AG01",
        name="Constituição 1"
    )
    station = PollingStation.objects.create(
        constituency=constituency,
        station_number=1,
        name="Escola Pantufo - Mesa 1"
    )
    return district, circle, constituency, station


@database_sync_to_async
def create_candidate_data():
    """Create test candidate data."""
    contender = Contender.objects.create(
        name="Independent Democratic Action",
        slug="ADI"
    )
    registration = CandidateRegistration.objects.create(
        contender=contender,
        election_type="Legislative",
        year=2026,
        representative_name="John Doe"
    )
    return contender, registration


@database_sync_to_async
def create_polling_result(polling_station, registration, user):
    """Create a polling station result with votes."""
    result = PollingStationResult.objects.create(
        polling_station=polling_station,
        election_type="Legislative",
        year=2026,
        abstentions=10,
        blank_votes=5,
        null_votes=3
    )
    
    vote = VoteCount.objects.create(
        polling_result=result,
        candidate_registration=registration,
        total_votes=100,
        user=user
    )
    
    return result, vote


@database_sync_to_async
def create_accumulated_result(registration):
    """Create an accumulated result."""
    return AccumulatedResult.objects.create(
        scope="National",
        candidate_registration=registration,
        election_type="Legislative",
        year=2026,
        total_votes=1000,
        estimated_seats=10
    )


# ==========================================
# WEBSOCKET TESTS
# ==========================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestElectionWebSocket:
    """Test ElectionConsumer WebSocket connections."""
    
    async def test_can_connect_to_server(self, settings):
        """Test that authenticated users can connect."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('testuser', 'testpass123', 'citizen')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={access}'
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()
    
    async def test_cannot_connect_without_token(self, settings):
        """Test that unauthenticated users cannot connect."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        communicator = WebsocketCommunicator(
            application=application,
            path='/ws/election/'
        )
        connected, _ = await communicator.connect()
        assert connected is False
    
    async def test_can_get_results(self, settings):
        """Test getting results via WebSocket."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        user, access = await create_user('testuser', 'testpass123', 'citizen')
        contender, registration = await create_candidate_data()
        await create_accumulated_result(registration)
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'type': 'get_results',
            'election_type': 'Legislative',
            'year': 2026,
            'scope': 'National'
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'results_update'
        assert 'data' in response
        
        await communicator.disconnect()
    
    async def test_can_subscribe_to_election(self, settings):
        """Test subscribing to an election."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        user, access = await create_user('testuser', 'testpass123', 'citizen')
        contender, registration = await create_candidate_data()
        await create_accumulated_result(registration)
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'type': 'subscribe_to_election',
            'election_type': 'Legislative',
            'year': 2026
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'subscription_confirmed'
        assert response['election_type'] == 'Legislative'
        assert response['year'] == 2026
        
        await communicator.disconnect()
    
    async def test_citizen_cannot_send_vote_update(self, settings):
        """Test that citizens cannot send vote updates."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        user, access = await create_user('citizen', 'testpass123', 'citizen')
        contender, registration = await create_candidate_data()
        district, circle, constituency, station = await create_geographic_data()
        result, vote = await create_polling_result(station, registration, user)
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'type': 'vote_update',
            'polling_result_id': result.id,
            'votes': []
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'
        assert 'permission' in response['message'].lower()
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestStaffWebSocket:
    """Test ElectoralStaffConsumer WebSocket connections."""
    
    async def test_staff_can_connect(self, settings):
        """Test that electoral staff can connect."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('staff', 'testpass123', 'electoral_staff')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()
    
    async def test_admin_can_connect(self, settings):
        """Test that admin can connect."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('admin', 'testpass123', 'admin')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()
    
    async def test_citizen_cannot_connect_to_staff(self, settings):
        """Test that citizens cannot connect to staff WebSocket."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('citizen', 'testpass123', 'citizen')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        connected, _ = await communicator.connect()
        assert connected is False
    
    async def test_staff_can_create_result(self, settings):
        """Test that staff can create a polling station result."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        # Create staff user
        user, access = await create_user('staff', 'testpass123', 'electoral_staff')
        
        # Create test data
        contender, registration = await create_candidate_data()
        district, circle, constituency, station = await create_geographic_data()
        
        # Connect
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        await communicator.connect()
        
        # Send create_result message
        await communicator.send_json_to({
            'action': 'create_result',
            'result_data': {
                'polling_station': station.id,
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
        })
        
        # Receive response - should be 'result_created'
        response = await communicator.receive_json_from()
        assert response['type'] == 'result_created'
        assert 'data' in response
        assert response['data']['polling_station'] == station.id
        
        await communicator.disconnect()
    
    async def test_staff_can_update_votes(self, settings):
        """Test that staff can update vote counts."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        user, access = await create_user('staff', 'testpass123', 'electoral_staff')
        contender, registration = await create_candidate_data()
        district, circle, constituency, station = await create_geographic_data()
        result, vote = await create_polling_result(station, registration, user)
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'action': 'update_votes',
            'polling_result_id': result.id,
            'votes': [
                {
                    'candidate_registration_id': registration.id,
                    'total_votes': 200
                }
            ]
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'votes_updated'
        assert 'data' in response
        
        await communicator.disconnect()
    
    async def test_staff_can_get_pending_results(self, settings):
        """Test that staff can get pending results."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        user, access = await create_user('staff', 'testpass123', 'electoral_staff')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'action': 'get_pending_results',
            'election_type': 'Legislative',
            'year': 2026
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'pending_results'
        assert 'data' in response
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketBroadcast:
    """Test WebSocket broadcast functionality."""
    
    async def test_broadcast_to_all_clients(self, settings):
        """Test that messages are broadcast to all connected clients."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        staff_user, staff_access = await create_user('staff', 'testpass123', 'electoral_staff')
        citizen_user, citizen_access = await create_user('citizen', 'testpass123', 'citizen')
        
        contender, registration = await create_candidate_data()
        district, circle, constituency, station = await create_geographic_data()
        result, vote = await create_polling_result(station, registration, staff_user)
        await create_accumulated_result(registration)
        
        # Connect staff
        staff_communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={staff_access}'
        )
        await staff_communicator.connect()
        
        # Connect citizen
        citizen_communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={citizen_access}'
        )
        await citizen_communicator.connect()
        
        # Subscribe citizen to updates
        await citizen_communicator.send_json_to({
            'type': 'subscribe_to_election',
            'election_type': 'Legislative',
            'year': 2026
        })
        
        sub_response = await citizen_communicator.receive_json_from()
        assert sub_response['type'] == 'subscription_confirmed'
        
        # Staff sends vote update
        await staff_communicator.send_json_to({
            'action': 'update_votes',
            'polling_result_id': result.id,
            'votes': [
                {
                    'candidate_registration_id': registration.id,
                    'total_votes': 300
                }
            ]
        })
        
        staff_response = await staff_communicator.receive_json_from()
        assert staff_response['type'] == 'votes_updated'
        
        await staff_communicator.disconnect()
        await citizen_communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketErrorHandling:
    """Test WebSocket error handling."""
    
    async def test_invalid_json(self, settings):
        """Test handling of invalid JSON."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('testuser', 'testpass123', 'citizen')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_to(text_data='invalid json')
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'
        assert 'json' in response['message'].lower()
        
        await communicator.disconnect()
    
    async def test_unknown_message_type(self, settings):
        """Test handling of unknown message types."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('testuser', 'testpass123', 'citizen')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/election/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'type': 'unknown_type'
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'
        assert 'unknown' in response['message'].lower()
        
        await communicator.disconnect()
    
    async def test_staff_unknown_action(self, settings):
        """Test handling of unknown actions in staff consumer."""
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        
        _, access = await create_user('staff', 'testpass123', 'electoral_staff')
        
        communicator = WebsocketCommunicator(
            application=application,
            path=f'/ws/staff/?token={access}'
        )
        await communicator.connect()
        
        await communicator.send_json_to({
            'action': 'unknown_action'
        })
        
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'
        assert 'unknown' in response['message'].lower()
        
        await communicator.disconnect()


