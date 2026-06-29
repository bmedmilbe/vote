from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver

from poll.models import AccumulatedResult, VoteCount


@receiver(post_save, sender=VoteCount)
def update_accumulated_metrics(sender, instance, **kwargs):
    """
    Triggered whenever a vote count is modified or added in a Mesa.
    Recalculates Constituency, Circle, District, and National totals.
    """
    polling_result = instance.polling_result
    candidate = instance.candidate_registration
    
    # 1. Get geographic ancestors
    constituency = polling_result.polling_station.constituency
    circle = constituency.circle
    district = circle.district
    
    # Helper to calculate and save a single specific scope level
    def save_scope_total(scope_name, d_id=None, c_id=None, cz_id=None, filters={}):
        total = VoteCount.objects.filter(
            candidate_registration=candidate,
            polling_result__election_type=polling_result.election_type,
            polling_result__year=polling_result.year,
            **filters
        ).aggregate(Sum('total_votes'))['total_votes__sum'] or 0
        
        AccumulatedResult.objects.update_or_create(
            scope=scope_name, district_id=d_id, circle_id=c_id, constituency_id=cz_id,
            candidate_registration=candidate, election_type=polling_result.election_type, year=polling_result.year,
            defaults={'total_votes': total}
        )

    # Re-calculate Constituency scope
    save_scope_total('Constituency', cz_id=constituency.id, filters={'polling_result__polling_station__constituency': constituency})
    
    # Re-calculate Circle scope
    save_scope_total('Circle', c_id=circle.id, filters={'polling_result__polling_station__constituency__circle': circle})
    
    # Re-calculate District scope
    save_scope_total('District', d_id=district.id, filters={'polling_result__polling_station__constituency__circle__district': district})
    
    # Re-calculate National scope
    save_scope_total('National', filters={})
