from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms

from .models import Address


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ('label', 'line1', 'city', 'pincode')
