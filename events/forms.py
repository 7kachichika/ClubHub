from __future__ import annotations

from django import forms

from .models import Event, Tag


class EventForm(forms.ModelForm):
    tags_text = forms.CharField(
        required=False,
        help_text="Comma-separated tags (e.g. Sports, Tech, Social).",
    )

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "start_at",
            "capacity",
            "location_name",
            "latitude",
            "longitude",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def _parse_tag_names(self) -> list[str]:
        tags_text = (self.cleaned_data.get("tags_text") or "").strip()
        return [n.strip() for n in tags_text.split(",") if n.strip()]

    def apply_tags(self, instance: Event) -> None:
        names = self._parse_tag_names()
        if not names:
            instance.tags.clear()
            return
        tags = []
        for n in names:
            tag, _ = Tag.objects.get_or_create(name=n)
            tags.append(tag)
        instance.tags.set(tags)

    def save(self, commit=True):
        instance: Event = super().save(commit=commit)
        if commit:
            self.apply_tags(instance)
        return instance


class CheckinForm(forms.Form):
    ticket_code = forms.UUIDField(help_text="Paste the UUID ticket code.")

