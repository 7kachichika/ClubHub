from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.auth import ORGANIZER_GROUP, STUDENT_GROUP
from accounts.models import OrganizerProfile, StudentProfile
from events.models import Event, Ticket


User = get_user_model()


class AccountsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.student_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP)
        self.organizer_group, _ = Group.objects.get_or_create(name=ORGANIZER_GROUP)

        self.student_user = User.objects.create_user(
            username="student_user",
            password="testpass123",
            email="student@example.com",
        )
        self.student_user.groups.add(self.student_group)
        self.student_profile = StudentProfile.objects.create(user=self.student_user)

        self.organizer_user = User.objects.create_user(
            username="organizer_user",
            password="testpass123",
            email="organizer@example.com",
        )
        self.organizer_user.groups.add(self.organizer_group)
        self.organizer_profile = OrganizerProfile.objects.create(user=self.organizer_user)

        self.other_student_user = User.objects.create_user(
            username="other_student",
            password="testpass123",
        )
        self.other_student_user.groups.add(self.student_group)
        self.other_student_profile = StudentProfile.objects.create(user=self.other_student_user)

    # ---------- register ----------

    def test_register_student_creates_user_group_profile_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newstudent",
                "email": "newstudent@example.com",
                "role": "student",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("student_dashboard"))

        user = User.objects.get(username="newstudent")
        self.assertEqual(user.email, "newstudent@example.com")
        self.assertTrue(user.groups.filter(name=STUDENT_GROUP).exists())
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())

        # 验证已自动登录
        response = self.client.get(reverse("student_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_register_organizer_creates_user_group_profile_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "neworganizer",
                "email": "neworganizer@example.com",
                "role": "organizer",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("organizer_dashboard"))

        user = User.objects.get(username="neworganizer")
        self.assertEqual(user.email, "neworganizer@example.com")
        self.assertTrue(user.groups.filter(name=ORGANIZER_GROUP).exists())
        self.assertTrue(OrganizerProfile.objects.filter(user=user).exists())

        response = self.client.get(reverse("organizer_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_register_redirects_authenticated_student_user(self):
        self.client.login(username="student_user", password="testpass123")

        response = self.client.get(reverse("register"))

        self.assertRedirects(response, reverse("student_dashboard"))

    # ---------- login_view ----------

    def test_login_view_logs_in_student_and_redirects_to_student_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "student_user",
                "password": "testpass123",
                "role": "student",
            },
        )

        self.assertRedirects(response, reverse("student_dashboard"))

    def test_login_view_logs_in_organizer_and_redirects_to_organizer_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "organizer_user",
                "password": "testpass123",
                "role": "organizer",
            },
        )

        self.assertRedirects(response, reverse("organizer_dashboard"))

    def test_login_view_rejects_wrong_role_for_student_account(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "student_user",
                "password": "testpass123",
                "role": "organizer",
            },
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertTrue(form.errors)
        self.assertIn("not an Organizer", str(form.errors))

    def test_login_view_redirects_authenticated_organizer_user(self):
        self.client.login(username="organizer_user", password="testpass123")

        response = self.client.get(reverse("login"))

        self.assertRedirects(response, reverse("organizer_dashboard"))

    # ---------- student_dashboard ----------

    def test_student_dashboard_requires_student_role(self):
        self.client.login(username="organizer_user", password="testpass123")

        response = self.client.get(reverse("student_dashboard"))

        self.assertNotEqual(response.status_code, 200)

    def test_student_dashboard_shows_confirmed_waitlisted_favorites_and_positions(self):
        event_confirmed = Event.objects.create(
            organizer=self.organizer_profile,
            title="Confirmed Event",
            description="Confirmed",
            start_at=timezone.now() + timedelta(days=3),
            capacity=5,
        )
        event_waitlist = Event.objects.create(
            organizer=self.organizer_profile,
            title="Waitlist Event",
            description="Waitlist",
            start_at=timezone.now() + timedelta(days=4),
            capacity=1,
        )
        favorite_event = Event.objects.create(
            organizer=self.organizer_profile,
            title="Favorite Event",
            description="Favorite",
            start_at=timezone.now() + timedelta(days=5),
            capacity=10,
        )

        confirmed_ticket = Ticket.objects.create(
            event=event_confirmed,
            student=self.student_profile,
            status=Ticket.Status.CONFIRMED,
        )

        earlier_waitlisted = Ticket.objects.create(
            event=event_waitlist,
            student=self.other_student_profile,
            status=Ticket.Status.WAITLISTED,
        )
        my_waitlisted = Ticket.objects.create(
            event=event_waitlist,
            student=self.student_profile,
            status=Ticket.Status.WAITLISTED,
        )

        Ticket.objects.filter(pk=earlier_waitlisted.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        Ticket.objects.filter(pk=my_waitlisted.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )
        my_waitlisted.refresh_from_db()

        self.student_profile.favorite_events.add(favorite_event)

        self.client.login(username="student_user", password="testpass123")
        response = self.client.get(reverse("student_dashboard"))

        self.assertEqual(response.status_code, 200)

        confirmed_tickets = response.context["confirmed_tickets"]
        waitlisted_tickets = response.context["waitlisted_tickets"]
        waitlist_positions = response.context["waitlist_positions"]
        favorite_events = response.context["favorite_events"]

        self.assertEqual(len(confirmed_tickets), 1)
        self.assertEqual(confirmed_tickets[0].id, confirmed_ticket.id)

        self.assertEqual(len(waitlisted_tickets), 1)
        self.assertEqual(waitlisted_tickets[0].id, my_waitlisted.id)
        self.assertEqual(waitlist_positions[my_waitlisted.id], 2)

        self.assertEqual(favorite_events.count(), 1)
        self.assertEqual(favorite_events.first().id, favorite_event.id)

    # ---------- organizer_dashboard ----------

    def test_organizer_dashboard_requires_organizer_role(self):
        self.client.login(username="student_user", password="testpass123")

        response = self.client.get(reverse("organizer_dashboard"))

        self.assertNotEqual(response.status_code, 200)

    def test_organizer_dashboard_shows_only_own_events_with_ticket_counts(self):
        own_event = Event.objects.create(
            organizer=self.organizer_profile,
            title="Own Event",
            description="Own",
            start_at=timezone.now() + timedelta(days=2),
            capacity=10,
        )
        other_organizer_user = User.objects.create_user(
            username="other_organizer",
            password="testpass123",
        )
        other_organizer_user.groups.add(self.organizer_group)
        other_organizer_profile = OrganizerProfile.objects.create(user=other_organizer_user)

        other_event = Event.objects.create(
            organizer=other_organizer_profile,
            title="Other Event",
            description="Other",
            start_at=timezone.now() + timedelta(days=2),
            capacity=10,
        )

        Ticket.objects.create(
            event=own_event,
            student=self.student_profile,
            status=Ticket.Status.CONFIRMED,
        )
        Ticket.objects.create(
            event=own_event,
            student=self.other_student_profile,
            status=Ticket.Status.WAITLISTED,
        )
        Ticket.objects.create(
            event=other_event,
            student=self.student_profile,
            status=Ticket.Status.CONFIRMED,
        )

        self.client.login(username="organizer_user", password="testpass123")
        response = self.client.get(reverse("organizer_dashboard"))

        self.assertEqual(response.status_code, 200)

        events = list(response.context["events"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, own_event.id)
        self.assertEqual(events[0].confirmed_count, 1)
        self.assertEqual(events[0].waitlist_count, 1)

    # ---------- logout ----------

    def test_logout_view_logs_user_out_and_redirects_to_event_list(self):
        self.client.login(username="student_user", password="testpass123")

        response = self.client.get(reverse("logout"))

        self.assertRedirects(response, reverse("event_list"))

        response = self.client.get(reverse("student_dashboard"))
        self.assertNotEqual(response.status_code, 200)

class AccountsFormsTests(TestCase):
    def setUp(self):
        self.student_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP)
        self.organizer_group, _ = Group.objects.get_or_create(name=ORGANIZER_GROUP)

        self.user = User.objects.create_user(
            username="existing_user",
            password="testpass123",
        )
        self.user.groups.add(self.student_group)
        StudentProfile.objects.create(user=self.user)

    # ---------- RegistrationForm ----------

    def test_registration_form_valid_student(self):
        from accounts.forms import RegistrationForm

        form = RegistrationForm(
            data={
                "username": "newuser",
                "email": "new@example.com",
                "role": "student",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            }
        )

        self.assertTrue(form.is_valid())

    def test_registration_form_rejects_duplicate_username(self):
        from accounts.forms import RegistrationForm

        form = RegistrationForm(
            data={
                "username": "existing_user",
                "email": "new@example.com",
                "role": "student",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_registration_form_rejects_password_mismatch(self):
        from accounts.forms import RegistrationForm

        form = RegistrationForm(
            data={
                "username": "user2",
                "email": "user2@example.com",
                "role": "student",
                "password1": "StrongPass123!",
                "password2": "DifferentPass123!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    # ---------- RoleLoginForm ----------

    def test_role_login_form_accepts_correct_student_role(self):
        from accounts.forms import RoleLoginForm

        form = RoleLoginForm(
            data={
                "username": "existing_user",
                "password": "testpass123",
                "role": "student",
            }
        )

        self.assertTrue(form.is_valid())

    def test_role_login_form_rejects_wrong_role(self):
        from accounts.forms import RoleLoginForm

        form = RoleLoginForm(
            data={
                "username": "existing_user",
                "password": "testpass123",
                "role": "organizer",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)