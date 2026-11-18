from django.db.models import Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.throttling import ScopedRateThrottle
from .models import Handover, PartListing, Report, Reservation
from .queries import filter_parts
from .services import ExchangeError, cancel_reservation, confirm_handover, reserve_part, update_part, withdraw_part


class StrictInputMixin:
    """Do not silently accept owner IDs, status changes or misspelled fields."""
    def to_internal_value(self, data):
        if hasattr(data, 'keys'):
            writable = {name for name, field in self.fields.items() if not field.read_only}
            extra = set(data.keys()) - writable
            if extra:
                raise serializers.ValidationError({name: 'This field is unknown or read-only.' for name in extra})
        return super().to_internal_value(data)


class PartSerializer(StrictInputMixin, serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = PartListing
        fields = ['id', 'owner', 'title', 'manufacturer', 'part_code', 'category', 'condition', 'supported_models', 'description', 'pickup_area', 'status', 'created_at', 'updated_at', 'is_owner']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def get_is_owner(self, obj):
        return self.context['request'].user.pk == obj.owner_id

    def validate_part_code(self, value):
        return value.strip().upper()

    def update(self, instance, validated_data):
        return update_part(part_id=instance.pk, user=self.context['request'].user, data=validated_data)


class HandoverSerializer(serializers.ModelSerializer):
    confirmed_by = serializers.CharField(source='confirmed_by.username', read_only=True)

    class Meta:
        model = Handover
        fields = ['id', 'confirmed_by', 'collected_at', 'note']


class ReservationSerializer(StrictInputMixin, serializers.ModelSerializer):
    part = PartSerializer(read_only=True)
    part_id = serializers.IntegerField(write_only=True, min_value=1)
    requester = serializers.CharField(source='requester.username', read_only=True)
    compatibility_confirmed = serializers.BooleanField(required=True)
    handover = HandoverSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = ['id', 'part', 'part_id', 'requester', 'repair_note', 'compatibility_confirmed', 'status', 'created_at', 'updated_at', 'handover']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def create(self, validated_data):
        return reserve_part(user=self.context['request'].user, **validated_data)


class HandoverInput(StrictInputMixin, serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')


class ReportSerializer(StrictInputMixin, serializers.ModelSerializer):
    reporter = serializers.CharField(source='reporter.username', read_only=True)

    class Meta:
        model = Report
        fields = ['id', 'part', 'reporter', 'reason', 'details', 'resolved', 'created_at']
        read_only_fields = ['id', 'resolved', 'created_at']


class ServiceErrorMixin:
    def handle_exception(self, exc):
        if isinstance(exc, ExchangeError):
            return Response({'detail': exc.message}, status=exc.status_code)
        return super().handle_exception(exc)


class PartViewSet(ServiceErrorMixin, viewsets.ModelViewSet):
    serializer_class = PartSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = PartListing.objects.select_related('owner')
        return filter_parts(queryset, self.request.query_params) if self.action == 'list' else queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def withdraw(self, request, pk=None):
        obj = self.get_object()
        part = withdraw_part(part_id=obj.pk, user=request.user)
        return Response(self.get_serializer(part).data)


class ReservationViewSet(ServiceErrorMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(Q(requester=self.request.user) | Q(part__owner=self.request.user)).select_related('part', 'part__owner', 'requester', 'handover')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        obj = self.get_object()
        reservation = cancel_reservation(reservation_id=obj.pk, user=request.user)
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=['post'])
    def collect(self, request, pk=None):
        obj = self.get_object()
        form = HandoverInput(data=request.data)
        form.is_valid(raise_exception=True)
        reservation = confirm_handover(reservation_id=obj.pk, user=request.user, **form.validated_data)
        return Response(self.get_serializer(reservation).data)


class ReportViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Report.objects.select_related('reporter', 'part')
        return queryset if self.request.user.is_staff else queryset.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class LoginTokenView(ObtainAuthToken):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'


router = DefaultRouter()
router.register('parts', PartViewSet, basename='api-part')
router.register('reservations', ReservationViewSet, basename='api-reservation')
router.register('reports', ReportViewSet, basename='api-report')
