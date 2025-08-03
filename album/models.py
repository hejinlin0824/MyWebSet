# album/models.py
from django.db import models
from django.contrib.auth.models import User
import os

class Folder(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    # 核心：一个指向自己的外键，用于实现无限层级的子文件夹
    # null=True, blank=True 表示顶级文件夹（没有父文件夹）是允许的
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"

class UploadedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # 新增字段：关联到文件夹。同样允许文件存在于根目录（不属于任何文件夹）
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True, related_name='files')

    def __str__(self):
        return os.path.basename(self.file.name)

    @property
    def file_type(self):
        # ... (这个方法保持不变)
        name, extension = os.path.splitext(self.file.name)
        extension = extension.lower()
        if extension in ['.jpg', '.jpeg', '.png']: return 'image'
        if extension == '.gif': return 'gif'
        if extension in ['.mp4', '.mov', '.avi', '.webm']: return 'video'
        if extension in ['.pdf', '.doc', '.docx', '.txt', '.zip', '.rar']: return 'document'
        return 'other'