from __future__ import annotations

import csv
import io
from collections import defaultdict

import qrcode
from django.conf import settings
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
from .services import (
    book_event_for_student,
    cancel_ticket_and_promote,
    check_in_ticket,
    rebuild_and_save_student_preferences,
)


def _build_student_preferences(student) -> dict[str, float]:
    """
    简化版偏好向量：
    - 收藏过的活动标签：+1
    - 报名/候补过的活动标签：+2
    """
    prefs = defaultdict(float)

    for event in student.favorite_events.prefetch_related("tags").all():
        for tag in event.tags.all():
            prefs[tag.name] += 1.0

    for ticket in student.tickets.select_related("event").prefetch_related("event__tags").all():
        for tag in ticket.event.tags.all():
            prefs[tag.name] += 2.0

    return dict(prefs)


def _get_student_preferences(student) -> dict[str, float]:
    """
    优先使用数据库里已保存的 preferences；
    如果为空，则临时根据历史行为构建。
    """
    prefs = student.preferences or {}
    if prefs:
        return prefs
    return _build_student_preferences(student)


def _score_event_for_student(event, prefs: dict[str, float]) -> float:
    """
    推荐分 = 偏好匹配 + 热度 + 临近开始时间
    """
    score = 0.0

    # 1) 偏好匹配：事件标签越符合用户偏好，分越高
    for tag in event.tags.all():
        score += float(prefs.get(tag.name, 0))

    # 2) 热度：confirmed_count 越高，分越高
    score += float(getattr(event, "confirmed_count", 0)) * 0.5

    # 3) 临近开始：未来 7 天内的活动给一点加分
    now = timezone.now()
    if event.start_at and event.start_at > now:
        hours_until_start = (event.start_at - now).total_seconds() / 3600
        if hours_until_start <= 24:
            score += 2.0
        elif hours_until_start <= 72:
            score += 1.2
        elif hours_until_start <= 168:
            score += 0.6

    return score


def _get_recommended_events(student, events, limit: int = 6):
    prefs = _get_student_preferences(student)

    scored = []
    for event in events:
        # 不推荐已经结束的活动
        if event.start_at and event.start_at < timezone.now():
            continue
        score = _score_event_for_student(event, prefs)
        scored.append((score, event))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in scored[:limit]]


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
    if start:
        try:
            start_dt = timezone.datetime.fromisoformat(start)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
            qs = qs.filter(start_at__gte=start_dt)
        except ValueError:
            pass
    if end:
        try:
            end_dt = timezone.datetime.fromisoformat(end)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)
            qs = qs.filter(start_at__lte=end_dt)
        except ValueError:
            pass

    tags = Tag.objects.order_by("name")
    events = list(qs.distinct())

    recommended_events = []
    if request.user.is_authenticated and is_student(request.user):
        student = get_student_profile(request.user)
        recommended_events = _get_recommended_events(student, events, limit=6)

    recommended_ids = {e.id for e in recommended_events}
    all_events = [e for e in events if e.id not in recommended_ids]

    return render(
        request,
        "events/event_list.html",
        {
            "events": all_events,
            "recommended_events": recommended_events,
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
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
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

    rebuild_and_save_student_preferences(student)
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
    rebuild_and_save_student_preferences(student)
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

    rebuild_and_save_student_preferences(student)

    wants_json = "application/json" in (request.headers.get("Accept") or "")
    if wants_json:
        return JsonResponse({"favorited": favorited})
    return redirect("event_detail", event_id=event_id)

@organizer_required
def create_event(request):
    organizer = get_organizer_profile(request.user)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = organizer
            event.save()
            form.apply_tags(event)
            messages.success(request, "Event created.")
            return redirect("organizer_dashboard")
    else:
        form = EventForm()
    return render(
        request,
        "events/event_form.html",
        {
            "form": form,
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
            "GOOGLE_MAPS_MAP_ID": settings.GOOGLE_MAPS_MAP_ID,
        },
    )


@organizer_required
@require_POST
def delete_event(request, event_id: int):
    organizer = get_organizer_profile(request.user)
    event = get_object_or_404(Event, pk=event_id, organizer=organizer)
    event_title = event.title
    event.delete()
    messages.success(request, f"Event '{event_title}' was deleted.")
    return redirect("organizer_dashboard")


@organizer_required
def export_attendees_csv(request, event_id: int):
    organizer = get_organizer_profile(request.user)
    event = get_object_or_404(Event, pk=event_id, organizer=organizer)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="event_{event_id}_attendees.csv"'

    writer = csv.writer(response)
    writer.writerow(["event_id", "event_title", "student_username", "student_email", "status", "checked_in"])
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
                rebuild_and_save_student_preferences(checked_ticket.student)
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