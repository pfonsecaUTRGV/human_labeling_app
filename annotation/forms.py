from django import forms
from django.contrib.auth.models import User
from annotation.models import TaxonomyCategory, TaxonomyItem


class SimpleSignupForm(forms.ModelForm):

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput
    )

    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput
    )

    class Meta:
        model = User
        fields = ["username"]

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    "Passwords do not match."
                )

        return cleaned_data

    def save(self, commit=True):

        user = super().save(
            commit=False
        )

        user.set_password(
            self.cleaned_data["password1"]
        )

        if commit:
            user.save()

        return user




class AnnotationForm(forms.Form):

    worker_count = forms.IntegerField(
        label="Number of visible workers",
        min_value=0,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",
            }
        ),
    )

    PPE_CHOICES = [
        ("high", "High compliance"),
        ("medium", "Medium compliance"),
        ("low", "Low compliance"),
        ("not_visible", "PPE not visible / cannot determine"),
    ]

    ppe_compliance = forms.ChoiceField(
        label="PPE compliance",
        choices=PPE_CHOICES,
        required=True,
        widget=forms.RadioSelect,
    )

    notes = forms.CharField(
        label="Optional notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Optional comments about the image...",
            }
        ),
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        categories = (
            TaxonomyCategory.objects
           # .prefetch_related("items")
            .all()
            .order_by("name")
        )

        self.taxonomy_fields = []

        for category in categories:

            field_name = (
                f"taxonomy_{category.id}"
            )

            items = (
                TaxonomyItem.objects
                .filter(
                    category=category,
                    active=True,
                )
                .order_by(
                    "canonical_name"
                )
            )

            # Stage is single-select.
            if category.name.lower() == "stage":

                self.fields[field_name] = (
                    forms.ModelChoiceField(
                        label=category.name,
                        queryset=items,
                        required=True,
                        widget=forms.RadioSelect,
                    )
                )

            else:

                self.fields[field_name] = (
                    forms.ModelMultipleChoiceField(
                        label=category.name,
                        queryset=items,
                        required=False,
                        widget=forms.CheckboxSelectMultiple,
                    )
                )

            self.taxonomy_fields.append(
                {
                    "name": field_name,
                    "category": category,
                }
            )