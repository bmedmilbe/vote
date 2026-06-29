from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
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

        for field in user._meta.fields:
            field_name = field.name
            if field_name not in ['password','id']:
                token[field_name] = str(getattr(user, field_name))
        
        return token
    



# ==========================================
# USER SERIALIZER
# ==========================================

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined']
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
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PollingStation
        fields = ['id', 'constituency', 'constituency_code', 'constituency_name', 
                  'station_number', 'name', 'full_name']
    
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
# TRANSACTION LAYER SERIALIZERS
# ==========================================

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
        # This would need a field for registered voters if available
        # Placeholder - you may want to add a registered_voters field
        return None


class VoteCountSerializer(serializers.ModelSerializer):
    contender_name = serializers.CharField(source='candidate_registration.contender.name', read_only=True)
    contender_slug = serializers.CharField(source='candidate_registration.contender.slug', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = VoteCount
        fields = ['id', 'polling_result', 'candidate_registration', 'contender_name',
                  'contender_slug', 'total_votes', 'user', 'user_username']
    
    def validate(self, data):
        """
        Check that the candidate registration matches the polling result's
        election type and year.
        """
        polling_result = data.get('polling_result')
        candidate_registration = data.get('candidate_registration')
        
        if polling_result and candidate_registration:
            if (candidate_registration.election_type != polling_result.election_type or
                candidate_registration.year != polling_result.year):
                raise serializers.ValidationError(
                    "This candidate/party is not registered for this specific election type and year."
                )
        return data


class PollingStationResultWithVotesSerializer(serializers.ModelSerializer):
    """
    Nested serializer for creating a PollingStationResult with its VoteCounts.
    """
    votes = VoteCountSerializer(many=True)
    
    class Meta:
        model = PollingStationResult
        fields = ['id', 'polling_station', 'election_type', 'year', 
                  'abstentions', 'blank_votes', 'null_votes', 'votes']
    
    def create(self, validated_data):
        votes_data = validated_data.pop('votes')
        polling_result = PollingStationResult.objects.create(**validated_data)
        
        for vote_data in votes_data:
            VoteCount.objects.create(polling_result=polling_result, **vote_data)
        
        return polling_result
    
    def update(self, instance, validated_data):
        votes_data = validated_data.pop('votes', [])
        
        # Update PollingStationResult fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update or create VoteCounts
        current_votes = {vote.candidate_registration_id: vote for vote in instance.votes.all()}
        
        for vote_data in votes_data:
            candidate_registration = vote_data.get('candidate_registration')
            if candidate_registration.id in current_votes:
                # Update existing
                vote = current_votes.pop(candidate_registration.id)
                vote.total_votes = vote_data.get('total_votes', vote.total_votes)
                vote.user = vote_data.get('user', vote.user)
                vote.save()
            else:
                # Create new
                VoteCount.objects.create(polling_result=instance, **vote_data)
        
        # Delete votes that were removed
        for vote in current_votes.values():
            vote.delete()
        
        return instance


# ==========================================
# ACCUMULATED LAYER SERIALIZERS
# ==========================================

class AccumulatedResultSerializer(serializers.ModelSerializer):
    contender_name = serializers.CharField(source='candidate_registration.contender.name', read_only=True)
    contender_slug = serializers.CharField(source='candidate_registration.contender.slug', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True, allow_null=True)
    circle_name = serializers.CharField(source='circle.name', read_only=True, allow_null=True)
    constituency_name = serializers.CharField(source='constituency.name', read_only=True, allow_null=True)
    constituency_code = serializers.CharField(source='constituency.code', read_only=True, allow_null=True)
    
    class Meta:
        model = AccumulatedResult
        fields = ['id', 'scope', 'district', 'district_name', 'circle', 'circle_name',
                  'constituency', 'constituency_name', 'constituency_code',
                  'candidate_registration', 'contender_name', 'contender_slug',
                  'election_type', 'year', 'total_votes', 'estimated_seats']
    
    def validate(self, data):
        """
        Validate that the correct geographic field is provided based on scope.
        """
        scope = data.get('scope')
        district = data.get('district')
        circle = data.get('circle')
        constituency = data.get('constituency')
        
        if scope == 'District' and not district:
            raise serializers.ValidationError("District scope requires a district.")
        elif scope == 'Circle' and not circle:
            raise serializers.ValidationError("Circle scope requires a circle.")
        elif scope == 'Constituency' and not constituency:
            raise serializers.ValidationError("Constituency scope requires a constituency.")
        elif scope == 'National' and (district or circle or constituency):
            raise serializers.ValidationError("National scope should not have geographic filters.")
        
        return data


# ==========================================
# SUMMARY AND STATISTICS SERIALIZERS
# ==========================================

class ElectionSummarySerializer(serializers.Serializer):
    """
    Serializer for election summary statistics.
    """
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
    """
    Serializer for ranking candidates by votes.
    """
    candidate = serializers.CharField(source='candidate_registration.contender.name')
    slug = serializers.CharField(source='candidate_registration.contender.slug')
    total_votes = serializers.IntegerField()
    percentage = serializers.FloatField()
    estimated_seats = serializers.IntegerField(required=False)
        