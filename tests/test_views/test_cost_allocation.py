# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Tests for ProjectCostAllocationView.

These tests verify that:
1. Viewing (GET) the cost allocation page does NOT create a database record
2. Submitting (POST) a valid form DOES create a database record with PENDING status
3. Canceling after viewing does not leave a pending allocation
4. Existing allocations are preserved when viewing the page

To run these tests, you need a ColdFront installation with this plugin installed.
Run from the ColdFront directory:

    python manage.py test coldfront_orcd_direct_charge.tests.test_views.test_cost_allocation

Or using pytest with pytest-django:

    pytest tests/test_views/test_cost_allocation.py -v
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from coldfront.core.project.models import (
    Project,
    ProjectStatusChoice,
    ProjectUser,
    ProjectUserRoleChoice,
    ProjectUserStatusChoice,
)

from coldfront_orcd_direct_charge.models import (
    ProjectCostAllocation,
    ProjectCostObject,
)


class CostAllocationViewTestCase(TestCase):
    """Base test case with common setup for cost allocation tests."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all test methods."""
        # Create a test user who will be the project owner (PI)
        cls.pi_user = User.objects.create_user(
            username="testpi",
            email="testpi@example.com",
            password="testpassword123",
        )

        # Ensure user has a userprofile with is_pi=True
        if hasattr(cls.pi_user, "userprofile"):
            cls.pi_user.userprofile.is_pi = True
            cls.pi_user.userprofile.save()

        # Get or create project status
        cls.active_status, _ = ProjectStatusChoice.objects.get_or_create(
            name="Active"
        )

        # Create a test project
        cls.project = Project.objects.create(
            title="test_cost_allocation_project",
            pi=cls.pi_user,
            status=cls.active_status,
            description="Test project for cost allocation tests",
        )

        # Add PI as a project user
        manager_role, _ = ProjectUserRoleChoice.objects.get_or_create(name="Manager")
        active_pu_status, _ = ProjectUserStatusChoice.objects.get_or_create(
            name="Active"
        )
        ProjectUser.objects.create(
            project=cls.project,
            user=cls.pi_user,
            role=manager_role,
            status=active_pu_status,
        )

    def setUp(self):
        """Set up test client and login."""
        self.client = Client()
        self.client.login(username="testpi", password="testpassword123")
        self.cost_allocation_url = reverse(
            "coldfront_orcd_direct_charge:project-cost-allocation",
            kwargs={"pk": self.project.pk},
        )


class TestCancelDoesNotCreateAllocation(CostAllocationViewTestCase):
    """Test that viewing (GET) the cost allocation page does not create a DB record."""

    def test_get_page_does_not_create_allocation(self):
        """
        GET request to cost allocation page should NOT create a ProjectCostAllocation.

        This is the main bug fix test - previously, viewing the page would create
        a PENDING allocation even if the user canceled.
        """
        # Verify no allocation exists before the request
        self.assertFalse(
            ProjectCostAllocation.objects.filter(project=self.project).exists()
        )

        # GET the cost allocation page
        response = self.client.get(self.cost_allocation_url)

        # Verify the page loads successfully
        self.assertEqual(response.status_code, 200)

        # Verify NO allocation was created
        self.assertFalse(
            ProjectCostAllocation.objects.filter(project=self.project).exists(),
            "GET request should NOT create a ProjectCostAllocation record",
        )

    def test_multiple_gets_do_not_create_allocation(self):
        """Multiple GET requests should not create any allocations."""
        # Simulate user viewing the page multiple times
        for _ in range(3):
            response = self.client.get(self.cost_allocation_url)
            self.assertEqual(response.status_code, 200)

        # Still no allocation should exist
        self.assertFalse(
            ProjectCostAllocation.objects.filter(project=self.project).exists()
        )


class TestSubmitCreatesAllocation(CostAllocationViewTestCase):
    """Test that submitting a valid form creates a PENDING allocation."""

    def test_valid_post_creates_pending_allocation(self):
        """POST with valid cost objects should create allocation with PENDING status."""
        # Verify no allocation exists before
        self.assertFalse(
            ProjectCostAllocation.objects.filter(project=self.project).exists()
        )

        # Submit a valid form with cost objects totaling 100%
        post_data = {
            "notes": "Test allocation notes",
            # Formset management form data
            "cost_objects-TOTAL_FORMS": "1",
            "cost_objects-INITIAL_FORMS": "0",
            "cost_objects-MIN_NUM_FORMS": "0",
            "cost_objects-MAX_NUM_FORMS": "1000",
            # Cost object data
            "cost_objects-0-cost_object": "TEST-COST-001",
            "cost_objects-0-percentage": "100.00",
        }

        response = self.client.post(self.cost_allocation_url, data=post_data)

        # Should redirect to project detail on success
        self.assertEqual(response.status_code, 302)

        # Verify allocation was created
        self.assertTrue(
            ProjectCostAllocation.objects.filter(project=self.project).exists()
        )

        # Verify status is PENDING
        allocation = ProjectCostAllocation.objects.get(project=self.project)
        self.assertEqual(
            allocation.status,
            ProjectCostAllocation.StatusChoices.PENDING,
        )

        # Verify cost object was created
        self.assertEqual(allocation.cost_objects.count(), 1)
        cost_obj = allocation.cost_objects.first()
        self.assertEqual(cost_obj.cost_object, "TEST-COST-001")
        self.assertEqual(cost_obj.percentage, 100.00)

    def test_invalid_post_does_not_create_allocation(self):
        """POST with invalid data should NOT create an allocation."""
        # Submit invalid form (percentages don't sum to 100%)
        post_data = {
            "notes": "Test allocation notes",
            "cost_objects-TOTAL_FORMS": "1",
            "cost_objects-INITIAL_FORMS": "0",
            "cost_objects-MIN_NUM_FORMS": "0",
            "cost_objects-MAX_NUM_FORMS": "1000",
            "cost_objects-0-cost_object": "TEST-COST-001",
            "cost_objects-0-percentage": "50.00",  # Only 50%, not 100%
        }

        response = self.client.post(self.cost_allocation_url, data=post_data)

        # Should stay on the page (200 with form errors)
        self.assertEqual(response.status_code, 200)

        # Verify NO allocation was created
        self.assertFalse(
            ProjectCostAllocation.objects.filter(project=self.project).exists(),
            "Invalid form submission should NOT create allocation",
        )


class TestExistingAllocationPreserved(CostAllocationViewTestCase):
    """Test that existing allocations are preserved when viewing the page."""

    def setUp(self):
        super().setUp()
        # Create an existing APPROVED allocation
        self.allocation = ProjectCostAllocation.objects.create(
            project=self.project,
            notes="Existing approved allocation",
            status=ProjectCostAllocation.StatusChoices.APPROVED,
        )
        ProjectCostObject.objects.create(
            allocation=self.allocation,
            cost_object="EXISTING-001",
            percentage=100.00,
        )

    def test_get_preserves_approved_status(self):
        """GET request should NOT change status of existing approved allocation."""
        # GET the page
        response = self.client.get(self.cost_allocation_url)
        self.assertEqual(response.status_code, 200)

        # Refresh allocation from DB
        self.allocation.refresh_from_db()

        # Status should still be APPROVED
        self.assertEqual(
            self.allocation.status,
            ProjectCostAllocation.StatusChoices.APPROVED,
        )

    def test_submit_changes_approved_to_pending(self):
        """POST should change existing APPROVED allocation to PENDING."""
        # Verify current status is APPROVED
        self.assertEqual(
            self.allocation.status,
            ProjectCostAllocation.StatusChoices.APPROVED,
        )

        # Submit changes
        post_data = {
            "notes": "Updated notes",
            "cost_objects-TOTAL_FORMS": "1",
            "cost_objects-INITIAL_FORMS": "1",
            "cost_objects-MIN_NUM_FORMS": "0",
            "cost_objects-MAX_NUM_FORMS": "1000",
            "cost_objects-0-id": str(self.allocation.cost_objects.first().pk),
            "cost_objects-0-allocation": str(self.allocation.pk),
            "cost_objects-0-cost_object": "UPDATED-001",
            "cost_objects-0-percentage": "100.00",
        }

        response = self.client.post(self.cost_allocation_url, data=post_data)
        self.assertEqual(response.status_code, 302)

        # Refresh and verify status changed to PENDING
        self.allocation.refresh_from_db()
        self.assertEqual(
            self.allocation.status,
            ProjectCostAllocation.StatusChoices.PENDING,
        )

    def test_existing_cost_objects_displayed(self):
        """Existing cost objects should be displayed in the form."""
        response = self.client.get(self.cost_allocation_url)
        self.assertEqual(response.status_code, 200)

        # Check that existing cost object is in the response
        self.assertContains(response, "EXISTING-001")


class TestActivityLogging(CostAllocationViewTestCase):
    """Test that activity logging only fires on actual submission."""

    def test_get_does_not_log_creation(self):
        """GET request should NOT create activity log for cost_allocation.created."""
        from coldfront_orcd_direct_charge.models import ActivityLog

        # Count existing logs
        initial_count = ActivityLog.objects.filter(
            action="cost_allocation.created"
        ).count()

        # GET the page
        self.client.get(self.cost_allocation_url)

        # No new log should be created
        final_count = ActivityLog.objects.filter(
            action="cost_allocation.created"
        ).count()
        self.assertEqual(initial_count, final_count)

    def test_post_logs_creation(self):
        """POST with valid data should create activity log."""
        from coldfront_orcd_direct_charge.models import ActivityLog

        # Count existing logs
        initial_count = ActivityLog.objects.filter(
            action="cost_allocation.created"
        ).count()

        # Submit valid form
        post_data = {
            "notes": "Test",
            "cost_objects-TOTAL_FORMS": "1",
            "cost_objects-INITIAL_FORMS": "0",
            "cost_objects-MIN_NUM_FORMS": "0",
            "cost_objects-MAX_NUM_FORMS": "1000",
            "cost_objects-0-cost_object": "LOG-TEST-001",
            "cost_objects-0-percentage": "100.00",
        }

        self.client.post(self.cost_allocation_url, data=post_data)

        # New log should be created
        final_count = ActivityLog.objects.filter(
            action="cost_allocation.created"
        ).count()
        self.assertEqual(final_count, initial_count + 1)
