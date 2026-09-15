from rest_framework import serializers

from .models import PriceLog


class PriceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceLog
        fields = ('price', 'timestamp')
