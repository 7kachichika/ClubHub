from django.conf import settings


def google_maps(request):
    return {
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "GOOGLE_MAPS_MAP_ID": getattr(settings, "GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID"),
    }