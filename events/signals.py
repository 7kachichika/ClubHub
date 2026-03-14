from __future__ import annotations

from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Ticket


@receiver(pre_save, sender=Ticket)
def _ticket_cache_old_status(sender, instance: Ticket, **kwargs):
    if not instance.pk:
        instance._old_status = None
        return
    try:
        old = Ticket.objects.get(pk=instance.pk)
        instance._old_status = old.status
    except Ticket.DoesNotExist:
        instance._old_status = None


@receiver(post_save, sender=Ticket)
def _ticket_email_notifications(sender, instance: Ticket, created: bool, **kwargs):
    if not instance.student_id:
        return
    user = instance.student.user
    if not user.email:
        return

    old_status = getattr(instance, "_old_status", None)

    should_email = False
    subject = ""
    message = ""

    if created and instance.status == Ticket.Status.CONFIRMED:
        should_email = True
        subject = f"[ClubHub] Booking confirmed: {instance.event.title}"
        message = (
            f"Your booking is confirmed.\n\n"
            f"Event: {instance.event.title}\n"
            f"Start: {timezone.localtime(instance.event.start_at)}\n"
            f"Ticket code: {instance.ticket_code}\n"
        )
    elif (not created) and instance.status == Ticket.Status.CONFIRMED and old_status == Ticket.Status.WAITLISTED:
        should_email = True
        subject = f"[ClubHub] Promoted from waitlist: {instance.event.title}"
        message = (
            f"Good news — you have been promoted from the waitlist.\n\n"
            f"Event: {instance.event.title}\n"
            f"Start: {timezone.localtime(instance.event.start_at)}\n"
            f"Ticket code: {instance.ticket_code}\n"
        )

    if should_email:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

