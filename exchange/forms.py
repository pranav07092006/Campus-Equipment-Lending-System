from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import PartListing, Report


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username']


class PartForm(forms.ModelForm):
    class Meta:
        model = PartListing
        fields = ['title', 'category', 'manufacturer', 'part_code', 'condition', 'supported_models', 'pickup_area', 'description']
        widgets = {
            'supported_models': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Exact model names, one per line'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Explain what you tested, any defects, and what is included.'}),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Tested 8 GB laptop memory module'}),
        }

    def clean_part_code(self):
        return self.cleaned_data['part_code'].strip().upper()


class ReservationForm(forms.Form):
    compatibility_confirmed = forms.BooleanField(label='I checked the manufacturer part code and confirmed compatibility with my device.')
    repair_note = forms.CharField(required=False, max_length=500, label='Repair note', widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Which device are you repairing? Please avoid sharing personal contact details.'}))


class HandoverForm(forms.Form):
    note = forms.CharField(required=False, max_length=500)


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'details']
        widgets = {'details': forms.Textarea(attrs={'rows': 3})}
