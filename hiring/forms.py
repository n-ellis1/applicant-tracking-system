from django import forms

from .models import JobOpening, Skill


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
