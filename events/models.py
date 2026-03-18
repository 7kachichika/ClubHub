import uuid

from django.db import models
from django.db.models import Q


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return self.name


class Event(models.Model):
    organizer = models.ForeignKey(
        "accounts.OrganizerProfile", on_delete=models.CASCADE, related_name="events"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    cover_image = models.ImageField(upload_to="event_covers/",blank=True,null=True)
    
    start_at = models.DateTimeField()
    capacity = models.PositiveIntegerField()

    location_name = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    tags = models.ManyToManyField(Tag, blank=True, related_name="events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at", "id"]

    def __str__(self) -> str:
        return self.title


class Ticket(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        WAITLISTED = "WAITLISTED", "Waitlisted"
        CANCELLED = "CANCELLED", "Cancelled"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="tickets"
    )
    status = models.CharField(max_length=12, choices=Status.choices)
    ticket_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "student"],
                condition=~Q(status="CANCELLED"),
                name="uniq_active_ticket_per_event_student",
            )
        ]

    def __str__(self) -> str:
        return f"Ticket(event={self.event_id}, student={self.student_id}, status={self.status})"
