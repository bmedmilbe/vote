# poll/signals/handlers.py - Updated signal handler
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from poll.models import AccumulatedResult, PollingStationResult, VoteCount

logger = logging.getLogger(__name__)


@receiver(post_save, sender=VoteCount)
@receiver(post_delete, sender=VoteCount)
def update_accumulated_metrics(sender, instance, **kwargs):
    """Update accumulated results when VoteCount changes."""
    try:
        polling_result = instance.polling_result
        candidate = instance.candidate_registration
        
        # Get geographic ancestors
        constituency = polling_result.polling_station.constituency
        circle = constituency.circle
        district = circle.district
        
        election_type = polling_result.election_type
        year = polling_result.year
        
        with transaction.atomic():
            # Helper to safely update or create
            def safe_update_or_create(**kwargs):
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
            
            # 1. Update Constituency level - Only candidate votes
            constituency_total = VoteCount.objects.filter(
                candidate_registration=candidate,
                polling_result__election_type=election_type,
                polling_result__year=year,
                polling_result__polling_station__constituency=constituency
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            safe_update_or_create(
                scope='Constituency',
                constituency=constituency,
                candidate_registration=candidate,
                election_type=election_type,
                year=year,
                defaults={'total_votes': constituency_total}
            )
            
            # 2. Update Circle level - Only candidate votes
            circle_total = VoteCount.objects.filter(
                candidate_registration=candidate,
                polling_result__election_type=election_type,
                polling_result__year=year,
                polling_result__polling_station__constituency__circle=circle
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            safe_update_or_create(
                scope='Circle',
                circle=circle,
                candidate_registration=candidate,
                election_type=election_type,
                year=year,
                defaults={'total_votes': circle_total}
            )
            
            # 3. Update District level - Only candidate votes
            district_total = VoteCount.objects.filter(
                candidate_registration=candidate,
                polling_result__election_type=election_type,
                polling_result__year=year,
                polling_result__polling_station__constituency__circle__district=district
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            safe_update_or_create(
                scope='District',
                district=district,
                candidate_registration=candidate,
                election_type=election_type,
                year=year,
                defaults={'total_votes': district_total}
            )
            
            # 4. Update National level - Only candidate votes
            national_total = VoteCount.objects.filter(
                candidate_registration=candidate,
                polling_result__election_type=election_type,
                polling_result__year=year
            ).aggregate(total=Sum('total_votes'))['total'] or 0
            
            safe_update_or_create(
                scope='National',
                candidate_registration=candidate,
                election_type=election_type,
                year=year,
                defaults={'total_votes': national_total}
            )
            
        logger.info(f"✅ Accumulated results updated for candidate {candidate.id}")
        
        # Broadcast via WebSocket
        broadcast_accumulated_update(election_type, year)
            
    except Exception as e:
        logger.error(f"❌ Error updating accumulated metrics: {e}")
        import traceback
        traceback.print_exc()


def broadcast_accumulated_update(election_type, year):
    """Broadcast accumulated results update via WebSocket."""
    try:
        national_results = AccumulatedResult.objects.filter(
            scope='National',
            election_type=election_type,
            year=year
        ).select_related('candidate_registration__contender')
        
        # Get overall election totals (including blanks and nulls for summary)
        results = PollingStationResult.objects.filter(
            election_type=election_type,
            year=year
        )
        
        total_abstentions = results.aggregate(total=Sum('abstentions'))['total'] or 0
        total_blank = results.aggregate(total=Sum('blank_votes'))['total'] or 0
        total_null = results.aggregate(total=Sum('null_votes'))['total'] or 0
        total_valid_votes = sum(r.total_votes for r in national_results)
        
        from poll.serializers import WebSocketAccumulatedResultSerializer
        serializer = WebSocketAccumulatedResultSerializer(national_results, many=True)
        
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'election_election_updates',
                {
                    'type': 'broadcast_vote_update',
                    'data': {
                        'type': 'results_update',
                        'data': serializer.data,
                        'election_type': election_type,
                        'year': year,
                        'summary': {
                            'total_valid_votes': total_valid_votes,
                            'total_abstentions': total_abstentions,
                            'total_blank_votes': total_blank,
                            'total_null_votes': total_null,
                            'total_votes': total_valid_votes + total_abstentions + total_blank + total_null,
                        }
                    }
                }
            )
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}")