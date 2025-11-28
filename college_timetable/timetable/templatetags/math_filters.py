# timetable/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """
    Nhân hai số trong template:
      {{ 10|mul:0.6 }} -> 6.0
    Nếu có lỗi kiểu dữ liệu thì trả về 0.
    """
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0
