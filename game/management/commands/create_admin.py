from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create or update the Django superuser with fixed credentials."

    def handle(self, *args, **options):
        User = get_user_model()
        username = "Vic-Nas"
        email = "admin@example.com"
        password = "Brajulia2000"

        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        if created:
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
        else:
            if not user.is_superuser:
                user.is_superuser = True
            if not user.is_staff:
                user.is_staff = True
            user.email = email
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Updated superuser '{username}'."))
