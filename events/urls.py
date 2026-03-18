from django.urls import path

from . import views


urlpatterns = [
    path("", views.event_list, name="event_list"),
    path("events/<int:event_id>/", views.event_detail, name="event_detail"),
    path("events/<int:event_id>/book/", views.book_event, name="book_event"),
    path("tickets/<int:ticket_id>/cancel/", views.cancel_ticket, name="cancel_ticket"),
    path("events/<int:event_id>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("organizers/<int:organizer_id>/follow/",views.toggle_follow_organizer,name="toggle_follow_organizer",),
    path("organizer/events/create/", views.create_event, name="create_event"),
    path("organizer/events/<int:event_id>/delete/",views.delete_event,name="delete_event",),
    path(
        "organizer/events/<int:event_id>/attendees.csv",
        views.export_attendees_csv,
        name="export_attendees_csv",
    ),
    path(
        "tickets/<uuid:ticket_code>/qr.png",
        views.ticket_qr_png,
        name="ticket_qr_png",
    ),
    path("organizer/checkin/", views.organizer_checkin, name="organizer_checkin"),
]

