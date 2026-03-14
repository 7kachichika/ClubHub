from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.contrib.auth.decorators import login_required, user_passes_test

from .models import OrganizerProfile, StudentProfile


STUDENT_GROUP = "Students"
ORGANIZER_GROUP = "Organizers"

Role = Literal["student", "organizer"]


def _in_group(user, name: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=name).exists()


def is_student(user) -> bool:
    return _in_group(user, STUDENT_GROUP)


def is_organizer(user) -> bool:
    return _in_group(user, ORGANIZER_GROUP)


def get_student_profile(user) -> StudentProfile:
    profile, _ = StudentProfile.objects.get_or_create(user=user)
    return profile


def get_organizer_profile(user) -> OrganizerProfile:
    profile, _ = OrganizerProfile.objects.get_or_create(user=user)
    return profile


def student_required(view_func):
    return login_required(user_passes_test(is_student)(view_func))


def organizer_required(view_func):
    return login_required(user_passes_test(is_organizer)(view_func))


@dataclass(frozen=True)
class RoleRedirect:
    role: Role

    @property
    def dashboard_url_name(self) -> str:
        return "student_dashboard" if self.role == "student" else "organizer_dashboard"

