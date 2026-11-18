from django.contrib import admin, messages
from .models import Handover, PartListing, Report, Reservation
from .services import ExchangeError, withdraw_part

admin.site.site_header = 'ReLoop moderation'
admin.site.site_title = 'ReLoop admin'
admin.site.index_title = 'Listings, handovers and reports'


class HistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(PartListing)
class PartAdmin(HistoryAdmin):
    list_display = ['title', 'owner', 'part_code', 'condition', 'status', 'created_at']
    list_filter = ['status', 'category', 'condition']
    search_fields = ['title', 'part_code', 'manufacturer', 'owner__username']
    actions = ['withdraw_available']

    @admin.action(description='Withdraw selected available listings')
    def withdraw_available(self, request, queryset):
        for part in queryset:
            try:
                withdraw_part(part_id=part.pk, user=request.user)
                self.log_change(request, part, 'Withdrew available listing through moderation.')
            except ExchangeError as error:
                self.message_user(request, f'{part.title}: {error.message}', messages.WARNING)


@admin.register(Reservation)
class ReservationAdmin(HistoryAdmin):
    list_display = ['id', 'part', 'requester', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['part__title', 'requester__username']


@admin.register(Handover)
class HandoverAdmin(HistoryAdmin):
    list_display = ['reservation', 'confirmed_by', 'collected_at']


@admin.register(Report)
class ReportAdmin(HistoryAdmin):
    list_display = ['id', 'part', 'reporter', 'reason', 'resolved', 'created_at']
    list_filter = ['resolved', 'reason']
    actions = ['resolve_reports']

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields if f.name != 'resolved']

    @admin.action(description='Mark selected reports as reviewed')
    def resolve_reports(self, request, queryset):
        for report in queryset:
            report.resolved = True
            report.save(update_fields=['resolved'])
            self.log_change(request, report, 'Marked report as reviewed.')
