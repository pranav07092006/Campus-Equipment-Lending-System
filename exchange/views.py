from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import HandoverForm, PartForm, ReportForm, ReservationForm, SignupForm
from .models import Handover, PartListing, Reservation
from .queries import filter_parts
from .services import ExchangeError, cancel_reservation, confirm_handover, reserve_part, update_part, withdraw_part


def home(request):
    parts = filter_parts(PartListing.objects.select_related('owner'), request.GET)
    page = Paginator(parts, 9).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'exchange/home.html', {
        'page_obj': page, 'categories': PartListing.Category.choices, 'conditions': PartListing.Condition.choices,
        'query_string': params.urlencode(),
        'available_count': PartListing.objects.filter(status='available').count(),
        'collected_count': Handover.objects.count(),
    })


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Your account is ready. You can donate parts or reserve them for a repair.')
        return redirect('dashboard')
    return render(request, 'registration/signup.html', {'form': form})


def part_detail(request, pk, reservation_form=None):
    part = get_object_or_404(PartListing.objects.select_related('owner'), pk=pk)
    current = None
    if request.user.is_authenticated:
        current = part.reservations.filter(status='active', requester=request.user).first()
    return render(request, 'exchange/part_detail.html', {
        'part': part, 'form': reservation_form or ReservationForm(),
        'report_form': ReportForm(), 'my_reservation': current,
    })


@login_required
def part_create(request):
    form = PartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        part = form.save(commit=False)
        part.owner = request.user
        part.save()
        messages.success(request, 'Your part is listed and available for reservation.')
        return redirect(part)
    return render(request, 'exchange/part_form.html', {'form': form, 'editing': False})


@login_required
def part_edit(request, pk):
    part = get_object_or_404(PartListing, pk=pk)
    if part.owner_id != request.user.pk:
        return HttpResponseForbidden('Only the donor can edit this listing.')
    if part.status != 'available':
        messages.error(request, 'Only available listings can be edited.')
        return redirect(part)
    form = PartForm(request.POST or None, instance=part)
    if request.method == 'POST' and form.is_valid():
        try:
            part = update_part(part_id=pk, user=request.user, data=form.cleaned_data)
            messages.success(request, 'Your listing has been updated.')
            return redirect(part)
        except ExchangeError as error:
            form.add_error(None, error.message)
    return render(request, 'exchange/part_form.html', {'form': form, 'editing': True, 'part': part})


@login_required
@require_POST
def part_withdraw(request, pk):
    try:
        withdraw_part(part_id=pk, user=request.user)
        messages.success(request, 'Listing withdrawn. Its history remains available in your dashboard.')
    except ExchangeError as error:
        messages.error(request, error.message)
    return redirect('dashboard')


@login_required
@require_POST
def part_reserve(request, pk):
    form = ReservationForm(request.POST)
    if form.is_valid():
        try:
            reserve_part(part_id=pk, user=request.user, **form.cleaned_data)
            messages.success(request, 'Part reserved. Track it in your dashboard. The donor confirms collection.')
            return redirect('dashboard')
        except ExchangeError as error:
            form.add_error(None, error.message)
    return part_detail(request, pk, form)


@login_required
def dashboard(request):
    return render(request, 'exchange/dashboard.html', {
        'parts': request.user.parts.all(),
        'outgoing': Reservation.objects.filter(requester=request.user).select_related('part', 'part__owner', 'handover'),
        'incoming': Reservation.objects.filter(part__owner=request.user).select_related('part', 'requester', 'handover'),
    })


@login_required
@require_POST
def reservation_cancel(request, pk):
    try:
        cancel_reservation(reservation_id=pk, user=request.user)
        messages.success(request, 'Reservation cancelled. The part is available again.')
    except ExchangeError as error:
        messages.error(request, error.message)
    return redirect('dashboard')


@login_required
@require_POST
def reservation_collect(request, pk):
    form = HandoverForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Collection note must be 500 characters or fewer.')
    else:
        try:
            confirm_handover(reservation_id=pk, user=request.user, **form.cleaned_data)
            messages.success(request, 'Collection confirmed. Your handover record is saved.')
        except ExchangeError as error:
            messages.error(request, error.message)
    return redirect('dashboard')


@login_required
@require_POST
def part_report(request, pk):
    part = get_object_or_404(PartListing, pk=pk)
    form = ReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.part, report.reporter = part, request.user
        report.save()
        messages.success(request, 'Report sent to the site administrator for review.')
    else:
        messages.error(request, 'Please select a reason and add details of up to 1,000 characters.')
    return redirect(part)


def about(request):
    return render(request, 'exchange/about.html')


def api_docs(request):
    return render(request, 'exchange/api_docs.html')
