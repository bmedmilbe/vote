# poll/consumers.py - Complete fixed version

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum

from .models import (
    PollingStationResult, 
    VoteCount, 
    AccumulatedResult,
    PollingStation,
    CandidateRegistration,
)
from .serializers import (
    PollingStationResultSerializer,
    WebSocketAccumulatedResultSerializer,
    WebSocketPollingStationResultSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ElectionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time election updates.
    Accessible by all authenticated users (citizens, staff, admin).
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.election_room_name = 'election_updates'
        self.room_group_name = f'election_{self.election_room_name}'
        
        # Get user from scope
        user = self.scope.get('user')
        
        if user and user.is_authenticated:
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            print(f"✅ User {user.username} connected to election updates")
        else:
            print("❌ Unauthenticated connection attempt rejected")
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        user = self.scope.get('user')
        if user and user.is_authenticated:
            print(f"✅ User {user.username} disconnected from election updates")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_results':
                await self.handle_get_results(data)
            elif message_type == 'vote_update':
                await self.handle_vote_update(data)
            elif message_type == 'subscribe_to_election':
                await self.handle_subscribe_to_election(data)
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_get_results(self, data):
        """Handle get_results request."""
        election_type = data.get('election_type', 'Legislative')
        year = data.get('year', 2026)
        scope = data.get('scope', 'National')
        
        results = await self.get_results(election_type, year, scope)
        await self.send(text_data=json.dumps({
            'type': 'results_update',
            'data': results,
            'election_type': election_type,
            'year': year,
            'scope': scope
        }))

    async def handle_vote_update(self, data):
        """Handle vote_update message."""
        user = self.scope.get('user')
        if user and user.is_authenticated and user.role in ['electoral_staff', 'admin']:
            result = await self.process_vote_update(data)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'broadcast_vote_update',
                    'data': result
                }
            )
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You do not have permission to send vote updates'
            }))

    async def handle_subscribe_to_election(self, data):
        """Handle subscription to a specific election."""
        election_type = data.get('election_type', 'Legislative')
        year = data.get('year', 2026)
        
        self.election_type = election_type
        self.year = year
        
        results = await self.get_results(election_type, year, 'National')
        await self.send(text_data=json.dumps({
            'type': 'subscription_confirmed',
            'election_type': election_type,
            'year': year,
            'initial_data': results
        }))

    @database_sync_to_async
    def get_results(self, election_type, year, scope='National'):
        """Get accumulated results from database."""
        try:
            queryset = AccumulatedResult.objects.filter(
                election_type=election_type,
                year=year,
                scope=scope
            ).select_related('candidate_registration__contender')
            
            serializer = WebSocketAccumulatedResultSerializer(queryset, many=True)
            return serializer.data
        except Exception as e:
            logger.error(f"Error getting results: {e}")
            return []

    @database_sync_to_async
    def process_vote_update(self, data):
        """Process a vote update and save to database."""
        try:
            polling_result_id = data.get('polling_result_id')
            votes = data.get('votes', [])
            
            with transaction.atomic():
                polling_result = PollingStationResult.objects.get(id=polling_result_id)
                
                for vote_data in votes:
                    candidate_id = vote_data.get('candidate_registration_id')
                    total_votes = vote_data.get('total_votes', 0)
                    
                    VoteCount.objects.update_or_create(
                        polling_result=polling_result,
                        candidate_registration_id=candidate_id,
                        defaults={'total_votes': total_votes}
                    )
                
                serializer = WebSocketPollingStationResultSerializer(polling_result)
                return {
                    'type': 'vote_update_success',
                    'data': serializer.data,
                    'polling_result_id': polling_result_id
                }
                
        except PollingStationResult.DoesNotExist:
            return {
                'type': 'error',
                'message': f'Polling result {polling_result_id} not found'
            }
        except Exception as e:
            logger.error(f"Error processing vote update: {e}")
            return {
                'type': 'error',
                'message': str(e)
            }

    async def broadcast_vote_update(self, event):
        """Broadcast vote update to all connected clients."""
        await self.send(text_data=json.dumps({
            'type': 'vote_update',
            'data': event['data']
        }))


class ElectoralStaffConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for electoral staff.
    Only accessible by users with 'electoral_staff' or 'admin' role.
    """
    
    async def connect(self):
        """Handle WebSocket connection for staff."""
        user = self.scope.get('user')
        if user and user.is_authenticated and user.role in ['electoral_staff', 'admin']:
            self.room_group_name = 'staff_updates'
            self.user = user
            
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            print(f"✅ Staff {user.username} connected to staff updates")
        else:
            print(f"❌ Unauthorized staff connection attempt")
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection for staff."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        if hasattr(self, 'user'):
            print(f"✅ Staff {self.user.username} disconnected from staff updates")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages from staff."""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'create_result':
                await self.handle_create_result(data)
            elif action == 'update_votes':
                await self.handle_update_votes(data)
            elif action == 'get_pending_results':
                await self.handle_get_pending_results(data)
            elif action == 'verify_result':
                await self.handle_verify_result(data)
            elif action == 'get_station_stats':
                await self.handle_get_station_stats(data)
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown action: {action}'
                }))
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from staff: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing staff message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_create_result(self, data):
        """Handle creating a new polling station result."""
        try:
            result_data = data.get('result_data', {})
            
            # Call the async version
            result = await self.create_polling_result_async(result_data, self.user)
            
            if result:
                await self.send(text_data=json.dumps({
                    'type': 'result_created',
                    'data': result,
                    'message': 'Polling station result created successfully'
                }))
                
                # Broadcast to election consumers
                await self.channel_layer.group_send(
                    'election_election_updates',
                    {
                        'type': 'broadcast_vote_update',
                        'data': {
                            'type': 'new_result',
                            'polling_result_id': result['id']
                        }
                    }
                )
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to create polling result. Please check your data.'
                }))
                
        except Exception as e:
            logger.error(f"Error creating polling result: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def create_polling_result_async(self, validated_data, user):
        """Create a polling station result in the database."""
        try:
            # Get votes data
            votes_data = validated_data.pop('votes', [])
            
            # Create the polling result
            polling_result = PollingStationResult.objects.create(
                polling_station_id=validated_data.get('polling_station'),
                election_type=validated_data.get('election_type'),
                year=validated_data.get('year'),
                abstentions=validated_data.get('abstentions', 0),
                blank_votes=validated_data.get('blank_votes', 0),
                null_votes=validated_data.get('null_votes', 0)
            )
            
            # Create vote counts
            for vote_data in votes_data:
                VoteCount.objects.create(
                    polling_result=polling_result,
                    candidate_registration_id=vote_data.get('candidate_registration'),
                    total_votes=vote_data.get('total_votes', 0),
                    user=user
                )
            
            # Serialize and return
            serializer = PollingStationResultSerializer(polling_result)
            return serializer.data
            
        except Exception as e:
            logger.error(f"Error in create_polling_result_async: {e}")
            return None

    async def handle_update_votes(self, data):
        """Handle updating vote counts."""
        try:
            polling_result_id = data.get('polling_result_id')
            votes = data.get('votes', [])
            
            if not polling_result_id:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'polling_result_id is required'
                }))
                return
            
            updated = await self.update_vote_counts_async(polling_result_id, votes, self.user)
            
            if updated:
                await self.send(text_data=json.dumps({
                    'type': 'votes_updated',
                    'data': updated,
                    'message': 'Votes updated successfully'
                }))
                
                await self.channel_layer.group_send(
                    'election_election_updates',
                    {
                        'type': 'broadcast_vote_update',
                        'data': {
                            'type': 'votes_updated',
                            'polling_result_id': polling_result_id,
                            'data': updated
                        }
                    }
                )
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to update votes'
                }))
                
        except Exception as e:
            logger.error(f"Error updating votes: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def update_vote_counts_async(self, polling_result_id, votes, user):
        """Update vote counts for a polling result."""
        try:
            polling_result = PollingStationResult.objects.get(id=polling_result_id)
            
            with transaction.atomic():
                # Clear existing votes
                polling_result.votes.all().delete()
                
                # Create new votes
                for vote_data in votes:
                    VoteCount.objects.create(
                        polling_result=polling_result,
                        candidate_registration_id=vote_data.get('candidate_registration_id'),
                        total_votes=vote_data.get('total_votes', 0),
                        user=user
                    )
                
                serializer = PollingStationResultSerializer(polling_result)
                return serializer.data
                
        except PollingStationResult.DoesNotExist:
            logger.error(f"Polling result {polling_result_id} not found")
            return None

    async def handle_get_pending_results(self, data):
        """Handle getting pending results."""
        try:
            election_type = data.get('election_type', 'Legislative')
            year = data.get('year', 2026)
            
            pending = await self.get_pending_results_async(election_type, year)
            
            await self.send(text_data=json.dumps({
                'type': 'pending_results',
                'data': pending,
                'count': len(pending)
            }))
            
        except Exception as e:
            logger.error(f"Error getting pending results: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def get_pending_results_async(self, election_type, year):
        """Get results that need verification."""
        results = PollingStationResult.objects.filter(
            election_type=election_type,
            year=year
        ).select_related('polling_station')
        
        # For now, return results with no votes (example of pending)
        pending = [r for r in results if r.votes.count() == 0]
        
        serializer = PollingStationResultSerializer(pending, many=True)
        return serializer.data

    async def handle_verify_result(self, data):
        """Handle verifying a polling station result."""
        try:
            polling_result_id = data.get('polling_result_id')
            verified = data.get('verified', True)
            notes = data.get('notes', '')
            
            if not polling_result_id:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'polling_result_id is required'
                }))
                return
            
            verified_result = await self.verify_polling_result_async(
                polling_result_id, 
                verified, 
                notes,
                self.user
            )
            
            await self.send(text_data=json.dumps({
                'type': 'result_verified',
                'data': verified_result,
                'message': f'Result verified: {verified}'
            }))
            
        except Exception as e:
            logger.error(f"Error verifying result: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def verify_polling_result_async(self, polling_result_id, verified, notes, user):
        """Verify a polling result."""
        try:
            polling_result = PollingStationResult.objects.get(id=polling_result_id)
            serializer = PollingStationResultSerializer(polling_result)
            return serializer.data
        except PollingStationResult.DoesNotExist:
            logger.error(f"Polling result {polling_result_id} not found")
            return None

    async def handle_get_station_stats(self, data):
        """Handle getting statistics for a polling station."""
        try:
            polling_station_id = data.get('polling_station_id')
            
            if not polling_station_id:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'polling_station_id is required'
                }))
                return
            
            stats = await self.get_station_stats_async(polling_station_id)
            
            await self.send(text_data=json.dumps({
                'type': 'station_stats',
                'data': stats
            }))
            
        except Exception as e:
            logger.error(f"Error getting station stats: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def get_station_stats_async(self, polling_station_id):
        """Get statistics for a polling station."""
        try:
            polling_station = PollingStation.objects.get(id=polling_station_id)
            
            results = PollingStationResult.objects.filter(
                polling_station=polling_station
            )
            
            total_results = results.count()
            total_votes = 0
            for r in results:
                total = r.votes.aggregate(total=Sum('total_votes'))['total'] or 0
                total_votes += total
            
            return {
                'station_id': polling_station_id,
                'station_name': polling_station.name,
                'total_results': total_results,
                'total_votes': total_votes
            }
        except PollingStation.DoesNotExist:
            logger.error(f"Polling station {polling_station_id} not found")
            return None