from django.urls import path

from . import views


urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),
    path("dashboard/organizer/", views.organizer_dashboard, name="organizer_dashboard"),
]

