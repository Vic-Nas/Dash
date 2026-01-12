from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class UpdateLastActivityMiddleware(MiddlewareMixin):
    """
    Update user's lastActivityAt timestamp on every request.
    This helps the cleanup task identify truly inactive accounts.
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Update once per minute to avoid too many DB writes
            try:
                profile = request.user.profile
                now = timezone.now()
                
                # Only update if last activity was more than 1 minute ago
                if not profile.lastActivityAt or (now - profile.lastActivityAt).total_seconds() > 60:
                    profile.lastActivityAt = now
                    profile.save(update_fields=['lastActivityAt'])
            except Exception:
                # Silently fail - don't break the request
                pass
        
        return None