# poll/serializers.py
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from poll.models import (
    AccumulatedResult,
    CandidateRegistration,
    Constituency,
    Contender,
    District,
    ElectoralCircle,
    PollingStation,
    PollingStationResult,
    User,
    VoteCount,
)

# ==========================================
# AUTHENTICATION SERIALIZERS
# ==========================================

class UserCreateSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError('Passwords must match.')
        return data

    def create(self, validated_data):
        data = {
            key: value for key, value in validated_data.items()
            if key not in ('password1', 'password2')
        }
        data['password'] = validated_data['password1']
        return self.Meta.model.objects.create_user(**data)

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'password1', 'password2',
            'first_name', 'last_name',
        )
        read_only_fields = ('id',)


class SignInSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        fields_to_include = [
            'username', 'email', 'first_name', 'last_name', 
            'role', 'role_display', 'is_active', 'is_staff'
        ]
        
        for field in fields_to_include:
            if hasattr(user, field):
                val = getattr(user, field)
                if callable(val):
                    token[field] = str(val())
                else:
                    token[field] = str(val) if val is not None else ""
                    
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': getattr(self.user, 'role', ''),
            'role_display': getattr(self.user, 'role_display', '') or (
                self.user.get_role_display() if hasattr(self.user, 'get_role_display') else ''
            ),
            'is_active': self.user.is_active,
            'is_staff': self.user.is_staff,
            'date_joined': self.user.date_joined.isoformat() if self.user.date_joined else None,
        }
        
        return data


# ==========================================
# USER SERIALIZER
# ==========================================

class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'role_display',
                  'is_active', 'is_staff', 'date_joined']
        read_only_fields = ['id', 'date_joined']


# ==========================================
# GEOGRAPHIC HIERARCHY SERIALIZERS
# ==========================================

class DistrictSerializer(serializers.ModelSerializer):
    circles_count = serializers.IntegerField(source='circles.count', read_only=True)
    
    class Meta:
        model = District
        fields = ['id', 'name', 'circles_count']


class ElectoralCircleSerializer(serializers.ModelSerializer):
    district_name = serializers.CharField(source='district.name', read_only=True)
    constituencies_count = serializers.IntegerField(source='constituencies.count', read_only=True)
    
    class Meta:
        model = ElectoralCircle
        fields = ['id', 'district', 'district_name', 'name', 'constituencies_count']


class ConstituencySerializer(serializers.ModelSerializer):
    circle_name = serializers.CharField(source='circle.name', read_only=True)
    district_name = serializers.CharField(source='circle.district.name', read_only=True)
    polling_stations_count = serializers.IntegerField(source='polling_stations.count', read_only=True)
    
    class Meta:
        model = Constituency
        fields = ['id', 'circle', 'circle_name', 'district_name', 'code', 'name', 'polling_stations_count']


class PollingStationSerializer(serializers.ModelSerializer):
    constituency_code = serializers.CharField(source='constituency.code', read_only=True)
    constituency_name = serializers.CharField(source='constituency.name', read_only=True)
    district_name = serializers.CharField(source='constituency.circle.district.name', read_only=True)
    circle_name = serializers.CharField(source='constituency.circle.name', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PollingStation
        fields = [
            'id', 'constituency', 'constituency_code', 'constituency_name',
            'district_name', 'circle_name', 'station_number', 'name', 
            'full_name'
        ]
    
    def get_full_name(self, obj):
        return f"{obj.constituency.code} | Mesa {obj.station_number}"


# ==========================================
# CANDIDATES & ELECTION PERIOD SERIALIZERS
# ==========================================

class ContenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contender
        fields = ['id', 'name', 'slug']


class CandidateRegistrationSerializer(serializers.ModelSerializer):
    contender_name = serializers.CharField(source='contender.name', read_only=True)
    contender_slug = serializers.CharField(source='contender.slug', read_only=True)
    
    class Meta:
        model = CandidateRegistration
        fields = ['id', 'contender', 'contender_name', 'contender_slug', 
                  'election_type', 'year', 'representative_name']


# ==========================================
# TRANSACTION LAYER SERIALIZERS (REST API)
# ==========================================

class VoteCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoteCount
        fields = ['id', 'candidate_registration', 'total_votes']
        read_only_fields = ['polling_result']


class PollingStationResultWithVotesSerializer(serializers.ModelSerializer):
    votes = VoteCountSerializer(many=True, required=True)
    
    class Meta:
        model = PollingStationResult
        fields = ['id', 'polling_station', 'election_type', 'year', 
                  'abstentions', 'blank_votes', 'null_votes', 'votes']
    
    def validate(self, data):
        if 'votes' not in data or not data['votes']:
            raise serializers.ValidationError({
                'votes': 'At least one vote entry is required.'
            })
        
        for vote in data['votes']:
            if not vote.get('candidate_registration'):
                raise serializers.ValidationError({
                    'votes': 'Each vote must have a candidate.'
                })
            if vote.get('total_votes', 0) < 0:
                raise serializers.ValidationError({
                    'votes': 'Total votes cannot be negative.'
                })
        
        return data
    
    def create(self, validated_data):
        votes_data = validated_data.pop('votes')
        
        with transaction.atomic():
            polling_result = PollingStationResult.objects.create(**validated_data)
            
            for vote_data in votes_data:
                VoteCount.objects.create(
                    polling_result=polling_result,
                    **vote_data
                )
            
            self.update_accumulated_results(polling_result)
            
            return polling_result
    
    def update(self, instance, validated_data):
        votes_data = validated_data.pop('votes', [])
        
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            instance.votes.all().delete()
            
            for vote_data in votes_data:
                VoteCount.objects.create(
                    polling_result=instance,
                    **vote_data
                )
            
            self.update_accumulated_results(instance)
            
            return instance
    
    def update_accumulated_results(self, polling_result):
        """Update all accumulated results for this election."""
        from django.db.models import Sum

        from .models import VoteCount
        
        election_type = polling_result.election_type
        year = polling_result.year
        
        # Get all candidates for this election
        candidates = VoteCount.objects.filter(
            polling_result__election_type=election_type,
            polling_result__year=year
        ).values_list('candidate_registration', flat=True).distinct()
        
        for candidate_id in candidates:
            # 1️⃣ National Level
            national_total = VoteCount.objects.filter(
                candidate_registration_id=candidate_id,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            self._safe_update_or_create(
                scope='National',
                candidate_registration_id=candidate_id,
                election_type=election_type,
                year=year,
                defaults={'total_votes': national_total}
            )
            
            # 2️⃣ District Level
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
                    
                    self._safe_update_or_create(
                        scope='District',
                        district_id=district_id,
                        candidate_registration_id=candidate_id,
                        election_type=election_type,
                        year=year,
                        defaults={'total_votes': district_total}
                    )
            
            # 3️⃣ Circle Level
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
                    
                    self._safe_update_or_create(
                        scope='Circle',
                        circle_id=circle_id,
                        candidate_registration_id=candidate_id,
                        election_type=election_type,
                        year=year,
                        defaults={'total_votes': circle_total}
                    )
            
            # 4️⃣ Constituency Level
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
                    
                    self._safe_update_or_create(
                        scope='Constituency',
                        constituency_id=constituency_id,
                        candidate_registration_id=candidate_id,
                        election_type=election_type,
                        year=year,
                        defaults={'total_votes': constituency_total}
                    )
    
    def _safe_update_or_create(self, **kwargs):
        """Safely update or create with duplicate handling."""
        try:
            obj, created = AccumulatedResult.objects.update_or_create(**kwargs)
            return obj, created
        except AccumulatedResult.MultipleObjectsReturned:
            filter_kwargs = {k: v for k, v in kwargs.items() if k != 'defaults'}
            objs = AccumulatedResult.objects.filter(**filter_kwargs)
            keep = objs.first()
            objs.exclude(id=keep.id).delete()
            if 'defaults' in kwargs:
                for key, value in kwargs['defaults'].items():
                    setattr(keep, key, value)
                keep.save()
            return keep, False


class PollingStationResultSerializer(serializers.ModelSerializer):
    polling_station_full_name = serializers.CharField(source='polling_station.__str__', read_only=True)
    constituency_code = serializers.CharField(source='polling_station.constituency.code', read_only=True)
    total_votes = serializers.SerializerMethodField()
    valid_votes = serializers.SerializerMethodField()
    total_registered = serializers.SerializerMethodField()
    
    class Meta:
        model = PollingStationResult
        fields = ['id', 'polling_station', 'polling_station_full_name', 'constituency_code',
                  'election_type', 'year', 'abstentions', 'blank_votes', 'null_votes',
                  'total_votes', 'valid_votes', 'total_registered']
    
    def get_total_votes(self, obj):
        return sum(vote.total_votes for vote in obj.votes.all())
    
    def get_valid_votes(self, obj):
        return self.get_total_votes(obj)
    
    def get_total_registered(self, obj):
        return None


# ==========================================
# ACCUMULATED LAYER SERIALIZERS (REST API)
# ==========================================

class AccumulatedResultSerializer(serializers.ModelSerializer):
    contender_name = serializers.CharField(source='candidate_registration.contender.name', read_only=True)
    contender_slug = serializers.CharField(source='candidate_registration.contender.slug', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True, allow_null=True)
    circle_name = serializers.CharField(source='circle.name', read_only=True, allow_null=True)
    constituency_name = serializers.CharField(source='constituency.name', read_only=True, allow_null=True)
    constituency_code = serializers.CharField(source='constituency.code', read_only=True, allow_null=True)
    percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = AccumulatedResult
        fields = [
            'id', 'scope', 'district', 'district_name', 'circle', 'circle_name',
            'constituency', 'constituency_name', 'constituency_code',
            'candidate_registration', 'contender_name', 'contender_slug',
            'election_type', 'year', 'total_votes', 'estimated_seats', 'percentage'
        ]
    
    def get_percentage(self, obj):
        """Calculate percentage of valid votes for this candidate in their scope."""
        scope_results = AccumulatedResult.objects.filter(
            scope=obj.scope,
            election_type=obj.election_type,
            year=obj.year
        )
        
        if obj.scope != 'National':
            if obj.scope == 'District' and obj.district:
                scope_results = scope_results.filter(district=obj.district)
            elif obj.scope == 'Circle' and obj.circle:
                scope_results = scope_results.filter(circle=obj.circle)
            elif obj.scope == 'Constituency' and obj.constituency:
                scope_results = scope_results.filter(constituency=obj.constituency)
        
        total_valid = sum(r.total_votes for r in scope_results)
        
        if total_valid > 0:
            return round((obj.total_votes / total_valid) * 100, 2)
        return 0
    
    def validate(self, data):
        scope = data.get('scope')
        district = data.get('district')
        circle = data.get('circle')
        constituency = data.get('constituency')
        
        if scope == 'National' and (district or circle or constituency):
            raise serializers.ValidationError("National scope should not have geographic filters.")
        elif scope == 'District' and not district:
            raise serializers.ValidationError("District scope requires a district.")
        elif scope == 'Circle' and not circle:
            raise serializers.ValidationError("Circle scope requires a circle.")
        elif scope == 'Constituency' and not constituency:
            raise serializers.ValidationError("Constituency scope requires a constituency.")
        
        return data


# ==========================================
# WEBSOCKET SERIALIZERS (For Real-time Updates)
# ==========================================

class WebSocketVoteCountSerializer(serializers.ModelSerializer):
    """Simplified VoteCount serializer for WebSocket updates"""
    contender_name = serializers.CharField(source='candidate_registration.contender.name', read_only=True)
    contender_slug = serializers.CharField(source='candidate_registration.contender.slug', read_only=True)
    
    class Meta:
        model = VoteCount
        fields = ['id', 'candidate_registration', 'contender_name', 
                  'contender_slug', 'total_votes']


class WebSocketPollingStationResultSerializer(serializers.ModelSerializer):
    """Simplified PollingStationResult serializer for WebSocket updates"""
    votes = WebSocketVoteCountSerializer(many=True, read_only=True)
    total_votes = serializers.SerializerMethodField()
    station_name = serializers.CharField(source='polling_station.name', read_only=True)
    constituency_code = serializers.CharField(source='polling_station.constituency.code', read_only=True)
    
    class Meta:
        model = PollingStationResult
        fields = ['id', 'polling_station', 'station_name', 'constituency_code',
                  'election_type', 'year', 'abstentions', 'blank_votes', 
                  'null_votes', 'votes', 'total_votes']
    
    def get_total_votes(self, obj):
        return sum(vote.total_votes for vote in obj.votes.all())


class WebSocketAccumulatedResultSerializer(serializers.ModelSerializer):
    """Simplified AccumulatedResult serializer for WebSocket updates"""
    contender_name = serializers.CharField(source='candidate_registration.contender.name', read_only=True)
    contender_slug = serializers.CharField(source='candidate_registration.contender.slug', read_only=True)
    location_name = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = AccumulatedResult
        fields = [
            'id', 'scope', 'location_name', 'candidate_registration', 
            'contender_name', 'contender_slug', 'election_type', 
            'year', 'total_votes', 'estimated_seats', 'percentage'
        ]
    
    def get_location_name(self, obj):
        if obj.scope == 'National':
            return 'National'
        elif obj.scope == 'District' and obj.district:
            return obj.district.name
        elif obj.scope == 'Circle' and obj.circle:
            return f"{obj.circle.name} ({obj.circle.district.name})"
        elif obj.scope == 'Constituency' and obj.constituency:
            return f"{obj.constituency.code} - {obj.constituency.name}"
        return None
    
    def get_percentage(self, obj):
        """Calculate percentage of valid votes for this candidate in their scope."""
        scope_results = AccumulatedResult.objects.filter(
            scope=obj.scope,
            election_type=obj.election_type,
            year=obj.year
        )
        
        if obj.scope != 'National':
            if obj.scope == 'District' and obj.district:
                scope_results = scope_results.filter(district=obj.district)
            elif obj.scope == 'Circle' and obj.circle:
                scope_results = scope_results.filter(circle=obj.circle)
            elif obj.scope == 'Constituency' and obj.constituency:
                scope_results = scope_results.filter(constituency=obj.constituency)
        
        total_valid = sum(r.total_votes for r in scope_results)
        
        if total_valid > 0:
            return round((obj.total_votes / total_valid) * 100, 2)
        return 0


# ==========================================
# SUMMARY AND STATISTICS SERIALIZERS
# ==========================================

class ElectionSummarySerializer(serializers.Serializer):
    election_type = serializers.CharField()
    year = serializers.IntegerField()
    total_polling_stations = serializers.IntegerField()
    total_registered_voters = serializers.IntegerField(required=False)
    total_abstentions = serializers.IntegerField()
    total_blank_votes = serializers.IntegerField()
    total_null_votes = serializers.IntegerField()
    total_valid_votes = serializers.IntegerField()
    total_votes = serializers.IntegerField()
    turnout_percentage = serializers.FloatField()


class CandidateRankingSerializer(serializers.Serializer):
    candidate = serializers.CharField(source='candidate_registration.contender.name')
    slug = serializers.CharField(source='candidate_registration.contender.slug')
    total_votes = serializers.IntegerField()
    percentage = serializers.FloatField()
    estimated_seats = serializers.IntegerField(required=False)


# ==========================================
# DASHBOARD SERIALIZERS
# ==========================================

class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for dashboard summary data"""
    total_polling_stations = serializers.IntegerField()
    total_abstentions = serializers.IntegerField()
    total_blank_votes = serializers.IntegerField()
    total_null_votes = serializers.IntegerField()
    total_valid_votes = serializers.IntegerField()
    total_votes = serializers.IntegerField()
    turnout_percentage = serializers.FloatField()


class DashboardDataSerializer(serializers.Serializer):
    """Serializer for complete dashboard data"""
    national_results = AccumulatedResultSerializer(many=True)
    district_summary = serializers.ListField()
    recent_results = PollingStationResultSerializer(many=True)
    statistics = DashboardSummarySerializer()
    election_meta = serializers.DictField()