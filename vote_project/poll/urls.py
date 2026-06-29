# poll/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    AccumulatedResultListView,
    NationalResultsView,
    DistrictResultsView,
    CircleResultsView,
    ConstituencyResultsView,
    PollingStationResultDetailView,
    PollingStationResultCreateView,
    PollingStationResultsByConstituencyView,
    ElectionStatisticsView,
    DashboardView,
    debug_auth,
    SignUpView,
    SignInView
)

app_name = 'poll'

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='sign-up'),
    # JWT Authentication
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Accumulated Results
    path('accumulated-results/', AccumulatedResultListView.as_view(), name='accumulated-results-list'),
    path('national-results/', NationalResultsView.as_view(), name='national-results'),
    path('district-results/<int:district_id>/', DistrictResultsView.as_view(), name='district-results'),
    path('circle-results/<int:circle_id>/', CircleResultsView.as_view(), name='circle-results'),
    path('constituency-results/<int:constituency_id>/', ConstituencyResultsView.as_view(), name='constituency-results'),
    
    # Polling Station Results
    path('polling-results/', PollingStationResultCreateView.as_view(), name='polling-result-create'),
    path('polling-results/<int:pk>/', PollingStationResultDetailView.as_view(), name='polling-result-detail'),
    path('polling-results/constituency/<int:constituency_id>/', 
         PollingStationResultsByConstituencyView.as_view(), 
         name='polling-results-by-constituency'),
    
    # Statistics and Dashboard
    path('statistics/', ElectionStatisticsView.as_view(), name='election-statistics'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('debug-auth/', debug_auth, name='debug-auth'),
]