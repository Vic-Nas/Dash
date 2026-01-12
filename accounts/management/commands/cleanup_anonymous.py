from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from accounts.models import Profile


class Command(BaseCommand):
    help = 'Delete inactive anonymous accounts to prevent database buildup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete accounts inactive for this many days (default: 365)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dryRun = options['dry_run']
        
        cutoffDate = timezone.now() - timedelta(days=days)
        
        # Find accounts to delete:
        # - Still anonymous (isAnonymous=True)
        # - Haven't changed password (hasChangedPassword=False)
        # - Last activity before cutoff date
        User = get_user_model()
        
        accountsToDelete = User.objects.filter(
            profile__isAnonymous=True,
            profile__hasChangedPassword=False,
            profile__lastActivityAt__lt=cutoffDate
        ).select_related('profile')
        
        count = accountsToDelete.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No inactive anonymous accounts found.'))
            return
        
        if dryRun:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Would delete {count} accounts:'))
            for user in accountsToDelete[:10]:  # Show first 10
                lastActive = user.profile.lastActivityAt.strftime('%Y-%m-%d %H:%M')
                self.stdout.write(f'  - {user.username} (last active: {lastActive})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            self.stdout.write(self.style.WARNING(f'Deleting {count} inactive anonymous accounts...'))
            accountsToDelete.delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Successfully deleted {count} accounts.'))