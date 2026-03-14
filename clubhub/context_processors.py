from django.conf import settings


def mapbox(request):
    return {"MAPBOX_TOKEN": getattr(settings, "MAPBOX_TOKEN", "")}

