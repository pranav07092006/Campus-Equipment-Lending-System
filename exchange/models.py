from django.conf import settings
from django.db import models
from django.urls import reverse


class PartListing(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        RESERVED = 'reserved', 'Reserved'
        COLLECTED = 'collected', 'Collected'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    class Category(models.TextChoices):
        SCREEN = 'screen', 'Screens'
        MEMORY = 'memory', 'Memory'
        STORAGE = 'storage', 'Storage'
        KEYBOARD = 'keyboard', 'Keyboards'
        OTHER = 'other', 'Other parts'

    class Condition(models.TextChoices):
        TESTED = 'tested', 'Tested and working'
        UNTESTED = 'untested', 'Untested'
        REPAIR = 'repair', 'Needs repair'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='parts')
    title = models.CharField(max_length=120)
    manufacturer = models.CharField(max_length=80)
    part_code = models.CharField(max_length=80, db_index=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    supported_models = models.TextField(max_length=1000, help_text='One supported device model per line. Confirm against manufacturer specifications.')
    description = models.TextField(max_length=2000)
    pickup_area = models.CharField(max_length=120, help_text='A general area or campus, not your private address.')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['available', 'reserved', 'collected', 'withdrawn']), name='valid_listing_status')]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('part-detail', args=[self.pk])

    @property
    def model_list(self):
        return [item.strip() for item in self.supported_models.splitlines() if item.strip()]


class Reservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        CANCELLED = 'cancelled', 'Cancelled'
        COLLECTED = 'collected', 'Collected'

    part = models.ForeignKey(PartListing, on_delete=models.PROTECT, related_name='reservations')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reservations')
    repair_note = models.TextField(max_length=500, blank=True)
    compatibility_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['active', 'cancelled', 'collected']), name='valid_reservation_status'),
            models.CheckConstraint(condition=models.Q(compatibility_confirmed=True), name='reservation_compatibility_confirmed'),
        ]

    def __str__(self):
        return f'RES-{self.pk}: {self.part.title}'


class Handover(models.Model):
    reservation = models.OneToOneField(Reservation, on_delete=models.PROTECT, related_name='handover')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField(max_length=500, blank=True)
    collected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Handover for RES-{self.reservation_id}'


class Report(models.Model):
    class Reason(models.TextChoices):
        MISMATCH = 'mismatch', 'Incorrect compatibility or description'
        CONDITION = 'condition', 'Condition concern'
        SPAM = 'spam', 'Spam or misleading listing'
        OTHER = 'other', 'Other'

    part = models.ForeignKey(PartListing, on_delete=models.PROTECT, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(max_length=1000)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Report #{self.pk}: {self.part.title}'
