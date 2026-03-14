from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from events.models import Ticket

from .auth import (
    ORGANIZER_GROUP,
    STUDENT_GROUP,
    RoleRedirect,
    get_organizer_profile,
    get_student_profile,
    organizer_required,
    student_required,
)
from .forms import RegistrationForm, RoleLoginForm


def login_view(request):
    if request.user.is_authenticated:
        # If already logged in, choose destination based on available profiles/groups.
        if hasattr(request.user, "organizer_profile"):
            return redirect("organizer_dashboard")
        if hasattr(request.user, "student_profile"):
            return redirect("student_dashboard")
        return redirect("event_list")

    if request.method == "POST":
        form = RoleLoginForm(request=request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            role = form.cleaned_data["role"]
            messages.success(request, "Logged in successfully.")
            return redirect(RoleRedirect(role=role).dashboard_url_name)
    else:
        form = RoleLoginForm(request=request)

    return render(request, "accounts/login.html", {"form": form})


def register(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "organizer_profile"):
            return redirect("organizer_dashboard")
        if hasattr(request.user, "student_profile"):
            return redirect("student_dashboard")
        return redirect("event_list")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Ensure email is saved even if User model doesn't require it.
            user.email = form.cleaned_data.get("email", "")
            user.save()

            role = form.cleaned_data["role"]
            group_name = STUDENT_GROUP if role == "student" else ORGANIZER_GROUP
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

            if role == "student":
                get_student_profile(user)
            else:
                get_organizer_profile(user)

            login(request, user)
            messages.success(request, "Account created and logged in.")
            return redirect(RoleRedirect(role=role).dashboard_url_name)
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "Logged out.")
    return redirect("event_list")


@student_required
def student_dashboard(request):
    student = get_student_profile(request.user)
    now = timezone.now()

    tickets = (
        Ticket.objects.filter(student=student)
        .select_related("event")
        .order_by("event__start_at", "created_at")
    )
    confirmed = [t for t in tickets if t.status == Ticket.Status.CONFIRMED]
    waitlisted = [t for t in tickets if t.status == Ticket.Status.WAITLISTED]

    waitlist_positions = {}
    for t in waitlisted:
        waitlist_positions[t.id] = Ticket.objects.filter(
            event=t.event,
            status=Ticket.Status.WAITLISTED,
            created_at__lte=t.created_at,
        ).count()

    favorites = (
        student.favorite_events.all()
        .select_related("organizer__user")
        .order_by("start_at")
    )

    return render(
        request,
        "accounts/student_dashboard.html",
        {
            "now": now,
            "confirmed_tickets": confirmed,
            "waitlisted_tickets": waitlisted,
            "waitlist_positions": waitlist_positions,
            "favorite_events": favorites,
        },
    )


@organizer_required
def organizer_dashboard(request):
    organizer = get_organizer_profile(request.user)
    from events.models import Event  # local import to avoid circularity in migrations

    now = timezone.now()

    events = (
        Event.objects.filter(organizer=organizer)
        .annotate(
            confirmed_count=Count(
                "tickets", filter=Q(tickets__status=Ticket.Status.CONFIRMED)
            ),
            waitlist_count=Count(
                "tickets", filter=Q(tickets__status=Ticket.Status.WAITLISTED)
            ),
        )
        .order_by("-start_at")
    )

    return render(
        request,
        "accounts/organizer_dashboard.html",
        {
            "events": events,
            "now": now,
        },
    )
