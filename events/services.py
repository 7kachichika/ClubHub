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

