# album/forms.py
from django import forms
from .models import Folder, UploadedFile

class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ('name',)
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': '文件夹名称', 'class': 'folder-name-input'}) # <-- 在这里添加 class 属性
        }

# (我们稍后会用到文件上传表单)
class UploadFileForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ('file',)