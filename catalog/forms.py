from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'rating': forms.Select(choices=Review.RATING_CHOICES),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
