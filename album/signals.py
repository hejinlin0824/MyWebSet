# album/signals.py
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Folder

@receiver(post_save, sender=User)
def create_default_folders(sender, instance, created, **kwargs):
    """当一个新用户被创建时，自动为他创建默认文件夹"""
    if created: # 确保只在新创建用户时执行
        default_folders = ['图片', '视频', '音乐', '文档', '动图']
        for folder_name in default_folders:
            Folder.objects.create(user=instance, name=folder_name, parent=None)