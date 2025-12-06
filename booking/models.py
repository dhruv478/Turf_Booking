from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# ------------------------------
# USER PROFILE MODEL
# ------------------------------
# Stores additional information for each User.
# One profile per user → OneToOneField
class profile(models.Model):

    # Choices for user role
    USER_TYPE = (
        ('owner','owner'),
        ('user','user'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # owner → turf owner
    # user → normal user who books turf
    user_type = models.CharField(max_length=50, choices=USER_TYPE)

    # Extra profile fields
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    game = models.CharField(max_length=50, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # Profile picture
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Owner’s UPI ID for payment
    upi_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        # Display username and role
        return f"{self.user.username} ({ self.user_type })"


# ------------------------------
# SIGNAL – CREATE PROFILE AUTOMATICALLY
# ------------------------------
# When a new Django User is created, create a matching Profile automatically.
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile.objects.create(user=instance)


# ------------------------------
# SIGNAL – SAVE PROFILE
# ------------------------------
# When User is saved, also save profile data.
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()



# ------------------------------
# TURF MODEL
# ------------------------------
# Stores all turf details posted by turf owners
class Turf(models.Model):

    # Turf owner reference (User table)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # Basic turf details
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    sport = models.CharField(max_length=50, null=True)

    # Contact and pricing
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    price_per_hour = models.DecimalField(max_digits=6, decimal_places=2)

    # Extra details
    description = models.CharField(max_length=200, null=True, blank=True)
    start_time = models.CharField(null=True, blank=True)
    end_time = models.CharField(null=True, blank=True)
    amenities = models.CharField(max_length=200, null=True, blank=True)

    # Turf image
    image = models.ImageField(upload_to="turfs/", null=True, blank=True)

    def __str__(self):
        # Format display: Turf Name (Location - Sport)
        return f"{self.name} ({self.location} - {self.sport})"



# ------------------------------
# BOOKING MODEL
# ------------------------------
# Stores user bookings for turfs
class Booking(models.Model):

    # Payment status options
    PENDING = 'pending'
    PAID = 'paid'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (PENDING, 'Pending Payment'),
        (PAID, 'Paid'),
        (CANCELLED, 'Cancelled'),
    ]

    # Reference to turf
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE, related_name='bookings')

    # User booking details
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)

    # Booking schedule
    date = models.DateField()
    time = models.TimeField()
    duration = models.CharField(max_length=50)
    TIME_SLOTS = [
        ("06:00-07:00", "06:00 - 07:00"),
        ("07:00-08:00", "07:00 - 08:00"),
        ("08:00-09:00", "08:00 - 09:00"),
        ("09:00-10:00", "09:00 - 10:00"),
        ("10:00-11:00", "10:00 - 11:00"),
        ("18:00-19:00", "06:00 - 07:00"),
        ("19:00-20:00", "07:00 - 08:00"),
        ("20:00-21:00", "08:00 - 09:00"),
        ("21:00-22:00", "09:00 - 10:00"),
        ("22:00-23:00", "10:00 - 11:00"),
        ("23:00-00:00", "11:00 - 12:00"),
        ("00:00-1:00", "12:00 - 01:00"),
        ("1:00-2:00", "01:00 - 02:00"),
        ("2:00-3:00", "02:00 - 03:00"),
        ("3:00-4:00", "03:00 - 04:00"),
    ]
    slot = models.CharField(max_length=20, choices=TIME_SLOTS,null=True)
    # User UPI (optional)
    upi_id = models.CharField(max_length=100, blank=True, null=True)

    # Payment status
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    # Total amount user must pay
    payable_now = models.DecimalField(max_digits=10, decimal_places=2)

    # Booking created time
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        # Example: "Dhruv - ABC Turf (2025-11-21 10:00)"
        return f"{self.name} - {self.turf.name} ({self.date} {self.time})"
