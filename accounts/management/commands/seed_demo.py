from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from datetime import timedelta

from django.utils import timezone

from accounts.auth import ORGANIZER_GROUP, STUDENT_GROUP, get_organizer_profile, get_student_profile
from events.models import Event, Tag, Ticket


class Command(BaseCommand):
    help = "Seed demo groups/users/events for ClubHub."

    def handle(self, *args, **options):
        User = get_user_model()

        students_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP)
        organizers_group, _ = Group.objects.get_or_create(name=ORGANIZER_GROUP)

        organizer_user, created_org = User.objects.get_or_create(
            username="organizer1", defaults={"email": "organizer1@example.com"}
        )
        if created_org:
            organizer_user.set_password("password1234")
            organizer_user.save()
        organizer_user.groups.add(organizers_group)
        organizer_profile = get_organizer_profile(organizer_user)

        student_user, created_stu = User.objects.get_or_create(
            username="student1", defaults={"email": "student1@example.com"}
        )
        if created_stu:
            student_user.set_password("password1234")
            student_user.save()
        student_user.groups.add(students_group)
        student_profile = get_student_profile(student_user)

        tech, _ = Tag.objects.get_or_create(name="Tech")
        social, _ = Tag.objects.get_or_create(name="Social")

        start_at = timezone.now() + timedelta(days=3)
        event, created_event = Event.objects.get_or_create(
            organizer=organizer_profile,
            title="Welcome Mixer",
            defaults={
                "description": "Meet new people and discover societies on campus.",
                "start_at": start_at,
                "capacity": 2,
                "location_name": "University of Glasgow",
                "latitude": 55.8721,
                "longitude": -4.2890,
            },
        )
        event.tags.set([tech, social])

        # Create a confirmed ticket for student1 (if not exists)
        Ticket.objects.get_or_create(
            event=event, student=student_profile, defaults={"status": Ticket.Status.CONFIRMED}
        )

        self.stdout.write(self.style.SUCCESS("Seeded demo data."))
        self.stdout.write("Demo organizer: organizer1 / password1234")
        self.stdout.write("Demo student: student1 / password1234")

