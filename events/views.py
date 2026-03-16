from __future__ import annotations

import csv
import io

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.auth import (
    get_organizer_profile,
    get_student_profile,
    is_organizer,
    is_student,
    organizer_required,
    student_required,
)

from .forms import CheckinForm, EventForm
from .models import Event, Tag, Ticket
from .services import book_event_for_student, cancel_ticket_and_promote, check_in_ticket


def parse_filter_datetime(value):
    # Small helper for datetime-local inputs from the filter form
    if not value:
        return None
    try:
        dt = timezone.datetime.fromisoformat(value)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except ValueError:
        return None


def event_list(request):
    qs = (
        Event.objects.all()
        .select_related("organizer__user")
        .prefetch_related("tags")
        .annotate(
            confirmed_count=Count(
                "tickets", filter=Q(tickets__status=Ticket.Status.CONFIRMED)
            )
        )
    )

    q = (request.GET.get("q") or "").strip()
    tag = (request.GET.get("tag") or "").strip()
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    if tag:
        qs = qs.filter(tags__name__iexact=tag)

    start_dt = parse_filter_datetime(start)
    end_dt = parse_filter_datetime(end)

    # Handle reversed date inputs without breaking the page
    if start_dt and end_dt and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    if start_dt:
        qs = qs.filter(start_at__gte=start_dt)

    if end_dt:
        qs = qs.filter(start_at__lte=end_dt)

    tags = Tag.objects.order_by("name")
    return render(
        request,
        "events/event_list.html",
        {
            "events": qs.distinct(),
            "tags": tags,
            "q": q,
            "tag": tag,
            "start": start,
            "end": end,
        },
    )


def event_detail(request, event_id: int):
    event = get_object_or_404(
        Event.objects.select_related("organizer__user").prefetch_related("tags"),
        pk=event_id,
    )
    confirmed_count = Ticket.objects.filter(
        event=event, status=Ticket.Status.CONFIRMED
    ).count()
    capacity_available = confirmed_count < event.capacity

    student_ticket = None
    is_favorited = False
    if request.user.is_authenticated and is_student(request.user):
        student = get_student_profile(request.user)
        student_ticket = Ticket.objects.filter(
            event=event,
            student=student,
            status__in=[Ticket.Status.CONFIRMED, Ticket.Status.WAITLISTED],
        ).first()
        is_favorited = student.favorite_events.filter(pk=event.pk).exists()

    return render(
        request,
        "events/event_detail.html",
        {
            "event": event,
            "confirmed_count": confirmed_count,
            "capacity_available": capacity_available,
            "student_ticket": student_ticket,
            "is_favorited": is_favorited,
        },
    )


@student_required
@require_POST
def book_event(request, event_id: int):
    event = get_object_or_404(Event, pk=event_id)
    student = get_student_profile(request.user)
    result = book_event_for_student(event=event, student=student)
    if not result.created:
        messages.info(request, "You already have a ticket for this event.")
    else:
        if result.ticket.status == Ticket.Status.CONFIRMED:
            messages.success(request, "Booked! Your ticket is confirmed.")
        else:
            messages.warning(request, "Event is full — you have joined the waitlist.")
    return redirect("event_detail", event_id=event_id)


@student_required
@require_POST
def cancel_ticket(request, ticket_id: int):
    student = get_student_profile(request.user)
    ticket = get_object_or_404(
        Ticket.objects.select_related("event"), pk=ticket_id, student=student
    )
    promoted = cancel_ticket_and_promote(ticket=ticket)
    messages.success(request, "Ticket cancelled.")
    if promoted:
        messages.info(request, "A waitlisted student was promoted automatically.")
    return redirect("student_dashboard")


@student_required
@require_POST
def toggle_favorite(request, event_id: int):
    event = get_object_or_404(Event, pk=event_id)
    student = get_student_profile(request.user)
    if student.favorite_events.filter(pk=event.pk).exists():
        student.favorite_events.remove(event)
        favorited = False
    else:
        student.favorite_events.add(event)
        favorited = True

    wants_json = "application/json" in (request.headers.get("Accept") or "")
    if wants_json:
        return JsonResponse({"favorited": favorited})
    return redirect("event_detail", event_id=event_id)


@organizer_required
def create_event(request):
    organizer = get_organizer_profile(request.user)
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = organizer
            event.save()
            form.apply_tags(event)
            messages.success(request, "Event created.")
            return redirect("organizer_dashboard")
    else:
        form = EventForm()
    return render(request, "events/event_form.html", {"form": form})


@organizer_required
def export_attendees_csv(request, event_id: int):
    organizer = get_organizer_profile(request.user)
    event = get_object_or_404(Event, pk=event_id, organizer=organizer)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="event_{event_id}_attendees.csv"'

    writer = csv.writer(response)
    writer.writerow(
        ["event_id", "event_title", "student_username", "student_email", "status", "checked_in"]
    )
    for t in (
        Ticket.objects.filter(event=event, status=Ticket.Status.CONFIRMED)
        .select_related("student__user")
        .order_by("created_at")
    ):
        writer.writerow(
            [
                event.id,
                event.title,
                t.student.user.username,
                t.student.user.email,
                t.status,
                "yes" if t.checked_in else "no",
            ]
        )
    return response


@login_required
def ticket_qr_png(request, ticket_code):
    ticket = get_object_or_404(
        Ticket.objects.select_related("student__user", "event__organizer__user"),
        ticket_code=ticket_code,
    )

    user = request.user
    allowed = user.is_superuser
    if not allowed and is_student(user):
        allowed = ticket.student.user_id == user.id
    if not allowed and is_organizer(user):
        allowed = ticket.event.organizer.user_id == user.id
    if not allowed:
        raise Http404()

    img = qrcode.make(str(ticket.ticket_code))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


@organizer_required
def organizer_checkin(request):
    organizer = get_organizer_profile(request.user)
    checked_ticket = None
    error = None

    if request.method == "POST":
        form = CheckinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["ticket_code"]
            ticket = (
                Ticket.objects.select_related("event__organizer__user", "student__user")
                .filter(ticket_code=code, event__organizer=organizer)
                .first()
            )
            if not ticket:
                error = "Ticket not found for your events."
            elif ticket.status != Ticket.Status.CONFIRMED:
                error = "Ticket is not confirmed."
            else:
                checked_ticket = check_in_ticket(ticket=ticket)
                messages.success(request, "Checked in successfully.")
        else:
            error = "Invalid ticket code."
    else:
        form = CheckinForm()

    return render(
        request,
        "events/checkin.html",
        {"form": form, "checked_ticket": checked_ticket, "error": error},
    )