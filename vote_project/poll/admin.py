from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

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

# ==========================================
# USER ADMIN
# ==========================================

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ()}),
    )


# ==========================================
# GEOGRAPHIC HIERARCHY ADMIN
# ==========================================

class ElectoralCircleInline(admin.TabularInline):
    model = ElectoralCircle
    extra = 0
    fields = ['name']
    show_change_link = True


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'circles_count']
    search_fields = ['name']
    ordering = ['name']
    inlines = [ElectoralCircleInline]
    
    def circles_count(self, obj):
        return obj.circles.count()
    circles_count.short_description = 'Electoral Circles'


class ConstituencyInline(admin.TabularInline):
    model = Constituency
    extra = 0
    fields = ['code', 'name']
    show_change_link = True


@admin.register(ElectoralCircle)
class ElectoralCircleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'district', 'constituencies_count']
    list_filter = ['district']
    search_fields = ['name', 'district__name']
    ordering = ['district', 'name']
    inlines = [ConstituencyInline]
    autocomplete_fields = ['district']
    
    def constituencies_count(self, obj):
        return obj.constituencies.count()
    constituencies_count.short_description = 'Constituencies'


class PollingStationInline(admin.TabularInline):
    model = PollingStation
    extra = 0
    fields = ['station_number', 'name']
    show_change_link = True


@admin.register(Constituency)
class ConstituencyAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'name', 'circle', 'polling_stations_count']
    list_filter = ['circle__district', 'circle']
    search_fields = ['code', 'name', 'circle__name']
    ordering = ['code']
    inlines = [PollingStationInline]
    autocomplete_fields = ['circle']
    prepopulated_fields = {'code': ('name',)}
    
    def polling_stations_count(self, obj):
        return obj.polling_stations.count()
    polling_stations_count.short_description = 'Polling Stations'


@admin.register(PollingStation)
class PollingStationAdmin(admin.ModelAdmin):
    list_display = ['id', 'station_number', 'name', 'constituency', 'full_location']
    list_filter = ['constituency__circle__district', 'constituency__circle', 'constituency']
    search_fields = ['name', 'station_number', 'constituency__code']
    ordering = ['constituency', 'station_number']
    autocomplete_fields = ['constituency']
    list_select_related = ['constituency']
    
    def full_location(self, obj):
        return f"{obj.constituency.code} - {obj.constituency.name}"
    full_location.short_description = 'Location'


# ==========================================
# CANDIDATES & ELECTION PERIOD ADMIN
# ==========================================

@admin.register(Contender)
class ContenderAdmin(admin.ModelAdmin):
    list_display = ['id', 'slug', 'name']
    search_fields = ['slug', 'name']
    ordering = ['slug']
    prepopulated_fields = {'slug': ('name',)}


class CandidateRegistrationInline(admin.TabularInline):
    model = CandidateRegistration
    extra = 0
    fields = ['election_type', 'year', 'representative_name']
    show_change_link = True


@admin.register(CandidateRegistration)
class CandidateRegistrationAdmin(admin.ModelAdmin):
    list_display = ['id', 'contender', 'election_type', 'year', 'representative_name']
    list_filter = ['election_type', 'year']
    search_fields = ['contender__name', 'contender__slug', 'representative_name']
    ordering = ['-year', 'contender', 'election_type']
    autocomplete_fields = ['contender']
    list_select_related = ['contender']


# ==========================================
# TRANSACTION LAYER ADMIN
# ==========================================

class VoteCountInline(admin.TabularInline):
    model = VoteCount
    extra = 0
    fields = ['candidate_registration', 'total_votes', 'user']
    show_change_link = True
    autocomplete_fields = ['candidate_registration', 'user']
    raw_id_fields = ['candidate_registration', 'user']


@admin.register(PollingStationResult)
class PollingStationResultAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'polling_station', 'election_type', 'year', 
        'abstentions', 'blank_votes', 'null_votes', 
        'total_votes_display', 'valid_votes_display'
    ]
    list_filter = ['election_type', 'year', 'polling_station__constituency__circle__district']
    search_fields = [
        'polling_station__name', 
        'polling_station__station_number',
        'polling_station__constituency__code'
    ]
    ordering = ['-year', 'polling_station']
    inlines = [VoteCountInline]
    autocomplete_fields = ['polling_station']
    list_select_related = ['polling_station__constituency']
    readonly_fields = ['total_votes_display', 'valid_votes_display']
    
    def total_votes_display(self, obj):
        total = sum(vote.total_votes for vote in obj.votes.all())
        return format_html('<strong>{}</strong>', total)
    total_votes_display.short_description = 'Total Votes'
    
    def valid_votes_display(self, obj):
        total = sum(vote.total_votes for vote in obj.votes.all())
        return format_html('<strong>{}</strong>', total)
    valid_votes_display.short_description = 'Valid Votes'


@admin.register(VoteCount)
class VoteCountAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'polling_result', 'candidate_registration', 
        'total_votes', 'user', 'candidate_display'
    ]
    list_filter = [
        'polling_result__election_type', 
        'polling_result__year',
        'candidate_registration__contender',
        'polling_result__polling_station__constituency'
    ]
    search_fields = [
        'polling_result__polling_station__name',
        'candidate_registration__contender__name',
        'candidate_registration__contender__slug',
        'user__username'
    ]
    ordering = ['-polling_result__year', 'candidate_registration__contender']
    autocomplete_fields = ['polling_result', 'candidate_registration', 'user']
    list_select_related = [
        'polling_result__polling_station',
        'candidate_registration__contender',
        'user'
    ]
    readonly_fields = ['candidate_display']
    
    def candidate_display(self, obj):
        return f"{obj.candidate_registration.contender.slug} ({obj.candidate_registration.election_type})"
    candidate_display.short_description = 'Candidate'
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


# ==========================================
# ACCUMULATED LAYER ADMIN
# ==========================================

@admin.register(AccumulatedResult)
class AccumulatedResultAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'scope', 'candidate_registration', 'election_type', 
        'year', 'total_votes', 'estimated_seats', 'location_display'
    ]
    list_filter = ['scope', 'election_type', 'year', 'candidate_registration__contender']
    search_fields = [
        'candidate_registration__contender__name',
        'candidate_registration__contender__slug',
        'district__name', 'circle__name', 'constituency__name'
    ]
    ordering = ['-year', 'scope', 'candidate_registration__contender']
    autocomplete_fields = ['candidate_registration', 'district', 'circle', 'constituency']
    list_select_related = [
        'candidate_registration__contender',
        'district', 'circle', 'constituency'
    ]
    readonly_fields = ['location_display']
    
    def location_display(self, obj):
        if obj.scope == 'National':
            return 'National'
        elif obj.scope == 'District':
            return obj.district.name if obj.district else '-'
        elif obj.scope == 'Circle':
            return f"{obj.circle.name} ({obj.circle.district.name})" if obj.circle else '-'
        elif obj.scope == 'Constituency':
            return f"{obj.constituency.code} - {obj.constituency.name}" if obj.constituency else '-'
        return '-'
    location_display.short_description = 'Location'


# ==========================================
# CUSTOM ADMIN VIEWS AND FILTERS
# ==========================================

class ElectionTypeFilter(admin.SimpleListFilter):
    title = 'Election Type'
    parameter_name = 'election_type_filter'
    
    def lookups(self, request, model_admin):
        return (
            ('Legislative', 'Legislative'),
            ('Presidential', 'Presidential'),
            ('Autarchic', 'Autarchic'),
        )
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(election_type=self.value())
        return queryset


# ==========================================
# ADMIN SITE CONFIGURATION
# ==========================================

# Customize admin site header
admin.site.site_header = "Election Management System"
admin.site.site_title = "Election Admin"
admin.site.index_title = "Welcome to Election Management System"

# Add custom admin actions
@admin.action(description='Export selected as CSV')
def export_as_csv(modeladmin, request, queryset):
    # You can implement CSV export here
    pass

# Register the action for relevant models
PollingStationResultAdmin.actions = [export_as_csv]
VoteCountAdmin.actions = [export_as_csv]
AccumulatedResultAdmin.actions = [export_as_csv]