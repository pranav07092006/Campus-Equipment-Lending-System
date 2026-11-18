"""Shared state transitions for the HTML interface and REST API.

A conditional database UPDATE claims a part before creating a reservation.
The database serializes competing writes on both SQLite and MySQL/InnoDB.
The transaction rolls the part back if reservation creation fails.
"""
from django.db import transaction
from django.utils import timezone
from .models import Handover, PartListing, Reservation


class ExchangeError(Exception):
    def __init__(self, message, status_code=409):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


EDITABLE_FIELDS = {'title', 'manufacturer', 'part_code', 'category', 'condition', 'supported_models', 'description', 'pickup_area'}


def reserve_part(*, part_id, user, compatibility_confirmed, repair_note=''):
    part = PartListing.objects.filter(pk=part_id).first()
    if not part:
        raise ExchangeError('This part does not exist.', 404)
    if part.owner_id == user.pk:
        raise ExchangeError('You cannot reserve your own part.', 403)
    if compatibility_confirmed is not True:
        raise ExchangeError('Confirm that you checked the exact part code and device compatibility.', 400)
    if len(repair_note) > 500:
        raise ExchangeError('The repair note must be 500 characters or fewer.', 400)
    with transaction.atomic():
        changed = PartListing.objects.filter(pk=part_id, status=PartListing.Status.AVAILABLE).exclude(owner=user).update(status=PartListing.Status.RESERVED, updated_at=timezone.now())
        if not changed:
            raise ExchangeError('This part is no longer available. Someone may have already reserved it.')
        return Reservation.objects.create(part_id=part_id, requester=user, compatibility_confirmed=True, repair_note=repair_note)


def update_part(*, part_id, user, data):
    if set(data) - EDITABLE_FIELDS:
        raise ExchangeError('Only listing details can be edited.', 400)
    part = PartListing.objects.filter(pk=part_id).first()
    if not part:
        raise ExchangeError('This part does not exist.', 404)
    if part.owner_id != user.pk:
        raise ExchangeError('Only the donor can edit this listing.', 403)
    # A conditional write also prevents editing a listing while someone reserves it.
    changed = PartListing.objects.filter(pk=part_id, owner=user, status=PartListing.Status.AVAILABLE).update(**data, updated_at=timezone.now())
    if not changed:
        raise ExchangeError('Only available listings can be edited. Cancel the reservation before changing its details.')
    return PartListing.objects.get(pk=part_id)


def withdraw_part(*, part_id, user):
    part = PartListing.objects.filter(pk=part_id).first()
    if not part:
        raise ExchangeError('This part does not exist.', 404)
    if part.owner_id != user.pk and not user.is_staff:
        raise ExchangeError('Only the donor or a moderator can withdraw this listing.', 403)
    changed = PartListing.objects.filter(pk=part_id, status=PartListing.Status.AVAILABLE).update(status=PartListing.Status.WITHDRAWN, updated_at=timezone.now())
    if not changed:
        raise ExchangeError('Only an available listing can be withdrawn.')
    return PartListing.objects.get(pk=part_id)


def cancel_reservation(*, reservation_id, user):
    reservation = Reservation.objects.select_related('part').filter(pk=reservation_id).first()
    if not reservation:
        raise ExchangeError('This reservation does not exist.', 404)
    if user.pk not in (reservation.requester_id, reservation.part.owner_id):
        raise ExchangeError('Only the repairer or donor can cancel this reservation.', 403)
    with transaction.atomic():
        changed = Reservation.objects.filter(pk=reservation_id, status=Reservation.Status.ACTIVE).update(status=Reservation.Status.CANCELLED, updated_at=timezone.now())
        if not changed:
            raise ExchangeError('Only an active reservation can be cancelled.')
        changed = PartListing.objects.filter(pk=reservation.part_id, status=PartListing.Status.RESERVED).update(status=PartListing.Status.AVAILABLE, updated_at=timezone.now())
        if not changed:
            raise ExchangeError('The listing state changed. Refresh and try again.')
    return Reservation.objects.select_related('part', 'requester').get(pk=reservation_id)


def confirm_handover(*, reservation_id, user, note=''):
    reservation = Reservation.objects.select_related('part').filter(pk=reservation_id).first()
    if not reservation:
        raise ExchangeError('This reservation does not exist.', 404)
    if reservation.part.owner_id != user.pk:
        raise ExchangeError('Only the donor can confirm collection.', 403)
    if len(note) > 500:
        raise ExchangeError('The handover note must be 500 characters or fewer.', 400)
    with transaction.atomic():
        changed = Reservation.objects.filter(pk=reservation_id, status=Reservation.Status.ACTIVE).update(status=Reservation.Status.COLLECTED, updated_at=timezone.now())
        if not changed:
            raise ExchangeError('Only an active reservation can be collected.')
        changed = PartListing.objects.filter(pk=reservation.part_id, status=PartListing.Status.RESERVED).update(status=PartListing.Status.COLLECTED, updated_at=timezone.now())
        if not changed:
            raise ExchangeError('The listing state changed. Refresh and try again.')
        Handover.objects.create(reservation=reservation, confirmed_by=user, note=note)
    return Reservation.objects.select_related('part', 'requester').get(pk=reservation_id)
