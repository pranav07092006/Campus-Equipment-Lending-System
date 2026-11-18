from django.db.models import Q
from .models import PartListing


def filter_parts(queryset, params):
    query = params.get('q', '').strip()[:200]
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(manufacturer__icontains=query) | Q(part_code__icontains=query) | Q(supported_models__icontains=query))
    if params.get('part_code', '').strip():
        queryset = queryset.filter(part_code__iexact=params['part_code'].strip())
    if params.get('category'):
        queryset = queryset.filter(category=params['category'])
    if params.get('condition'):
        queryset = queryset.filter(condition=params['condition'])
    status = params.get('status', PartListing.Status.AVAILABLE)
    if status != 'all':
        queryset = queryset.filter(status=status)
    return queryset
