from django.contrib import admin

from .models import Event, Tag, Ticket


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "organizer", "start_at", "capacity")
    list_filter = ("start_at", "tags")
    search_fields = ("title", "description", "location_name")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "student", "status", "ticket_code", "checked_in")
    list_filter = ("status", "checked_in", "event")
    search_fields = ("ticket_code", "student__user__username", "student__user__email", "event__title")
