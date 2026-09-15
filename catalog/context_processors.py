from .models import Category


def categories(request):
    return {'nav_categories': Category.objects.all()}
