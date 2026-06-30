# poll/migrations/XXXX_add_unique_constraint_to_accumulatedresult.py
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0006_pollingstationresult_notes_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='accumulatedresult',
            unique_together={
                ('scope', 'district', 'circle', 'constituency', 
                 'candidate_registration', 'election_type', 'year')
            },
        ),
    ]