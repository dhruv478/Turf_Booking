"""
URL configuration for turfbooking project.

This file maps URLs to views.
Django processes each URL from top to bottom and matches the correct view.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from booking.views import *

urlpatterns = [

    # ADMIN PANEL
    path('admin/', admin.site.urls),

    # PUBLIC PAGES
    path('', home, name='home'),                # Home page
    path('turfs/', turfs, name='turfs'),        # Show all turfs
    path('turms/', turms, name='turms'),        # Terms page (same view as turfs)

    # ROLE SELECTION PAGE
    path('auth/role/', role, name='role'),

    # LOGIN ROUTES
    path('auth/login_user/', lambda r: login_user(r, 'user'), name='login_user'), # Login for normal users
    path('auth/login_owner/', login_owner, name='login_owner'),  # Login for turf owners

    # SIGNUP ROUTES
    path('auth/signup_user/', signup_user, name='signup_user'),   # User signup
    path('auth/signup_owner/', signup_owner, name='signup_owner'), # Owner signup


    # LOGOUT
    path('auth/logout/', logout_user, name='logout'),

    # OWNER (DASHBOARD + CRUD)
    path('owner/', owner_dashboard, name="owner_dashboard"),         # Owner dashboard
    path('owner/add/', add_turf, name="add_turf"),                   # Add turf
    path('owner/update/<int:id>/', update_turf, name="update_turf"), # Edit turf
    path('owner/delete/<int:id>/', delete_turf, name="delete_turf"), # Delete turf

    # TURF DETAIL + BOOKING
    path("turf/<int:turf_id>/", turf_detail, name="turf_detail"),    # Turf detail page
    path('turf/<int:turf_id>/book/', book_turf, name='book_turf'),   # Book turf

    # PAYMENT ROUTES
    path('booking/<int:booking_id>/pay/', booking_pay, name='booking_pay'),
    path('booking/<int:booking_id>/confirm/', confirm_payment, name='confirm_payment'),
    path('booking/<int:booking_id>/success/', booking_success, name='booking_success'),

    # PROFILE ROUTES
    path('profile/', profile_redirect, name='profile'),               # Auto redirect based on user type
    path('profile/edit/user/', profile_view, name='profile_view'),    # User edit profile
    path('profile/edit/owner', owner_profile_view, name='owner_profile_view'),  # Owner edit profile

    path('profile/user/', user_profile, name='user_profile'),         # User profile page
    path('profile/owner/', owner_profile, name='owner_profile'),      # Owner profile page
]

# MEDIA FILES (Images / Turf Pics / Avatar)


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)