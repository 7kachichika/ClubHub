from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError, transaction

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

from django.urls import reverse
from django.contrib.auth.models import Group
from django.test import Client


class EventViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Groups（确保 student_required / organizer_required 正常工作）
        self.student_group, _ = Group.objects.get_or_create(name="Students")
        self.organizer_group, _ = Group.objects.get_or_create(name="Organizers")

        # Users
        self.organizer_user = User.objects.create_user(
            username="organizer_view",
            password="testpass123",
        )
        self.organizer_user.groups.add(self.organizer_group)
        self.organizer = OrganizerProfile.objects.create(user=self.organizer_user)

        self.student_user = User.objects.create_user(
            username="student_view",
            password="testpass123",
        )
        self.student_user.groups.add(self.student_group)
        self.student = StudentProfile.objects.create(user=self.student_user)

        self.other_student_user = User.objects.create_user(
            username="other_student",
            password="testpass123",
        )
        self.other_student_user.groups.add(self.student_group)
        self.other_student = StudentProfile.objects.create(user=self.other_student_user)

        # Tag
        self.tag = Tag.objects.create(name="Music")

        # Event
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="View Test Event",
            description="Test",
            start_at=timezone.now() + timedelta(days=2),
            capacity=1,
        )
        self.event.tags.add(self.tag)

    # ---------- book_event ----------

    def test_book_event_creates_ticket_for_student(self):
        self.client.login(username="student_view", password="testpass123")

        response = self.client.post(
            reverse("book_event", args=[self.event.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Ticket.objects.filter(
                event=self.event,
                student=self.student,
            ).count(),
            1,
        )

    def test_book_event_prevents_duplicate_booking(self):
        Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        self.client.login(username="student_view", password="testpass123")

        self.client.post(reverse("book_event", args=[self.event.id]))

        self.assertEqual(
            Ticket.objects.filter(event=self.event, student=self.student).count(),
            1,
        )

    # ---------- cancel_ticket ----------

    def test_cancel_ticket_changes_status_and_promotes_waitlist(self):
        self.event.capacity = 1
        self.event.save()

        confirmed = Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )
        waitlisted = Ticket.objects.create(
            event=self.event,
            student=self.other_student,
            status=Ticket.Status.WAITLISTED,
        )

        self.client.login(username="student_view", password="testpass123")

        response = self.client.post(
            reverse("cancel_ticket", args=[confirmed.id])
        )

        confirmed.refresh_from_db()
        waitlisted.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(confirmed.status, Ticket.Status.CANCELLED)
        self.assertEqual(waitlisted.status, Ticket.Status.CONFIRMED)

    def test_cancel_ticket_only_allows_owner(self):
        ticket = Ticket.objects.create(
            event=self.event,
            student=self.other_student,
            status=Ticket.Status.CONFIRMED,
        )

        self.client.login(username="student_view", password="testpass123")

        response = self.client.post(
            reverse("cancel_ticket", args=[ticket.id])
        )

        # 应该被拒绝（通常是 404）
        self.assertNotEqual(response.status_code, 200)

    # ---------- toggle_favorite ----------

    def test_toggle_favorite_adds_and_removes(self):
        self.client.login(username="student_view", password="testpass123")

        # add
        self.client.post(reverse("toggle_favorite", args=[self.event.id]))
        self.assertTrue(
            self.student.favorite_events.filter(pk=self.event.pk).exists()
        )

        # remove
        self.client.post(reverse("toggle_favorite", args=[self.event.id]))
        self.assertFalse(
            self.student.favorite_events.filter(pk=self.event.pk).exists()
        )

    def test_toggle_favorite_returns_json_when_requested(self):
        self.client.login(username="student_view", password="testpass123")

        response = self.client.post(
            reverse("toggle_favorite", args=[self.event.id]),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("favorited", response.json())

    # ---------- create_event ----------

    def test_create_event_by_organizer(self):
        self.client.login(username="organizer_view", password="testpass123")

        response = self.client.post(
            reverse("create_event"),
            {
                "title": "New Event",
                "description": "Test",
                "start_at": (timezone.now() + timedelta(days=3)).isoformat(),
                "capacity": 10,
                "tags_text": "Music, Tech",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Event.objects.filter(title="New Event").exists())

    def test_create_event_forbidden_for_student(self):
        self.client.login(username="student_view", password="testpass123")

        response = self.client.get(reverse("create_event"))

        self.assertNotEqual(response.status_code, 200)

    # ---------- export_attendees_csv ----------

    def test_export_attendees_csv_returns_csv(self):
        Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        self.client.login(username="organizer_view", password="testpass123")

        response = self.client.get(
            reverse("export_attendees_csv", args=[self.event.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    # ---------- ticket_qr_png ----------

    def test_ticket_qr_png_access_control(self):
        ticket = Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        # owner can access
        self.client.login(username="student_view", password="testpass123")
        response = self.client.get(
            reverse("ticket_qr_png", args=[ticket.code])
        )
        self.assertEqual(response.status_code, 200)

        # unrelated user cannot
        self.client.login(username="other_student", password="testpass123")
        response = self.client.get(
            reverse("ticket_qr_png", args=[ticket.code])
        )
        self.assertNotEqual(response.status_code, 200)

class EventFormsTests(TestCase):
    def setUp(self):
        self.organizer_user = User.objects.create_user(
            username="org_form",
            password="testpass123",
        )
        self.organizer = OrganizerProfile.objects.create(user=self.organizer_user)

    # ---------- EventForm ----------

    def test_event_form_valid_and_tag_parsing(self):
        from events.forms import EventForm

        form = EventForm(
            data={
                "title": "Form Event",
                "description": "Test",
                "start_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "capacity": 10,
                "tags_text": "Music, Tech, Music",
            }
        )

        self.assertTrue(form.is_valid())

        event = form.save(commit=False)
        event.organizer = self.organizer
        event.save()

        form.apply_tags(event)

        tags = list(event.tags.values_list("name", flat=True))
        self.assertEqual(sorted(tags), ["Music", "Tech"])

    def test_event_form_empty_tags_clears_tags(self):
        from events.forms import EventForm

        form = EventForm(
            data={
                "title": "No Tag Event",
                "description": "Test",
                "start_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "capacity": 5,
                "tags_text": "",
            }
        )

        self.assertTrue(form.is_valid())

        event = form.save(commit=False)
        event.organizer = self.organizer
        event.save()

        form.apply_tags(event)

        self.assertEqual(event.tags.count(), 0)

    def test_event_form_invalid_capacity(self):
        from events.forms import EventForm

        form = EventForm(
            data={
                "title": "Bad Event",
                "description": "Test",
                "start_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "capacity": -1,
                "tags_text": "Music",
            }
        )

        self.assertFalse(form.is_valid())

    # ---------- CheckinForm ----------

    def test_checkin_form_accepts_valid_uuid(self):
        from events.forms import CheckinForm
        import uuid

        form = CheckinForm(
            data={
                "code": str(uuid.uuid4())
            }
        )

        self.assertTrue(form.is_valid())

    def test_checkin_form_rejects_invalid_uuid(self):
        from events.forms import CheckinForm

        form = CheckinForm(
            data={
                "code": "not-a-uuid"
            }
        )

        self.assertFalse(form.is_valid())

# =========================
# Models Tests
# =========================

class EventModelsTests(TestCase):
    def setUp(self):
        self.organizer_user = User.objects.create_user(
            username="org_model",
            password="testpass123",
        )
        self.organizer = OrganizerProfile.objects.create(user=self.organizer_user)

        self.student_user = User.objects.create_user(
            username="student_model",
            password="testpass123",
        )
        self.student = StudentProfile.objects.create(user=self.student_user)

        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Model Event",
            description="Model test",
            start_at=timezone.now() + timedelta(days=2),
            capacity=10,
        )

    def test_ticket_unique_active_constraint_blocks_second_active_ticket(self):
        Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Ticket.objects.create(
                    event=self.event,
                    student=self.student,
                    status=Ticket.Status.WAITLISTED,
                )

    def test_ticket_allows_new_active_ticket_after_cancelled_ticket(self):
        Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CANCELLED,
        )

        new_ticket = Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        self.assertEqual(new_ticket.status, Ticket.Status.CONFIRMED)
        self.assertEqual(
            Ticket.objects.filter(event=self.event, student=self.student).count(),
            2,
        )

    def test_model_string_methods(self):
        tag = Tag.objects.create(name="Music")
        ticket = Ticket.objects.create(
            event=self.event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        self.assertEqual(str(tag), "Music")
        self.assertEqual(str(self.event), "Model Event")
        self.assertIn("Ticket(", str(ticket))

# =========================
# Recommendation Tests
# =========================

class RecommendationLogicTests(TestCase):
    def setUp(self):
        self.organizer_user = User.objects.create_user(
            username="org_reco",
            password="testpass123",
        )
        self.organizer = OrganizerProfile.objects.create(user=self.organizer_user)

        self.student_user = User.objects.create_user(
            username="student_reco",
            password="testpass123",
        )
        self.student = StudentProfile.objects.create(user=self.student_user)

        self.music_tag = Tag.objects.create(name="Music")
        self.tech_tag = Tag.objects.create(name="Tech")
        self.sports_tag = Tag.objects.create(name="Sports")

    def test_build_student_preferences_counts_favorites_and_tickets(self):
        from events.views import _build_student_preferences

        favorite_event = Event.objects.create(
            organizer=self.organizer,
            title="Favorite Event",
            description="Favorite",
            start_at=timezone.now() + timedelta(days=3),
            capacity=10,
        )
        favorite_event.tags.add(self.music_tag)

        booked_event = Event.objects.create(
            organizer=self.organizer,
            title="Booked Event",
            description="Booked",
            start_at=timezone.now() + timedelta(days=4),
            capacity=10,
        )
        booked_event.tags.add(self.music_tag, self.tech_tag)

        self.student.favorite_events.add(favorite_event)
        Ticket.objects.create(
            event=booked_event,
            student=self.student,
            status=Ticket.Status.CONFIRMED,
        )

        prefs = _build_student_preferences(self.student)

        self.assertEqual(prefs["Music"], 3.0)  # favorite +1, ticket +2
        self.assertEqual(prefs["Tech"], 2.0)   # ticket +2

    def test_get_student_preferences_prefers_saved_preferences(self):
        from events.views import _get_student_preferences

        self.student.preferences = {"Music": 99.0}
        self.student.save(update_fields=["preferences", "preferences_updated_at"])

        prefs = _get_student_preferences(self.student)

        self.assertEqual(prefs, {"Music": 99.0})

    def test_score_event_for_student_adds_preference_popularity_and_time_bonus(self):
        from events.views import _score_event_for_student

        event = Event.objects.create(
            organizer=self.organizer,
            title="Scored Event",
            description="Score",
            start_at=timezone.now() + timedelta(hours=12),
            capacity=10,
        )
        event.tags.add(self.music_tag)
        event.confirmed_count = 4  # 热度分 = 4 * 0.5 = 2.0

        score = _score_event_for_student(event, {"Music": 2.5})

        # 偏好 2.5 + 热度 2.0 + 24h 内时间加分 2.0 = 6.5
        self.assertAlmostEqual(score, 6.5)

    def test_get_recommended_events_excludes_past_events_and_respects_limit_and_order(self):
        from events.views import _get_recommended_events

        self.student.preferences = {"Music": 3.0, "Tech": 1.0}
        self.student.save(update_fields=["preferences", "preferences_updated_at"])

        top_event = Event.objects.create(
            organizer=self.organizer,
            title="Top Event",
            description="Top",
            start_at=timezone.now() + timedelta(hours=10),
            capacity=10,
        )
        top_event.tags.add(self.music_tag)
        top_event.confirmed_count = 2  # 3 + 1 + 2 = 6

        second_event = Event.objects.create(
            organizer=self.organizer,
            title="Second Event",
            description="Second",
            start_at=timezone.now() + timedelta(days=10),
            capacity=10,
        )
        second_event.tags.add(self.tech_tag)
        second_event.confirmed_count = 6  # 1 + 3 = 4

        low_event = Event.objects.create(
            organizer=self.organizer,
            title="Low Event",
            description="Low",
            start_at=timezone.now() + timedelta(days=15),
            capacity=10,
        )
        low_event.tags.add(self.sports_tag)
        low_event.confirmed_count = 0  # 0

        past_event = Event.objects.create(
            organizer=self.organizer,
            title="Past Event",
            description="Past",
            start_at=timezone.now() - timedelta(days=1),
            capacity=10,
        )
        past_event.tags.add(self.music_tag)
        past_event.confirmed_count = 100  # 即使很高，也不应被推荐

        recommended = _get_recommended_events(
            self.student,
            [low_event, second_event, past_event, top_event],
            limit=2,
        )

        self.assertEqual([event.id for event in recommended], [top_event.id, second_event.id])
        self.assertNotIn(past_event.id, [event.id for event in recommended])
        self.assertEqual(len(recommended), 2)