from django import forms

from .models import PAYMENT_METHOD_CHOICES


class CheckoutForm(forms.Form):
    address = forms.ChoiceField(choices=(), widget=forms.RadioSelect)
    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES, widget=forms.RadioSelect)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].choices = [
            (a.id, str(a)) for a in user.addresses.all()
        ]


class TriggerForm(forms.Form):
    target_price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    address = forms.ChoiceField(choices=())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].choices = [
            (a.id, str(a)) for a in user.addresses.all()
        ]
