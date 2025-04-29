from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField(
        label='Select a file',
        widget=forms.FileInput(attrs={
            'class': 'form-control form-control-lg',
            'accept': '.xlsx,.xls'
        })
    ) 