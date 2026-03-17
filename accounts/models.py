from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile"
    )
    favorite_events = models.ManyToManyField(
        "events.Event", blank=True, related_name="favorited_by"
    )

    preferences = models.JSONField(
        default=dict,blank=True
    )

    preferences_updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self) -> str:
        return f"StudentProfile(user={self.user_id})"


class OrganizerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organizer_profile",
    )

    def __str__(self) -> str:
        return f"OrganizerProfile(user={self.user_id})"
