from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import OrganizerProfile, StudentProfile
from events.models import Event, Tag, Ticket
from events.services import (
    book_event_for_student,
    cancel_ticket_and_promote,
    check_in_ticket,
    promote_waitlist_if_possible,
    rebuild_and_save_student_preferences,
)


User = get_user_model()


class EventServicesTests(TestCase):
    def setUp(self):
        self.organizer_user = User.objects.create_user(
            username="organizer1",
            password="testpass123",
        )
        self.organizer = OrganizerProfile.objects.create(user=self.organizer_user)

        self.student_user_1 = User.objects.create_user(
            username="student1",
            password="testpass123",
        )
        self.student_1 = StudentProfile.objects.create(user=self.student_user_1)

        self.student_user_2 = User.objects.create_user(
            username="student2",
            password="testpass123",
        )
        self.student_2 = StudentProfile.objects.create(user=self.student_user_2)

        self.student_user_3 = User.objects.create_user(
            username="student3",
            password="testpass123",
        )
        self.student_3 = StudentProfile.objects.create(user=self.student_user_3)

        self.music_tag = Tag.objects.create(name="Music")
        self.tech_tag = Tag.objects.create(name="Tech")
        self.sports_tag = Tag.objects.create(name="Sports")

        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Main Event",
            description="Test event",
            start_at=timezone.now() + timedelta(days=3),
            capacity=2,
        )
        self.event.tags.add(self.music_tag, self.tech_tag)

    def test_book_event_creates_confirmed_ticket_when_capacity_available(self):
        result = book_event_for_student(event=self.event, student=self.student_1)

        self.assertTrue(result.created)
        self.assertEqual(result.ticket.status, Ticket.Status.CONFIRMED)
        self.assertEqual(
            Ticket.objects.filter(
                event=self.event,
                student=self.student_1,
                status=Ticket.Status.CONFIRMED,
            ).count(),
            1,
        )

    def test_book_event_creates_waitlisted_ticket_when_event_is_full(self):
        Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
        )
        Ticket.objects.create(
            event=self.event,
            student=self.student_2,
            status=Ticket.Status.CONFIRMED,
        )

        result = book_event_for_student(event=self.event, student=self.student_3)

        self.assertTrue(result.created)
        self.assertEqual(result.ticket.status, Ticket.Status.WAITLISTED)
        self.assertEqual(
            Ticket.objects.filter(
                event=self.event,
                student=self.student_3,
                status=Ticket.Status.WAITLISTED,
            ).count(),
            1,
        )

    def test_book_event_returns_existing_active_ticket_without_creating_duplicate(self):
        existing_ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
        )

        result = book_event_for_student(event=self.event, student=self.student_1)

        self.assertFalse(result.created)
        self.assertEqual(result.ticket.id, existing_ticket.id)
        self.assertEqual(
            Ticket.objects.filter(event=self.event, student=self.student_1).count(),
            1,
        )

    def test_promote_waitlist_if_possible_promotes_earliest_waitlisted_ticket(self):
        self.event.capacity = 1
        self.event.save(update_fields=["capacity"])

        Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
        )

        first_waitlisted = Ticket.objects.create(
            event=self.event,
            student=self.student_2,
            status=Ticket.Status.WAITLISTED,
        )
        second_waitlisted = Ticket.objects.create(
            event=self.event,
            student=self.student_3,
            status=Ticket.Status.WAITLISTED,
        )

        Ticket.objects.filter(pk=first_waitlisted.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        Ticket.objects.filter(pk=second_waitlisted.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        confirmed_ticket = Ticket.objects.get(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
        )
        confirmed_ticket.status = Ticket.Status.CANCELLED
        confirmed_ticket.save(update_fields=["status", "updated_at"])

        promoted = promote_waitlist_if_possible(event=self.event)

        first_waitlisted.refresh_from_db()
        second_waitlisted.refresh_from_db()

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted.id, first_waitlisted.id)
        self.assertEqual(first_waitlisted.status, Ticket.Status.CONFIRMED)
        self.assertEqual(second_waitlisted.status, Ticket.Status.WAITLISTED)

    def test_promote_waitlist_if_possible_returns_none_when_no_waitlist(self):
        promoted = promote_waitlist_if_possible(event=self.event)

        self.assertIsNone(promoted)

    def test_cancel_ticket_and_promote_cancels_confirmed_ticket_and_promotes_waitlist(self):
        self.event.capacity = 1
        self.event.save(update_fields=["capacity"])

        confirmed_ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
        )
        waitlisted_ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_2,
            status=Ticket.Status.WAITLISTED,
        )

        promoted = cancel_ticket_and_promote(ticket=confirmed_ticket)

        confirmed_ticket.refresh_from_db()
        waitlisted_ticket.refresh_from_db()

        self.assertEqual(confirmed_ticket.status, Ticket.Status.CANCELLED)
        self.assertIsNotNone(promoted)
        self.assertEqual(promoted.id, waitlisted_ticket.id)
        self.assertEqual(waitlisted_ticket.status, Ticket.Status.CONFIRMED)

    def test_cancel_ticket_and_promote_cancels_waitlisted_ticket_without_promotion(self):
        waitlisted_ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.WAITLISTED,
        )

        promoted = cancel_ticket_and_promote(ticket=waitlisted_ticket)

        waitlisted_ticket.refresh_from_db()

        self.assertIsNone(promoted)
        self.assertEqual(waitlisted_ticket.status, Ticket.Status.CANCELLED)

    def test_cancel_ticket_and_promote_returns_none_for_already_cancelled_ticket(self):
        cancelled_ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CANCELLED,
        )

        promoted = cancel_ticket_and_promote(ticket=cancelled_ticket)

        cancelled_ticket.refresh_from_db()

        self.assertIsNone(promoted)
        self.assertEqual(cancelled_ticket.status, Ticket.Status.CANCELLED)

    def test_check_in_ticket_marks_ticket_checked_in_and_sets_timestamp(self):
        ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
        )

        returned_ticket = check_in_ticket(ticket=ticket)

        ticket.refresh_from_db()

        self.assertEqual(returned_ticket.id, ticket.id)
        self.assertTrue(ticket.checked_in)
        self.assertIsNotNone(ticket.checked_in_at)

    def test_check_in_ticket_is_idempotent_for_already_checked_in_ticket(self):
        ticket = Ticket.objects.create(
            event=self.event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
            checked_in=True,
            checked_in_at=timezone.now() - timedelta(hours=1),
        )
        original_checked_in_at = ticket.checked_in_at

        returned_ticket = check_in_ticket(ticket=ticket)

        ticket.refresh_from_db()

        self.assertEqual(returned_ticket.id, ticket.id)
        self.assertTrue(ticket.checked_in)
        self.assertEqual(ticket.checked_in_at, original_checked_in_at)

    def test_rebuild_and_save_student_preferences_rebuilds_from_current_behaviour(self):
        favorite_event = Event.objects.create(
            organizer=self.organizer,
            title="Favorite Event",
            description="Favorite",
            start_at=timezone.now() + timedelta(days=5),
            capacity=10,
        )
        favorite_event.tags.add(self.music_tag, self.sports_tag)

        booked_event = Event.objects.create(
            organizer=self.organizer,
            title="Booked Event",
            description="Booked",
            start_at=timezone.now() + timedelta(days=6),
            capacity=10,
        )
        booked_event.tags.add(self.music_tag, self.tech_tag)

        checked_in_event = Event.objects.create(
            organizer=self.organizer,
            title="Checked In Event",
            description="Checked in",
            start_at=timezone.now() + timedelta(days=7),
            capacity=10,
        )
        checked_in_event.tags.add(self.tech_tag)

        self.student_1.favorite_events.add(favorite_event)

        Ticket.objects.create(
            event=booked_event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
            checked_in=False,
        )
        Ticket.objects.create(
            event=checked_in_event,
            student=self.student_1,
            status=Ticket.Status.CONFIRMED,
            checked_in=True,
            checked_in_at=timezone.now(),
        )

        self.student_1.preferences = {"OldTag": 999}
        self.student_1.save(update_fields=["preferences", "preferences_updated_at"])

        prefs = rebuild_and_save_student_preferences(self.student_1)

        self.student_1.refresh_from_db()

        self.assertEqual(prefs["Music"], 3.0)   # 收藏 +1，订票 +2
        self.assertEqual(prefs["Sports"], 1.0)  # 仅收藏 +1
        self.assertEqual(prefs["Tech"], 5.0)    # 订票 +2，已签到 +3
        self.assertNotIn("OldTag", prefs)
        self.assertEqual(self.student_1.preferences, prefs)