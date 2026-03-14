from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .auth import ORGANIZER_GROUP, STUDENT_GROUP, get_organizer_profile, get_student_profile


class RoleLoginForm(AuthenticationForm):
    ROLE_CHOICES = (
        ("student", "Student"),
        ("organizer", "Organizer"),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)

    def clean(self):
        cleaned = super().clean()
        user = self.get_user()
        role = cleaned.get("role")
        if not user:
            return cleaned

        if user.is_superuser:
            # Allow superuser to choose either role for quick testing.
            if role == "student":
                get_student_profile(user)
            elif role == "organizer":
                get_organizer_profile(user)
            return cleaned

        if role == "student":
            if not user.groups.filter(name=STUDENT_GROUP).exists():
                raise forms.ValidationError(
                    "This account is not a Student. Please switch role."
                )
            get_student_profile(user)
        elif role == "organizer":
            if not user.groups.filter(name=ORGANIZER_GROUP).exists():
                raise forms.ValidationError(
                    "This account is not an Organizer. Please switch role."
                )
            get_organizer_profile(user)

        return cleaned


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

