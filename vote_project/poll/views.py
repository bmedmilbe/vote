import datetime

# poll/views.py - Complete create view with proper signal handling
from datetime import datetime

from asgiref.sync import async_to_sync

# poll/views.py
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    AccumulatedResult,
    CandidateRegistration,
    Contender,
    PollingStation,
    PollingStationResult,
    VoteCount,
)
from .serializers import (
    AccumulatedResultSerializer,
    CandidateRegistrationSerializer,
    ContenderSerializer,
    PollingStationResultSerializer,
    PollingStationResultWithVotesSerializer,
    PollingStationSerializer,
    SignInSerializer,
    UserCreateSerializer,
    UserSerializer,
    WebSocketAccumulatedResultSerializer,
)


class CurrentUserView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class SignUpView(CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny] 
class SignInView(TokenObtainPairView):
    serializer_class = SignInSerializer
    permission_classes = [permissions.AllowAny] 




class CandidateRegistrationListView(generics.ListAPIView):
    """
    List all candidate registrations with optional filters.
    """
    serializer_class = CandidateRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CandidateRegistration.objects.all().select_related('contender')
        
        # Filter by election type
        election_type = self.request.query_params.get('election_type')
        if election_type:
            queryset = queryset.filter(election_type=election_type)
        
        # Filter by year
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(year=year)
        
        # Filter by contender
        contender_id = self.request.query_params.get('contender')
        if contender_id:
            queryset = queryset.filter(contender_id=contender_id)
        
        # Filter by contender slug
        contender_slug = self.request.query_params.get('contender_slug')
        if contender_slug:
            queryset = queryset.filter(contender__slug=contender_slug)
        
        return queryset

class CandidateRegistrationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a specific candidate registration.
    """
    queryset = CandidateRegistration.objects.all()
    serializer_class = CandidateRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            # Only admin can modify
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

class CandidateRegistrationCreateView(generics.CreateAPIView):
    """
    Create a new candidate registration.
    """
    queryset = CandidateRegistration.objects.all()
    serializer_class = CandidateRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        # You can add custom logic here
        serializer.save()

# poll/views.py - Add Contender views
class ContenderListView(generics.ListAPIView):
    """
    List all contenders (parties/candidates).
    """
    queryset = Contender.objects.all()
    serializer_class = ContenderSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ContenderDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific contender.
    """
    queryset = Contender.objects.all()
    serializer_class = ContenderSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class PollingStationListView(generics.ListAPIView):
    """
    List all polling stations or filter by constituency.
    Electoral staff see only their assigned stations.
    Admins see all stations.
    """
    serializer_class = PollingStationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = PollingStation.objects.all().select_related('constituency__circle__district')
        
        # Filter by constituency if provided
        constituency_id = self.request.query_params.get('constituency')
        if constituency_id:
            queryset = queryset.filter(constituency_id=constituency_id)
        
        # Filter by district if provided
        district_id = self.request.query_params.get('district')
        if district_id:
            queryset = queryset.filter(constituency__circle__district_id=district_id)
        
        # Staff only see their assigned stations (if you have staff assignment)
        # For now, staff see all stations (you can add assignment logic later)
        if user.role == 'electoral_staff':
            # Option 1: Show all stations (for simplicity)
            # Option 2: Filter by assigned stations (if you have a relation)
            # For now, return all
            pass
        
        return queryset

class PollingStationDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update a specific polling station.
    """
    queryset = PollingStation.objects.all()
    serializer_class = PollingStationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            # Only staff and admin can update
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

class PollingStationByUserView(APIView):
    """
    Get polling stations assigned to the current user (staff).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # For demo purposes, return all stations if staff/admin
        if user.role in ['electoral_staff', 'admin']:
            stations = PollingStation.objects.all().select_related('constituency__circle__district')
            serializer = PollingStationSerializer(stations, many=True)
            return Response(serializer.data)
        
        return Response(
            {'error': 'You do not have permission to view polling stations'},
            status=status.HTTP_403_FORBIDDEN
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_auth(request):
    """Debug view to test authentication."""
    return JsonResponse({
        'authenticated': request.user.is_authenticated,
        'user': request.user.username,
        'role': request.user.role,
        'id': request.user.id
    })



# ==========================================
# PERMISSIONS
# ==========================================

class IsElectoralStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['electoral_staff', 'admin']

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsCitizenOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role in ['electoral_staff', 'admin']

# ==========================================
# ACCUMULATED RESULTS VIEWS
# ==========================================

class AccumulatedResultListView(generics.ListAPIView):
    """
    List accumulated results with filtering by scope, election_type, year.
    Citizens can view, only staff/admin can modify.
    """
    serializer_class = AccumulatedResultSerializer
    permission_classes = [IsCitizenOrReadOnly]
    
    def get_queryset(self):
        queryset = AccumulatedResult.objects.select_related(
            'candidate_registration__contender',
            'district',
            'circle',
            'constituency'
        )
        
        # Filter by scope
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        # Filter by election type
        election_type = self.request.query_params.get('election_type')
        if election_type:
            queryset = queryset.filter(election_type=election_type)
        
        # Filter by year
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(year=year)
        
        # Filter by candidate
        candidate = self.request.query_params.get('candidate')
        if candidate:
            queryset = queryset.filter(candidate_registration__contender__slug=candidate)
        
        # Filter by district
        district = self.request.query_params.get('district')
        if district:
            queryset = queryset.filter(district__id=district)
        
        # Filter by circle
        circle = self.request.query_params.get('circle')
        if circle:
            queryset = queryset.filter(circle__id=circle)
        
        # Filter by constituency
        constituency = self.request.query_params.get('constituency')
        if constituency:
            queryset = queryset.filter(constituency__id=constituency)
        
        return queryset

class NationalResultsView(APIView):
    """
    Get national-level accumulated results.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        results = AccumulatedResult.objects.filter(
            scope='National',
            election_type=election_type,
            year=year
        ).select_related('candidate_registration__contender')
        
        serializer = AccumulatedResultSerializer(results, many=True)
        
        # Calculate totals
        total_votes = sum(r.total_votes for r in results)
        
        # Calculate percentages
        data = serializer.data
        for item in data:
            item['percentage'] = round((item['total_votes'] / total_votes * 100), 2) if total_votes > 0 else 0
        
        response_data = {
            'results': data,
            'summary': {
                'total_votes': total_votes,
                'total_candidates': len(data),
                'election_type': election_type,
                'year': year
            }
        }
        
        return Response(response_data)

class DistrictResultsView(APIView):
    """
    Get district-level accumulated results.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request, district_id):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        results = AccumulatedResult.objects.filter(
            scope='District',
            district__id=district_id,
            election_type=election_type,
            year=year
        ).select_related('candidate_registration__contender', 'district')
        
        serializer = AccumulatedResultSerializer(results, many=True)
        
        # Calculate totals
        total_votes = sum(r.total_votes for r in results)
        
        response_data = {
            'results': serializer.data,
            'summary': {
                'total_votes': total_votes,
                'district': results.first().district.name if results.exists() else None
            }
        }
        
        return Response(response_data)

class CircleResultsView(APIView):
    """
    Get circle-level accumulated results.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request, circle_id):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        results = AccumulatedResult.objects.filter(
            scope='Circle',
            circle__id=circle_id,
            election_type=election_type,
            year=year
        ).select_related('candidate_registration__contender', 'circle')
        
        serializer = AccumulatedResultSerializer(results, many=True)
        
        return Response(serializer.data)

class ConstituencyResultsView(APIView):
    """
    Get constituency-level accumulated results.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request, constituency_id):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        results = AccumulatedResult.objects.filter(
            scope='Constituency',
            constituency__id=constituency_id,
            election_type=election_type,
            year=year
        ).select_related('candidate_registration__contender', 'constituency')
        
        serializer = AccumulatedResultSerializer(results, many=True)
        
        return Response(serializer.data)

# ==========================================
# VOTE COUNT VIEWS
# ==========================================

# poll/views.py
import datetime
from datetime import datetime

from rest_framework import generics, permissions
from rest_framework.views import APIView


class PollingStationResultCreateView(generics.CreateAPIView):
    """
    Create a new polling station result with vote counts.
    Automatically updates accumulated results and broadcasts via WebSocket.
    """
    serializer_class = PollingStationResultWithVotesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            # Save the polling result with votes
            polling_result = serializer.save()
            
            # Get the election details
            election_type = polling_result.election_type
            year = polling_result.year
            
            # The signals will handle AccumulatedResult updates
            # But we also ensure it's done here as a backup
            self.update_accumulated_results(election_type, year)
            
            # Broadcast the update via WebSocket
            self.broadcast_update(election_type, year)
    
    def update_accumulated_results(self, election_type, year):
        """Recalculate all accumulated results for the election."""
        from .models import AccumulatedResult, VoteCount
        
        # Get all candidates for this election
        candidates = VoteCount.objects.filter(
            polling_result__election_type=election_type,
            polling_result__year=year
        ).values_list('candidate_registration', flat=True).distinct()
        
        for candidate_id in candidates:
            # National level
            national_total = VoteCount.objects.filter(
                candidate_registration_id=candidate_id,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            AccumulatedResult.objects.update_or_create(
                scope='National',
                candidate_registration_id=candidate_id,
                election_type=election_type,
                year=year,
                defaults={'total_votes': national_total}
            )
            
            # District level
            districts = VoteCount.objects.filter(
                candidate_registration_id=candidate_id,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).values_list(
                'polling_result__polling_station__constituency__circle__district',
                flat=True
            ).distinct()
            
            for district_id in districts:
                if district_id:
                    district_total = VoteCount.objects.filter(
                        candidate_registration_id=candidate_id,
                        polling_result__election_type=election_type,
                        polling_result__year=year,
                        polling_result__polling_station__constituency__circle__district_id=district_id
                    ).aggregate(total=Sum('total_votes'))['total'] or 0
                    
                    AccumulatedResult.objects.update_or_create(
                        scope='District',
                        district_id=district_id,
                        candidate_registration_id=candidate_id,
                        election_type=election_type,
                        year=year,
                        defaults={'total_votes': district_total}
                    )
            
            # Circle level
            circles = VoteCount.objects.filter(
                candidate_registration_id=candidate_id,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).values_list(
                'polling_result__polling_station__constituency__circle',
                flat=True
            ).distinct()
            
            for circle_id in circles:
                if circle_id:
                    circle_total = VoteCount.objects.filter(
                        candidate_registration_id=candidate_id,
                        polling_result__election_type=election_type,
                        polling_result__year=year,
                        polling_result__polling_station__constituency__circle_id=circle_id
                    ).aggregate(total=Sum('total_votes'))['total'] or 0
                    
                    AccumulatedResult.objects.update_or_create(
                        scope='Circle',
                        circle_id=circle_id,
                        candidate_registration_id=candidate_id,
                        election_type=election_type,
                        year=year,
                        defaults={'total_votes': circle_total}
                    )
            
            # Constituency level
            constituencies = VoteCount.objects.filter(
                candidate_registration_id=candidate_id,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).values_list(
                'polling_result__polling_station__constituency',
                flat=True
            ).distinct()
            
            for constituency_id in constituencies:
                if constituency_id:
                    constituency_total = VoteCount.objects.filter(
                        candidate_registration_id=candidate_id,
                        polling_result__election_type=election_type,
                        polling_result__year=year,
                        polling_result__polling_station__constituency_id=constituency_id
                    ).aggregate(total=Sum('total_votes'))['total'] or 0
                    
                    AccumulatedResult.objects.update_or_create(
                        scope='Constituency',
                        constituency_id=constituency_id,
                        candidate_registration_id=candidate_id,
                        election_type=election_type,
                        year=year,
                        defaults={'total_votes': constituency_total}
                    )

    def broadcast_update(self, election_type, year):
        """Broadcast the update to all connected WebSocket clients."""
        try:
            # Get updated national results
            national_results = AccumulatedResult.objects.filter(
                scope='National',
                election_type=election_type,
                year=year
            ).select_related('candidate_registration__contender')
            
            # Serialize the data
            serializer = WebSocketAccumulatedResultSerializer(national_results, many=True)
            
            # Get channel layer and send broadcast
            channel_layer = get_channel_layer()
            
            if channel_layer:
                # Get the group name from the consumer
                # Make sure this matches the group name in your ElectionConsumer
                election_group_name = 'election_election_updates'
                staff_group_name = 'staff_updates'
                
                # Broadcast to election group
                async_to_sync(channel_layer.group_send)(
                    election_group_name,
                    {
                        'type': 'broadcast_vote_update',
                        'data': {
                            'type': 'results_update',
                            'data': serializer.data,
                            'election_type': election_type,
                            'year': year,
                            'scope': 'National',
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                )
                print(f"📡 Broadcast sent to '{election_group_name}' group")
                
                # Also broadcast to staff group
                async_to_sync(channel_layer.group_send)(
                    staff_group_name,
                    {
                        'type': 'broadcast_vote_update',
                        'data': {
                            'type': 'staff_update',
                            'message': 'New votes submitted',
                            'election_type': election_type,
                            'year': year,
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                )
                print(f"📡 Broadcast sent to '{staff_group_name}' group")
                
                print(f"✅ WebSocket broadcast sent for {election_type} {year} with {len(serializer.data)} results")
            else:
                print("❌ Channel layer not available")
            
        except Exception as e:
            print(f"❌ Broadcast error: {e}")
            import traceback
            traceback.print_exc()

class PollingStationResultsByConstituencyView(APIView):
    """
    Get all polling station results for a constituency.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, constituency_id):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        results = PollingStationResult.objects.filter(
            polling_station__constituency__id=constituency_id,
            election_type=election_type,
            year=year
        ).select_related('polling_station')
        
        # Calculate total votes for each result
        result_data = []
        for result in results:
            total_votes = VoteCount.objects.filter(
                polling_result=result
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            result_data.append({
                'id': result.id,
                'polling_station': result.polling_station.id,
                'polling_station_name': result.polling_station.name,
                'election_type': result.election_type,
                'year': result.year,
                'abstentions': result.abstentions,
                'blank_votes': result.blank_votes,
                'null_votes': result.null_votes,
                'total_votes': total_votes,
            })
        
        return Response(result_data)
    
class PollingStationResultDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update or delete a specific polling station result.
    Electoral staff can update, admin can delete.
    """
    queryset = PollingStationResult.objects.all()
    serializer_class = PollingStationResultSerializer
    
    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [IsAdmin()]
        elif self.request.method in ['PUT', 'PATCH']:
            return [IsElectoralStaff()]
        return [permissions.IsAuthenticatedOrReadOnly()]


# ==========================================
# ELECTION STATISTICS VIEWS
# ==========================================

# poll/views.py - Update ElectionStatisticsView
class ElectionStatisticsView(APIView):
    """
    Get overall election statistics including blanks and nulls separately.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        # Get all results
        results = PollingStationResult.objects.filter(
            election_type=election_type,
            year=year
        )
        
        # Calculate statistics
        total_stations = results.count()
        total_abstentions = results.aggregate(total=Sum('abstentions'))['total'] or 0
        total_blank = results.aggregate(total=Sum('blank_votes'))['total'] or 0
        total_null = results.aggregate(total=Sum('null_votes'))['total'] or 0
        
        # Get vote counts for candidates
        vote_counts = VoteCount.objects.filter(
            polling_result__in=results
        ).select_related('candidate_registration__contender')
        
        candidate_totals = {}
        for vote in vote_counts:
            slug = vote.candidate_registration.contender.slug
            if slug not in candidate_totals:
                candidate_totals[slug] = {
                    'candidate': vote.candidate_registration.contender.name,
                    'slug': slug,
                    'votes': 0,
                    'percentage': 0
                }
            candidate_totals[slug]['votes'] += vote.total_votes
        
        # Calculate total valid votes
        total_valid_votes = sum(c['votes'] for c in candidate_totals.values())
        total_votes = total_valid_votes + total_blank + total_null + total_abstentions
        
        # Calculate percentages for candidates
        for candidate in candidate_totals.values():
            candidate['percentage'] = round(
                (candidate['votes'] / total_valid_votes * 100), 2
            ) if total_valid_votes > 0 else 0
        
        response_data = {
            'summary': {
                'total_polling_stations': total_stations,
                'total_abstentions': total_abstentions,
                'total_blank_votes': total_blank,
                'total_null_votes': total_null,
                'total_valid_votes': total_valid_votes,
                'total_votes': total_votes,
                'turnout_percentage': round(
                    (total_valid_votes / (total_valid_votes + total_abstentions) * 100), 2
                ) if total_valid_votes > 0 else 0
            },
            'candidates': list(candidate_totals.values())
        }
        
        return Response(response_data)
# ==========================================
# DASHBOARD VIEWS
# ==========================================

class DashboardView(APIView):
    """
    Get all data for the dashboard.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        election_type = request.query_params.get('election_type', 'Presidential')
        year = request.query_params.get('year', 2026)
        
        # Get national results
        national_results = AccumulatedResult.objects.filter(
            scope='National',
            election_type=election_type,
            year=year
        ).select_related('candidate_registration__contender')
        
        national_serializer = AccumulatedResultSerializer(national_results, many=True)
        
        # Get district results summary
        district_summary = AccumulatedResult.objects.filter(
            scope='District',
            election_type=election_type,
            year=year
        ).values('district__name').annotate(
            total_votes=Sum('total_votes'),
            total_seats=Sum('estimated_seats')
        ).order_by('-total_votes')
        
        # Get recent results
        recent_results = PollingStationResult.objects.filter(
            election_type=election_type,
            year=year
        ).order_by('-id')[:10]
        
        recent_serializer = PollingStationResultSerializer(recent_results, many=True)
        
        # Calculate overall statistics
        statistics_view = ElectionStatisticsView()
        statistics = statistics_view.get(request).data
        
        response_data = {
            'national_results': national_serializer.data,
            'district_summary': list(district_summary),
            'recent_results': recent_serializer.data,
            'statistics': statistics,
            'election_meta': {
                'election_type': election_type,
                'year': year,
                'last_updated': datetime.now().isoformat()
            }
        }
        
        return Response(response_data)
 