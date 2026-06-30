from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('citizen', 'Citizen'),
        ('electoral_staff', 'Electoral Staff'),
        ('admin', 'Administrator'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='citizen')
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


# ==========================================
# GEOGRAPHIC HIERARCHY (Nested Structure)
# ==========================================

class District(models.Model):
    """Distrito: The top-level geographic entity in STP (e.g., Água Grande)."""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class ElectoralCircle(models.Model):
    """Círculo: Belongs to a District."""
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='circles')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.district.name})"

class Constituency(models.Model):
    """Circunscrição: Belongs to an Electoral Circle."""
    circle = models.ForeignKey(ElectoralCircle, on_delete=models.CASCADE, related_name='constituencies')
    code = models.CharField(max_length=10, unique=True, help_text="e.g., AG01")
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.name}"

class PollingStation(models.Model):
    """Mesa: The actual physical voting table inside a Constituency."""
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, related_name='polling_stations')
    station_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, help_text="e.g., Escola Pantufo - Mesa 1")

    class Meta:
        unique_together = ('constituency', 'station_number')

    def __str__(self):
        return f"{self.constituency.code} | Mesa {self.station_number}"


# ==========================================
# CANDIDATES & ELECTION PERIOD
# ==========================================

class Contender(models.Model):
    """Partido / Candidato / Coligação."""
    name = models.CharField(max_length=150, unique=True)
    slug = models.CharField(max_length=20, unique=True, help_text="Acronym (e.g., ADI, MLSTP)")

    def __str__(self):
        return self.slug

class CandidateRegistration(models.Model):
    """Binds a candidate/party to a specific election type and year."""
    ELECTION_TYPES = [
        ('Legislative', 'Legislative'),
        ('Presidential', 'Presidential'),
        ('Autarchic', 'Autarchic'),
    ]
    contender = models.ForeignKey(Contender, on_delete=models.CASCADE)
    election_type = models.CharField(max_length=20, choices=ELECTION_TYPES)
    year = models.PositiveIntegerField()
    representative_name = models.CharField(max_length=150, help_text="Main runner name")

    class Meta:
        unique_together = ('contender', 'election_type', 'year')

    def __str__(self):
        return f"{self.contender.slug} - {self.election_type} ({self.year})"


# ==========================================
# TRANSACTION LAYER (Data Entry Per Mesa)
# ==========================================

class PollingStationResult(models.Model):
    """The master record for a single Mesa in a specific Election/Year."""
    polling_station = models.ForeignKey(PollingStation, on_delete=models.CASCADE)
    election_type = models.CharField(max_length=20, choices=CandidateRegistration.ELECTION_TYPES)
    year = models.PositiveIntegerField()
    abstentions = models.PositiveIntegerField(default=0)
    blank_votes = models.PositiveIntegerField(default=0)
    null_votes = models.PositiveIntegerField(default=0)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_results')
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    class Meta:
        unique_together = ('polling_station', 'election_type', 'year')

    def __str__(self):
        return f"{self.polling_station} | {self.election_type} ({self.year})"

class VoteCount(models.Model):
    """The actual votes received by a specific candidate at this specific Mesa."""
    polling_result = models.ForeignKey(PollingStationResult, on_delete=models.CASCADE, related_name='votes')
    candidate_registration = models.ForeignKey(CandidateRegistration, on_delete=models.CASCADE)
    total_votes = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='votes', null=True, blank=True)
    class Meta:
        unique_together = ('polling_result', 'candidate_registration')

    def clean(self):
        # Enforce that the candidate is running in the exact same election type and year as this Mesa form
        if (self.candidate_registration.election_type != self.polling_result.election_type or 
            self.candidate_registration.year != self.polling_result.year):
            raise ValidationError("This candidate/party is not registered for this specific election type and year.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ==========================================
# ACCUMULATED LAYER (Soma / Acomulados)
# ==========================================
# poll/models.py - Update AccumulatedResult
# poll/models.py - Update AccumulatedResult (Keep it simple)
class AccumulatedResult(models.Model):
    """
    Pre-calculated cache table storing accumulated totals across different scopes.
    Allows lightning-fast queries for frontend graphs.
    """
    SCOPE_CHOICES = [
        ('Constituency', 'Constituency Total'),
        ('Circle', 'Circle Total'),
        ('District', 'District Total'),
        ('National', 'National Total'),
    ]
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    
    # Dynamic foreign keys depending on the scope level
    district = models.ForeignKey(District, on_delete=models.CASCADE, null=True, blank=True)
    circle = models.ForeignKey(ElectoralCircle, on_delete=models.CASCADE, null=True, blank=True)
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, null=True, blank=True)
    
    # Common Election Meta
    candidate_registration = models.ForeignKey(CandidateRegistration, on_delete=models.CASCADE)
    election_type = models.CharField(max_length=20, choices=CandidateRegistration.ELECTION_TYPES)
    year = models.PositiveIntegerField()
    
    # Aggregated Values - Only candidate votes
    total_votes = models.PositiveIntegerField(default=0)
    estimated_seats = models.PositiveIntegerField(default=0, help_text="Deputados / Vereadores calculated via Hondt method.")

    class Meta:
        constraints = [
            # National level uniqueness
            models.UniqueConstraint(
                fields=['scope', 'candidate_registration', 'election_type', 'year'],
                condition=models.Q(scope='National'),
                name='unique_accumulated_national'
            ),
            # District level uniqueness
            models.UniqueConstraint(
                fields=['scope', 'district', 'candidate_registration', 'election_type', 'year'],
                condition=models.Q(scope='District'),
                name='unique_accumulated_district'
            ),
            # Circle level uniqueness
            models.UniqueConstraint(
                fields=['scope', 'circle', 'candidate_registration', 'election_type', 'year'],
                condition=models.Q(scope='Circle'),
                name='unique_accumulated_circle'
            ),
            # Constituency level uniqueness
            models.UniqueConstraint(
                fields=['scope', 'constituency', 'candidate_registration', 'election_type', 'year'],
                condition=models.Q(scope='Constituency'),
                name='unique_accumulated_constituency'
            ),
        ]

    def __str__(self):
        return f"[{self.scope}] {self.candidate_registration.contender.slug}: {self.total_votes} votes ({self.year})"