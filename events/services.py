from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from accounts.models import StudentProfile

from .models import Event, Ticket


@dataclass(frozen=True)
class BookingResult:
    ticket: Ticket
    created: bool


def book_event_for_student(*, event: Event, student: StudentProfile) -> BookingResult:
    """
    Core booking logic (M3): confirm if capacity allows, else waitlist.
    Uses an atomic transaction to avoid inconsistent counts.
    """
    with transaction.atomic():
        # Row lock (works fully on PostgreSQL; still keeps logic consistent on SQLite).
        event_locked = Event.objects.select_for_update().get(pk=event.pk)

        existing = Ticket.objects.filter(
            event=event_locked,
            student=student,
            status__in=[Ticket.Status.CONFIRMED, Ticket.Status.WAITLISTED],
        ).first()
        if existing:
            return BookingResult(ticket=existing, created=False)

        confirmed_count = Ticket.objects.filter(
            event=event_locked, status=Ticket.Status.CONFIRMED
        ).count()
        status = (
            Ticket.Status.CONFIRMED
            if confirmed_count < event_locked.capacity
            else Ticket.Status.WAITLISTED
        )

        ticket = Ticket.objects.create(event=event_locked, student=student, status=status)
        return BookingResult(ticket=ticket, created=True)


def promote_waitlist_if_possible(*, event: Event) -> Ticket | None:
    """
    Must-have (S1): FIFO promotion from waitlist when capacity opens.
    """
    with transaction.atomic():
        event_locked = Event.objects.select_for_update().get(pk=event.pk)
        confirmed_count = Ticket.objects.filter(
            event=event_locked, status=Ticket.Status.CONFIRMED
        ).count()
        if confirmed_count >= event_locked.capacity:
            return None

        next_ticket = (
            Ticket.objects.select_for_update()
            .filter(event=event_locked, status=Ticket.Status.WAITLISTED)
            .order_by("created_at", "id")
            .first()
        )
        if not next_ticket:
            return None

        next_ticket.status = Ticket.Status.CONFIRMED
        next_ticket.save(update_fields=["status", "updated_at"])
        return next_ticket


def cancel_ticket_and_promote(*, ticket: Ticket) -> Ticket | None:
    """
    Cancellation (M4): cancel ticket and trigger promotion if it frees a spot.
    Returns the promoted ticket (if any).
    """
    event = None
    with transaction.atomic():
        ticket_locked = Ticket.objects.select_for_update().select_related("event").get(
            pk=ticket.pk
        )
        if ticket_locked.status == Ticket.Status.CANCELLED:
            return None
        was_confirmed = ticket_locked.status == Ticket.Status.CONFIRMED
        event = ticket_locked.event
        ticket_locked.status = Ticket.Status.CANCELLED
        ticket_locked.save(update_fields=["status", "updated_at"])

    if was_confirmed:
        return promote_waitlist_if_possible(event=event)
    return None


def check_in_ticket(*, ticket: Ticket) -> Ticket:
    if ticket.checked_in:
        return ticket
    ticket.checked_in = True
    ticket.checked_in_at = timezone.now()
    ticket.save(update_fields=["checked_in", "checked_in_at", "updated_at"])
    return ticket

from collections import defaultdict
from django.utils import timezone

def compute_user_preferences(student):
    """
    根据用户历史行为，生成 tag 权重（简单版）
    """
    prefs = defaultdict(float)

    # 收藏
    for event in student.favorite_events.all():
        for tag in event.tags.all():
            prefs[tag.name] += 1.0

    # 订票
    for ticket in student.tickets.all():
        for tag in ticket.event.tags.all():
            prefs[tag.name] += 2.0

    return dict(prefs)


def score_event(event, prefs):
    """
    计算单个 event 的推荐分
    """
    score = 0

    # 1. 偏好匹配
    for tag in event.tags.all():
        score += prefs.get(tag.name, 0)

    # 2. 热度（报名人数）
    score += event.confirmed_count * 0.5

    # 3. 新鲜度（越新越高）
    now = timezone.now()
    delta_hours = (now - event.created_at).total_seconds() / 3600
    freshness = max(0, 48 - delta_hours) / 48  # 48小时衰减

    score += freshness * 2

    return score


def get_recommended_events(student, events):
    """
    返回排序后的推荐 events
    """
    prefs = compute_user_preferences(student)

    scored = []
    for e in events:
        s = score_event(e, prefs)
        scored.append((s, e))

    scored.sort(reverse=True, key=lambda x: x[0])

    return [e for _, e in scored]

from collections import defaultdict


def rebuild_and_save_student_preferences(student) -> dict[str, float]:
    """
    根据当前学生的真实行为，重建偏好向量并落库。
    规则：
    - 收藏活动的 tag：+1
    - 已报名/候补活动的 tag：+2
    - 已签到活动的 tag：额外 +1
    """
    prefs = defaultdict(float)

    # 收藏行为
    for event in student.favorite_events.prefetch_related("tags").all():
        for tag in event.tags.all():
            prefs[tag.name] += 1.0

    # 票务/参与行为
    for ticket in student.tickets.select_related("event").prefetch_related("event__tags").all():
        base = 2.0
        if ticket.checked_in:
            base += 1.0

        for tag in ticket.event.tags.all():
            prefs[tag.name] += base

    student.preferences = dict(prefs)
    student.save(update_fields=["preferences", "preferences_updated_at"])
    return student.preferences