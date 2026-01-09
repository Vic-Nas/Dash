from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django import forms
from .models import Profile


class SignUpForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'password1', 'password2')


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('profilePic',)
        widgets = {
            'profilePic': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            })
        }
