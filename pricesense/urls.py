from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.views import SiteLoginView

urlpatterns = [
    # Intercepted before admin.site.urls registers its own -- Django
    # Admin redirects here (with its own ?next=) whenever a logged-out
    # visitor hits any /admin/... page; forwarding to our shared login
    # page means there's one login form for the whole site, not two.
    path('admin/login/', RedirectView.as_view(url='/login/', query_string=True)),
    path('admin/', admin.site.urls),

    path('login/', SiteLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/', include('accounts.urls')),

    path('orders/', include('orders.urls')),

    path('', include('catalog.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
