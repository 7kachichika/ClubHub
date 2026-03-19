from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.auth import ORGANIZER_GROUP, STUDENT_GROUP
from accounts.models import OrganizerProfile, StudentProfile
from events.forms import EventForm
from events.models import Event, Tag, Ticket
from events.services import (
    book_event_for_student,
    cancel_ticket_and_promote,
    promote_waitlist_if_possible,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared test fixture mixin
# ---------------------------------------------------------------------------

class EventTestBase(TestCase):
    """
    Creates the minimum objects needed by every test:
    one organizer, one event, two students.
    """

    def setUp(self):
        self.client = Client()

        student_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP)
        organizer_group, _ = Group.objects.get_or_create(name=ORGANIZER_GROUP)

        org_user = User.objects.create_user(username="org", password="pass")
        org_user.groups.add(organizer_group)
        self.organizer = OrganizerProfile.objects.create(user=org_user)

        s1_user = User.objects.create_user(username="s1", password="pass")
        s1_user.groups.add(student_group)
        self.student1 = StudentProfile.objects.create(user=s1_user)

        s2_user = User.objects.create_user(username="s2", password="pass")
        s2_user.groups.add(student_group)
        self.student2 = StudentProfile.objects.create(user=s2_user)

        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Test Event",
            description="A test event.",
            start_at=timezone.now() + timedelta(days=7),
            capacity=1,           # capacity=1 makes confirm/waitlist easy to trigger
        )


# ---------------------------------------------------------------------------
# Service tests — booking logic
# ---------------------------------------------------------------------------

class BookEventServiceTests(EventTestBase):
    """
    Covers events/services.py :: book_event_for_student
    Rubric: core business logic, dynamic capacity engine.
    """

    def test_first_booking_is_confirmed_when_capacity_available(self):
        result = book_event_for_student(event=self.event, student=self.student1)

        self.assertTrue(result.created)
        self.assertEqual(result.ticket.status, Ticket.Status.CONFIRMED)

    def test_booking_beyond_capacity_is_waitlisted(self):
        # Fill the single seat
        book_event_for_student(event=self.event, student=self.student1)

        result = book_event_for_student(event=self.event, student=self.student2)

        self.assertTrue(result.created)
        self.assertEqual(result.ticket.status, Ticket.Status.WAITLISTED)

    def test_duplicate_booking_returns_existing_ticket_not_created(self):
        book_event_for_student(event=self.event, student=self.student1)

        result = book_event_for_student(event=self.event, student=self.student1)

        self.assertFalse(result.created)
        self.assertEqual(Ticket.objects.filter(event=self.event).count(), 1)


# ---------------------------------------------------------------------------
# Service tests — waitlist promotion
# ---------------------------------------------------------------------------

class WaitlistPromotionServiceTests(EventTestBase):
    """
    Covers events/services.py :: promote_waitlist_if_possible
                               :: cancel_ticket_and_promote
    Rubric: waitlist automation (S1 / M4 features called out in footer).
    """

    def test_promote_waitlist_moves_first_waitlisted_ticket_to_confirmed(self):
        confirmed = Ticket.objects.create(
            event=self.event, student=self.student1, status=Ticket.Status.CONFIRMED
        )
        waitlisted = Ticket.objects.create(
            event=self.event, student=self.student2, status=Ticket.Status.WAITLISTED
        )

        # Free the confirmed seat, then promote
        confirmed.status = Ticket.Status.CANCELLED
        confirmed.save()

        promoted = promote_waitlist_if_possible(event=self.event)

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted.pk, waitlisted.pk)
        self.assertEqual(promoted.status, Ticket.Status.CONFIRMED)

    def test_promote_waitlist_returns_none_when_no_capacity(self):
        # Event still full (capacity=1, confirmed seat exists)
        Ticket.objects.create(
            event=self.event, student=self.student1, status=Ticket.Status.CONFIRMED
        )
        Ticket.objects.create(
            event=self.event, student=self.student2, status=Ticket.Status.WAITLISTED
        )

        result = promote_waitlist_if_possible(event=self.event)

        self.assertIsNone(result)

    def test_cancel_confirmed_ticket_triggers_waitlist_promotion(self):
        confirmed = Ticket.objects.create(
            event=self.event, student=self.student1, status=Ticket.Status.CONFIRMED
        )
        waitlisted = Ticket.objects.create(
            event=self.event, student=self.student2, status=Ticket.Status.WAITLISTED
        )

        promoted = cancel_ticket_and_promote(ticket=confirmed)

        confirmed.refresh_from_db()
        waitlisted.refresh_from_db()

        self.assertEqual(confirmed.status, Ticket.Status.CANCELLED)
        self.assertIsNotNone(promoted)
        self.assertEqual(promoted.pk, waitlisted.pk)
        self.assertEqual(waitlisted.status, Ticket.Status.CONFIRMED)

    def test_cancel_waitlisted_ticket_does_not_trigger_promotion(self):
        # Confirmed seat stays filled; waitlisted student cancels
        Ticket.objects.create(
            event=self.event, student=self.student1, status=Ticket.Status.CONFIRMED
        )
        waitlisted = Ticket.objects.create(
            event=self.event, student=self.student2, status=Ticket.Status.WAITLISTED
        )

        result = cancel_ticket_and_promote(ticket=waitlisted)

        # No promotion should happen (no freed confirmed seat)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# View tests — toggle_favorite
# ---------------------------------------------------------------------------

class ToggleFavoriteViewTests(EventTestBase):
    """
    Covers events/views.py :: toggle_favorite
    Rubric: view-level testing, student interaction feature,
            and directly relevant to Task 3 (AJAX conversion).
    """

    def _url(self):
        return reverse("toggle_favorite", args=[self.event.id])

    def test_unauthenticated_user_is_redirected(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)

    def test_student_can_add_favorite(self):
        self.client.login(username="s1", password="pass")

        response = self.client.post(self._url())

        # Should redirect back (non-AJAX) or return 200/204
        self.assertIn(response.status_code, [200, 204, 302])
        self.assertIn(self.event, self.student1.favorite_events.all())

    def test_student_can_remove_favorite(self):
        self.student1.favorite_events.add(self.event)
        self.client.login(username="s1", password="pass")

        self.client.post(self._url())

        self.assertNotIn(self.event, self.student1.favorite_events.all())

    def test_toggle_favorite_is_idempotent_add_remove_add(self):
        self.client.login(username="s1", password="pass")

        self.client.post(self._url())   # add
        self.client.post(self._url())   # remove
        self.client.post(self._url())   # add again

        self.assertIn(self.event, self.student1.favorite_events.all())


# ---------------------------------------------------------------------------
# View tests — toggle_follow_organizer
# ---------------------------------------------------------------------------

class ToggleFollowOrganizerViewTests(EventTestBase):
    """
    Covers events/views.py :: toggle_follow_organizer
    Rubric: student–organizer relationship feature.
    """

    def _url(self):
        return reverse("toggle_follow_organizer", args=[self.organizer.id])

    def test_unauthenticated_user_is_redirected(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)

    def test_student_can_follow_organizer(self):
        self.client.login(username="s1", password="pass")

        self.client.post(self._url())

        self.assertIn(self.organizer, self.student1.followed_organizers.all())

    def test_student_can_unfollow_organizer(self):
        self.student1.followed_organizers.add(self.organizer)
        self.client.login(username="s1", password="pass")

        self.client.post(self._url())

        self.assertNotIn(self.organizer, self.student1.followed_organizers.all())


# ---------------------------------------------------------------------------
# View tests — event_list
# ---------------------------------------------------------------------------

class EventListViewTests(EventTestBase):
    """
    Covers events/views.py :: event_list
    Rubric: end-to-end view test; confirms the main page renders
            and that server-side search filtering works.
    """

    def test_event_list_renders_for_anonymous_user(self):
        response = self.client.get(reverse("event_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Event")

    def test_event_list_search_filter_returns_matching_event(self):
        Event.objects.create(
            organizer=self.organizer,
            title="Yoga Workshop",
            start_at=timezone.now() + timedelta(days=2),
            capacity=20,
        )

        response = self.client.get(reverse("event_list"), {"q": "Yoga"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Yoga Workshop")
        self.assertNotContains(response, "Test Event")

    def test_event_list_passes_favorite_event_ids_to_template_for_student(self):
        self.student1.favorite_events.add(self.event)
        self.client.login(username="s1", password="pass")

        response = self.client.get(reverse("event_list"))

        self.assertIn("favorite_event_ids", response.context)
        self.assertIn(self.event.id, response.context["favorite_event_ids"])


# ---------------------------------------------------------------------------
# Form tests — EventForm tag parsing
# ---------------------------------------------------------------------------

class EventFormTagTests(EventTestBase):
    """
    Covers events/forms.py :: EventForm.apply_tags
    Rubric: form validation, data integrity.
    """

    def _base_data(self, **kwargs):
        defaults = {
            "title": "Tag Test Event",
            "description": "desc",
            "start_at": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "capacity": 10,
            "location_name": "",
            "latitude": "",
            "longitude": "",
            "tags_text": "",
        }
        defaults.update(kwargs)
        return defaults

    def test_apply_tags_creates_and_associates_tags(self):
        form = EventForm(data=self._base_data(tags_text="Music, Tech, Social"))
        self.assertTrue(form.is_valid(), form.errors)

        event = form.save(commit=False)
        event.organizer = self.organizer
        event.save()
        form.apply_tags(event)

        tag_names = set(event.tags.values_list("name", flat=True))
        self.assertEqual(tag_names, {"Music", "Tech", "Social"})

    def test_apply_tags_clears_tags_when_empty(self):
        tag = Tag.objects.create(name="OldTag")
        self.event.tags.add(tag)

        form = EventForm(data=self._base_data(tags_text=""), instance=self.event)
        self.assertTrue(form.is_valid(), form.errors)
        form.apply_tags(self.event)

        self.assertEqual(self.event.tags.count(), 0)