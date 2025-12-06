from io import BytesIO
import base64
import json
import profile
import qrcode
from datetime import datetime as dt
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login, logout as django_logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Sum, Q
from django.utils import timezone
from . import models        # keep a module import so we don't assume exact class capitalization
from .form import (
    BookingForm, LoginForm, OwnerSignupForm,
    TurfForm, UserSignupForm
)

User = get_user_model()


# ---------------------------
# Helper utilities
# ---------------------------
def is_owner(user):
    """Return True if the user has owner role. Adjust if your role field name differs."""
    return getattr(user, "role", "") == "owner"


def generate_upi_qr_base64(upi_link: str) -> str:
    """
    Generate a PNG QR image from a UPI link and return base64-encoded string.
    Returns empty string on failure.
    """
    try:
        qr = qrcode.make(upi_link)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        return ""


# ---------------------------
# Public / Browsing Views
# ---------------------------
def home(request):
    """Homepage: show a few turfs (first 4)."""
    turfs = models.Turf.objects.all()[:4]
    return render(request, "home.html", {"turfs": turfs})


def turfs(request):
    """
    Turf listing with optional filtering by city, sport, and free-text search.
    Returns all matching turfs and a unique list of cities for filters.
    """
    selected_city = request.GET.get("city", "").strip()
    selected_sport = request.GET.get("sport", "").strip()
    search_query = request.GET.get("q", "").strip()

    qs = models.Turf.objects.all()

    if selected_city:
        qs = qs.filter(location__iexact=selected_city)

    if selected_sport:
        qs = qs.filter(sport__iexact=selected_sport)

    if search_query:
        qs = qs.filter(Q(name__icontains=search_query) | Q(location__icontains=search_query))

    # distinct list of locations for filter UI
    cities = models.Turf.objects.values_list("location", flat=True).distinct().order_by("location")

    return render(request, "turfs.html", {
        "turfs": qs,
        "cities": cities,
        "selected_city": selected_city,
        "selected_sport": selected_sport,
        "search_query": search_query,
    })


def turf_detail(request, turf_id):
    """Show single turf detail + booking form (render same template used by booking page)."""
    turf = get_object_or_404(models.Turf, id=turf_id)
    form = BookingForm(initial={"payable_now": turf.price_per_hour})  # example pre-fill
    return render(request, "bookingpage.html", {"turf": turf, "form": form})


# ---------------------------
# Booking / Payment Views
# ---------------------------
@login_required
def book_turf(request, turf_id):
    """
    Create a Booking (keeps it pending) and redirect to payment page.
    If form invalid, re-render booking page with errors.
    """
    turf = get_object_or_404(models.Turf, id=turf_id)

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.turf = turf
            booking.user = request.user if hasattr(booking, "user") else None  # optional: attach user
            booking.payment_status = models.Booking.PENDING
            # if payable_now is blank, compute an example (duration * turf.price_per_hour)
            if not booking.payable_now:
                # safe default: assume a 'duration' field exists (in hours)
                try:
                    duration = Decimal(getattr(booking, "duration", 1))
                    booking.payable_now = (turf.price_per_hour or Decimal("0")) * duration
                except Exception:
                    booking.payable_now = turf.price_per_hour or 0
            booking.save()
            return redirect("booking_pay", booking_id=booking.id)
    else:
        form = BookingForm(initial={"payable_now": turf.price_per_hour})

    return render(request, "bookingpage.html", {"turf": turf, "form": form})


@login_required
def booking_pay(request, booking_id):
    """
    Show UPI deep link and QR code for payment.
    Uses owner's UPI id from profile (owner must have set it).
    """
    booking = get_object_or_404(models.Booking, id=booking_id)

    # Protect: only the booking owner (or turf owner) should view this
    if booking.user and booking.user != request.user and not is_owner(request.user):
        messages.error(request, "You don't have permission to view this payment page.")
        return redirect("home")

    # Get owner's UPI; guard against missing profile or UPI
    owner_profile = getattr(booking.turf.owner, "profile", None)
    owner_upi = getattr(owner_profile, "upi_id", None)

    if not owner_upi:
        messages.error(request, "Owner hasn't configured UPI. Contact the owner.")
        return redirect("home")

    # Build UPI deep link
    upi_link = (
        f"upi://pay?"
        f"pa={owner_upi}&"
        f"pn={booking.turf.owner.get_full_name() or booking.turf.owner.username}&"
        f"am={booking.payable_now}&"
        f"cu=INR&"
        f"tn=Booking {booking.id}"
    )

    qr_image_b64 = generate_upi_qr_base64(upi_link)

    return render(request, "booking_pay.html", {
        "booking": booking,
        "upi_qr": qr_image_b64,
        "upi_link": upi_link,
    })


@require_POST
@login_required
def confirm_payment(request, booking_id):
    """
    Endpoint the frontend calls after payment is completed.
    Expects POST data with 'txn_id' and optional 'upi_id'.
    Marks booking as PAID on success.
    """
    booking = get_object_or_404(models.Booking, id=booking_id)

    # Only booking creator or turf owner can confirm payment
    if booking.user and booking.user != request.user and booking.turf.owner != request.user:
        return HttpResponseBadRequest("Not allowed")

    txn_id = request.POST.get("txn_id", "").strip()
    upi_id = request.POST.get("upi_id", "").strip() or getattr(booking, "upi_id", "")

    if not txn_id:
        messages.error(request, "Transaction id required.")
        return redirect("booking_pay", booking_id=booking.id)

    # Mark paid and save transaction info
    booking.txn_id = txn_id
    booking.upi_id = upi_id
    booking.payment_status = models.Booking.PAID
    booking.save()

    # TODO: send confirmation email / sms here if desired

    return redirect("booking_success", booking_id=booking.id)


@login_required
def booking_success(request, booking_id):
    """Show booking receipt / confirmation page."""
    booking = get_object_or_404(models.Booking, id=booking_id)
    return render(request, "booking_receipt.html", {"booking": booking})

def owner_dashboard(request):
    """
    Owner dashboard:
    - Add Turf (form POST)
    - Show owner's turfs
    - Show basic analytics (counts, bookings per turf, monthly revenue)
    """
    # Turf add form handling
    if request.method == "POST":
        form = TurfForm(request.POST, request.FILES)
        if form.is_valid():
            turf = form.save(commit=False)
            turf.owner = request.user
            turf.save()
            messages.success(request, "Turf added.")
            return redirect("owner_dashboard")
    else:
        form = TurfForm()

    # Owner's turfs
    turfs = models.Turf.objects.filter(owner=request.user)

    # Analytics
    total_turfs = turfs.count()

    # Bookings per turf name (owner's turfs only)
    bookings_per_turf = (
        models.Booking.objects.filter(turf__owner=request.user)
        .values("turf__name")
        .annotate(total=Count("id"))
    )

    # Monthly revenue (for the current month)
    now = timezone.now()
    monthly_revenue = (
        models.Booking.objects.filter(turf__owner=request.user, date__year=now.year, date__month=now.month)
        .aggregate(total=Sum("payable_now"))["total"] or 0
    )

    # Data for charts (simple lists)
    turf_names = [t.name for t in turfs]
    turf_bookings = [models.Booking.objects.filter(turf=t).count() for t in turfs]
    time = [models.Booking.objects.filter(turf=t).count() for t in turfs]

    return render(request, "owner_dashboard.html", {
        "turfs": turfs,
        "form": form,
        "total_turfs": total_turfs,
        "bookings_per_turf": bookings_per_turf,
        "monthly_revenue": monthly_revenue,
        "turf_names": turf_names,
        "turf_bookings": turf_bookings,
        "time":time,
    })

@login_required
def add_turf(request):
    """Separate page to add a turf (optional if owner_dashboard contains form)."""
    if request.method == "POST":
        form = TurfForm(request.POST, request.FILES)
        if form.is_valid():
            turf = form.save(commit=False)
            turf.owner = request.user
            turf.save()
            messages.success(request, "Turf added.")
            return redirect("owner_dashboard")
    else:
        form = TurfForm()
    return render(request, "add_turf.html", {"form": form})


@login_required
def update_turf(request, id):
    """Edit an existing turf owned by the current owner."""
    turf = get_object_or_404(models.Turf, id=id, owner=request.user)
    if request.method == "POST":
        form = TurfForm(request.POST, request.FILES, instance=turf)
        if form.is_valid():
            form.save()
            messages.success(request, "Turf updated.")
            return redirect("owner_dashboard")
    else:
        form = TurfForm(instance=turf)
    return render(request, "edit_turf.html", {"form": form, "turf": turf})

@login_required
def delete_turf(request, id):
    """Delete a turf owned by the owner."""
    turf = get_object_or_404(models.Turf, id=id, owner=request.user)
    turf.delete()
    messages.success(request, "Turf deleted.")
    return redirect("owner_dashboard")


# ---------------------------
# Authentication: Login / Signup
# ---------------------------
def role(request):
    """Role choice page (owner or user) before signup/login."""
    return render(request, "auth/role.html")


def login_user(request, role=None):
    """
    Handles both owner and user login depending on role passed.
    We store requested role in session so OAuth callback can set role later (used in google_login_redirect).
    """
    request.session["login_role"] = role

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user:
                # check role match
                try:
                    user_type = user.profile.user_type
                except models.profile.DoesNotExist:
                    messages.error(request, "Profile missing for this user.")
                    return redirect('login_user')

                if user_type == role:
                    django_login(request, user)
                    return redirect('owner_dashboard' if role == 'owner' else 'home')

                messages.error(request, f"This account is not a {role} account.")
                return redirect('login_user')

            messages.error(request, "Invalid username or password.")
            return redirect('login_user')
    else:
        form = LoginForm()

    return render(request, "auth/login.html", {"form": form, "role": role})


def login_owner(request):
    """Shortcut to login page for owners."""
    request.session["login_role"] = "owner"
    return login_user(request, role="owner")


def login_user_route(request):
    """Shortcut to login page for regular users."""
    request.session["login_role"] = "user"
    return login_user(request, role="user")


def signup_user(request):
    """
    Signup a regular user. After saving, ensure a profile exists and is tagged as 'user'.
    """
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = "user"
            user.save()

            # ensure profile exists (some projects attach profile via signal)
            profile_obj, created = models.profile.objects.get_or_create(user=user)
            profile_obj.user_type = "user"
            profile_obj.save()

            messages.success(request, "User registered successfully!")
            return redirect("login_user")
    else:
        form = UserSignupForm()

    return render(request, "auth/signup.html", {"form": form, "role": "user"})


def signup_owner(request):
    """
    Signup an owner account. After saving, ensure profile exists and user.role set.
    """
    if request.method == "POST":
        form = OwnerSignupForm(request.POST)
        if form.is_valid():
            owner = form.save(commit=False)
            owner.role = "owner"
            owner.save()

            profile_obj, created = models.profile.objects.get_or_create(user=owner)
            profile_obj.user_type = "owner"
            profile_obj.save()

            messages.success(request, "Owner registered successfully!")
            return redirect("login_owner")
    else:
        form = OwnerSignupForm()

    return render(request, "auth/signup.html", {"form": form, "role": "owner"})


def logout_user(request):
    """Logout any logged in user."""
    django_logout(request)
    return redirect("home")

# ---------------------------
# Profile Views
# ---------------------------

def profile_view(request):
    """
    Edit and show regular user profile.
    Handles avatar upload and simple fields.
    """
    profile_obj = getattr(request.user, "profile", None)
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        name_parts = full_name.split(" ", 1)
        request.user.first_name = name_parts[0] if name_parts else ""
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        # fields to store on profile (guard against missing attributes)
        if profile_obj is not None:
            profile_obj.phone = request.POST.get("phone", profile_obj.phone)
            profile_obj.location = request.POST.get("location", profile_obj.location)
            profile_obj.game = request.POST.get("game", profile_obj.game)
            profile_obj.bio = request.POST.get("bio", profile_obj.bio)
            if "avatar" in request.FILES:
                profile_obj.avatar = request.FILES["avatar"]

        request.user.save()
        if profile_obj is not None:
            profile_obj.save()

        return redirect("profile_view")

    return render(request, "profile.html", {"profile": profile_obj})


def owner_profile_view(request):
    """
    Edit and show owner profile (owner-specific fields such as UPI).
    """
    profile_obj = getattr(request.user, "profile", None)

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        name_parts = full_name.split(" ", 1)
        request.user.first_name = name_parts[0] if name_parts else ""
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        if profile_obj is not None:
            profile_obj.phone = request.POST.get("phone", profile_obj.phone)
            profile_obj.location = request.POST.get("location", profile_obj.location)
            profile_obj.game = request.POST.get("game", profile_obj.game)
            profile_obj.bio = request.POST.get("bio", profile_obj.bio)
            profile_obj.upi_id = request.POST.get("upi_id", profile_obj.upi_id)
            if "avatar" in request.FILES:
                profile_obj.avatar = request.FILES["avatar"]

        request.user.save()
        if profile_obj is not None:
            profile_obj.save()

        return redirect("owner_profile_view")

    return render(request, "owner_profile.html", {"profile": profile_obj})


def profile_redirect(request):
    """Redirect user to appropriate profile view depending on their profile.user_type."""
    profile_obj = getattr(request.user, "profile", None)
    user_type = getattr(profile_obj, "user_type", None)

    if user_type == "owner":
        return redirect("owner_profile_view")
    return redirect("profile_view")


def user_profile(request):
    """Simple view that renders user info (read-only page)."""
    return render(request, "auth/user_profile.html", {"user": request.user})


def owner_profile(request):
    """Simple view for owner info (read-only page)."""
    return render(request, "auth/owner_profile.html", {"user": request.user})


# Placeholder / legacy view — remove if unused
def turms(request):
    return render(request, "turms.html")
