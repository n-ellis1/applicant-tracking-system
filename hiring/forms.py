from django import forms
from django.utils import timezone

from .models import Candidate, JobOpening, Skill, validate_not_future


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "input w-full"})}

    def clean_name(self):
        # The form field has already trimmed surrounding spaces.
        name = self.cleaned_data["name"]
        others = Skill.objects.exclude(pk=self.instance.pk)
        if others.filter(name__iexact=name).exists():
            raise forms.ValidationError("A skill with this name already exists.")
        return name


class JobOpeningForm(forms.ModelForm):
    # Status and closed date are left out: only closing and reopening change them.
    class Meta:
        model = JobOpening
        fields = [
            "title",
            "department",
            "employment_type",
            "location",
            "description",
            "skills",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input w-full"}),
            "department": forms.TextInput(attrs={"class": "input w-full"}),
            "employment_type": forms.Select(attrs={"class": "select w-full"}),
            "location": forms.TextInput(
                attrs={"class": "input w-full", "placeholder": "e.g. Remote"}
            ),
            "description": forms.Textarea(
                attrs={"class": "textarea w-full", "rows": 6}
            ),
            "skills": forms.CheckboxSelectMultiple(attrs={"class": "checkbox"}),
        }


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "location",
            "profile_url",
            "source",
            "source_details",
            "notes",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "input w-full"}),
            "last_name": forms.TextInput(attrs={"class": "input w-full"}),
            "email": forms.EmailInput(attrs={"class": "input w-full"}),
            "phone": forms.TextInput(attrs={"class": "input w-full"}),
            "location": forms.TextInput(attrs={"class": "input w-full"}),
            "profile_url": forms.URLInput(
                attrs={"class": "input w-full", "placeholder": "https://"}
            ),
            "source": forms.Select(attrs={"class": "select w-full"}),
            "source_details": forms.TextInput(
                attrs={"class": "input w-full", "placeholder": "e.g. referred by"}
            ),
            "notes": forms.Textarea(attrs={"class": "textarea w-full", "rows": 4}),
        }

    def clean_email(self):
        # The form field has already trimmed surrounding spaces.
        email = self.cleaned_data["email"].lower()
        others = Candidate.objects.exclude(pk=self.instance.pk)
        if others.filter(email__iexact=email).exists():
            raise forms.ValidationError("A candidate with this email already exists.")
        return email


class EligibleChoiceField(forms.ModelChoiceField):
    """Lists only the eligible records but accepts any existing one.

    A stale or forged choice then reaches the service, which explains why it's
    refused, instead of failing with a generic "Select a valid choice".
    """

    def to_python(self, value):
        if value in self.empty_values:
            return None
        model = self.queryset.model
        try:
            return model._default_manager.get(pk=value)
        except ValueError, TypeError, model.DoesNotExist:
            raise forms.ValidationError(
                self.error_messages["invalid_choice"], code="invalid_choice"
            ) from None


class CandidateApplicationForm(forms.Form):
    job = EligibleChoiceField(
        queryset=JobOpening.objects.none(),
        widget=forms.Select(attrs={"class": "select w-full"}),
    )
    applied_on = forms.DateField(
        initial=timezone.localdate,
        validators=[validate_not_future],
        widget=forms.DateInput(attrs={"class": "input w-full", "type": "date"}),
    )

    def __init__(self, *args, candidate, **kwargs):
        super().__init__(*args, **kwargs)
        # The picker offers only open jobs the candidate hasn't applied to.
        # The service re-checks every submission.
        self.fields["job"].queryset = JobOpening.objects.filter(
            status=JobOpening.Status.OPEN
        ).exclude(applications__candidate=candidate)
