from django import forms
from .models import Profile


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