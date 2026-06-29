from rest_framework.generics import CreateAPIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q
from django.db import models
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import AccumulatedResult, PollingStationResult, VoteCount, CandidateRegistration
from .serializers import AccumulatedResultSerializer, PollingStationResultSerializer

from .serializers import SignInSerializer, UserCreateSerializer


class SignUpView(CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny] 
class SignInView(TokenObtainPairView):
    serializer_class = SignInSerializer
    permission_classes = [permissions.AllowAny] 




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
        election_type = request.query_params.get('election_type', 'Legislative')
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
        election_type = request.query_params.get('election_type', 'Legislative')
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
        election_type = request.query_params.get('election_type', 'Legislative')
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
        election_type = request.query_params.get('election_type', 'Legislative')
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

class PollingStationResultCreateView(generics.CreateAPIView):
    """
    Create a new polling station result with vote counts.
    Only electoral staff and admin can create.
    """
    serializer_class = PollingStationResultSerializer
    permission_classes = [IsElectoralStaff]
    
    def perform_create(self, serializer):
        # Set user for audit
        serializer.save()

class PollingStationResultsByConstituencyView(APIView):
    """
    Get all polling station results for a constituency.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request, constituency_id):
        election_type = request.query_params.get('election_type', 'Legislative')
        year = request.query_params.get('year', 2026)
        
        results = PollingStationResult.objects.filter(
            polling_station__constituency__id=constituency_id,
            election_type=election_type,
            year=year
        ).select_related('polling_station')
        
        serializer = PollingStationResultSerializer(results, many=True)
        
        return Response(serializer.data)

# ==========================================
# ELECTION STATISTICS VIEWS
# ==========================================

class ElectionStatisticsView(APIView):
    """
    Get overall election statistics.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        election_type = request.query_params.get('election_type', 'Legislative')
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
        
        # Get vote counts
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
                    'votes': 0
                }
            candidate_totals[slug]['votes'] += vote.total_votes
        
        total_votes = sum(c['votes'] for c in candidate_totals.values())
        total_valid_votes = total_votes  # Valid votes are the sum of all votes
        
        # Calculate percentages
        for candidate in candidate_totals.values():
            candidate['percentage'] = round((candidate['votes'] / total_valid_votes * 100), 2) if total_valid_votes > 0 else 0
        
        response_data = {
            'summary': {
                'total_polling_stations': total_stations,
                'total_abstentions': total_abstentions,
                'total_blank_votes': total_blank,
                'total_null_votes': total_null,
                'total_valid_votes': total_valid_votes,
                'total_votes': total_valid_votes + total_blank + total_null + total_abstentions,
                'turnout_percentage': round((total_valid_votes / (total_valid_votes + total_abstentions) * 100), 2) if total_valid_votes > 0 else 0
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
        election_type = request.query_params.get('election_type', 'Legislative')
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
    