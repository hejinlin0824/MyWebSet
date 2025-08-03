# album/templatetags/album_filters.py

from django import template
from django.utils.safestring import mark_safe
import re
import os
register = template.Library()


@register.filter(name='basename')
def basename(value):
    """返回路径的文件名部分"""
    return os.path.basename(str(value))


@register.filter(name='highlight')
def highlight(text, query):
    """
    一个模板过滤器，用于在高亮显示文本中的查询关键词。
    它不区分大小写，并能正确处理HTML转义。
    """
    if not query or not text:
        return text

    # 使用 re.escape 来确保查询词中的特殊字符（如 . * + ?）被当作普通字符处理
    # re.IGNORECASE 标志用于不区分大小写匹配
    # re.sub 会找到所有匹配项并进行替换
    # r'<mark>\1</mark>' 中的 \1 指的是第一个捕获组（也就是括号里的内容）
    highlighted_text = re.sub(
        f'({re.escape(query)})', 
        r'<mark>\1</mark>', 
        str(text), 
        flags=re.IGNORECASE
    )
    
    # 将结果标记为“安全的”，以防止 Django 自动转义 <mark> 标签
    return mark_safe(highlighted_text)