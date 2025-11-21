from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import profile

# Get the active User model (important when using custom users)
User = get_user_model()


# --------------------------------------------------------------
# SIGNAL: Create profile automatically after a new User is created
# --------------------------------------------------------------
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    This signal runs automatically whenever a User object is saved.
    If the User is newly created, we also create a matching Profile.
    
    Purpose:
    - Ensures every new user (Owner or Normal User) has a profile.
    - Avoids errors like user.profile.DoesNotExist.
    - Assigns default role = 'user' (you can update to 'owner' during signup).
    """

    if created:
        # Create profile only if it does not exist
        profile.objects.get_or_create(
            user=instance,
            defaults={"user_type": "user"}  # Default type assigned to new users
        )
