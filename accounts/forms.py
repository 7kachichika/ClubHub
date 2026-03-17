from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        return username


class RegistrationForm(UserCreationForm):
    ROLE_CHOICES = (
        ("student", "Student"),
        ("organizer", "Organizer"),
    )

    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username is required.")

        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")

        return username