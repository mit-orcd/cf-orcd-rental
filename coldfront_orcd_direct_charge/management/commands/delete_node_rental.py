# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to delete node rental reservations.

Deletes one or more reservations by their IDs. By default, requires confirmation
unless --force is specified.

Examples:
    coldfront delete_node_rental 42
    coldfront delete_node_rental 42 43 44
    coldfront delete_node_rental 42 --force
    coldfront delete_node_rental 42 --dry-run
"""

from django.core.management.base import BaseCommand

from coldfront_orcd_direct_charge.models import Reservation


class Command(BaseCommand):
    help = "Delete one or more node rental reservations"

    def add_arguments(self, parser):
        # Required positional argument(s)
        parser.add_argument(
            "reservation_ids",
            type=int,
            nargs="+",
            help="ID(s) of the reservation(s) to delete",
        )

        # Optional arguments
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete without confirmation prompt",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without making changes",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-essential output",
        )

    def handle(self, *args, **options):
        reservation_ids = options["reservation_ids"]
        force = options["force"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # Look up all reservations first
        reservations = []
        not_found = []

        for res_id in reservation_ids:
            try:
                reservation = Reservation.objects.get(pk=res_id)
                reservations.append(reservation)
            except Reservation.DoesNotExist:
                not_found.append(res_id)

        # Report any not found
        if not_found:
            self.stdout.write(self.style.ERROR(
                f"Reservation(s) not found: {', '.join(map(str, not_found))}"
            ))
            if not reservations:
                return

        # Show what will be deleted
        if not quiet or dry_run:
            self.stdout.write("")
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"[DRY-RUN] Would delete {len(reservations)} reservation(s):"
                ))
            else:
                self.stdout.write(f"Reservations to delete ({len(reservations)}):")
            self.stdout.write("")

            for res in reservations:
                self._print_reservation_details(res)
                self.stdout.write("")

        # Dry-run mode: exit here
        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))
            return

        # Confirm deletion unless --force is specified
        if not force:
            self.stdout.write(self.style.WARNING(
                "This action cannot be undone."
            ))
            confirm = input(f"Delete {len(reservations)} reservation(s)? [y/N]: ")
            if confirm.lower() not in ("y", "yes"):
                self.stdout.write("Deletion cancelled.")
                return

        # Delete the reservations
        deleted_ids = []
        for res in reservations:
            res_id = res.pk
            res.delete()
            deleted_ids.append(res_id)
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Deleted reservation #{res_id}"
                ))

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"Successfully deleted {len(deleted_ids)} reservation(s): "
                f"{', '.join(map(str, deleted_ids))}"
            ))

    def _print_reservation_details(self, reservation):
        """Print details of a reservation."""
        self.stdout.write(f"  Reservation #{reservation.pk}:")
        self.stdout.write(f"    Node: {reservation.node_instance.associated_resource_address} "
                         f"({reservation.node_instance.node_type.name})")
        self.stdout.write(f"    Project: {reservation.project.title}")
        self.stdout.write(f"    Requesting User: {reservation.requesting_user.username}")
        self.stdout.write(f"    Start: {reservation.start_date} at 4:00 PM")
        self.stdout.write(f"    Duration: {reservation.num_blocks} block(s) "
                         f"({reservation.num_blocks * 12} hours)")
        self.stdout.write(f"    End: {reservation.end_datetime.strftime('%Y-%m-%d %I:%M %p')}")
        self.stdout.write(f"    Status: {reservation.get_status_display()}")
        if reservation.processed_by:
            self.stdout.write(f"    Processed by: {reservation.processed_by.username}")
        if reservation.rental_notes:
            notes = reservation.rental_notes[:50] + "..." if len(reservation.rental_notes) > 50 else reservation.rental_notes
            self.stdout.write(f"    Rental Notes: {notes}")
        if reservation.manager_notes:
            notes = reservation.manager_notes[:50] + "..." if len(reservation.manager_notes) > 50 else reservation.manager_notes
            self.stdout.write(f"    Manager Notes: {notes}")
