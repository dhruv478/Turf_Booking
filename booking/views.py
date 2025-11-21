# ------------------------------ IMPORTS ------------------------------
# Importing required modules and Django functions
import datetime
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from .models import Booking, Turf
from .form import BookingForm, LoginForm, OwnerSignupForm, TurfForm, UserSignupForm
import json
from .models import profile
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model, login
from firebase_admin import auth as firebase_auth
import qrcode
from io import BytesIO
import base64
from datetime import datetime
from django.db.models import Count, Sum

# ------------------------------ HOME PAGE ------------------------------
def home(request):
    # Show only first 4 turfs on homepage
    turfs = Turf.objects.all()
    return render(request, "home.html", {"turfs": turfs})


# ------------------------------ OWNER DASHBOARD ------------------------------
def owner_dashboard(request):
    # Add turf when form is submitted
    if request.method == "POST":
        form = TurfForm(request.POST, request.FILES)
        if form.is_valid():
            turf = form.save(commit=False)
            turf.owner = request.user  # Set owner as logged-in user
            turf.save()
            return redirect('owner_dashboard')
    else:
        form = TurfForm()

    # Get all turfs by current owner
    turfs = Turf.objects.filter(owner=request.user)

    # Dashboard statistics
    total_turfs = turfs.count()  # Total turfs owner added

    # Count bookings for each turf
    bookings_per_turf = Booking.objects.filter(
        turf__owner=request.user
    ).values('turf__name').annotate(total=Count('id'))

    # Monthly revenue (current month)
    monthly_revenue = Booking.objects.filter(
        turf__owner=request.user,
        date__month=datetime.now().month
    ).aggregate(total=Sum('payable_now'))['total'] or 0

    # Data for chart
    turf_names = [t.name for t in turfs]
    turf_bookings = [Booking.objects.filter(turf=t).count() for t in turfs]

    return render(request, 'owner_dashboard.html', {
        'turfs': turfs,
        'form': form,
        'total_turfs': total_turfs,
        'bookings_per_turf': bookings_per_turf,
        'monthly_revenue': monthly_revenue,
        'turf_names': turf_names,
        'turf_bookings': turf_bookings,
    })


# ------------------------------ ADD TURF ------------------------------
def add_turf(request):
    if request.method == "POST":
        form = TurfForm(request.POST, request.FILES)
        if form.is_valid():
            turf = form.save(commit=False)
            turf.owner = request.user
            turf.save()
            return redirect("owner_dashboard")
    else:
        form = TurfForm()
    return render(request, "add_turf.html", {"form": form})


# ------------------------------ UPDATE TURF ------------------------------
def update_turf(request, id):
    # Allow owner to edit a turf
    turf = get_object_or_404(Turf, id=id, owner=request.user)

    if request.method == "POST":
        form = TurfForm(request.POST, request.FILES, instance=turf)
        if form.is_valid():
            form.save()
            return redirect("owner_dashboard")
    else:
        form = TurfForm(instance=turf)

    return render(request, "edit_turf.html", {"form": form, "turf": turf})


# ------------------------------ DELETE TURF ------------------------------
def delete_turf(request, id):
    turf = get_object_or_404(Turf, id=id, owner=request.user)
    turf.delete()
    return redirect('owner_dashboard')


# ------------------------------ DISPLAY ALL TURFS ------------------------------
def turfs(request):
    # Unique city list for filter
    cities = Turf.objects.values_list('location', flat=True).distinct().order_by('location')

    # Read filters from URL
    selected_city = request.GET.get('city', '')
    selected_sport = request.GET.get('sport', '')
    search_query = request.GET.get('q')

    turfs = Turf.objects.all()

    # Filter by city
    if selected_city:
        turfs = turfs.filter(location__iexact=selected_city)

    # Filter by sport
    if selected_sport:
        turfs = turfs.filter(sport__iexact=selected_sport)

    # Search by name or location
    if search_query:
        turfs = turfs.filter(
            Q(name__icontains=search_query) |
            Q(location__icontains=search_query)
        )

    return render(request, 'turfs.html', {
        'turfs': turfs,
        'cities': cities,
        'selected_city': selected_city,
        'selected_sport': selected_sport,
        'search_query': search_query,
    })


# ------------------------------ TURF DETAILS PAGE ------------------------------
def turf_detail(request, turf_id):
    turf = get_object_or_404(Turf, id=turf_id)
    return render(request, 'bookingpage.html', {'turf': turf})


# ------------------------------ BOOKING TURF ------------------------------
def book_turf(request, turf_id):
    turf = get_object_or_404(Turf, id=turf_id)

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.turf = turf
            booking.payment_status = Booking.PENDING  # Payment pending
            booking.save()
            return redirect('booking_pay', booking_id=booking.id)
    else:
        form = BookingForm(initial={'payable_now': turf.price_per_hour})

    return render(request, 'bookingpage.html', {'turf': turf, 'form': form})


# ------------------------------ PAYMENT PAGE ------------------------------
def booking_pay(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    # Owner UPI
    owner_upi = booking.turf.owner.profile.upi_id

    # Create UPI payment link
    upi_link = (
        f"upi://pay?"
        f"pa={owner_upi}&"
        f"pn={booking.turf.owner.first_name}&"
        f"am={booking.payable_now}&"
        f"cu=INR&"
        f"tn=Booking {booking.id}"
    )

    # Generate QR Code
    qr = qrcode.make(upi_link)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_image = base64.b64encode(buffer.getvalue()).decode()

    return render(request, "booking_pay.html", {
        "booking": booking,
        "upi_qr": qr_image,
        "upi_link": upi_link,
    })


# ------------------------------ CONFIRM PAYMENT ------------------------------
@require_POST
def confirm_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    txn_id = request.POST.get('txn_id')
    upi_id = request.POST.get('upi_id', booking.upi_id)

    if not txn_id:
        messages.error(request, "Transaction ID required.")
        return redirect('booking_pay', booking_id=booking.id)

    booking.txn_id = txn_id
    booking.upi_id = upi_id
    booking.payment_status = Booking.PAID
    booking.save()

    return redirect('booking_success', booking_id=booking.id)


# ------------------------------ BOOKING SUCCESS RECEIPT ------------------------------
def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'booking_receipt.html', {'booking': booking})


# ------------------------------ LOGIN (USER & OWNER) ------------------------------
def login_user(request, role=None):
    request.session['login_role'] = role  # Save role for Google login

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user:
                if getattr(user, 'role', None) == role:
                    login(request, user)

                    if role == 'owner':
                        return redirect('owner_dashboard')
                    return redirect('home')
                else:
                    messages.error(request, f"This account is not a {role} account.")
                    return redirect(request.path)

            messages.error(request, "Invalid username or password.")
            return redirect(request.path)

    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form, 'role': role})


def login_owner(request):
    request.session['login_role'] = 'owner'
    return login_user(request, role='owner')


def login_user_route(request):
    request.session['login_role'] = 'user'
    return login_user(request, role='user')


# ------------------------------ SIGNUP (USER) ------------------------------
def signup_user(request):
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'user'
            user.save()

            profile_obj, created = profile.objects.get_or_create(user=user)
            profile_obj.user_type = "user"
            profile_obj.save()

            messages.success(request, 'User registered successfully!')
            return redirect('login_user')
    else:
        form = UserSignupForm()

    return render(request, 'auth/signup.html', {'form': form, 'role': 'user'})


# ------------------------------ SIGNUP (OWNER) ------------------------------
def signup_owner(request):
    if request.method == 'POST':
        form = OwnerSignupForm(request.POST)
        if form.is_valid():
            owner = form.save(commit=False)
            owner.role = 'owner'
            owner.save()

            profile_obj, created = profile.objects.get_or_create(user=owner)
            profile_obj.user_type = "owner"
            profile_obj.save()

            messages.success(request, 'Owner registered successfully!')
            return redirect('login_owner')
    else:
        form = OwnerSignupForm()

    return render(request, 'auth/signup.html', {'form': form, 'role': 'owner'})


# ------------------------------ SELECT ROLE PAGE ------------------------------
def role(request):
    return render(request, 'auth/role.html')


User = get_user_model()

# ------------------------------ FIREBASE LOGIN ------------------------------
@csrf_exempt
def firebase_login(request):
    """
    Login using Google Firebase Token
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        body = json.loads(request.body.decode('utf-8'))
        id_token = body.get('token')

        if not id_token:
            return JsonResponse({'error': 'No token provided'}, status=400)

        decoded = firebase_auth.verify_id_token(id_token)
        uid = decoded.get('uid')
        email = decoded.get('email')
        name = decoded.get('name') or decoded.get('email').split('@')[0]

        # Create or get user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': name}
        )

        # Ensure profile exists
        try:
            profile = user.profile
        except profile.DoesNotExist:
            profile.objects.create(user=user, user_type='user')

        login(request, user)

        return JsonResponse({'status': 'ok', 'created': created})

    except Exception as e:
        return JsonResponse({'error': 'token verification failed', 'detail': str(e)}, status=400)


# ------------------------------ GOOGLE LOGIN REDIRECT ------------------------------
def google_login_redirect(request):
    user = request.user
    role = request.session.get("login_role", "user")

    profile_obj, created = profile.objects.get_or_create(user=user)
    profile_obj.user_type = role
    profile_obj.save()

    user.role = role
    user.save()

    if role == "owner":
        return redirect("owner_dashboard")

    return redirect("home")


# ------------------------------ LOGOUT ------------------------------
def logout_user(request):
    logout(request)
    return redirect('home')


# ------------------------------ USER PROFILE ------------------------------
def profile_view(request):
    profile = request.user.profile

    if request.method == "POST":

        full_name = request.POST.get("full_name", "")
        name_parts = full_name.split(" ", 1)

        # Update user name
        request.user.first_name = name_parts[0]
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Update profile data
        profile.phone = request.POST.get("phone")
        profile.location = request.POST.get("location")
        profile.game = request.POST.get("game")
        profile.bio = request.POST.get("bio")

        if "avatar" in request.FILES:
            profile.avatar = request.FILES["avatar"]

        request.user.save()
        profile.save()

        return redirect("profile_view")

    return render(request, "profile.html", {"profile": profile})


# ------------------------------ OWNER PROFILE ------------------------------
def owner_profile_view(request):
    profile = request.user.profile

    if request.method == "POST":

        full_name = request.POST.get("full_name", "")
        name_parts = full_name.split(" ", 1)

        request.user.first_name = name_parts[0]
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        profile.phone = request.POST.get("phone")
        profile.location = request.POST.get("location")
        profile.game = request.POST.get("game")
        profile.bio = request.POST.get("bio")
        profile.upi_id = request.POST.get("upi_id")

        if "avatar" in request.FILES:
            profile.avatar = request.FILES["avatar"]

        request.user.save()
        profile.save()

        return redirect("owner_profile_view")

    return render(request, "owner_profile.html", {"profile": profile})


# ------------------------------ PROFILE REDIRECT ------------------------------
def profile_redirect(request):
    user_type = request.user.profile.user_type

    if user_type == "owner":
        return redirect("owner_profile_view")
    else:
        return redirect("profile_view")


# ------------------------------ STATIC PROFILE VIEW ------------------------------
def user_profile(request):
    return render(request, 'auth/user_profile.html', {'user': request.user})


def owner_profile(request):
    return render(request, 'auth/owner_profile.html', {'user': request.user})


# ------------------------------ TERMS & CONDITIONS ------------------------------
def turms(request):
    return render(request, "turms.html")
