# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django import forms
from django.core.exceptions import ValidationError

from django.contrib.auth.models import User

from coldfront_orcd_direct_charge.models import (
    GpuNodeInstance,
    ProjectCostAllocation,
    ProjectCostObject,
    ProjectMemberRole,
    Reservation,
    ReservationMetadataEntry,
)


# Duration choices for reservation (1-14 blocks of 12 hours each)
# Note: Even blocks end at 4PM which is truncated to 9AM (losing 7 hours)
# Odd blocks end at 4AM which is before 9AM (no truncation)
DURATION_CHOICES = [
    (1, "12 hours (4PM → 4AM next day)"),
    (2, "17 hours (4PM → 9AM next day)"),
    (3, "36 hours (4PM → 4AM in 2 days)"),
    (4, "41 hours (4PM → 9AM in 2 days)"),
    (5, "60 hours (4PM → 4AM in 3 days)"),
    (6, "65 hours (4PM → 9AM in 3 days)"),
    (7, "84 hours (4PM → 4AM in 4 days)"),
    (8, "89 hours (4PM → 9AM in 4 days)"),
    (9, "108 hours (4PM → 4AM in 5 days)"),
    (10, "113 hours (4PM → 9AM in 5 days)"),
    (11, "132 hours (4PM → 4AM in 6 days)"),
    (12, "137 hours (4PM → 9AM in 6 days)"),
    (13, "156 hours (4PM → 4AM in 7 days)"),
    (14, "161 hours (4PM → 9AM in 7 days)"),
]


class ReservationRequestForm(forms.ModelForm):
    """Form for submitting a reservation request for a GPU node."""

    num_blocks = forms.ChoiceField(
        choices=DURATION_CHOICES,
        label="Duration",
        help_text="Select the duration of your reservation (in 12-hour blocks)",
    )

    class Meta:
        model = Reservation
        fields = ["node_instance", "project", "start_date", "num_blocks", "rental_notes"]
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "rental_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Optional notes about your reservation request...",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Filter node instances to only rentable H200x8 nodes
        self.fields["node_instance"].queryset = GpuNodeInstance.objects.filter(
            is_rentable=True,
            node_type__name="H200x8",
        )
        self.fields["node_instance"].label = "GPU Node"

        # Filter projects to only those the user is a member of
        if user:
            from coldfront.core.project.models import Project

            user_projects = Project.objects.filter(
                projectuser__user=user,
                projectuser__status__name="Active",
                status__name="Active",
            )
            self.fields["project"].queryset = user_projects
        
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.DateInput):
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        node_instance = cleaned_data.get("node_instance")
        start_date = cleaned_data.get("start_date")
        num_blocks = cleaned_data.get("num_blocks")

        if start_date:
            from datetime import date, timedelta
            
            # Enforce 7-day advance booking requirement
            earliest_bookable = date.today() + timedelta(days=7)
            if start_date < earliest_bookable:
                raise ValidationError(
                    f"Reservations require a minimum 7-day lead time. "
                    f"The earliest available start date is {earliest_bookable.strftime('%b %d, %Y')}."
                )

        if node_instance and start_date and num_blocks:
            num_blocks = int(num_blocks)
            # Check for overlapping approved reservations
            from datetime import datetime, time, timedelta

            new_start = datetime.combine(start_date, time(Reservation.START_HOUR, 0))
            new_end = Reservation.calculate_end_datetime(new_start, num_blocks)

            overlapping = Reservation.objects.filter(
                node_instance=node_instance,
                status=Reservation.StatusChoices.APPROVED,
            )

            for reservation in overlapping:
                existing_start = reservation.start_datetime
                existing_end = reservation.end_datetime

                # Check if there's any overlap
                if new_start < existing_end and new_end > existing_start:
                    raise ValidationError(
                        f"This reservation overlaps with an existing approved reservation "
                        f"from {existing_start.strftime('%b %d %I:%M %p')} to "
                        f"{existing_end.strftime('%b %d %I:%M %p')}."
                    )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.num_blocks = int(self.cleaned_data["num_blocks"])
        if self.user:
            instance.requesting_user = self.user
        if commit:
            instance.save()
        return instance


class ReservationDeclineForm(forms.Form):
    """Form for declining a reservation with optional notes."""

    manager_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        required=False,
        label="Notes (optional)",
        help_text="Provide a reason for declining this reservation (visible to requester)",
    )


class ReservationMetadataEntryForm(forms.ModelForm):
    """Form for adding a single metadata entry to a reservation."""

    class Meta:
        model = ReservationMetadataEntry
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Add a new metadata note...",
                }
            ),
        }
        labels = {
            "content": "New Metadata Entry",
        }


class ProjectCostAllocationForm(forms.ModelForm):
    """Form for editing the overall cost allocation notes."""

    class Meta:
        model = ProjectCostAllocation
        fields = ["notes"]
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "Notes about this cost allocation...",
                }
            ),
        }
        labels = {
            "notes": "Allocation Notes",
        }


class ProjectCostObjectForm(forms.ModelForm):
    """Form for individual cost object entries."""

    class Meta:
        model = ProjectCostObject
        fields = ["cost_object", "percentage"]
        widgets = {
            "cost_object": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., ABC-123-XYZ",
                }
            ),
            "percentage": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),
        }
        labels = {
            "cost_object": "Cost Object",
            "percentage": "Percentage (%)",
        }


class BaseProjectCostObjectFormSet(forms.BaseInlineFormSet):
    """Custom formset for cost objects with percentage validation."""

    def clean(self):
        """Validate that all percentages sum to 100%."""
        super().clean()

        if any(self.errors):
            return

        total = 0
        valid_forms = 0

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                percentage = form.cleaned_data.get("percentage", 0)
                if percentage:
                    total += percentage
                    valid_forms += 1

        # Only validate if there are cost objects
        if valid_forms > 0 and total != 100:
            raise ValidationError(
                f"Cost object percentages must sum to 100%. "
                f"Current total: {total}%"
            )


# Create the formset factory
ProjectCostObjectFormSet = forms.inlineformset_factory(
    ProjectCostAllocation,
    ProjectCostObject,
    form=ProjectCostObjectForm,
    formset=BaseProjectCostObjectFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# =============================================================================
# Member Management Forms
# =============================================================================


class AddMemberForm(forms.Form):
    """Form for adding a new member to a project with a role."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter username",
                "autocomplete": "off",
            }
        ),
        help_text="Enter the username of the user to add",
    )
    role = forms.ChoiceField(
        choices=[],  # Will be set dynamically based on current user's permissions
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select the role for this member",
    )

    def __init__(self, *args, project=None, current_user=None, can_add_financial_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.current_user = current_user

        # Set role choices based on current user's permissions
        role_choices = [
            (ProjectMemberRole.RoleChoices.MEMBER, "Member"),
            (ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN, "Technical Admin"),
        ]
        if can_add_financial_admin:
            role_choices.append(
                (ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN, "Financial Admin")
            )
        self.fields["role"].choices = role_choices

    def clean_username(self):
        username = self.cleaned_data["username"]

        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError(f"User '{username}' does not exist.")

        # Check if user is already the project owner
        if self.project and self.project.pi == user:
            raise ValidationError(f"'{username}' is the project owner and cannot be added as a member.")

        # Check if user already has a role in this project
        if self.project and ProjectMemberRole.objects.filter(project=self.project, user=user).exists():
            raise ValidationError(f"'{username}' already has a role in this project.")

        return username


class UpdateMemberRoleForm(forms.Form):
    """Form for updating a member's role in a project."""

    role = forms.ChoiceField(
        choices=[],  # Will be set dynamically
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select the new role for this member",
    )

    def __init__(self, *args, can_set_financial_admin=False, current_role=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Set role choices based on permissions
        role_choices = [
            (ProjectMemberRole.RoleChoices.MEMBER, "Member"),
            (ProjectMemberRole.RoleChoices.TECHNICAL_ADMIN, "Technical Admin"),
        ]
        if can_set_financial_admin:
            role_choices.append(
                (ProjectMemberRole.RoleChoices.FINANCIAL_ADMIN, "Financial Admin")
            )
        self.fields["role"].choices = role_choices

        # Set initial value if provided
        if current_role:
            self.fields["role"].initial = current_role
