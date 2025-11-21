from django import forms
from .models import Booking, Turf
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from booking.models import profile


# -------------------------------------------------------------------
# TURF FORM
# This form is used by Turf Owners to add or edit their turf details.
# It is directly linked to Turf model fields.
# -------------------------------------------------------------------
class TurfForm(forms.ModelForm):
    class Meta:
        model = Turf
        fields = [
            # 'owner',   # Owner is added automatically in views
            'name',
            'location',
            'sport',
            'contact_number',
            'price_per_hour',
            'description',
            'start_time',
            'end_time',
            'amenities',
            'image',
        ]


# -------------------------------------------------------------------
# BOOKING FORM
# Used by a user when booking a turf.
# Includes widgets for better UI and input controls.
# -------------------------------------------------------------------
class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['name', 'mobile', 'date', 'time', 'duration', 'upi_id', 'payable_now']

        # Custom widgets for better form appearance
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your full name'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10-digit phone number'
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'duration': forms.Select(choices=[
                ('1 Hour', '1 Hour'),
                ('2 Hours', '2 Hours'),
                ('3 Hours', '3 Hours'),
                ('4 Hours', '4 Hours')
            ], attrs={'class': 'form-control'}),
            'upi_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. yourname@upi'
            }),
            'payable_now': forms.NumberInput(attrs={
                'class': 'form-control',
                'readonly': True   # cannot edit amount manually
            }),
        }


# -------------------------------------------------------------------
# USER SIGNUP FORM (Normal User)
# Extends Django's default UserCreationForm.
# Also creates a Profile object automatically with user_type="user".
# -------------------------------------------------------------------
class UserSignupForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'placeholder': 'Email',
        'class': 'form-control'
    }))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Full Name', 'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'placeholder': 'Confirm Password', 'class': 'form-control'}),
        }

    def save(self, commit=True):
        """
        Save user and create profile with user_type='user'.
        """
        user = super().save(commit=False)
        if commit:
            user.save()
            profile.objects.create(user=user, user_type='user')  # Create Profile
        return user


# -------------------------------------------------------------------
# OWNER SIGNUP FORM (Turf Owner)
# Similar to user signup but assigns user_type="owner".
# -------------------------------------------------------------------
class OwnerSignupForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'placeholder': 'Email',
        'class': 'form-control'
    }))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'User Name', 'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'placeholder': 'Enter Password', 'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'placeholder': 'Confirm Password', 'class': 'form-control'}),
        }

    def save(self, commit=True):
        """
        Save owner user and create profile with user_type='owner'.
        """
        user = super().save(commit=False)
        if commit:
            user.save()
            profile.objects.create(user=user, user_type='owner')  # Create Owner Profile
        return user


# -------------------------------------------------------------------
# LOGIN FORM
# Extends Django AuthenticationForm with placeholders and CSS classes.
# Used for both User & Owner logins.
# -------------------------------------------------------------------
class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Email / Username',
        'class': 'form-control'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Password',
        'class': 'form-control'
    }))
