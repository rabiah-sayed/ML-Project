from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import AddressForm, SignUpForm
from .models import Address, Wallet


class SiteLoginView(LoginView):
    """The one login form for everyone -- customers and staff alike, no
    separate admin login page (pricesense/urls.py redirects
    /admin/login/ here too, preserving Django Admin's own ?next=). A
    staff user (is_staff, e.g. any Django Admin account) lands on the
    Admin dashboard after signing in; everyone else lands on the shop,
    same as before. An explicit ?next= (e.g. a specific admin page, or a
    customer's original destination) still wins over both defaults.
    This doesn't grant any *extra* access -- a staff account could
    already reach /admin/ with this session, it just used to require
    logging in there a second time.
    """

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        if self.request.user.is_staff:
            return '/admin/'
        return super().get_success_url()


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Wallet.objects.get_or_create(user=user)
            login(request, user)
            return redirect('onboarding_address')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def onboarding_address(request):
    """Post-signup step: collect the user's first address, wallet already created at signup."""
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address saved. Add some funds to your wallet to get started.')
            return redirect('wallet_detail')
    else:
        form = AddressForm(initial={'label': 'home'})
    return render(request, 'accounts/onboarding_address.html', {'form': form})


@login_required
def wallet_detail(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        try:
            amount = float(amount)
            if amount > 0:
                wallet.add_funds(amount)
                messages.success(request, f'Added {amount} to your wallet.')
        except (TypeError, ValueError):
            messages.error(request, 'Enter a valid amount.')
        return redirect('wallet_detail')
    return render(request, 'accounts/wallet_detail.html', {'wallet': wallet})


@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect('address_list')
    else:
        form = AddressForm(initial={'label': 'home'})
    return render(request, 'accounts/address_list.html', {'addresses': addresses, 'form': form})
