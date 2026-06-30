# poll/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AccumulatedResultListView,
    CandidateRegistrationCreateView,
    CandidateRegistrationDetailView,
    CandidateRegistrationListView,
    CircleResultsView,
    ConstituencyResultsView,
    ContenderDetailView,
    ContenderListView,
    CurrentUserView,
    DashboardView,
    DistrictResultsView,
    ElectionStatisticsView,
    NationalResultsView,
    PollingStationByUserView,
    PollingStationDetailView,
    PollingStationListView,
    PollingStationResultCreateView,
    PollingStationResultDetailView,
    PollingStationResultsByConstituencyView,
    SignInView,
    SignUpView,
    debug_auth,
)

app_name = 'poll'

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='sign-up'),
    path('user/', CurrentUserView.as_view(), name='user-view'),
    # JWT Authentication
    path('token/', SignInView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Candidates & Registrations
    path('contenders/', ContenderListView.as_view(), name='contenders-list'),
    path('contenders/<int:pk>/', ContenderDetailView.as_view(), name='contenders-detail'),
    path('candidate-registrations/', CandidateRegistrationListView.as_view(), name='candidate-registrations-list'),
    path('candidate-registrations/create/', CandidateRegistrationCreateView.as_view(), name='candidate-registrations-create'),
    path('candidate-registrations/<int:pk>/', CandidateRegistrationDetailView.as_view(), name='candidate-registrations-detail'),

    # Polling Stations
    path('polling-stations/', PollingStationListView.as_view(), name='polling-stations-list'),
    path('polling-stations/<int:pk>/', PollingStationDetailView.as_view(), name='polling-stations-detail'),
    path('my-polling-stations/', PollingStationByUserView.as_view(), name='my-polling-stations'),
    
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